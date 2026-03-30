import json
import re
from typing import Optional, Dict, Any
from engine.session_manager import SessionManager
from engine.doc_processor import DocProcessor
from engine.ai import call_ai

class Chatbot:
    """
    Intelligence layer that handles dual-mode responses:
    1. Public Natural Chat for the customer.
    2. Private JSON State for the engine (RESOLVING, RAISE_TICKET, ESCALATE_HUMAN).
    
    Uses Hybrid Context: 
    - Full company/customer management rules (preprocessed) 
    - RAG retrieval for technical product details.
    """
    
    def __init__(self, session_manager: SessionManager, doc_processor: DocProcessor, company_context: str = ""):
        self.sm = session_manager
        self.doc_processor = doc_processor
        self.company_context = company_context

    def handle_message(self, session_id: str, message: str, customer_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user message using hybrid context (Full rules + RAG product docs).
        """
        # 1. Update email if provided
        if customer_email:
            self.sm.update_email(session_id, customer_email)

        # 2. Get conversation history
        history = self.sm.get_history(session_id, limit=10)
        history_str = ""
        for m in history:
            role = "Customer" if m['role'] == "user" else "Assistant"
            history_str += f"{role}: {m['content']}\n"
        
        # 3. Retrieve Product RAG context (Scalable for large technical docs)
        product_results = self.doc_processor.retrieve_context(message, doc_type="product", limit=2)
        product_context_str = "\n".join([r["content"] for r in product_results])

        # 4. Assemble the Hybrid Prompt
        system_prompt = f"""
You are the Tackety Support Engine. You provide technical help and resolve issues.

## COMPANY POLICIES & CUSTOMER MANAGEMENT (Mandatory Rules):
{self.company_context if self.company_context else "Default policies apply."}

## PRODUCT TECHNICAL KNOWLEDGE (Retrieved Context):
{product_context_str if product_context_str else "Refer to general technical best practices."}

## Operational Instructions:
- Mode 1 (Response): Provide a short, empathetic, professional response to the customer.
- Mode 2 (JSON State): You MUST append a JSON block at the end of your response.
  States:
  - RESOLVING: Default. Chatting normally and helping.
  - RESOLVED: Use ONLY if the query is fully answered and no ticket is needed.
  - RAISE_TICKET: Use for MUST-TRACK tasks. ALWAYS use this for technical BUGS, CRASHES, or SERVER ERRORS that you cannot fix. Set 'is_technical' accordingly.
  - ESCALATE_HUMAN: Use for complex handoffs or explicit human requests.

JSON Format:
{{
  "state": "RESOLVING" | "RESOLVED" | "RAISE_TICKET" | "ESCALATE_HUMAN",
  "confidence": 0.9,
  "collected": {{
    "issue_summary": "Short 1-sentence summary",
    "is_technical": true | false,
    "issue_type": "bug" | "billing" | "refund" | "feature_request",
    "customer_email": "{customer_email if customer_email else 'null'}"
  }}
}}
"""
        
        # 5. Call AI
        response_text = call_ai(
            prompt=f"{history_str}\nCustomer: {message}",
            system_prompt=system_prompt
        )

        # 6. Parse structured response
        parsed = self._parse_structured_response(response_text)
        
        # 7. Store interaction in history
        self.sm.add_message(session_id, "user", message)
        self.sm.add_message(session_id, "assistant", parsed.get('response', ''))
        
        # 8. Update session status in DB if state changed
        if parsed.get('state') != "RESOLVING":
            self.sm.close_session(session_id, status=parsed['state'].lower())
            
        return parsed

    def _parse_structured_response(self, raw_text: str) -> Dict[str, Any]:
        """Extracts JSON from the AI output strictly."""
        try:
            # Look for the JSON block
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                # Ensure it has a response field if AI put it outside JSON
                if "response" not in data:
                     data["response"] = raw_text.replace(match.group(0), "").strip()
                return data
            
            # Fallback if no JSON found
            return {
                "response": raw_text,
                "state": "RESOLVING",
                "collected": {}
            }
        except Exception:
            return {
                "response": "I'm having trouble processing your request. Could you try again?",
                "state": "RESOLVING",
                "collected": {}
            }
