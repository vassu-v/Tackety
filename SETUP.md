# 🚀 Tackety Engine Setup & Integration Guide

Welcome to the Tackety Issue Engine. This guide provides step-by-step instructions on how to self-host the engine, supply your own organizational intelligence (documents), and integrate the Fast-API backend with your own applications.

> For a deep-dive into how the internal semantic clustering, terminology mapping, and routing architecture actually works under the hood, please refer to the [Engine Architecture Documentation (engine/README.md)](engine/README.md).

---

## 1. Prerequisites

Ensure your environment is ready before starting:

1. **Python 3.10+** (3.10 and 3.12 are both verified working; if you have multiple versions installed, prefer 3.10)
2. **Create a virtual environment and install dependencies**:
   ```bash
   python -m venv .venv
   # Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. **Environment file**: copy `engine/.env.example` to `engine/.env` and fill in your values.
   ```env
   AI_API=your_gemini_api_key_here

   # Optional but recommended for anything beyond a quick local demo - see
   # step 3 below for what happens if you skip this.
   TACKETY_API_KEY=some-long-random-string
   ```
   `engine/.env` is gitignored - never commit it with a real key in it.

---

## 2. Providing Your Intelligence (Replacing Docs)

Tackety is powered by your company's internal knowledge. It expects three specific PDF documents to form its "Intelligence Heart":

1. `company_doc.pdf`: General knowledge, FAQs, and product overview. (Feeds the RAG database).
2. `product_doc.pdf`: Technical specifications and API documentation. (Feeds the Terminology Mapper for clustering).
3. `customer_management_doc.pdf`: Strict policies, refund rules, and escalation protocols. (Injected directly into the Chatbot's System Prompt).

### How to process your documents:

1. Place your three PDFs matching the exact filenames above into a directory (e.g., `my_docs/`).
2. Run the `setup_docs.py` script and point it to your directory using the `TACKETY_DOCS_DIR` environment variable.

```powershell
# Windows
$env:TACKETY_DOCS_DIR="C:\path\to\your\my_docs"
python engine/setup_docs.py

# Linux/macOS
TACKETY_DOCS_DIR=/path/to/your/my_docs python engine/setup_docs.py
```

*Note: The script uses robust AI summarization and semantic embedding. It may take a few minutes to complete.*

---

## 3. Running the Engine

The engine is built on **FastAPI**, providing high performance and automatic documentation.

To start the server locally:
```bash
cd engine
python api.py
```
*The engine will now be active at `http://localhost:8000`.*

If you didn't set `TACKETY_API_KEY` in step 1, the server generates a random one on every start and prints it to the console - copy it from there (it changes on every restart, so set it explicitly in `engine/.env` for anything you want to keep using across restarts).

### Running the test suite

```bash
pip install -r requirements-dev.txt
pytest
```
The tests run entirely offline against an in-memory-style temp database - no live server, no real AI provider key needed. `tests/live_smoke.py` is a separate, manual live-server check (see the docstring at the top of that file for how to run it).

---

## 4. Integrating with FastAPI (Endpoints)

Once the engine is running, you can interact with it programmatically. 

> [!TIP]
> You can view the interactive FastAPI schema and test endpoints directly at `http://localhost:8000/docs`.

### Core Flow: The Chat Client

> [!NOTE]
> `/session/start` and `/session/message` are rate-limited per client IP (default 30 requests/minute - each `/session/message` call costs a real LLM request, so this is a cost guard, not just a load guard). Override with `TACKETY_RATE_LIMIT_PER_MINUTE` in `engine/.env`. Exceeding it returns `429`.

**1. Start a Session**
A new user connects to your support widget.
```http
POST /session/start
Content-Type: application/json

{
    "customer_email": "user@example.com"
}
```
*Response*: `{"session_id": "uuid-1234-..."}`

**2. Send a Message**
The user explains their issue. The engine will retrieve context, consult policies, respond to the user, and **automatically route** the issue under the hood.
```http
POST /session/message
Content-Type: application/json

{
    "session_id": "uuid-1234-...",
    "message": "My checkout page is hanging continuously."
}
```

*Response*:
```json
{
    "response": "I'm sorry you're experiencing this. Let me report it right away.",
    "session_status": "RAISE_TICKET",
    "routing": {
        "type": "TECHNICAL",
        "cluster_id": 1,
        "slug": "CHECKOUT_HANG",
        "urgency": "NORMAL"
    }
}
```
*Note: Your frontend can use the `routing` metadata to render detailed ticket cards.*

### Core Flow: Dashboard & Webhooks

> [!IMPORTANT]
> Every endpoint below requires an `X-API-Key` header matching your `TACKETY_API_KEY` (see section 1). The customer-facing `/session/*` endpoints above do not.

**1. Poll the Engine State**
Your agent and admin dashboards can retrieve real-time clustered intelligence:
```http
GET /support/queue
X-API-Key: your-tackety-api-key
```
*Returns arrays of `technical_clusters` and manual `support_cases`.*

**2. Resolve a Cluster or Case**
```http
POST /clusters/{cluster_id}/resolve
POST /support/cases/{case_id}/resolve
X-API-Key: your-tackety-api-key
```
Resolving a cluster fires a `ticket.resolved` webhook to every customer who reported it.

**3. Register Webhooks**
Tackety uses generic, HMAC-SHA256 signed webhooks to push events to your infrastructure. Register an endpoint via the API (not by editing `engine/webhooks.py` directly):
```http
POST /setup/webhook
X-API-Key: your-tackety-api-key
Content-Type: application/json

{
    "event": "ticket.created",
    "url": "https://your-server.example.com/webhooks/tackety",
    "secret": "a-shared-secret-you-choose"
}
```
Registered URLs are validated and rejected if they resolve to a private, loopback, or link-local address (SSRF protection) - only public `http(s)` targets are accepted.
*   Supported Events: `ticket.created`, `ticket.resolved`, `support.ticket_raised`, `handoff.initiated`.

---

## 5. View the Demo UIs

While the engine is running, open `http://localhost:8000/demo/master.html` (or any of the pages below directly - they're all linked from a shared nav bar). Paste your `TACKETY_API_KEY` into the nav bar's key field once; it's remembered per-browser via localStorage.

*   **System Overview**: `demo/master.html` - live counts and an explanation of the routing flow, no fabricated numbers.
*   **Customer Chat**: `demo/index.html` - talks to the chatbot; shows the raw engine response for every message.
*   **Developer Queue**: `demo/queue.html` - ranked technical clusters, with a working Resolve action.
*   **Agent Workspace**: `demo/agent.html` - non-technical tickets and live handovers, with working Resolve actions.
