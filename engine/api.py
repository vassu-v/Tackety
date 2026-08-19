import sys
import os

# Add project root to path so engine imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Header

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

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

# ── App Setup ──────────────────────────────────────────────────────────

app = FastAPI(title="Tackety Issue Engine", version="0.1.0")

# CORS — allow the demo frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Component Initialization ──────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1. Base Storage & Retrieval
sm = SessionManager(db_path=os.path.join(DATA_DIR, "conversations.db"))
doc_processor = DocProcessor(db_path=os.path.join(DATA_DIR, "knowledge.db"))

# 2. Hybrid Context Pre-loading (Rules In-Full)
company_context = ""
context_path = os.path.join(DATA_DIR, "company_context.txt")
try:
    if os.path.exists(context_path):
        with open(context_path, "r", encoding="utf-8") as f:
            company_context = f.read()
            print(f"Loaded {len(company_context)} chars of preprocessed company rules.")
    else:
        print("WARNING: No preprocessed company context found. Run setup_docs.py first.")
except Exception as e:
    print(f"Error loading company context: {e}")

product_context = ""
product_context_path = os.path.join(DATA_DIR, "product_context.txt")
try:
    if os.path.exists(product_context_path):
        with open(product_context_path, "r", encoding="utf-8") as f:
            product_context = f.read()
            print(f"Loaded {len(product_context)} chars of product terminology map.")
    else:
        print("WARNING: No product terminology map found. Run setup_docs.py first.")
except Exception as e:
    print(f"Error loading product context: {e}")

management_context = ""
management_context_path = os.path.join(DATA_DIR, "management_rules.txt")
try:
    if os.path.exists(management_context_path):
        with open(management_context_path, "r", encoding="utf-8") as f:
            management_context = f.read()
            print(f"Loaded {len(management_context)} chars of management rules.")
    else:
        print("WARNING: No management rules found. Run setup_docs.py first.")
except Exception as e:
    print(f"Error loading management context: {e}")

# 3. Decision & Handoff Components (Dependency Injection)
normalizer = Normalizer(doc_processor, product_context=product_context)
support_hub = SupportHub(db_path=os.path.join(DATA_DIR, "support.db"))
issue_engine = IssueEngine(db_path=os.path.join(DATA_DIR, "issues.db"), embedding_dim=doc_processor.embedding_dim)
# webhook_configs is permanent developer config, not ephemeral conversation
# data - it lives in issues.db (permanent store), not conversations.db
# (TTL-wiped by design). See engine/webhooks.py for the reasoning.
webhooks = Webhooks(db_path=os.path.join(DATA_DIR, "issues.db"))

# 4. Intelligence Hubs
chatbot = Chatbot(sm, doc_processor, company_context=company_context, management_context=management_context)
router = Router(normalizer, support_hub, issue_engine, webhooks, doc_processor)

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

@app.post("/session/start", response_model=StartSessionResponse)
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

    return {"status": "success", "resolved_id": cluster_id, "notifications_sent": len(result["emails"])}

@app.post("/session/message", response_model=MessageResponse)
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
