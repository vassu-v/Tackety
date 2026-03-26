# Contributing to Tackety

First off, thank you for considering contributing to Tackety! It's people like you that make Tackety such a great open-source tool for developers.

Tackety is fundamentally a developer-first infrastructure tool. Our goal is to keep it lightweight, transparent, and resilient. Before writing any code, we highly recommend reading our architectural blueprint in [`DESIGN.md`](./DESIGN.md) to understand the "why" behind the system.

## 🏛️ Core Architectural Principles

Please keep these principles in mind when proposing changes:

1. **Decoupled by Default:** The AI engine, the normalizer, and the database router are strictly separated. Do not couple them back together. 
2. **Stateless AI:** The core engine must remain stateless. We reconstruct context from the `conversations.db` database on every turn. Do not introduce in-memory state or session stickiness that relies on a specific worker.
3. **Vendor Agnosticism:** Tackety does **not** ship with built-in email providers like SendGrid or Mailgun. We fire Webhooks. The developer handles the rest. Do not submit PRs adding direct integrations to specific third-party services (except for the swappable AI `call_ai.py` integrations).
4. **SQLite-First:** Tackety uses portable SQLite (`conversations.db`, `issues.db`, `support.db`) and `sqlite-vec` for embeddings. We are not migrating to Postgres or external vector databases like Pinecone at this stage. 

## 🛠️ Development Setup

To run Tackety locally and start contributing:

1. **Clone the repository:**
   ```bash
   git clone https://github.com/vassu-v/Tackety.git
   cd Tackety
   ```

2. **Set up a virtual environment (Recommended):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   cd engine
   pip install fastapi uvicorn google-genai python-dotenv
   ```
   *(Note: Ensure you have `sqlite-vec` dependencies installed if you are modifying clustering functionality).*

4. **Environment Variables:**
   Create a `.env` in the `engine/` folder:
   ```env
   AI_API=your_llm_api_key
   ```

5. **Run the API server:**
   ```bash
   python api.py
   ```

## 📝 Submitting Changes

### Step 1: Discuss major changes
If you are planning a significant architectural change or adding a heavy new dependency, **please open an Issue first** to discuss it. We want to avoid you spending hours on a PR that doesn't align with the roadmap.

### Step 2: Branching Strategy
- Branch off from the `main` branch.
- Use descriptive branch names: `feature/add-vllm-support`, `fix/normalization-threshold-bug`, `docs/update-readme`.

### Step 3: Writing Code
- Keep your changes as focused as possible.
- Ensure your code follows standard Python formatting guidelines (PEP 8). We recommend using `black` or `ruff`.
- If you modify `api.py` or the AI calls, test the `demo/index.html` interface to ensure you haven't broken the client-side payloads.

### Step 4: Submitting your Pull Request (PR)
- Push your branch to your fork.
- Open a PR against the `main` branch of Tackety.
- In your PR description, explain:
  - **What** this PR changes.
  - **Why** the change is necessary.
  - **How** to test it locally.

## 🚫 What We Won't Merge

To save you time, here are a few things that generally will be rejected:
- **Adding heavy external databases:** E.g., Redis, PostgreSQL, or managed Vector DBs.
- **Vendor Lock-in tools:** E.g., bundling a specific SMTP sender or Jira directly. Use Webhooks.
- **Consumer-App UI Changes:** The `demo/` UI is intentionally styled to look like a terminal/developer console. Please do not submit PRs changing it back to a bubbly consumer chat app.

Thank you for helping us build better infrastructure!
