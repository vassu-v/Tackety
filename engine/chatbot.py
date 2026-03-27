import json
import re
from typing import Optional, Dict, Any
from engine.session_manager import SessionManager
from engine.doc_processor import DocProcessor
from engine.ai import call_ai

class Chatbot:
    """
    The Intelligence Layer of Tackety.
    Handles natural conversation, state tracking, and ticket generation.
    Stateless by design; reconstructs context from SessionManager on every turn.
    Uses DocProcessor for RAG context retrieval from the company doc.
    """

    def __init__(self, session_manager: SessionManager, doc_processor: DocProcessor):
        self.sm = session_manager
        self.doc_processor = doc_processor
        self.system_prompt_template = (
            "You are an expert customer support agent for our software product.\n"
            "Goal: Be helpful, concise, and professional.\n\n"
            "COMPANY KNOWLEDGE (Use this to answer questions):\n"
            "{company_context}\n\n"
            "MANDATORY Response Format (Strict JSON):\n"
            "{{\n"
            "  \"response\": \"Your natural message to the customer\",\n"
            "  \"state\": \"RESOLVING\" | \"ESCALATE_HUMAN\" | \"RAISE_TICKET\",\n"
            "  \"confidence\": 0.9,\n"
            "  \"collected\": {{\n"
            "    \"issue_summary\": \"Short summary of the issue so far\",\n"
            "    \"issue_type\": \"technical\" | \"customer_service\"\n"
            "  }}\n"
            "}}\n\n"
            "States:\n"
            "- RESOLVING: Use this while gathering info, answering questions, or troubleshooting.\n"
            "- ESCALATE_HUMAN: Use this if the issue is about billing, accounts, or complex policies.\n"
            "- RAISE_TICKET: Use this if the issue is a technical bug, crash, or data problem.\n\n"
            "Tone: Short, friendly, and conversational in the 'response' field. No long paragraphs."
        )

    def handle_message(self, session_id: str, message: str, customer_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes a user message, performs RAG retrieval, and returns the structured AI response.
        """
        # 1. Update email if provided
        if customer_email:
            self.sm.update_email(session_id, customer_email)

        # 2. Store the user's message
        self.sm.add_message(session_id, "user", message)

        # 3. Get full history for context
        history = self.sm.get_history(session_id)
        
        # 4. Build conversation context
        context = ""
        for m in history:
            role = "Customer" if m['role'] == "user" else "Assistant"
            context += f"{role}: {m['content']}\n"
            
        # 5. Retrieve RAG context from doc_processor (using the latest message as the query)
        rag_results = self.doc_processor.retrieve_context(message, doc_type="company", limit=3)
        company_context = ""
        for r in rag_results:
            company_context += f"--- {r['section_title']} ---\n{r['content']}\n\n"
            
        if not company_context.strip():
            company_context = "No specific company knowledge found for this query."
            
        system_prompt = self.system_prompt_template.format(company_context=company_context)
        
        # 6. Call the AI
        raw_ai_response = call_ai(
            prompt=context,
            system_prompt=system_prompt
        )

        # 7. Parse structured response
        parsed = self._parse_structured_response(raw_ai_response)
        
        # 8. Store the assistant's natural response
        self.sm.add_message(session_id, "assistant", parsed['response'])
        
        # 9. Update session status in DB if state changed
        if parsed['state'] != "RESOLVING":
            self.sm.close_session(session_id, status=parsed['state'].lower())
            
        return parsed

    def _parse_structured_response(self, raw_text: str) -> Dict[str, Any]:
        """Extracts JSON from the AI output strictly."""
        try:
            # Look for the JSON block
            match = re.search(r'\{.*\}', raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            
            # Fallback if no JSON found
            return {
                "response": raw_text,
                "state": "RESOLVING",
                "collected": {}
            }
        except Exception:
            # Last resort fallback
            return {
                "response": "I'm having trouble processing your request. Could you try again?",
                "state": "RESOLVING",
                "collected": {}
            }
