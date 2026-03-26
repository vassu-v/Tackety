import sqlite3
import uuid
import os
from datetime import datetime, timedelta


class SessionManager:
    """
    Manages conversation sessions and messages in conversations.db.
    
    This is the stateful layer of the system. The AI (chatbot) is stateless —
    it reconstructs conversation context from the message history stored here
    on every single turn.
    
    Cleanup of expired sessions is lazy: it runs every `cleanup_interval` 
    new session creations, purging closed sessions older than `ttl_days`.
    """

    def __init__(self, db_path="conversations.db", ttl_days=3, cleanup_interval=10):
        """
        Args:
            db_path: Path to the SQLite database file. Use ':memory:' for testing.
            ttl_days: Number of days before closed sessions are purged. Configurable.
            cleanup_interval: Run cleanup every N new session creations.
        """
        self.db_path = db_path
        self.ttl_days = ttl_days
        self.cleanup_interval = cleanup_interval
        self._session_counter = 0
        self._conn = self._create_conn()
        self._init_db()

    def _create_conn(self):
        """Creates and configures a database connection."""
        # check_same_thread=False is needed because FastAPI (uvicorn) runs 
        # requests in separate threads, and SQLite connections aren't 
        # shared across threads by default.
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row  # Access columns by name
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent read performance
        return conn

    @property
    def conn(self):
        """Returns the persistent database connection."""
        return self._conn

    def close(self):
        """Closes the database connection. Call on shutdown."""
        if self._conn:
            self._conn.close()
            self._conn = None

    def _init_db(self):
        """Creates the sessions and messages tables if they don't exist."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id              TEXT PRIMARY KEY,
                status          TEXT NOT NULL DEFAULT 'active',
                customer_email  TEXT,
                created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                closed_at       TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  TEXT NOT NULL,
                role        TEXT NOT NULL,
                content     TEXT NOT NULL,
                timestamp   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session 
                ON messages(session_id);

            CREATE INDEX IF NOT EXISTS idx_sessions_status_closed 
                ON sessions(status, closed_at);
        """)
        self.conn.commit()


    # ── Session Lifecycle ──────────────────────────────────────────────

    def start_session(self, customer_email=None):
        """
        Creates a new conversation session.

        Args:
            customer_email: Optional email captured during conversation.

        Returns:
            str: The UUID of the newly created session.
        """
        session_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO sessions (id, status, customer_email) VALUES (?, 'active', ?)",
            (session_id, customer_email)
        )
        self.conn.commit()

        # Lazy cleanup trigger
        self._session_counter += 1
        self._maybe_cleanup()

        return session_id

    def close_session(self, session_id, status="closed"):
        """
        Closes a session and records the closing timestamp.

        Args:
            session_id: The UUID of the session to close.
            status: The final status — 'closed' or 'escalated'.
        """
        self.conn.execute(
            "UPDATE sessions SET status = ?, closed_at = ? WHERE id = ?",
            (status, datetime.utcnow().isoformat(), session_id)
        )
        self.conn.commit()

    def get_session(self, session_id):
        """
        Fetches session metadata.

        Args:
            session_id: The UUID of the session.

        Returns:
            dict or None: Session data if found, None otherwise.
        """
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_email(self, session_id, customer_email):
        """
        Updates the customer email for a session (if provided mid-conversation).

        Args:
            session_id: The UUID of the session.
            customer_email: The email to associate with the session.
        """
        self.conn.execute(
            "UPDATE sessions SET customer_email = ? WHERE id = ?",
            (customer_email, session_id)
        )
        self.conn.commit()

    # ── Message Management ─────────────────────────────────────────────

    def add_message(self, session_id, role, content):
        """
        Records a message in the conversation.

        Args:
            session_id: The UUID of the session this message belongs to.
            role: 'user' or 'assistant'.
            content: The full message text.
        """
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content)
        )
        self.conn.commit()

    def get_history(self, session_id):
        """
        Fetches the full message history for a session, ordered chronologically.
        This is what the chatbot uses to reconstruct conversation context.

        Args:
            session_id: The UUID of the session.

        Returns:
            list[dict]: Messages in chronological order.
                Each dict has: role, content, timestamp.
        """
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM messages "
            "WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,)
        ).fetchall()
        return [dict(row) for row in rows]

    # ── Lazy Cleanup ───────────────────────────────────────────────────

    def _maybe_cleanup(self):
        """
        Runs cleanup every `cleanup_interval` session creations.
        Deletes messages and sessions that are closed and older than `ttl_days`.
        Only touches closed sessions — active conversations are never affected.
        """
        if self._session_counter % self.cleanup_interval != 0:
            return

        cutoff = (datetime.utcnow() - timedelta(days=self.ttl_days)).isoformat()
        # Delete orphaned messages first (referential integrity)
        self.conn.execute(
            "DELETE FROM messages WHERE session_id IN ("
            "  SELECT id FROM sessions "
            "  WHERE status != 'active' AND closed_at < ?"
            ")",
            (cutoff,)
        )
        # Then delete the expired sessions
        self.conn.execute(
            "DELETE FROM sessions WHERE status != 'active' AND closed_at < ?",
            (cutoff,)
        )
        self.conn.commit()

