<div align="center">
  <img src="tackety.png" alt="Tackety" width="200"/>
  <h1>Tackety</h1>
  <p><strong>The Developer-First Issue Clustering & Support Engine</strong></p>

  [![License: AGPL v3](https://img.shields.io/badge/License-AGPL_v3-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
  [![Python version](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
  [![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi)](https://fastapi.tiangolo.com/)
</div>

---

**Tackety** is an open-source, self-hostable complaint management and issue clustering system designed for developers at small-to-mid-sized SaaS teams. 

It acts as an intelligent bridge between customer support and developer workflows by transforming raw user feedback into prioritized, semantically grouped technical tickets. Instead of support tickets piling up in a strict First-In, First-Out (FIFO) queue, Tackety analyzes the impact, extracts the technical context, and tells you what to fix first.

## 🌟 Why Tackety?

Most support systems operate blindly. A minor cosmetic glitch reported on Monday gets fixed before a critical checkout crash reported on Tuesday simply because it arrived earlier. The developer isn't lazy; the system just provides zero signal about priority.

**Tackety solves this by:**
1. Automatically translating customer terminology into internal product modules via your own documentation.
2. Clustering similar issues using vector similarity search.
3. Escalating urgency based on actual support volume and impact.

## 🚀 Core Features

- **Automated Issue Routing:** The engine acts as the first line of defense. It converses with users and classifies incoming complaints as either *customer service* (refunds, billing) or *technical issues* (bugs, crashes) on the fly.
- **Intelligent Normalization:** Translates wildly varied customer descriptions (e.g., "cart is broken", "cannot add items") into standardized developer terminology (e.g., "Checkout Module") using vector embeddings of your product docs.
- **Semantic Clustering:** Groups identical issues using lightweight vector text embeddings (`sqlite-vec`), extracting real signal from infinite noise. Weight accumulates on the right cluster.
- **Stateless AI Architecture:** No massive, bloated databases. The LLM has no memory between calls. The conversation history is completely reconstructed from highly portable, decoupled SQLite databases.
- **Swappable AI Backend:** BYO Model. Pre-configured for speed and intelligence via modern SDKs, but requires changing only one file (`call_ai.py`) to run entirely locally via Ollama or vLLM.
- **Webhook Integration (BYO Notification Stack):** Tackety fires secure webhooks on ticket creation, human handoff, and resolution. Connect it to your existing Slack, Email SDK, or PagerDuty stack. No vendor lock-in.

## 🏗️ Project Architecture

Tackety is modularized to ensure strict separation of concerns:

- **[`/engine`](./engine)** — The Core Backend. Contains the FastAPI logic, the swappable AI brain, vector search functions, and the state-management databases (`conversations.db`, `issues.db`, `support.db`).
- **[`/demo`](./demo)** — The Client Interface. A sleek, terminal-inspired frontend interface demonstrating the client-side interaction with the Tackety engine. It visualizes the internal JSON logs, routing states, and ticket dispatches in real-time.
- **[`DESIGN.md`](./DESIGN.md)** — The complete architectural blueprint. If you want to know *why* we chose three separate SQLite databases instead of one, or why the Normalizer uses a specific similarity threshold, read this.

## 🛠️ Quick Start Guide

Tackety is designed to be configured and run rapidly with minimal overhead. 

### 1. Prerequisites
- Python 3.10+
- The required AI python SDK and `fastapi` stack.

### 2. Setup the Engine
Navigate to the engine directory and install requirements:
```bash
cd engine
pip install fastapi uvicorn google-genai python-dotenv
```

### 3. Environment Variables
Create a `.env` file in the `engine/` directory to authenticate your AI model:
```env
AI_API=your_api_key_here
```

### 4. Run the Server
Tackety's API ships with a baked-in runner. Start the FastAPI server on port 8000:
```bash
python api.py
```

*For more expansive endpoints, database specifics, and session tracking details, refer to the **[Engine Documentation](./engine/README.md)**.*

## 🤝 Contributing

As a self-hostable, developer-first tool, community contributions to Tackety are highly welcomed. 
- Please thoroughly read [`DESIGN.md`](./DESIGN.md) before proposing architecture changes, as many decisions (like the omission of a built-in email provider) are intentional features, not bugs.
- Ensure your changes do not violate the decoupled nature of the engine, AI caller, and router.

## 📜 License

This project is open-source and licensed under the AGPL v3 License - see the [LICENSE](LICENSE) file for details.
