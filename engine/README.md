# ⚙️ Tackety Core Engine

Welcome to the heart of the **Tackety Issue Engine**. This directory houses the business logic, intelligence layers, and API surface that transform raw customer messages into structured, clustered technical data.

> ⚠️ **Looking for Installation or Integration Instructions?** 
> Please see the [Quick-Start SETUP Guide (../SETUP.md)](../SETUP.md) located at the root of the repository. This document (engine/README.md) focuses exclusively on the internal architectural design and data flow.

---

## 🏛️ Architecture Overview (Phase 3.7 Release)

The engine follows a decoupled, three-layer "Intelligence Heart" architecture heavily reinforced with context injection and dynamic rendering capabilities:

1.  **The Intake Layer** (`chatbot.py`): The direct customer interface. Instructed by dense **Company Policies** and **Retrieved Knowledge Base**, it decides if a query is resolved, needs a technical ticket, or requires a human handover.
2.  **The Processing Layer** (`router.py`, `normalizer.py`, `issue_engine.py`): The "Heart" that maps terminology (using both internal product maps and dynamically generating novel slugs) and clusters technical issues via semantic vector similarity.
3.  **The Surface Layer** (`api.py`): Exposes the clustered intelligence (`/support/queue`) and loops routing metadata directly back into chat clients.

### Core Components

*   🧠 **`chatbot.py` (Structured Intelligence)**
    *   Dual-mode orchestrator: provides natural chat using `gemini-2.5-flash` while maintaining a strictly structured JSON state for the engine.
    *   **Strict Protocol Injection**: Customer management rules are summarized by an LLM during setup and permanently injected into the Chatbot's System Prompt on every turn. This ensures maximum policy compliance (Refunds, Escalations) without relying heavily on variable RAG results.

*   🫀 **`issue_engine.py` (The Engineering Heart)**
    *   Uses **`sqlite-vec`** for semantic clustering.
    *   Groups technical tickets by similarity, tracks their **Weight** (volume), and auto-escalates **Urgency** (Normal ➜ Urgent ➜ Critical) based on impact.

*   🤝 **`human_queue.py` (The Support Hub)**
    *   Manages manual intervention tasks.
    *   Handles **Non-Technical Tickets** (Billing, Policy) and **Active Handovers** (Live Chat sessions) completely decoupled from Engineering noise.

*   🗺️ **`normalizer.py` (Terminology Mapping)**
    *   Translates "user-speak" into internal technical slugs.
    *   **Dynamic Slugs**: Prioritizes matching against established `PRODUCT_MAP` terminology. If identical, groups it together. If unprecedented, the AI securely invents a descriptive mapping (e.g., `UNEXPECTED_COLOR_SHIFT`) so it can still enter the clustering flow.

*   📄 **`doc_processor.py` & `fileprocess.py` (The Knowledge Base)**
    *   Handles chunking, embedding generation using `sentence-transformers`, and dynamic preprocessing.
    *   Supported file formats: **`.txt`, `.md`, and `.pdf`** (via `pypdf`).
    *   Specializes raw documents into RAG databases, technical terminology mappings, and dense Chatbot prompt policies.

*   🔌 **`api.py` (The Gateway)**
    *   FastAPI-based REST surface. Parses responses from the Router and loops `routing` schemas directly back to clients for dynamic UI renders.

*   📡 **`webhooks.py` (Event Dispatcher)**
    *   Generic, signed **HMAC-SHA256** notification system.

---

## 💾 Data Persistence

Tackety uses three distinct SQLite databases to ensure clear separation of concerns (all generated within `engine/data/`):

1.  **`conversations.db`**: Ephemeral short-term chat history and session states.
2.  **`issues.db`**: Permanent technical records (Clusters, Tickets, and Weights).
3.  **`support.db`**: Permanent non-technical tasks and active human queue cases.
4.  **`knowledge.db`**: RAG embeddings and references. (Backed by `sqlite-vec`).

_Note: The `engine/data` folder is specifically ignored in `.gitignore` to protect sensitive ticket state._

---

## 🚀 Getting Started (Self-Hosted)

*For detailed, step-by-step instructions on injecting your own documents and exploring the API, please refer to the [SETUP.md](../SETUP.md) guide.*

### Quick Start
```bash
python engine/setup_docs.py
cd engine
python api.py
```

*The core application will start on `http://localhost:8000`.*

---

## 🖥️ Surfaces & Interfaces

Tackety provides three primary visual contexts located in the `/demo` namespace for interaction:

1.  **`/demo/index.html`**: The highly dynamic Customer Chat surface. Supports routing metadata loopback to show exactly how Tackety parsed an issue.
2.  **`/demo/agent.html`**: The Support Worker workspace. Real-time access to non-technical escalations and Live Chat Handoffs. 
3.  **`/demo/master.html`**: The Administrative Command Center. Live system flow tracking, cluster aggregation, and telemetry.

---

## 🔮 Next Steps (Roadmap)

1.  **Interactive Resolution**: Allow developers to manually merge or resolve clusters from the Master Command Center.
2.  **Live Handoff Bridge**: Allow Agents to seamlessly assume control of active Chat Sessions from the Agent UI without dropping the user socket.
3.  **Auth Layer**: Implement token-based security for the Intelligence Dashboard endpoints.
