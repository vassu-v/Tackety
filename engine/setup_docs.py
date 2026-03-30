import os
import sys

# Ensure engine imports resolve correctly from within the engine directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.doc_processor import DocProcessor
from engine.fileprocess import filetypeprocessor

# --- CONFIGURATION (Self-Hosting Friendly) ---
# Can be overridden via command line or environment
DOCS_SOURCE_DIR = os.getenv("TACKETY_DOCS_DIR", "demo/docs")
DATA_DIR = "engine/data"

def run_setup():
    print(f"--- Tackety Knowledge Setup (Source: {DOCS_SOURCE_DIR}) ---")
    
    if not os.path.exists(DOCS_SOURCE_DIR):
        print(f"Error: Docs directory '{DOCS_SOURCE_DIR}' not found. Please create it or set TACKETY_DOCS_DIR.")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)
    dp = DocProcessor(db_path=os.path.join(DATA_DIR, "knowledge.db"))

    # 1. Company Doc -> RAG (knowledge.db)
    # This provides the deep searchable knowledge base
    company_pdf = os.path.join(DOCS_SOURCE_DIR, "company_doc.pdf")
    company_text = filetypeprocessor(company_pdf)
    if company_text:
        print("Ingesting Company Knowledge into RAG database...")
        dp.clear_docs("company")
        dp.ingest_document(company_text, "company")
    else:
        print(f"Warning: Could not process {company_pdf}")

    # 2. Product Doc -> Mapping (product_context.txt)
    # This provides the technical slugs for the Normalizer
    product_pdf = os.path.join(DOCS_SOURCE_DIR, "product_doc.pdf")
    product_text = filetypeprocessor(product_pdf)
    if product_text:
        dp.process_product_doc(product_text, os.path.join(DATA_DIR, "product_context.txt"))
    else:
        print(f"Warning: Could not process {product_pdf}")

    # 3. Customer Management -> Summary (management_rules.txt)
    # This provides core policies for prompt injection in Chatbot
    mgmt_pdf = os.path.join(DOCS_SOURCE_DIR, "customer_management_doc.pdf")
    mgmt_text = filetypeprocessor(mgmt_pdf)
    if mgmt_text:
        dp.process_customer_management(mgmt_text, os.path.join(DATA_DIR, "management_rules.txt"))
    else:
        print(f"Warning: Could not process {mgmt_pdf}")

    print("\nSetup complete. Documentation preprocessed and knowledge base initialized.")

if __name__ == "__main__":
    run_setup()
