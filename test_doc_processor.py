import os
from engine.doc_processor import DocProcessor
import time

def test_doc_processor():
    print("Initializing DocProcessor...")
    dp = DocProcessor(db_path="test_knowledge.db")
    
    print("Clearing old test data...")
    dp.clear_docs("company")
    dp.clear_docs("product")

    company_doc_md = """# Company Overview
Tackety is a next-generation issue clustering engine designed for developers. We believe in open-source, self-hosted, privacy-first software.

# Refund Policy
We offer a 30-day money-back guarantee for all hosted plans. No questions asked. Refunds take 3-5 business days to process.

# Data Privacy  
All data is stored locally in SQLite databases. We do not transmit any customer data to external servers except for the AI model API calls.
"""

    product_doc_md = """# Authentication Module
The authentication module handles user login and session tokens. If users report being randomly logged out, it is usually a JWT expiration issue.

# Checkout Module / Cart
The cart state is synchronized via local storage and the backend database. A common issue is the cart not updating when items are added; this is tied to the state sync delay.

# Payment Gateway
We use Stripe for processing payments. If Stripe fails, the fallback is PayPal.
"""

    print("Ingesting company doc...")
    dp.ingest_document(company_doc_md, "company")
    
    print("Ingesting product doc...")
    dp.ingest_document(product_doc_md, "product")
    
    print("\n--- Retrieval Tests ---")
    
    q1 = "How long do refunds take?"
    print(f"\nQuerying company docs: '{q1}'")
    results = dp.retrieve_context(q1, "company", limit=1)
    for r in results:
        print(f"[{r['distance']:.3f}] {r['section_title']}: {r['content']}")
        
    q2 = "Items aren't showing up in my cart after I add them"
    print(f"\nQuerying product docs: '{q2}'")
    results = dp.retrieve_context(q2, "product", limit=1)
    for r in results:
        print(f"[{r['distance']:.3f}] {r['section_title']}: {r['content']}")

    print("\nTest complete.")
    
if __name__ == "__main__":
    t0 = time.time()
    test_doc_processor()
    print(f"Time taken: {time.time() - t0:.2f}s")
    
    # Cleanup test db
    if os.path.exists("test_knowledge.db"):
        try:
             os.remove("test_knowledge.db")
        except:
             pass
