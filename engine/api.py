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
from engine.ai import call_ai

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


    # If email provided mid-conversation, update it
    if req.customer_email:
        sm.update_email(req.session_id, req.customer_email)

    # Store the user's message
    sm.add_message(req.session_id, "user", req.message)

    # Get full conversation history for context
    history = sm.get_history(req.session_id)

    # Build the prompt from history
    conversation_context = "\n".join(
        [f"{m['role'].upper()}: {m['content']}" for m in history]
    )

    system_prompt = (
        "You are a helpful and friendly customer support assistant for a SaaS product. "
        "Keep your responses short, clear, and conversational — no long paragraphs. "
        "Be empathetic and solution-oriented. "
        "If the user describes a technical bug, acknowledge it and let them know you'll raise a ticket. "
        "If the user has a billing or account question, help them directly or offer to connect them with a team member."
    )

    # Call the AI
    ai_response = call_ai(
        prompt=conversation_context,
        system_prompt=system_prompt
    )

    # Store the assistant's response
    sm.add_message(req.session_id, "assistant", ai_response)

    return MessageResponse(
        response=ai_response,
        session_status=session["status"]
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
