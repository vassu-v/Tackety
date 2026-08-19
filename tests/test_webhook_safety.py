"""
Covers the SSRF fix: webhook registration must reject internal/private/
loopback targets and accept legitimate public ones.

is_safe_webhook_url() does a real DNS lookup to resolve the hostname
before checking whether the resulting IP is private/loopback/etc. The
negative-path tests below (blocked hostnames) don't care what a real
lookup returns - a private/loopback IP is private regardless of what
actually resolves. But the positive-path tests (public URL should be
allowed) would otherwise depend on a real, working DNS resolver and
network access, which contradicts this suite's "runs fully offline"
claim - so those two mock socket.getaddrinfo to a fixed public IP.
"""
from unittest.mock import patch
from engine.url_safety import is_safe_webhook_url


def _fake_public_getaddrinfo(host, port):
    """Mimics socket.getaddrinfo()'s return shape for a public IP,
    without touching the network."""
    return [(2, 1, 6, '', ('93.184.216.34', 0))]


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
    with patch("engine.url_safety.socket.getaddrinfo", side_effect=_fake_public_getaddrinfo):
        safe, reason = is_safe_webhook_url("https://example.com/hook")
    assert safe is True
    assert reason == ""


def test_registration_endpoint_rejects_ssrf_url(client, auth_headers):
    res = client.post("/setup/webhook", headers=auth_headers, json={
        "event": "ticket.created", "url": "http://169.254.169.254/", "secret": "s"
    })
    assert res.status_code == 400


def test_registration_endpoint_accepts_public_url(client, auth_headers):
    with patch("engine.url_safety.socket.getaddrinfo", side_effect=_fake_public_getaddrinfo):
        res = client.post("/setup/webhook", headers=auth_headers, json={
            "event": "ticket.created", "url": "https://example.com/hook-a", "secret": "s"
        })
    assert res.status_code == 200
    assert res.json()["status"] == "success"
