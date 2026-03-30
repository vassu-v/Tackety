import sqlite3
import sqlite_vec
import struct
import os
from typing import List, Dict, Any, Optional

class IssueEngine:
    """
    The Core Intelligence Cluster Engine (The Engineering Heart).
    Groups technical issues by semantic similarity using sqlite-vec.
    Tracks issue weight (volume) and auto-escalates urgency.
    """

    def __init__(self, db_path: str = "issues.db", cluster_threshold: float = 0.75):
        self.db_path = db_path
        self.cluster_threshold = cluster_threshold
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the technical clusters and tickets tables."""
        conn = self._get_conn()
        
        # 1. Clusters table (The high-level technical problem groups)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS clusters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_slug TEXT NOT NULL,
                summary TEXT,
                category TEXT,
                weight INTEGER DEFAULT 0,
                urgency TEXT DEFAULT 'NORMAL',
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        ''')

        # 2. Virtual Vector table for cluster similarity
        conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_clusters USING vec0(
                rowid INTEGER PRIMARY KEY,
                embedding float[384]
            )
        ''')

        # 3. Individual Tickets table (References back to the raw intake)
        conn.execute('''
            CREATE TABLE IF NOT EXISTS technical_tickets (
                id TEXT PRIMARY KEY,
                session_id TEXT,
                cluster_id INTEGER,
                raw_summary TEXT,
                normalized_slug TEXT,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(cluster_id) REFERENCES clusters(id)
            )
        ''')
        
        conn.commit()
        conn.close()

    def serialize_f32(self, vector: List[float]) -> bytes:
        return struct.pack(f"{len(vector)}f", *vector)

    def process_ticket(self, ticket_id: str, session_id: str, normalized_data: Dict[str, Any], raw_summary: str, embedding: List[float]):
        """
        Main entry point for engineering tickets.
        1. Searches for similar cluster.
        2. Updates or Creates.
        3. Persists ticket.
        """
        conn = self._get_conn()
        slug = normalized_data.get("normalized_slug", "UNKNOWN")
        category = normalized_data.get("doc_reference", "General")
        query_vec = self.serialize_f32(embedding)

        # 1. Search for similar clusters using cosine distance
        # We search vec_clusters and get distances
        match = conn.execute(f"""
            SELECT 
                v.rowid as cluster_id,
                vec_distance_cosine(v.embedding, ?) as distance
            FROM vec_clusters v
            JOIN clusters c ON v.rowid = c.id
            WHERE c.status = 'OPEN'
            ORDER BY distance ASC
            LIMIT 1
        """, (query_vec,)).fetchone()

        cluster_id = None
        # Threshold check: sqlite-vec distance is (1 - cosine_similarity)
        # similarity = 1 - distance. So distance < 0.25 means similarity > 0.75
        if match and (1 - match['distance']) >= self.cluster_threshold:
            cluster_id = match['cluster_id']
            # Update existing cluster weight
            conn.execute("UPDATE clusters SET weight = weight + 1 WHERE id = ?", (cluster_id,))
        else:
            # 2. Create new cluster
            cursor = conn.execute(
                "INSERT INTO clusters (issue_slug, summary, category, weight) VALUES (?, ?, ?, ?)",
                (slug, raw_summary, category, 1)
            )
            cluster_id = cursor.lastrowid
            
            # Insert vector for future matching
            conn.execute(
                "INSERT INTO vec_clusters (rowid, embedding) VALUES (?, ?)",
                (cluster_id, query_vec)
            )

        # 3. Recalculate Urgency
        self._update_urgency(conn, cluster_id)

        # 4. Create the final ticket entry
        conn.execute(
            "INSERT INTO technical_tickets (id, session_id, cluster_id, raw_summary, normalized_slug) VALUES (?, ?, ?, ?, ?)",
            (ticket_id, session_id, cluster_id, raw_summary, slug)
        )

        conn.commit()
        conn.close()
        return cluster_id

    def _update_urgency(self, conn, cluster_id: int):
        """Standard urgency model based on weight."""
        cluster = conn.execute("SELECT weight FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
        if not cluster: return
        
        weight = cluster['weight']
        urgency = "NORMAL"
        if weight >= 5:
            urgency = "CRITICAL"
        elif weight >= 3:
            urgency = "URGENT"
        
        conn.execute("UPDATE clusters SET urgency = ? WHERE id = ?", (urgency, cluster_id))

    def get_ranked_clusters(self) -> List[Dict[str, Any]]:
        """Returns all open clusters ordered by weight and urgency."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT * FROM clusters 
            WHERE status = 'OPEN' 
            ORDER BY 
              CASE urgency 
                WHEN 'CRITICAL' THEN 1 
                WHEN 'URGENT' THEN 2 
                ELSE 3 
              END, 
            weight DESC
        """).fetchall()
        
        results = []
        for r in rows:
            res = dict(r)
            # Fetch tickets in this cluster
            tickets = conn.execute("SELECT * FROM technical_tickets WHERE cluster_id = ?", (r['id'],)).fetchall()
            res["tickets"] = [dict(t) for t in tickets]
            results.append(res)
            
        conn.close()
        return results
