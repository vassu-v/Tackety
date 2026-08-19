import sys
import os
import logging
import tempfile
import traceback

# Add project root to path so engine imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header, Request, UploadFile, File
from fastapi.responses import JSONResponse

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional, Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("tackety")

from engine.session_manager import SessionManager
from engine.doc_processor import DocProcessor
from engine.chatbot import Chatbot
from engine.router import Router
from engine.normalizer import Normalizer
from engine.human_queue import SupportHub
from engine.issue_engine import IssueEngine
from engine.webhooks import Webhooks
from engine.auth import verify_api_key, announce_key
from engine.url_safety import is_safe_webhook_url
from engine.rate_limit import rate_limit
from engine.setup_docs import process_company_doc, process_product_doc, process_customer_management_doc
from engine.fileprocess import filetypeprocessor

# ── App Setup ──────────────────────────────────────────────────────────

app = FastAPI(title="Tackety Issue Engine", version="0.1.0")

# CORS — allow the demo frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """
    Without this, an unhandled exception (e.g. a missing AI_API key, a
    downstream AI provider outage) returns a bare 'Internal Server Error'
    plain-text body with nothing logged beyond uvicorn's own traceback
    dump - hard to diagnose in production and impossible for API clients
    to parse. This logs the full traceback server-side and returns a
    structured JSON body without leaking internals to the client.
    """
    logger.error("Unhandled exception on %s %s:\n%s", request.method, request.url.path, traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check the server logs for details."}
    )

# ── Component Initialization ──────────────────────────────────────────
DATA_DIR = os.getenv("TACKETY_DATA_DIR") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1. Base Storage & Retrieval
sm = SessionManager(db_path=os.path.join(DATA_DIR, "conversations.db"))
doc_processor = DocProcessor(db_path=os.path.join(DATA_DIR, "knowledge.db"))

# 2. Hybrid Context Pre-loading (Rules In-Full)
CONTEXT_FILES = {
    "company": ("company_context.txt", "preprocessed company rules"),
    "product": ("product_context.txt", "product terminology map"),
    "management": ("management_rules.txt", "management rules"),
}


def _load_context_file(kind: str) -> str:
    filename, label = CONTEXT_FILES[kind]
    path = os.path.join(DATA_DIR, filename)
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                text = f.read()
                logger.info("Loaded %d chars of %s", len(text), label)
                return text
        logger.warning("No %s found at %s - run setup_docs.py or use the web setup UI.", label, path)
    except Exception as e:
        logger.error("Error loading %s: %s", label, e)
    return ""


company_context = _load_context_file("company")
product_context = _load_context_file("product")
management_context = _load_context_file("management")

# 3. Decision & Handoff Components (Dependency Injection)
normalizer = Normalizer(doc_processor, product_context=product_context)
support_hub = SupportHub(db_path=os.path.join(DATA_DIR, "support.db"))
issue_engine = IssueEngine(db_path=os.path.join(DATA_DIR, "issues.db"), embedding_dim=doc_processor.embedding_dim)
# webhook_configs is permanent developer config, not ephemeral conversation
# data - it lives in issues.db (permanent store), not conversations.db
# (TTL-wiped by design). See engine/webhooks.py for the reasoning.
webhooks = Webhooks(db_path=os.path.join(DATA_DIR, "issues.db"))
webhooks.start_background_retry(interval_seconds=int(os.getenv("TACKETY_WEBHOOK_RETRY_INTERVAL", "30")))

# 4. Intelligence Hubs
chatbot = Chatbot(sm, doc_processor, company_context=company_context, management_context=management_context)
router = Router(normalizer, support_hub, issue_engine, webhooks, doc_processor)


def reload_contexts():
    """
    Re-reads all three preprocessed context files from disk and pushes
    them into the live chatbot/normalizer instances. Called after the
    web-based setup upload (see POST /setup/docs) so newly uploaded docs
    take effect immediately - no server restart needed. chatbot.py and
    normalizer.py read self.company_context/self.product_context/
    self.management_context fresh on every call, so mutating these
    attributes in place is sufficient; no need to reconstruct the objects.
    """
    chatbot.company_context = _load_context_file("company")
    chatbot.management_context = _load_context_file("management")
    normalizer.product_context = _load_context_file("product")


announce_key()

# ── Auth ───────────────────────────────────────────────────────────────

def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Guards developer/agent-facing endpoints. The customer-facing chat
    surface (/session/*) and /health stay open by design - this only
    protects endpoints that read or mutate ticket/queue/webhook data.
    """
    if not verify_api_key(x_api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")

# ── Request/Response Models ────────────────────────────────────────────

class StartSessionRequest(BaseModel):
    customer_email: Optional[str] = None

class StartSessionResponse(BaseModel):
    session_id: str

class MessageRequest(BaseModel):
    session_id: str
    message: str
    customer_email: Optional[str] = None

class MessageResponse(BaseModel):
    response: str
    session_status: str
    routing: Optional[Dict[str, Any]] = None

class WebhookRegistration(BaseModel):
    event: str
    url: str
    secret: str

# ── Endpoints ──────────────────────────────────────────────────────────

@app.post("/session/start", response_model=StartSessionResponse, dependencies=[Depends(rate_limit)])
def start_session(req: StartSessionRequest):
    """Creates a new conversation session."""
    session_id = sm.start_session(customer_email=req.customer_email)
    return StartSessionResponse(session_id=session_id)

@app.post("/setup/webhook", dependencies=[Depends(require_api_key)])
def register_webhook(req: WebhookRegistration):
    """Registers a webhook URL for a specific event."""
    safe, reason = is_safe_webhook_url(req.url)
    if not safe:
        raise HTTPException(status_code=400, detail=f"Refusing to register webhook URL: {reason}")
    webhooks.register(req.event, req.url, req.secret)
    return {"status": "success", "event": req.event}

MAX_SETUP_UPLOAD_BYTES = 20 * 1024 * 1024  # 20MB - generous for a text/policy PDF, not for arbitrary files
ALLOWED_SETUP_EXTENSIONS = {".pdf", ".md", ".txt"}

_SETUP_DOC_HANDLERS = {
    "company_doc": ("company", process_company_doc),
    "product_doc": ("product", process_product_doc),
    "customer_management_doc": ("management", process_customer_management_doc),
}


def _process_uploaded_doc(field_name: str, upload: UploadFile) -> Dict[str, Any]:
    """Extracts text from one uploaded file and runs it through the
    matching preprocessing pipeline. Returns a per-file result dict
    rather than raising, so one bad file doesn't abort the others in
    the same request."""
    kind, handler = _SETUP_DOC_HANDLERS[field_name]
    ext = os.path.splitext(upload.filename or "")[1].lower()
    if ext not in ALLOWED_SETUP_EXTENSIONS:
        return {"field": field_name, "status": "error", "detail": f"Unsupported file type '{ext}' - use .pdf, .md, or .txt"}

    contents = upload.file.read()
    if len(contents) > MAX_SETUP_UPLOAD_BYTES:
        return {"field": field_name, "status": "error", "detail": f"File too large (max {MAX_SETUP_UPLOAD_BYTES // (1024*1024)}MB)"}
    if not contents:
        return {"field": field_name, "status": "error", "detail": "File is empty"}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(contents)
            tmp_path = tmp.name

        text = filetypeprocessor(tmp_path)
        if not text or not text.strip():
            return {"field": field_name, "status": "error", "detail": "Could not extract any text from this file"}

        handler(doc_processor, text, DATA_DIR)
        return {"field": field_name, "status": "success", "chars_extracted": len(text)}
    except Exception as e:
        logger.exception("Setup doc processing failed for %s", field_name)
        return {"field": field_name, "status": "error", "detail": str(e)}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/setup/docs", dependencies=[Depends(require_api_key)])
def upload_setup_docs(
    company_doc: Optional[UploadFile] = File(None),
    product_doc: Optional[UploadFile] = File(None),
    customer_management_doc: Optional[UploadFile] = File(None),
):
    """
    Web-based equivalent of running `python engine/setup_docs.py` -
    upload your company/product/customer-management docs (.pdf, .md, or
    .txt) and they're preprocessed the same way the CLI script does.
    Context updates take effect immediately (see reload_contexts()) -
    no server restart required. Each doc is independent; you can upload
    just one at a time.

    This calls the real AI provider (call_ai) to summarize/preprocess
    each doc, so it's only as fast as that round-trip, and it fails per-
    file rather than for the whole request if AI_API isn't configured
    or a provider call fails.
    """
    uploads = {
        "company_doc": company_doc,
        "product_doc": product_doc,
        "customer_management_doc": customer_management_doc,
    }
    provided = {k: v for k, v in uploads.items() if v is not None}
    if not provided:
        raise HTTPException(status_code=400, detail="Provide at least one of company_doc, product_doc, customer_management_doc")

    results = [_process_uploaded_doc(field, upload) for field, upload in provided.items()]
    reload_contexts()

    any_success = any(r["status"] == "success" for r in results)
    return {
        "status": "success" if any_success else "error",
        "results": results,
    }


@app.get("/setup/docs/status", dependencies=[Depends(require_api_key)])
def get_setup_docs_status():
    """Reports which knowledge-base context files currently exist, so
    the setup UI can show 'configured' vs 'not configured' per doc
    without guessing from chat behavior."""
    status = {}
    for kind, (filename, label) in CONTEXT_FILES.items():
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            stat = os.stat(path)
            status[kind] = {
                "configured": True,
                "label": label,
                "size_bytes": stat.st_size,
                "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            }
        else:
            status[kind] = {"configured": False, "label": label}
    return status

@app.post("/clusters/{cluster_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve_cluster(cluster_id: int):
    """Marks a cluster as resolved and notifies all affected customers."""
    # 1. Resolve in issue_engine and get metadata
    result = issue_engine.resolve_cluster(cluster_id)
    if result is None:
        raise HTTPException(status_code=404, detail="No open cluster with that id")

    # 2. Trigger webhook for each customer
    for email in result["emails"]:
        webhooks.dispatch_event("ticket.resolved", {
            "cluster_id": cluster_id,
            "cluster_summary": result["summary"],
            "customer_email": email,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        })

    # "queued" not "sent": dispatch_event() is now durable-but-async (see
    # engine/webhooks.py) - this is the count of customers whose
    # notification was persisted for delivery, not a confirmation that
    # the webhook receiver actually got it. Check GET /webhooks/outbox
    # for real delivery status.
    return {"status": "success", "resolved_id": cluster_id, "notifications_queued": len(result["emails"])}

@app.post("/session/message", response_model=MessageResponse, dependencies=[Depends(rate_limit)])
def send_message(req: MessageRequest, idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key")):
    """
    Sends a message in an existing session.
    Stores the user message, calls AI with full history, stores and returns the response.

    Pass an Idempotency-Key header to make retries safe: if this message
    results in a ticket/case being raised, replaying the same key will not
    create a second ticket or fire a second webhook. Without it, a client
    retry after a network timeout can double-create.
    """
    session = sm.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=409, detail=f"Session is {session['status']}, not active")

    # Delegate message handling, RAG, and state tracking to the Chatbot layer
    chatbot_res = chatbot.handle_message(
        session_id=req.session_id,
        message=req.message,
        customer_email=req.customer_email
    )

    # Route the AI's hidden decision
    routing_result = router.route_decision(req.session_id, chatbot_res, client_request_id=idempotency_key)

    return MessageResponse(
        response=chatbot_res["response"],
        session_status=chatbot_res["state"],
        routing=routing_result
    )

@app.get("/session/{session_id}/history")
def get_session_history(session_id: str):
    """Returns the full message history for a session."""
    session = sm.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history = sm.get_history(session_id)
    return {"messages": history}


@app.get("/support/queue", dependencies=[Depends(require_api_key)])
def get_support_queue():
    """
    Returns the unified support and intelligence status.
    Technicals are grouped by the IssueEngine (clusters).
    Non-technicals and handovers are listed by the SupportHub.
    """
    return {
        "technical_clusters": issue_engine.get_ranked_clusters(),
        "support_cases": support_hub.get_open_cases()
    }

@app.post("/support/cases/{case_id}/resolve", dependencies=[Depends(require_api_key)])
def resolve_support_case(case_id: int):
    """Marks a non-technical ticket or handover case as resolved."""
    found = support_hub.resolve_case(case_id)
    if not found:
        raise HTTPException(status_code=404, detail="No open case with that id")
    return {"status": "success", "resolved_id": case_id}

@app.get("/webhooks/outbox", dependencies=[Depends(require_api_key)])
def get_webhook_outbox(limit: int = 100):
    """
    Visibility into webhook delivery: every dispatch is durable (see
    engine/webhooks.py) - this shows what's pending retry, delivered, or
    given up on after repeated failures, instead of that information only
    ever existing in server logs.
    """
    entries = webhooks.get_outbox(limit=limit)
    return {
        "entries": entries,
        "pending": len([e for e in entries if e["status"] == "pending"]),
        "failed": len([e for e in entries if e["status"] == "failed"]),
    }



@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# ── Static Demo Routes ───────────────────────────────────────────────

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "demo")
if os.path.exists(DEMO_DIR):
    app.mount("/demo", StaticFiles(directory=DEMO_DIR), name="demo")
    print(f"Mounted demo dashboard at http://localhost:8000/demo/queue.html")
else:
    print(f"WARNING: Demo directory not found at {DEMO_DIR}")


# ── Run Server ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  Tackety Issue Engine API")
    print("  http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
