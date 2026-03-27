import os
from engine.doc_processor import DocProcessor

def setup():
    # Use the same data directory as the API
    data_dir = os.path.join("engine", "data")
    os.makedirs(data_dir, exist_ok=True)
    db_path = os.path.join(data_dir, "knowledge.db")
    
    print(f"Initializing knowledge base at {db_path}...")
    dp = DocProcessor(db_path=db_path)
    
    print("Clearing old data...")
    dp.clear_docs("company")
    dp.clear_docs("product")

    company_doc = """# Company Overview
Tackety is a self-hostable, developer-first issue clustering system. We focus on automation and privacy.

# Refund Policy
We offer 100% refunds within 30 days of purchase. Just email support@tackety.engine.

# Contact Info
Support email: support@tackety.engine
Human escalation: escalation@tackety.engine
"""

    product_doc = """# Authentication Issues
If users are logged out randomly, it's likely a cookie setting or JWT expiration.

# Checkout Crashes
If the cart crashes with many items, check the local storage sync logic in demo/index.html.

# Database Locked
If you see 'database is locked', the SessionManager RLock is likely working, but ensure WAL mode is enabled.
"""

    print("Ingesting docs...")
    dp.ingest_document(company_doc, "company")
    dp.ingest_document(product_doc, "product")
    print("Setup complete.")

if __name__ == "__main__":
    setup()
