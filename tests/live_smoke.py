"""
Manual, live end-to-end smoke check - NOT part of the automated pytest
suite (deliberately named to avoid pytest's default test_*.py / *_test.py
collection patterns, since running it has real preconditions pytest
can't satisfy on its own).

Requires:
  1. A real AI_API key configured in engine/.env (this hits your actual
     configured AI provider - not free, not offline).
  2. The server actually running: python engine/api.py
  3. TACKETY_API_KEY set to the same value the server is using, either
     via environment variable or by editing API_KEY below.

Run with:  python tests/live_smoke.py

For the automated, offline, no-API-key-required test suite, see the
other files in this directory and run `pytest`.
"""
import os
import requests
import time

API_URL = os.getenv("TACKETY_TEST_API_URL", "http://localhost:8000")
API_KEY = os.getenv("TACKETY_API_KEY", "")
AUTH_HEADERS = {"X-API-Key": API_KEY}


def run_smoke_test():
    print("\n--- Tackety Live Smoke Test (requires a running server + real AI key) ---\n")

    if not API_KEY:
        print("WARNING: TACKETY_API_KEY is not set - /support/queue calls below will 401.")
        print("Set it to match the server's key (see its startup console output).\n")

    # 1. Start a session
    res = requests.post(f"{API_URL}/session/start", json={"customer_email": "realignment_tester@example.com"})
    res.raise_for_status()
    session_id = res.json()["session_id"]
    print(f"Started Session: {session_id}")

    # 2. Simulate 4 distinct paths
    scenarios = [
        {"msg": "The checkout page hangs when I try to pay. It just spins forever.", "desc": "Technical Bug (Engine)"},
        {"msg": "The /api/v1/user endpoint is returning a 500 Internal Server Error.", "desc": "Technical Bug (Clustering Test)"},
        {"msg": "I am unhappy with the service and want a full refund for my last invoice.", "desc": "Non-Technical Ticket (Support Hub)"},
        {"msg": "I need to speak with a human agent right now about my account.", "desc": "Active Handover (Support Hub)"},
    ]

    for scenario in scenarios:
        s_res = requests.post(f"{API_URL}/session/start", json={"customer_email": "tester@example.com"})
        s_res.raise_for_status()
        s_id = s_res.json()["session_id"]

        print(f"\n[TEST] Sending: '{scenario['msg']}' ({scenario['desc']})")
        res = requests.post(f"{API_URL}/session/message", json={
            "session_id": s_id,
            "message": scenario["msg"],
            "customer_email": "tester@example.com"
        })
        res.raise_for_status()
        data = res.json()
        print(f"AI Response State: {data['session_status']}")

    # 3. Verify the split buckets
    print("\n[TEST] Verifying Realignment at /support/queue...")
    time.sleep(1)
    res = requests.get(f"{API_URL}/support/queue", headers=AUTH_HEADERS)
    res.raise_for_status()
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

    if len(tech_clusters) >= 1 and len(support_cases.get("NON_TECHNICAL_TICKETS", [])) >= 1:
        print("\nSUCCESS: Architecture Realignment correctly separated Technical and Support flows.")
    else:
        print("\nFAILURE: Realignment logic did not meet expectations.")


if __name__ == "__main__":
    try:
        run_smoke_test()
    except Exception as e:
        print(f"Error: {e}. Make sure the server is running and AI_API/TACKETY_API_KEY are set.")
