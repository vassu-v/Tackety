import sys
import os

# Add project root to path so engine imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException

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
webhooks = Webhooks()

# 4. Intelligence Hubs
chatbot = Chatbot(sm, doc_processor, company_context=company_context, management_context=management_context)
router = Router(normalizer, support_hub, issue_engine, webhooks, doc_processor)

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

# ── Endpoints ──────────────────────────────────────────────────────────

@app.post("/session/start", response_model=StartSessionResponse)
def start_session(req: StartSessionRequest):
    """Creates a new conversation session."""
    session_id = sm.start_session(customer_email=req.customer_email)
    return StartSessionResponse(session_id=session_id)


@app.post("/session/message", response_model=MessageResponse)
def send_message(req: MessageRequest):
    """
    Sends a message in an existing session.
    Stores the user message, calls AI with full history, stores and returns the response.
    """
    session = sm.get_session(req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delegate message handling, RAG, and state tracking to the Chatbot layer
    chatbot_res = chatbot.handle_message(
        session_id=req.session_id,
        message=req.message,
        customer_email=req.customer_email
    )

    # Route the AI's hidden decision
    routing_result = router.route_decision(req.session_id, chatbot_res)

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


@app.get("/support/queue")
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
