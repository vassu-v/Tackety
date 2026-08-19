import os
import sys

# Ensure engine imports resolve correctly from within the engine directory
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Optional
from engine.doc_processor import DocProcessor
from engine.fileprocess import filetypeprocessor

# --- CONFIGURATION (Self-Hosting Friendly) ---
# Can be overridden via command line or environment
DOCS_SOURCE_DIR = os.getenv("TACKETY_DOCS_DIR", "demo/docs")
DATA_DIR = "engine/data"


def process_company_doc(dp: DocProcessor, text: str, data_dir: str) -> str:
    """
    Preprocesses the company doc into company_context.txt, the full-text
    context the chatbot injects directly into its system prompt (see
    chatbot.py's "Hybrid Context" docstring - company/policy context is
    meant to be injected in full, not retrieved via RAG on each turn,
    unlike the product doc).

    NOTE on a bug this fixes: the company doc used to also be pushed into
    the RAG vector store under doc_type="company" via ingest_document().
    Nothing anywhere ever retrieves doc_type="company" - chatbot.py and
    normalizer.py both only ever call retrieve_context(doc_type="product").
    So that RAG ingestion was pure wasted work, AND process_company_doc()
    (the function that actually produces what the chatbot uses) was never
    called at all - meaning company_context.txt never existed, and the
    chatbot's "GENERAL COMPANY CONTEXT" section of its system prompt was
    silently empty in every deployment that followed this script. Fixed
    by calling the right function instead of the RAG-ingestion one.
    """
    return dp.process_company_doc(text, os.path.join(data_dir, "company_context.txt"))


def process_product_doc(dp: DocProcessor, text: str, data_dir: str) -> str:
    """
    Product doc does double duty, correctly: it's RAG-ingested (so
    retrieve_context(doc_type="product") can pull specific relevant
    sections per message) AND preprocessed into product_context.txt
    (the terminology map the Normalizer injects in full). Both paths are
    real and both get used.
    """
    dp.clear_docs("product")
    dp.ingest_document(text, "product")
    return dp.process_product_doc(text, os.path.join(data_dir, "product_context.txt"))


def process_customer_management_doc(dp: DocProcessor, text: str, data_dir: str) -> str:
    """Preprocessed into management_rules.txt, injected in full into the
    chatbot's system prompt - same pattern as the company doc."""
    return dp.process_customer_management(text, os.path.join(data_dir, "management_rules.txt"))


def _read_source(base_path_no_ext: str) -> Optional[str]:
    """Looks for base_path_no_ext.pdf, then .md, then .txt and returns
    the extracted text, or None if neither exists."""
    for ext in (".pdf", ".md", ".txt"):
        candidate = base_path_no_ext + ext
        if os.path.exists(candidate):
            return filetypeprocessor(candidate)
    return None


def run_setup(docs_source_dir: str = None, data_dir: str = None):
    docs_source_dir = docs_source_dir or DOCS_SOURCE_DIR
    data_dir = data_dir or DATA_DIR

    print(f"--- Tackety Knowledge Setup (Source: {docs_source_dir}) ---")

    if not os.path.exists(docs_source_dir):
        print(f"Error: Docs directory '{docs_source_dir}' not found. Please create it or set TACKETY_DOCS_DIR.")
        sys.exit(1)

    os.makedirs(data_dir, exist_ok=True)
    dp = DocProcessor(db_path=os.path.join(data_dir, "knowledge.db"))

    company_text = _read_source(os.path.join(docs_source_dir, "company_doc"))
    if company_text:
        print("Preprocessing company doc into company_context.txt...")
        process_company_doc(dp, company_text, data_dir)
    else:
        print("Warning: Could not process company_doc (.pdf, .md, or .txt)")

    product_text = _read_source(os.path.join(docs_source_dir, "product_doc"))
    if product_text:
        print("Ingesting product doc into RAG + preprocessing terminology map...")
        process_product_doc(dp, product_text, data_dir)
    else:
        print("Warning: Could not process product_doc (.pdf, .md, or .txt)")

    mgmt_text = _read_source(os.path.join(docs_source_dir, "customer_management_doc"))
    if mgmt_text:
        print("Preprocessing customer management doc into management_rules.txt...")
        process_customer_management_doc(dp, mgmt_text, data_dir)
    else:
        print("Warning: Could not process customer_management_doc (.pdf, .md, or .txt)")

    print("\nSetup complete. Documentation preprocessed and knowledge base initialized.")


if __name__ == "__main__":
    run_setup()
