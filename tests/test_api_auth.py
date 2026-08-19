"""
Covers the auth gap fixed in phase-0-hardening: developer/agent-facing
endpoints must reject unauthenticated and wrongly-authenticated requests,
while the customer-facing chat surface and /health must stay open.
"""


def test_health_is_public(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_support_queue_requires_auth(client):
    res = client.get("/support/queue")
    assert res.status_code == 401


def test_support_queue_rejects_wrong_key(client):
    res = client.get("/support/queue", headers={"X-API-Key": "definitely-wrong"})
    assert res.status_code == 401


def test_support_queue_accepts_correct_key(client, auth_headers):
    res = client.get("/support/queue", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "technical_clusters" in body
    assert "support_cases" in body


def test_setup_webhook_requires_auth(client):
    res = client.post("/setup/webhook", json={
        "event": "ticket.created", "url": "https://example.com/hook", "secret": "s"
    })
    assert res.status_code == 401


def test_clusters_resolve_requires_auth(client):
    res = client.post("/clusters/1/resolve")
    assert res.status_code == 401


def test_support_case_resolve_requires_auth(client):
    res = client.post("/support/cases/1/resolve")
    assert res.status_code == 401


def test_session_start_does_not_require_auth(client):
    """The customer-facing chat surface must stay open by design."""
    res = client.post("/session/start", json={})
    assert res.status_code == 200
    assert "session_id" in res.json()
