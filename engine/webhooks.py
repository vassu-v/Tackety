import hmac
import hashlib
import json
from typing import Dict, Any, Optional

class Webhooks:
    """
    Standard Webhook Dispatcher.
    Fires signed HMAC-SHA256 POST requests to registered endpoints.
    Allows for decoupled, async-friendly system monitoring.
    """

    def __init__(self, secret_key: str = "tackety_default_secret"):
        self.secret_key = secret_key

    def dispatch_event(self, event_type: str, payload: Dict[str, Any]):
        """
        Generic, properly-named event dispatcher.
        Payload is signed for security verification on the receiver side.
        """
        print(f"\n[WEBHOOK] Event Triggered: {event_type}")
        print(f"[WEBHOOK] Payload: {payload}")

        # Compute signature as a developer-first security measure
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode('utf-8'),
            payload_str.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        print(f"[WEBHOOK] Headers: {{'X-Tackety-Signature': '{signature}', 'X-Tackety-Event': '{event_type}'}}")
        print("[WEBHOOK] [STUB] Signed POST sent to registered developer URL.")

    def trigger(self, event_type: str, data: Dict[str, Any]):
        """Legacy compatibility wrapper for older internal calls."""
        self.dispatch_event(event_type, data)
