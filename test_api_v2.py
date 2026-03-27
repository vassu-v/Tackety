import requests
import time

API_URL = "http://localhost:8000"

def test_flow():
    print("1. Starting session...")
    r = requests.post(f"{API_URL}/session/start", json={"customer_email": "test@example.com"})
    sid = r.json()["session_id"]
    print(f"Session ID: {sid}")
    
    print("\n2. Asking a general question (Should RESOLVE)...")
    r = requests.post(f"{API_URL}/session/message", json={
        "session_id": sid,
        "message": "Hi, I have a question about your refund policy."
    })
    res = r.json()
    print(f"AI: {res['response']}")
    print(f"State: {res['session_status']}")
    
    print("\n3. Reporting a bug (Should RAISE_TICKET)...")
    r = requests.post(f"{API_URL}/session/message", json={
        "session_id": sid,
        "message": "My checkout cart keeps crashing when I add more than 5 items. Can you fix this?"
    })
    res = r.json()
    print(f"AI: {res['response']}")
    print(f"State: {res['session_status']}")

    print("\n4. Asking about billing (Should ESCALATE_HUMAN)...")
    # New session for clear state
    r2 = requests.post(f"{API_URL}/session/start", json={})
    sid2 = r2.json()["session_id"]
    r = requests.post(f"{API_URL}/session/message", json={
        "session_id": sid2,
        "message": "I was double charged on my last invoice. Can I speak to a human about this billing issue?"
    })
    res = r.json()
    print(f"AI: {res['response']}")
    print(f"State: {res['session_status']}")

if __name__ == "__main__":
    test_flow()
