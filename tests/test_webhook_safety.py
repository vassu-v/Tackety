"""
Covers the SSRF fix: webhook registration must reject internal/private/
loopback targets and accept legitimate public ones.
"""
from engine.url_safety import is_safe_webhook_url


def test_blocks_cloud_metadata_endpoint():
    safe, reason = is_safe_webhook_url("http://169.254.169.254/latest/meta-data/")
    assert safe is False
    assert "169.254.169.254" in reason


def test_blocks_loopback():
    safe, _ = is_safe_webhook_url("http://localhost:8000/hook")
    assert safe is False


def test_blocks_private_range():
    safe, _ = is_safe_webhook_url("http://10.0.0.5/hook")
    assert safe is False


def test_blocks_disallowed_scheme():
    safe, reason = is_safe_webhook_url("ftp://example.com/hook")
    assert safe is False
    assert "scheme" in reason


def test_allows_public_https():
    safe, reason = is_safe_webhook_url("https://example.com/hook")
    assert safe is True
    assert reason == ""


def test_registration_endpoint_rejects_ssrf_url(client, auth_headers):
    res = client.post("/setup/webhook", headers=auth_headers, json={
        "event": "ticket.created", "url": "http://169.254.169.254/", "secret": "s"
    })
    assert res.status_code == 400


def test_registration_endpoint_accepts_public_url(client, auth_headers):
    res = client.post("/setup/webhook", headers=auth_headers, json={
        "event": "ticket.created", "url": "https://example.com/hook-a", "secret": "s"
    })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
