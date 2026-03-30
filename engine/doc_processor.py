import sqlite3
import sqlite_vec
import struct
from typing import List, Dict, Optional
import os
from engine.ai import call_ai

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Warning: sentence-transformers not found. Ensure it is installed: pip install sentence-transformers")
    SentenceTransformer = None

class DocProcessor:
    """
    Handles RAG operations: chunking text, generating embeddings, and storing/retrieving
    them from the dedicated knowledge.db using sqlite-vec.
    """

    def __init__(self, db_path: str = "knowledge.db", model_name: str = "all-MiniLM-L6-v2"):
        self.db_path = db_path
        self._init_db()
        self.model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None and SentenceTransformer is not None:
             self._model = SentenceTransformer(self.model_name)
        elif SentenceTransformer is None:
             raise RuntimeError("sentence-transformers is not installed. Cannot generate embeddings.")
        return self._model

    def _get_conn(self):
        """Returns a new db connection with sqlite_vec loaded."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes the virtual tables for vector storage."""
        conn = self._get_conn()
        # Create standard tables to hold text content
        conn.execute('''
            CREATE TABLE IF NOT EXISTS docs_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                doc_type TEXT NOT NULL, -- 'company' or 'product'
                section_title TEXT,
                content TEXT NOT NULL
            )
        ''')
        
        # Create vec table holding the embeddings (384 dims for all-MiniLM-L6-v2)
        # We store rowid linking to docs_content.id
        conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_docs USING vec0(
                rowid INTEGER PRIMARY KEY,
                embedding float[384]
            )
        ''')
        conn.commit()
        conn.close()

    def serialize_f32(self, vector: List[float]) -> bytes:
        """Serializes a list of floats into the binary format sqlite-vec expects."""
        return struct.pack(f"{len(vector)}f", *vector)

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """Simple token/character-based chunking as a fallback."""
        # For a real system, recursive character text splitting or heading-based splitting is better.
        # This is a basic implementation for now.
        words = text.split()
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += chunk_size - overlap
        return chunks
        
    def _chunk_by_heading(self, text: str) -> List[Dict[str, str]]:
        """
        Chunks markdown-style text by headers.
        Returns [{"title": "Header", "content": "Text..."}, ...]
        """
        lines = text.split('\n')
        chunks = []
        current_title = "General"
        current_content = []

        for line in lines:
            if line.startswith('#'):
                # Save previous chunk
                if current_content:
                    chunks.append({
                        "title": current_title,
                        "content": "\n".join(current_content).strip()
                    })
                current_title = line.lstrip('#').strip()
                current_content = []
            else:
                current_content.append(line)
                
        # Save last chunk
        if current_content:
             chunks.append({
                "title": current_title,
                "content": "\n".join(current_content).strip()
             })
             
        return [c for c in chunks if c["content"]] # Filter out empties

    def ingest_document(self, text: str, doc_type: str):
        """
        Chunks the document, embeds it, and stores it in knowledge.db.
        doc_type should be 'company' or 'product'.
        """
        model = self._get_model()
        chunks = self._chunk_by_heading(text)
        
        # If no headings found, fall back to basic chunking
        if not chunks:
            raw_chunks = self._chunk_text(text)
            chunks = [{"title": "General", "content": c} for c in raw_chunks]

        conn = self._get_conn()
        for chunk in chunks:
            # 1. Insert content
            cursor = conn.execute(
                "INSERT INTO docs_content (doc_type, section_title, content) VALUES (?, ?, ?)",
                (doc_type, chunk["title"], chunk["content"])
            )
            content_id = cursor.lastrowid
            
            # 2. Generate embedding
            embedding = model.encode(chunk["content"]).tolist()
            
            # 3. Insert vector
            conn.execute(
                "INSERT INTO vec_docs (rowid, embedding) VALUES (?, ?)",
                (content_id, self.serialize_f32(embedding))
            )
            
        conn.commit()
        conn.close()

    def retrieve_context(self, query: str, doc_type: str, limit: int = 3) -> List[Dict[str, str]]:
        """
        Embeds the query and retrieves the most relevant chunks of doc_type.
        """
        model = self._get_model()
        query_embedding = model.encode(query).tolist()
        query_vec = self.serialize_f32(query_embedding)
        
        conn = self._get_conn()
        
        # Using sqlite-vec for cosine distance (vec_distance_cosine)
        rows = conn.execute(f"""
            SELECT 
                dc.section_title, 
                dc.content, 
                vec_distance_cosine(v.embedding, ?) as distance
            FROM vec_docs v
            JOIN docs_content dc ON v.rowid = dc.id
            WHERE dc.doc_type = ?
            ORDER BY distance ASC
            LIMIT ?
        """, (query_vec, doc_type, limit)).fetchall()
        
        results = [dict(row) for row in rows]
        conn.close()
        return results

    def process_company_doc(self, text: str, output_path: str) -> str:
        """
        Preprocesses (cleans/summarizes) the company doc using AI 
        and saves it to a plain text file for prompt injection.
        """
        print(f"Preprocessing company doc for prompt injection...")
        system_prompt = (
            "You are a document preprocessor for a customer support engine. "
            "Your job is to take raw company internal documents and convert them into a 'Support Prompt Context'.\n"
            "Rules:\n"
            "1. Focus heavily on POLIDIES, REFUNDS, ESCALATION RULES, and PRICING.\n"
            "2. Keep it dense and keyword-rich.\n"
            "3. Remove fluff and conversational filler.\n"
            "4. Format it for an AI System Prompt."
        )
        
        preprocessed_text = call_ai(prompt=text, system_prompt=system_prompt)
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(preprocessed_text)
            
        print(f"Company context saved to {output_path}")
        return preprocessed_text

    def process_product_doc(self, text: str, output_path: str) -> str:
        """
        Specialized preprocessing for the product doc (Terminology Mapping).
        Focuses on extracting technical IDs, slugs, and specific feature names.
        """
        print(f"Preprocessing product doc for terminology mapping...")
        system_prompt = (
            "You are a technical document preprocessor. "
            "Your job is to take a product manual and extract a 'Technical Terminology Map'.\n"
            "Rules:\n"
            "1. Extract specific FEATURE SLUGS (e.g. AUTH_JWT, CHECKOUT_V3).\n"
            "2. Identify technical modules and their responsibilities.\n"
            "3. Format it as a clear key-value reference for an LLM to use as a mapping anchor."
        )
        
        preprocessed_text = call_ai(prompt=text, system_prompt=system_prompt)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(preprocessed_text)
            
        print(f"Product map saved to {output_path}")
        return preprocessed_text

    def clear_docs(self, doc_type: str):
        """Clears all embeddings for a specific doc type."""
        conn = self._get_conn()
        # Get IDs to delete from vec table
        ids = conn.execute("SELECT id FROM docs_content WHERE doc_type = ?", (doc_type,)).fetchall()
        id_list = [str(r[0]) for r in ids]
        
        if id_list:
            id_str = ",".join(id_list)
            conn.execute(f"DELETE FROM vec_docs WHERE rowid IN ({id_str})")
            conn.execute("DELETE FROM docs_content WHERE doc_type = ?", (doc_type,))
            
        conn.commit()
        conn.close()
