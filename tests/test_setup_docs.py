"""
Covers POST /setup/docs (web-based knowledge-base setup, no CLI needed)
and the company-doc pipeline bug fix in engine/setup_docs.py.

engine.doc_processor.call_ai is mocked here specifically - it's a
different import site than engine.chatbot.call_ai / engine.normalizer.call_ai
(each module does `from engine.ai import call_ai`, binding its own name),
so the conftest mock_ai_response fixture, which only patches the chat/
normalizer sites, doesn't cover this path.
"""
import io


def test_upload_requires_at_least_one_file(client, auth_headers):
    res = client.post("/setup/docs", headers=auth_headers, files={})
    assert res.status_code == 400


def test_upload_rejects_unsupported_extension(client, auth_headers, monkeypatch):
    monkeypatch.setattr("engine.doc_processor.call_ai", lambda **kw: "processed")
    res = client.post(
        "/setup/docs", headers=auth_headers,
        files={"company_doc": ("notes.exe", io.BytesIO(b"binary junk"), "application/octet-stream")}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "error"
    assert body["results"][0]["status"] == "error"
    assert "Unsupported file type" in body["results"][0]["detail"]


def test_upload_company_doc_generates_context_and_reloads_live(client, auth_headers, app, monkeypatch):
    monkeypatch.setattr("engine.doc_processor.call_ai", lambda **kw: "Preprocessed company context for prompt injection.")

    text = "# Company\nTackety is a support engine.\n## Policies\nRefunds within 30 days."
    res = client.post(
        "/setup/docs", headers=auth_headers,
        files={"company_doc": ("company_doc.md", io.BytesIO(text.encode()), "text/markdown")}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "success"
    assert body["results"][0]["status"] == "success"
    assert body["results"][0]["chars_extracted"] > 0

    # The bug this fixes: company_context.txt must actually exist after
    # this call, and the live chatbot instance must reflect it without a
    # restart - reload_contexts() is called at the end of the endpoint.
    assert app.chatbot.company_context == "Preprocessed company context for prompt injection."


def test_upload_product_doc_populates_rag_and_context(client, auth_headers, app, monkeypatch):
    monkeypatch.setattr("engine.doc_processor.call_ai", lambda **kw: "PRODUCT_SLUG_MAP: CHECKOUT_V2")

    text = "# Checkout Module\nHandles payment processing and cart state."
    res = client.post(
        "/setup/docs", headers=auth_headers,
        files={"product_doc": ("product_doc.md", io.BytesIO(text.encode()), "text/markdown")}
    )
    assert res.status_code == 200
    assert res.json()["results"][0]["status"] == "success"
    assert app.normalizer.product_context == "PRODUCT_SLUG_MAP: CHECKOUT_V2"

    # Also RAG-ingested - retrieve_context(doc_type="product") should find it.
    results = app.doc_processor.retrieve_context("checkout payment", doc_type="product", limit=1)
    assert len(results) >= 1


def test_upload_empty_file_reports_error_without_500(client, auth_headers):
    res = client.post(
        "/setup/docs", headers=auth_headers,
        files={"company_doc": ("company_doc.txt", io.BytesIO(b""), "text/plain")}
    )
    assert res.status_code == 200
    assert res.json()["results"][0]["status"] == "error"


def test_status_endpoint_reports_configured_state(client, auth_headers, app, monkeypatch):
    monkeypatch.setattr("engine.doc_processor.call_ai", lambda **kw: "some context")
    client.post(
        "/setup/docs", headers=auth_headers,
        files={"customer_management_doc": ("mgmt.txt", io.BytesIO(b"Refund policy: 30 days."), "text/plain")}
    )

    res = client.get("/setup/docs/status", headers=auth_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["management"]["configured"] is True
    assert body["management"]["size_bytes"] > 0
