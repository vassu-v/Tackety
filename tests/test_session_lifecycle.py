"""
Covers session lifecycle behavior, including the 409-on-closed-session
guard added in phase-0-hardening, and the end-to-end chat -> router ->
ticket/case routing path with a scripted (mocked) AI response.
"""


def test_message_to_unknown_session_404s(client):
    res = client.post("/session/message", json={
        "session_id": "not-a-real-session-id", "message": "hello"
    })
    assert res.status_code == 404


def test_history_of_unknown_session_404s(client):
    res = client.get("/session/not-a-real-session-id/history")
    assert res.status_code == 404


def test_resolving_message_keeps_session_active(client, mock_ai_response):
    mock_ai_response({
        "state": "RESOLVING",
        "collected": {"issue_summary": "still chatting", "is_technical": False}
    }, response_text="Tell me more about the issue.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]

    res = client.post("/session/message", json={"session_id": session_id, "message": "hi"})
    assert res.status_code == 200
    assert res.json()["session_status"] == "RESOLVING"

    # Session should still be active - a second message must not 409.
    res2 = client.post("/session/message", json={"session_id": session_id, "message": "more info"})
    assert res2.status_code == 200


def test_technical_ticket_raises_and_appears_in_queue(client, auth_headers, mock_ai_response):
    mock_ai_response({
        "state": "RAISE_TICKET",
        "collected": {
            "issue_summary": "Checkout crashes with a 500 error",
            "is_technical": True,
            "customer_email": "buyer@example.com"
        }
    }, response_text="I've logged that as a bug for the team.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]

    res = client.post("/session/message", json={"session_id": session_id, "message": "checkout is broken"})
    assert res.status_code == 200
    body = res.json()
    assert body["session_status"] == "RAISE_TICKET"
    assert body["routing"]["type"] == "TECHNICAL"

    queue = client.get("/support/queue", headers=auth_headers).json()
    cluster_ids = [c["id"] for c in queue["technical_clusters"]]
    assert body["routing"]["cluster_id"] in cluster_ids


def test_closed_session_rejects_further_messages(client, mock_ai_response):
    mock_ai_response({
        "state": "RAISE_TICKET",
        "collected": {"issue_summary": "billing question", "is_technical": False}
    }, response_text="I've passed this to our support team.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]

    first = client.post("/session/message", json={"session_id": session_id, "message": "I want a refund"})
    assert first.status_code == 200
    assert first.json()["routing"]["type"] == "NON_TECHNICAL"

    # Session is now closed (non-active) - a further message must 409,
    # not silently proceed as if nothing happened.
    second = client.post("/session/message", json={"session_id": session_id, "message": "hello again"})
    assert second.status_code == 409


def test_escalate_human_creates_handover_case(client, auth_headers, mock_ai_response):
    mock_ai_response({
        "state": "ESCALATE_HUMAN",
        "collected": {"issue_summary": "wants a human", "is_technical": False}
    }, response_text="Connecting you with a support agent now.")

    start = client.post("/session/start", json={})
    session_id = start.json()["session_id"]

    res = client.post("/session/message", json={"session_id": session_id, "message": "let me talk to a human"})
    assert res.status_code == 200
    assert res.json()["routing"]["type"] == "HANDOVER"

    queue = client.get("/support/queue", headers=auth_headers).json()
    handover_sessions = [c["session_id"] for c in queue["support_cases"]["CHAT_HANDOVERS"]]
    assert session_id in handover_sessions
