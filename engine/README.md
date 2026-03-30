# ⚙️ Tackety Core Engine

Welcome to the heart of the **Tackety Issue Engine**. This directory houses the business logic, intelligence layers, and API surface that transform raw customer messages into structured, clustered technical data.

---

## 🏛️ Architecture Overview

The engine follows a decoupled, three-layer "Intelligence Heart" architecture:

1.  **The Intake Layer** (`chatbot.py`): Decides if a query is resolved, needs a technical ticket, or requires a human handover.
2.  **The Processing Layer** (`router.py`, `normalizer.py`, `issue_engine.py`): The "Heart" that maps terminology and clusters technical issues via vector similarity.
3.  **The Surface Layer** (`api.py`): Exposes the clustered intelligence and support queues to the dashboard and external clients.

### Core Components

*   🧠 **`chatbot.py` (Structured Intelligence)**
    *   Dual-mode orchestrator: provides natural chat to the user while maintaining a strictly structured JSON state for the engine.
    *   **Classifies** issues as `TECHNICAL` (engineering) or `NON-TECHNICAL` (support).

*   🫀 **`issue_engine.py` (The Engineering Heart)**
    *   Uses **`sqlite-vec`** for semantic clustering.
    *   Groups technical tickets by similarity, tracks their **Weight** (volume), and auto-escalates **Urgency** (Normal ➜ Urgent ➜ Critical) based on impact.

*   🤝 **`human_queue.py` (The Support Hub)**
    *   Manages manual intervention tasks.
    *   Handles **Non-Technical Tickets** (Billing, Policy) and **Active Handovers** (Live Chat sessions).

*   🗺️ **`normalizer.py` (Terminology Mapping)**
    *   Translates "user-speak" into internal technical slugs using a hybrid RAG model.
    *   Ensures that different descriptions of the same technical bug (e.g., "spinning wheel" vs "hang") map to the same cluster.

*   📄 **`doc_processor.py` (The Knowledge Base)**
    *   Handles document chunking, embedding generation, and vector retrieval.
    *   Performs specialized **Preprocessing** on product manuals to create dense terminology maps.

*   🔌 **`api.py` (The Gateway)**
    *   FastAPI-based REST surface.
    *   Serves both the chat session endpoints and the real-time **Intelligence Dashboard** data.

*   📡 **`webhooks.py` (Event Dispatcher)**
    *   Generic, signed **HMAC-SHA256** notification system.
    *   Fires events for `ticket.created`, `handoff.initiated`, etc., to external developer URLs.

---

## 💾 Data Persistence

Tackety uses three distinct SQLite databases to ensure clear separation of concerns:

1.  **`conversations.db`**: Ephemeral short-term chat history and session states.
2.  **`issues.db`**: Permanent technical records (Clusters, Tickets, and Weights).
3.  **`support.db`**: Permanent non-technical tasks and active human queue cases.

---

## 🚀 Getting Started

### Prerequisites

1.  Python 3.10+
2.  Install core dependencies:
    ```bash
    pip install fastapi uvicorn google-genai python-dotenv sqlite-vec sentence-transformers
    ```

3.  **Setup Intelligence**:
    Initialize your knowledge base and preprocess your terminology maps:
    ```bash
    python setup_docs.py
    ```

### Starting the Server

```bash
cd engine
python api.py
```

*The server will start on `http://localhost:8000`. The dashboard is viewable at `/demo/queue.html`.*

---

## 🔌 Key API Endpoints

Explore the full interactive documentation at `http://localhost:8000/docs`.

#### 1. Interactive Chat
*   `POST /session/message`: Sends a message and returns the AI response + current engine state.

#### 2. Intelligence Dashboard
*   `GET /support/queue`: Returns the unified status of the technical clusters and support cases.

#### 3. Session Management
*   `POST /session/start`: Initializes a new user session.
*   `GET /session/{session_id}/history`: Fetches the chronological history.

---

## 🔮 Next Steps (Roadmap)

1.  **Interactive Resolution**: Allow developers to manually merge or resolve clusters from the dashboard.
2.  **Live Handoff Bridge**: A dedicated agent-side UI to take over active chat sessions.
3.  **Auth Layer**: Token-based security for the Intelligence Dashboard.
