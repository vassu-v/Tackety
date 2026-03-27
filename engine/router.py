from typing import Dict, Any

class Router:
    """
    Premature version of the Handoff Hub.
    Accepts the hidden JSON emitted by the Chatbot layer.
    Lays the groundwork for the future Normalizer and Human Queue integrations.
    """
    
    def __init__(self):
        # In the future, this will take instances of Normalizer and HumanQueue
        pass
        
    def route_decision(self, session_id: str, chatbot_json: Dict[str, Any]):
        """
        Receives the structural output from the Chatbot and decides the next step.
        """
        state = chatbot_json.get("state", "RESOLVING")
        
        if state == "RESOLVING":
            # The chatbot is still handling the conversation. No routing needed.
            return
            
        print(f"\n[ROUTER] [STATE] Session {session_id} changed to: {state}")
        
        collected = chatbot_json.get("collected", {})
        if collected:
             print(f"[ROUTER] [INFO] Collected: {collected}")
             
        if state == "RAISE_TICKET":
            print(f"[ROUTER] -> Deferring to FUTURE Normalizer queue...")
            # Future: normalizer.process(collected['issue_summary'])
            
        elif state == "ESCALATE_HUMAN":
            print(f"[ROUTER] -> Deferring to FUTURE Human agent queue...")
            # Future: human_queue.enqueue(session_id, collected)
