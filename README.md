<div align="center">
  <img src="tackety.png" alt="Tackety" width="180"/>
  <h1>Tackety</h1>
  <p><strong>The Developer-First Issue Clustering & Support Engine</strong></p>

  [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
  [![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
  [![SQLite](https://img.shields.io/badge/SQLite-portable-003B57?logo=sqlite&logoColor=white)](https://sqlite.org/)
  [![Status](https://img.shields.io/badge/status-active%20development-orange)]()
  [![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)](CONTRIBUTING.md)

</div>

---

**Tackety** is an open-source, self-hostable support engine that sits between your customers and your developers. It clusters semantically similar issues, translates customer language into internal product terminology, and tells your team what to fix first — ranked by real impact, not arrival time. No Zendesk. No vendor lock-in. One portable SQLite file.

---

## 🌟 The Problem

Most support systems operate blindly. A minor cosmetic glitch reported on Monday gets fixed before a critical checkout crash reported on Tuesday — simply because it arrived earlier. The developer isn't lazy. The system provides zero signal about what actually matters.

**Tackety solves this by:**
1. Running a customer-facing AI chatbot that classifies issues on the fly — technical bug or customer service request.
2. Translating raw customer language into internal product terminology using your own docs.
3. Clustering similar issues semantically and escalating urgency based on real volume.

---

## ⚡ Current State

The core engine is **working and runnable today.**

| Component | Status |
|-----------|--------|
| Session management (lazy TTL cleanup) | ✅ Done |
| Stateless AI integration (`call_ai.py`) | ✅ Done |
| Conversation history reconstruction | ✅ Done |
| FastAPI backend + session endpoints | ✅ Done |
| Terminal-style demo UI with engine stream | ✅ Done |
| Chatbot with RAG + state classification | ✅ Done |
| Normalizer (customer → product terminology) | 🔲 In development |
| Human agent queue (least-loaded allocation) | 🔲 In development |
| Webhook system (HMAC-signed events) | 🔲 In development |
| Issue clustering integration | 🔲 In development |
| Developer dashboard endpoints | 🔲 In development |

> You can run the demo today. The remaining components are actively being built. Read [`DESIGN.md`](./DESIGN.md) to understand the full architecture and roadmap.

---

## 🚀 Core Features

- **Automated Issue Routing** — Converses with users and classifies complaints as *customer service* (refunds, billing) or *technical issues* (bugs, crashes) in real time.
- **Intelligent Normalization** — Translates varied customer descriptions ("cart is broken", "cannot add items") into standardized developer terminology ("Checkout Module") using vector embeddings of your product docs.
- **Semantic Clustering** — Groups identical issues using lightweight vector embeddings via `sqlite-vec`. Weight accumulates on the right cluster. Urgency escalates automatically.
- **Stateless AI Architecture** — The LLM has no memory between calls. Conversation history is reconstructed from portable SQLite databases on every turn. No bloat, no lock-in.
- **Swappable AI Backend** — Change your AI provider by editing exactly one file (`call_ai.py`). Run locally via Ollama or use any cloud provider. Nothing else in the codebase changes.
- **Webhook Integration** — Tackety fires HMAC-signed webhooks on ticket creation, human handoff, and resolution. Connect your own Slack, email SDK, or PagerDuty stack. No vendor bundled.

---

## 🏗️ Architecture

Tackety is built around strict separation of concerns. Each component has exactly one job.

```
Customer opens chat
        │
        ▼
[conversations.db] ── session created
        │
        ▼
chatbot.py ── RAG context + conversation loop
  ├─ RESOLVED       → session closes
  ├─ ESCALATE_HUMAN → human_queue → support.db → webhook: handoff.initiated
  └─ RAISE_TICKET   → normalizer → issue_engine → issues.db → webhook: ticket.created
```

- **[`/engine`](./engine)** — Core backend. FastAPI, swappable AI caller, session management, vector search.
- **[`/demo`](./demo)** — Terminal-style chat UI with live engine stream panel.
- **[`DESIGN.md`](./DESIGN.md)** — Complete architectural blueprint. Every decision documented with reasoning and what was rejected.

---

## 🖥️ Demo

After starting the server, open `demo/index.html` to see:
- Terminal-style chat interface
- Live engine stream logging on the left panel showing classifier state in real time
- Ticket dispatch cards rendered inline when issues are routed

---

## 🛠️ Quick Start

### 1. Prerequisites

- Python 3.10+

### 2. Install dependencies

```bash
cd engine
pip install fastapi uvicorn google-genai python-dotenv sentence-transformers sqlite-vec
```

### 3. Environment variables

Create a `.env` file in the `engine/` directory:

```env
AI_API=your_api_key_here
```

### 4. Run the server

```bash
python api.py
```

Server starts at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### 5. Open the demo

Open `demo/index.html` in your browser while the server is running.

---

## 🔌 Key Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/session/start` | Create a new conversation session |
| `POST` | `/session/message` | Send a message, get AI response |
| `GET` | `/session/{id}/history` | Retrieve full message history |
| `GET` | `/health` | Health check |

Full endpoint documentation in [`engine/README.md`](./engine/README.md).

---

## 🧠 Design Philosophy

Tackety is built on a few non-negotiable principles:

- **Stateless AI, stateful database** — The LLM reconstructs context from SQLite on every turn. No session stickiness, no memory leaks.
- **Three separate databases** — `conversations.db` (ephemeral), `issues.db` (permanent developer records), `support.db` (agent-facing). Different owners, different lifetimes, no coupling.
- **One swappable AI file** — `call_ai.py` is the only place an external AI API is ever called. Swap providers by editing one function.
- **Webhooks, not bundled email** — Tackety fires signed POST events. You connect your own notification stack. No vendor lock-in by design.

Read [`DESIGN.md`](./DESIGN.md) for the full reasoning behind every architectural decision.

---

## 🤝 Contributing

Contributions are welcome. Before opening a PR, read [`CONTRIBUTING.md`](./CONTRIBUTING.md) — many decisions in this codebase are intentional, not oversights.

Key things to preserve:
- Decoupled components (AI, router, databases are strictly separated)
- Stateless AI architecture
- SQLite-first approach
- No bundled third-party notification providers

---

## 📜 License

AGPL v3 — see [LICENSE](./LICENSE) for details.

