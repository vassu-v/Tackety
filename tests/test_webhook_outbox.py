"""
Covers the webhook durability fix: dispatch_event() must persist an
outbox row per target *before* attempting delivery, a failed delivery
must stay 'pending' for retry rather than being silently dropped, and
repeated failure must eventually give up (status 'failed') rather than
retrying forever.

engine.webhooks.urllib.request.urlopen is mocked directly - these are
unit tests of the durability/retry mechanism, not of real HTTP delivery
(which engine/url_safety.py and test_webhook_safety.py already cover at
the registration boundary).
"""
import io
import os
import tempfile
from unittest.mock import patch, MagicMock

from engine.webhooks import Webhooks, MAX_ATTEMPTS


def _fresh_webhooks():
    path = os.path.join(tempfile.mkdtemp(), "outbox_test.db")
    return Webhooks(db_path=path)


def _success_response():
    resp = MagicMock()
    resp.status = 200
    resp.__enter__ = lambda self: self
    resp.__exit__ = lambda self, *a: False
    return resp


def test_dispatch_with_no_registered_webhook_creates_no_outbox_row():
    wh = _fresh_webhooks()
    wh.dispatch_event("ticket.created", {"a": 1})
    assert wh.get_outbox() == []


def test_successful_delivery_marks_row_delivered():
    wh = _fresh_webhooks()
    wh.register("ticket.created", "https://example.com/hook", "secret")

    with patch("engine.webhooks.urllib.request.urlopen", return_value=_success_response()):
        wh.dispatch_event("ticket.created", {"a": 1})

    entries = wh.get_outbox()
    assert len(entries) == 1
    assert entries[0]["status"] == "delivered"
    assert entries[0]["delivered_at"] is not None


def test_failed_delivery_stays_pending_for_retry():
    wh = _fresh_webhooks()
    wh.register("ticket.created", "https://example.com/hook", "secret")

    with patch("engine.webhooks.urllib.request.urlopen", side_effect=Exception("connection refused")):
        wh.dispatch_event("ticket.created", {"a": 1})

    entries = wh.get_outbox()
    assert len(entries) == 1
    assert entries[0]["status"] == "pending"
    assert entries[0]["attempts"] == 1
    assert "connection refused" in entries[0]["last_error"]


def test_retry_pending_skips_rows_not_yet_due():
    """A row whose next_attempt_at is in the future (real backoff, not the
    immediate first attempt) must not be retried early."""
    wh = _fresh_webhooks()
    wh.register("ticket.created", "https://example.com/hook", "secret")

    with patch("engine.webhooks.urllib.request.urlopen", side_effect=Exception("down")):
        wh.dispatch_event("ticket.created", {"a": 1})  # attempt 1, schedules a future retry

    with patch("engine.webhooks.urllib.request.urlopen", return_value=_success_response()) as mock_urlopen:
        wh.retry_pending()  # should be a no-op: next_attempt_at hasn't arrived yet
        mock_urlopen.assert_not_called()

    assert wh.get_outbox()[0]["attempts"] == 1


def test_gives_up_after_max_attempts():
    wh = _fresh_webhooks()
    wh.register("ticket.created", "https://example.com/hook", "secret")

    with patch("engine.webhooks.urllib.request.urlopen", side_effect=Exception("down")):
        wh.dispatch_event("ticket.created", {"a": 1})  # attempt 1
        row_id = wh.get_outbox()[0]["id"]
        for _ in range(MAX_ATTEMPTS - 1):
            wh._attempt_delivery(row_id)  # force-attempt past the backoff delay

    entry = wh.get_outbox()[0]
    assert entry["status"] == "failed"
    assert entry["attempts"] == MAX_ATTEMPTS


def test_outbox_endpoint_reports_counts(client, auth_headers):
    res = client.get("/webhooks/outbox", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert "entries" in body and "pending" in body and "failed" in body
