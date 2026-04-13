import json
import re
from typing import Dict, Any, Optional
from engine.doc_processor import DocProcessor
from engine.ai import call_ai

class Normalizer:
    """
    Terminology Mapping Engine.
    Translates raw customer descriptions into technical slugs and documentation references.
    Does NOT perform classification (Team/Priority).
    """
    def __init__(self, doc_processor: DocProcessor, product_context: str = ""):
        self.doc_processor = doc_processor
        self.product_context = product_context

    def normalize(self, issue_summary: str) -> Dict[str, Any]:
        """
        Maps raw issue summary to internal technical terminology.
        Returns: {normalized_slug, doc_reference}
        """
        print(f"[NORMALIZER] Terminology Mapping for: '{issue_summary}'")
        
        # 1. Retrieve most relevant technical context sections (RAG)
        rag_context = self.doc_processor.retrieve_context(issue_summary, doc_type="product", limit=2)
        rag_str = "\n".join([f"- {r['section_title']}: {r['content']}" for r in rag_context])

        # 2. Mapping Prompt using both RAG and the fixed Product Map
        system_prompt = f"""
        You are a Technical Terminology Mapper. Your job is to translate customer issues into internal feature slugs.
        
        ## PRODUCT TERMINOLOGY MAP (Established Slugs):
        {self.product_context if self.product_context else "Use general technical naming."}
        
        ## LIVE DOC CONTEXT (Retrieved Sections):
        {rag_str if rag_str else "No direct matches found."}
        
        ## SLUG GENERATION RULES:
        1. Priority 1: Match the issue to an established slug from the Product Map.
        2. Priority 2: If the issue is entirely unprecedented, DYNAMICALLY GENERATE a new, highly descriptive slug. 
           - Must be ALL_CAPS.
           - Must use underscores (e.g., UI_UNEXPECTED_COLOR_SHIFT, AUTH_OAUTH_TIMEOUT).
        
        Return ONLY a JSON object:
        {{
          "normalized_slug": "CAPS_LOCK_SLUG",
          "doc_reference": "Matching Section Title (or 'Dynamic Issue' if new)"
        }}
        """

        raw_res = call_ai(prompt=f"Customer Issue: {issue_summary}", system_prompt=system_prompt)
        
        try:
            match = re.search(r'\{.*\}', raw_res, re.DOTALL)
            if match:
                parsed = json.loads(match.group(0))
                return {
                    "normalized_slug": str(parsed.get("normalized_slug", "GENERAL_TECHNICAL")).upper(),
                    "doc_reference": str(parsed.get("doc_reference", "General"))
                }
        except Exception as e:
            print(f"[NORMALIZER] Mapping Fail: {e}")

        return {
            "normalized_slug": "NORMALIZATION_FAILED",
            "doc_reference": "General"
        }
