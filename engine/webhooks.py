import hmac
import hashlib
import json
import logging
import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger("tackety.webhooks")

MAX_ATTEMPTS = 8
# Exponential backoff in seconds, indexed by attempt number (1-based).
# Capped at the last value for anything beyond this list's length.
BACKOFF_SECONDS = [30, 60, 120, 300, 600, 1800, 3600]


class Webhooks:
    """
    Webhook dispatcher with a durable outbox and retry.

    webhook_configs lives in its own table here, owned by this class -
    it used to live in conversations.db, which is TTL-wiped by design
    (see DESIGN.md section 7). Webhook registrations are permanent
    developer config, not ephemeral conversation data, so a clean wipe
    of conversations.db should never be able to silently delete them.
    Point db_path at issues.db (or a dedicated config store) instead.

    Why an outbox: the previous implementation was fire-and-forget - if
    the receiving endpoint was down, the event was logged and dropped
    forever, with no way to know it happened short of reading server
    logs. dispatch_event() now writes one outbox row per registered
    target *before* attempting delivery, so the event is durable the
    moment this function returns even if every delivery attempt fails.
    A background thread retries pending rows with exponential backoff
    until MAX_ATTEMPTS is reached, at which point the row is marked
    'failed' and stays visible via get_outbox() rather than vanishing.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        self._stop_event = threading.Event()
        self._retry_thread: Optional[threading.Thread] = None

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _now(self) -> str:
        # Naive UTC isoformat string - matches the convention used
        # elsewhere in this codebase (see session_manager.py) so string
        # comparison in SQL ("<=") sorts correctly without a timezone
        # library dependency in the query itself.
        return datetime.now(timezone.utc).replace(tzinfo=None).isoformat()

    def _init_db(self):
        conn = self._get_conn()
        conn.execute('''
            CREATE TABLE IF NOT EXISTS webhook_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                url TEXT NOT NULL,
                secret TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS webhook_outbox (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event TEXT NOT NULL,
                url TEXT NOT NULL,
                secret TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                attempts INTEGER NOT NULL DEFAULT 0,
                next_attempt_at TIMESTAMP NOT NULL,
                last_error TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delivered_at TIMESTAMP
            )
        ''')
        conn.execute('''
            CREATE INDEX IF NOT EXISTS idx_outbox_status_next_attempt
                ON webhook_outbox(status, next_attempt_at)
        ''')
        conn.commit()
        conn.close()

    def register(self, event: str, url: str, secret: str):
        """Registers a webhook URL for a specific event. Caller is
        responsible for validating the URL (see engine/url_safety.py)."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO webhook_configs (event, url, secret) VALUES (?, ?, ?)",
            (event, url, secret)
        )
        conn.commit()
        conn.close()

    def _get_configs(self, event_type: str) -> List[Dict[str, str]]:
        conn = self._get_conn()
        configs = conn.execute(
            "SELECT url, secret FROM webhook_configs WHERE event = ?", (event_type,)
        ).fetchall()
        conn.close()
        return [dict(c) for c in configs]

    def dispatch_event(self, event_type: str, payload: Dict[str, Any]):
        """
        Persists one outbox row per registered target for this event, then
        attempts immediate delivery for each. A target that's unreachable
        right now is not lost - it stays 'pending' for the background
        retry loop to pick up.
        """
        configs = self._get_configs(event_type)
        if not configs:
            logger.info("No registered URLs for event: %s", event_type)
            return

        payload_str = json.dumps(payload, sort_keys=True)
        conn = self._get_conn()
        row_ids = []
        for config in configs:
            cursor = conn.execute(
                "INSERT INTO webhook_outbox (event, url, secret, payload, status, next_attempt_at) "
                "VALUES (?, ?, ?, ?, 'pending', ?)",
                (event_type, config['url'], config['secret'], payload_str, self._now())
            )
            row_ids.append(cursor.lastrowid)
        conn.commit()
        conn.close()

        for row_id in row_ids:
            self._attempt_delivery(row_id)

    def _attempt_delivery(self, row_id: int):
        """Attempts one outbox row's delivery and updates its status.
        Safe to call repeatedly - a row already delivered/failed is a
        no-op (checked by the caller via the status filter in queries,
        but also re-checked here for direct calls like the immediate
        attempt in dispatch_event)."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM webhook_outbox WHERE id = ?", (row_id,)).fetchone()
        if not row or row['status'] != 'pending':
            conn.close()
            return

        payload_bytes = row['payload'].encode('utf-8')
        signature = hmac.new(row['secret'].encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        headers = {
            'Content-Type': 'application/json',
            'X-Tackety-Signature': signature,
            'X-Tackety-Event': row['event']
        }
        req = urllib.request.Request(row['url'], data=payload_bytes, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                logger.info("Delivered %s to %s (status %s)", row['event'], row['url'], response.status)
                conn.execute(
                    "UPDATE webhook_outbox SET status = 'delivered', delivered_at = ? WHERE id = ?",
                    (self._now(), row_id)
                )
        except Exception as e:
            attempts = row['attempts'] + 1
            if attempts >= MAX_ATTEMPTS:
                logger.warning("Giving up on %s to %s after %d attempts: %s", row['event'], row['url'], attempts, e)
                conn.execute(
                    "UPDATE webhook_outbox SET status = 'failed', attempts = ?, last_error = ? WHERE id = ?",
                    (attempts, str(e), row_id)
                )
            else:
                backoff = BACKOFF_SECONDS[min(attempts - 1, len(BACKOFF_SECONDS) - 1)]
                next_attempt = (datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=backoff)).isoformat()
                logger.info("Delivery failed for %s to %s (attempt %d/%d, retry in %ds): %s",
                            row['event'], row['url'], attempts, MAX_ATTEMPTS, backoff, e)
                conn.execute(
                    "UPDATE webhook_outbox SET attempts = ?, next_attempt_at = ?, last_error = ? WHERE id = ?",
                    (attempts, next_attempt, str(e), row_id)
                )

        conn.commit()
        conn.close()

    def retry_pending(self):
        """Attempts delivery for every pending row whose next_attempt_at
        has passed. Called on a timer by the background thread, and
        callable directly (e.g. from a test or a manual trigger)."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id FROM webhook_outbox WHERE status = 'pending' AND next_attempt_at <= ?",
            (self._now(),)
        ).fetchall()
        conn.close()

        for row in rows:
            self._attempt_delivery(row['id'])

    def get_outbox(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Returns the most recent outbox entries, newest first - for
        visibility into what's pending, delivered, or given up on."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT id, event, url, status, attempts, next_attempt_at, last_error, created_at, delivered_at "
            "FROM webhook_outbox ORDER BY created_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def start_background_retry(self, interval_seconds: int = 30):
        """Starts a daemon thread that calls retry_pending() on a timer.
        Idempotent - calling this more than once is a no-op after the
        first call, so it's safe to call from a startup hook that could
        theoretically run more than once (e.g. under a reloader)."""
        if self._retry_thread is not None:
            return

        def _loop():
            while not self._stop_event.wait(interval_seconds):
                try:
                    self.retry_pending()
                except Exception:
                    logger.exception("Webhook retry loop iteration failed")

        self._retry_thread = threading.Thread(target=_loop, daemon=True, name="webhook-retry")
        self._retry_thread.start()
        logger.info("Webhook retry background thread started (interval=%ds)", interval_seconds)

    def stop_background_retry(self):
        self._stop_event.set()
        if self._retry_thread is not None:
            self._retry_thread.join(timeout=5)
            self._retry_thread = None

    def trigger(self, event_type: str, data: Dict[str, Any]):
        """Legacy compatibility wrapper for older internal calls."""
        self.dispatch_event(event_type, data)
