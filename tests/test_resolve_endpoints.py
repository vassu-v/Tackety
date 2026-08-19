"""
Covers POST /clusters/{id}/resolve and POST /support/cases/{id}/resolve,
including the double-resolve fix (no re-notification, clean 404 instead).
"""


def test_resolve_nonexistent_cluster_404s(client, auth_headers):
    res = client.post("/clusters/999999/resolve", headers=auth_headers)
    assert res.status_code == 404


def test_resolve_nonexistent_case_404s(client, auth_headers):
    res = client.post("/support/cases/999999/resolve", headers=auth_headers)
    assert res.status_code == 404


def test_cluster_resolve_then_double_resolve_404s(client, auth_headers, mock_ai_response):
    mock_ai_response({
        "state": "RAISE_TICKET",
        "collected": {
            "issue_summary": "Payment gateway times out",
            "is_technical": True,
            "customer_email": "payer@example.com"
        }
    }, response_text="Logged as a bug.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]
    res = client.post("/session/message", json={"session_id": session_id, "message": "payment times out"})
    cluster_id = res.json()["routing"]["cluster_id"]

    first_resolve = client.post(f"/clusters/{cluster_id}/resolve", headers=auth_headers)
    assert first_resolve.status_code == 200
    assert first_resolve.json()["notifications_sent"] == 1

    second_resolve = client.post(f"/clusters/{cluster_id}/resolve", headers=auth_headers)
    assert second_resolve.status_code == 404


def test_case_resolve_then_double_resolve_404s(client, auth_headers, mock_ai_response):
    mock_ai_response({
        "state": "RAISE_TICKET",
        "collected": {"issue_summary": "wants a refund", "is_technical": False}
    }, response_text="Passed to support.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]
    client.post("/session/message", json={"session_id": session_id, "message": "refund please"})

    queue = client.get("/support/queue", headers=auth_headers).json()
    matching = [c for c in queue["support_cases"]["NON_TECHNICAL_TICKETS"] if c["session_id"] == session_id]
    assert len(matching) == 1
    case_id = matching[0]["id"]

    first_resolve = client.post(f"/support/cases/{case_id}/resolve", headers=auth_headers)
    assert first_resolve.status_code == 200

    second_resolve = client.post(f"/support/cases/{case_id}/resolve", headers=auth_headers)
    assert second_resolve.status_code == 404
