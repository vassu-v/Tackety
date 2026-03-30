# 🚀 Tackety Engine Setup & Integration Guide

Welcome to the Tackety Issue Engine. This guide provides step-by-step instructions on how to self-host the engine, supply your own organizational intelligence (documents), and integrate the Fast-API backend with your own applications.

> For a deep-dive into how the internal semantic clustering, terminology mapping, and routing architecture actually works under the hood, please refer to the [Engine Architecture Documentation (engine/README.md)](engine/README.md).

---

## 1. Prerequisites

Ensure your environment is ready before starting:

1. **Python 3.10+**
2. **Install Core Dependencies**:
   ```bash
   pip install fastapi uvicorn google-genai python-dotenv sqlite-vec sentence-transformers pypdf
   ```
3. **API Keys**: Create an `.env` file in the `engine/` directory and add your LLM API key.
   ```env
   AI_API=your_gemini_api_key_here
   ```

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

---

## 4. Integrating with FastAPI (Endpoints)

Once the engine is running, you can interact with it programmatically. 

> [!TIP]
> You can view the interactive FastAPI schema and test endpoints directly at `http://localhost:8000/docs`.

### Core Flow: The Chat Client

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

**1. Poll the Engine State**
Your agent and admin dashboards can retrieve real-time clustered intelligence:
```http
GET /support/queue
```
*Returns arrays of `technical_clusters` and manual `support_cases`.*

**2. Listen to Webhooks**
Tackety uses generic, HMAC-SHA256 signed webhooks to push events to your infrastructure.
*   Configure the endpoints in `engine/webhooks.py`.
*   Supported Events: `ticket.created`, `support.ticket_raised`, `handoff.initiated`.

---

## 5. View the Demo UIs

To see the engine in action, open the following files in your browser (while the engine is running):

*   **Customer Chat**: `demo/index.html`
*   **Agent Workspace**: `demo/agent.html`
*   **Master Console**: `demo/master.html`
