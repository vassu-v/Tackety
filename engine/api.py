import sys
import os

# Add project root to path so engine imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, HTTPException

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

from engine.session_manager import SessionManager
from engine.doc_processor import DocProcessor
from engine.chatbot import Chatbot
from engine.router import Router

# ── App Setup ──────────────────────────────────────────────────────────

app = FastAPI(title="Tackety Issue Engine", version="0.1.0")

# CORS — allow the demo frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database lives inside the engine/data/ directory for standalone operation
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)

sm = SessionManager(db_path=os.path.join(DATA_DIR, "conversations.db"))
doc_processor = DocProcessor(db_path=os.path.join(DATA_DIR, "knowledge.db"))
chatbot = Chatbot(sm, doc_processor)
router = Router()

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
    router.route_decision(req.session_id, chatbot_res)

    return MessageResponse(
        response=chatbot_res["response"],
        session_status=chatbot_res["state"]
    )


@app.get("/session/{session_id}/history")
def get_session_history(session_id: str):
    """Returns the full message history for a session."""
    session = sm.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    history = sm.get_history(session_id)
    return {"messages": history}



@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok", "version": "0.1.0"}


# ── Run Server ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    print("\n  Tackety Issue Engine API")
    print("  http://localhost:8000\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)
