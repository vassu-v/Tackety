from typing import Dict, Any, Optional
from engine.normalizer import Normalizer
from engine.human_queue import SupportHub
from engine.issue_engine import IssueEngine
from engine.webhooks import Webhooks
from engine.doc_processor import DocProcessor

class Router:
    """
    The Orchestration Hub for Issue Routing.
    Coordinates the transition from Chatbot Decisions to specialized Processing Engines.
    
    Path 1: RESOLVED -> No action.
    Path 2: Technical -> Normalizer -> Issue Engine -> issues.db.
    Path 3: Non-Technical -> Support Hub (Ticket) -> support.db.
    Path 4: Handover -> Support Hub (Session) -> support.db.
    """
    
    def __init__(self, normalizer: Normalizer, support_hub: SupportHub, issue_engine: IssueEngine, webhooks: Webhooks, doc_processor: DocProcessor):
        self.normalizer = normalizer
        self.support_hub = support_hub
        self.issue_engine = issue_engine
        self.webhooks = webhooks
        self.doc_processor = doc_processor
        
    def route_decision(self, session_id: str, chatbot_json: Dict[str, Any], client_request_id: Optional[str] = None):
        """
        Main routing entry point. Directs based on state and technical flags.

        client_request_id, when provided by the caller (e.g. an
        Idempotency-Key header on POST /session/message), makes ticket/case
        creation and the resulting webhook dispatch safe to retry: replaying
        the same key returns the original result instead of creating a
        duplicate ticket or double-firing a webhook.
        """
        state = chatbot_json.get("state", "RESOLVING")
        collected = chatbot_json.get("collected", {})
        
        # Path 1: Active resolving or final resolved success
        if state in ["RESOLVING", "RESOLVED"]:
            return None
            
        print(f"\n[ROUTER] Orchestrating Heart for Session {session_id} (State: {state})")
        
        summary = collected.get("issue_summary", "No summary provided")
        is_technical = collected.get("is_technical", False)
        
        # Path 2 & 3: Raising structured tickets
        if state == "RAISE_TICKET":
            if is_technical:
                # Engineering Pipeline
                print(f"[ROUTER] Directing technical issue to Intelligence Engine.")
                
                # 1. Terminology Mapping (Terminology only, no classification)
                mapping = self.normalizer.normalize(summary)
                
                # 2. Embedding for Clustering
                # We reuse the doc_processor to generate the same vector type
                model = self.doc_processor._get_model()
                embedding = model.encode(summary).tolist()

                # Customer email comes from the chatbot's structured output - the
                # Router has no direct access to conversations.db (by design, see
                # DESIGN.md section 7), so this is the only correct source for it.
                customer_email = collected.get("customer_email")

                # 3. Process through Issue Engine (Clustering/Weights)
                result = self.issue_engine.process_ticket(
                    session_id=session_id,
                    normalized_data=mapping,
                    raw_summary=summary,
                    embedding=embedding,
                    customer_email=customer_email,
                    client_request_id=client_request_id
                )
                cluster_id = result["cluster_id"]

                # 4. Notify - only on genuine creation, not a retried replay
                if result["created"]:
                    self.webhooks.dispatch_event("ticket.created", {
                        "ticket_id": result["ticket_id"],
                        "cluster_id": cluster_id,
                        "summary": summary,
                        "slug": mapping["normalized_slug"],
                        "session_id": session_id
                    })

                return {
                    "type": "TECHNICAL",
                    "cluster_id": cluster_id,
                    "slug": mapping["normalized_slug"],
                    "urgency": self._get_cluster_urgency(cluster_id) # helper needed if we want urgency, or just omit for now if not easily available
                }
            else:
                # Support Pipeline (Non-Technical Ticket)
                print(f"[ROUTER] Directing non-technical issue to Support Hub.")
                created = self.support_hub.enqueue_ticket(session_id, summary, client_request_id=client_request_id)
                if created:
                    self.webhooks.dispatch_event("support.ticket_raised", {
                        "session_id": session_id,
                        "summary": summary
                    })
                return {
                    "type": "NON_TECHNICAL",
                    "summary": summary
                }

        # Path 4: Direct Handover
        elif state == "ESCALATE_HUMAN":
             print(f"[ROUTER] Escalating Active Session {session_id} to Human Agent.")
             created = self.support_hub.enqueue_handover(session_id, summary, client_request_id=client_request_id)
             if created:
                 self.webhooks.dispatch_event("handoff.initiated", {
                     "session_id": session_id,
                     "summary": summary
                 })
             return {
                 "type": "HANDOVER",
                 "summary": summary
             }
             
        return None
        
    def _get_cluster_urgency(self, cluster_id):
        # Helper to fetch urgency to pass back to the UI
        try:
             conn = self.issue_engine._get_conn()
             row = conn.execute("SELECT urgency FROM clusters WHERE id = ?", (cluster_id,)).fetchone()
             conn.close()
             if row:
                 return row[0]
        except Exception:
             pass
        return "NORMAL"
