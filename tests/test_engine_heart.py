import requests
import time
import uuid

API_URL = "http://localhost:8000"

def test_engine_heart():
    print("\n--- Testing Tackety Architecture Realignment (Technical vs Support) ---\n")

    # 1. Start a session
    res = requests.post(f"{API_URL}/session/start", json={"customer_email": "realignment_tester@example.com"})
    session_id = res.json()["session_id"]
    print(f"Started Session: {session_id}")

    # 2. Simulate 4 distinct paths
    scenarios = [
        {
            "msg": "The checkout page hangs when I try to pay. It just spins forever.",
            "desc": "Technical Bug (Engine)"
        },
        {
            "msg": "The /api/v1/user endpoint is returning a 500 Internal Server Error.",
            "desc": "Technical Bug (Clustering Test)"
        },
        {
            "msg": "I am unhappy with the service and want a full refund for my last invoice.",
            "desc": "Non-Technical Ticket (Support Hub)"
        },
        {
             "msg": "I need to speak with a human agent right now about my account.",
             "desc": "Active Handover (Support Hub)"
        }
    ]

    for scenario in scenarios:
        # Start a fresh session for each test case to ensure zero context bleeding
        s_res = requests.post(f"{API_URL}/session/start", json={"customer_email": "tester@example.com"})
        s_id = s_res.json()["session_id"]
        
        print(f"\n[TEST] Sending: '{scenario['msg']}' ({scenario['desc']})")
        res = requests.post(f"{API_URL}/session/message", json={
            "session_id": s_id,
            "message": scenario["msg"],
            "customer_email": "tester@example.com"
        })
        data = res.json()
        print(f"AI Response State: {data['session_status']}")

    # 3. Verify the Split Buckets
    print("\n[TEST] Verifying Realignment at /support/queue...")
    time.sleep(1) # Brief pause for processing
    res = requests.get(f"{API_URL}/support/queue")
    queue_data = res.json()

    print("\n--- INTELLIGENCE ENGINE (Technical Clusters) ---")
    tech_clusters = queue_data.get("technical_clusters", [])
    for cluster in tech_clusters:
        print(f"\nCLUSTER: {cluster['issue_slug']} ({cluster['weight']} tickets) [{cluster['urgency']}]")
        for t in cluster['tickets']:
             print(f"  - {t['raw_summary']}")

    print("\n--- SUPPORT HUB (Manual Cases) ---")
    support_cases = queue_data.get("support_cases", {})
    for case_type, cases in support_cases.items():
        print(f"\nTYPE: {case_type} ({len(cases)} cases)")
        for c in cases:
            print(f"  - {c['summary']}")

    # Basic Validation
    if len(tech_clusters) >= 1 and len(support_cases.get("NON_TECHNICAL_TICKETS", [])) >= 1:
        print("\nSUCCESS: Architecture Realignment correctly separated Technical and Support flows.")
    else:
        print("\nFAILURE: Realignment logic did not meet expectations.")

if __name__ == "__main__":
    try:
        test_engine_heart()
    except Exception as e:
        print(f"Error: {e}. Make sure the server is running on port 8000.")
