import hmac
import hashlib
import json
import sqlite3
import urllib.request
from typing import Dict, Any, Optional, List

class Webhooks:
    """
    Standard Webhook Dispatcher.
    Fires signed HMAC-SHA256 POST requests to registered endpoints.
    Allows for decoupled, async-friendly system monitoring.

    webhook_configs lives in its own table here, owned by this class -
    it used to live in conversations.db, which is TTL-wiped by design
    (see DESIGN.md section 7). Webhook registrations are permanent
    developer config, not ephemeral conversation data, so a clean wipe
    of conversations.db should never be able to silently delete them.
    Point db_path at issues.db (or a dedicated config store) instead.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

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
        Generic, properly-named event dispatcher.
        Payload is signed for security verification on the receiver side.
        """
        configs = self._get_configs(event_type)
        if not configs:
            print(f"[WEBHOOK] No registered URLs for event: {event_type}")
            return

        payload_str = json.dumps(payload, sort_keys=True)
        payload_bytes = payload_str.encode('utf-8')

        for config in configs:
            url = config['url']
            secret = config['secret'].encode('utf-8')
            
            signature = hmac.new(
                secret,
                payload_bytes,
                hashlib.sha256
            ).hexdigest()

            headers = {
                'Content-Type': 'application/json',
                'X-Tackety-Signature': signature,
                'X-Tackety-Event': event_type
            }

            req = urllib.request.Request(url, data=payload_bytes, headers=headers, method='POST')
            
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    print(f"[WEBHOOK] Sent {event_type} to {url}. Status: {response.status}")
            except Exception as e:
                print(f"[WEBHOOK] Failed to send {event_type} to {url}: {e}")

    def trigger(self, event_type: str, data: Dict[str, Any]):
        """Legacy compatibility wrapper for older internal calls."""
        self.dispatch_event(event_type, data)
