import sqlite3
import os
from typing import List, Dict, Any, Optional

class SupportHub:
    """
    Managed Support Queue for Non-Technical issues and Human Handovers.
    Directs manual intervention tasks into the support.db for agents to resolve.
    """

    def __init__(self, db_path: str = "support.db"):
        self.db_path = db_path
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the support cases table."""
        conn = self._get_conn()
        
        # We use a single table for both tickets (non-tech) and handovers (active chat)
        # Type field: 'NON_TECHNICAL_TICKET' or 'CHAT_HANDOVER'
        conn.execute('''
            CREATE TABLE IF NOT EXISTS cases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                case_type TEXT NOT NULL,
                summary TEXT,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                client_request_id TEXT
            )
        ''')

        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_cases_client_request_id "
                "ON cases(client_request_id) WHERE client_request_id IS NOT NULL"
            )
        except sqlite3.OperationalError:
            pass

        conn.commit()
        conn.close()

    def _already_enqueued(self, conn, client_request_id: Optional[str]) -> bool:
        if not client_request_id:
            return False
        row = conn.execute(
            "SELECT id FROM cases WHERE client_request_id = ?", (client_request_id,)
        ).fetchone()
        return row is not None

    def enqueue_ticket(self, session_id: str, summary: str, client_request_id: Optional[str] = None) -> bool:
        """Adds a non-technical ticket to the support queue. Safe to retry:
        replaying the same client_request_id is a no-op after the first call.
        Returns True if a new case was created, False if this was a replay."""
        conn = self._get_conn()
        if self._already_enqueued(conn, client_request_id):
            conn.close()
            return False
        conn.execute(
            "INSERT INTO cases (session_id, case_type, summary, client_request_id) VALUES (?, ?, ?, ?)",
            (session_id, 'NON_TECHNICAL_TICKET', summary, client_request_id)
        )
        conn.commit()
        conn.close()
        print(f"[SUPPORT_HUB] Enqueued Non-Technical Ticket for Session {session_id}")
        return True

    def enqueue_handover(self, session_id: str, summary: str, client_request_id: Optional[str] = None) -> bool:
        """Adds an active human handover request to the queue. Safe to retry.
        Returns True if a new case was created, False if this was a replay."""
        conn = self._get_conn()
        if self._already_enqueued(conn, client_request_id):
            conn.close()
            return False
        conn.execute(
            "INSERT INTO cases (session_id, case_type, summary, client_request_id) VALUES (?, ?, ?, ?)",
            (session_id, 'CHAT_HANDOVER', summary, client_request_id)
        )
        conn.commit()
        conn.close()
        print(f"[SUPPORT_HUB] Enqueued Active Handover for Session {session_id}")
        return True

    def get_open_cases(self) -> Dict[str, List[Dict[str, Any]]]:
        """Returns all open cases grouped by their type."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM cases WHERE status = 'OPEN' ORDER BY created_at DESC").fetchall()
        
        buckets = {
            "NON_TECHNICAL_TICKETS": [],
            "CHAT_HANDOVERS": []
        }
        
        for r in rows:
            case = dict(r)
            if case["case_type"] == "NON_TECHNICAL_TICKET":
                buckets["NON_TECHNICAL_TICKETS"].append(case)
            else:
                buckets["CHAT_HANDOVERS"].append(case)
                
        conn.close()
        return buckets

    def resolve_case(self, case_id: int) -> bool:
        """Marks a case as closed. Returns False if no such open case exists."""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE cases SET status = 'CLOSED', resolved_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'OPEN'",
            (case_id,)
        )
        conn.commit()
        found = cursor.rowcount > 0
        conn.close()
        return found
