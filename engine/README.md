# ⚙️ Tackety Core Engine

Welcome to the heart of the **Tackety Issue Engine**. This directory houses the business logic, state management, and API surface for the customer support system. It is designed to be purely backend, isolated from any specific UI, and easily extensible.

---

## 🏛️ Architecture Overview

The engine is built around a decoupled architecture to ensure that the AI, database, and business logic can evolve independently.

### Current Components

*   📄 **`api.py` (The Gateway)**
    *   A purely RESTful, high-performance API built on **FastAPI**.
    *   It serves as the entry point for frontend clients (like the demo UI) to interact with the engine.
    *   Runs on port `8000` by default.

*   🧠 **`ai.py` (The Swappable Brain)**
    *   The single point of interaction with Large Language Models.
    *   Currently powered by the modern `google-genai` SDK.
    *   **Model Agnostic:** Handles differences between models under the hood (e.g., automatically injecting `system_instruction` into the prompt for models like `gemma-3-27b-it` that do not support it natively via the SDK).
    *   **Resilient Configuration:** Falls back between multiple API key environment variables (`AI_API`, `GOOGLE_API_KEY`). Defaults to `gemini-2.5-flash`.

*   💾 **`session_manager.py` (The Stateful Memory)**
    *   Since LLMs are stateless, this module reconstructs conversation context on every single turn.
    *   Stores conversation history in an SQLite database located at `engine/data/conversations.db`.
    *   **Thread-Safe**: Configured to work seamlessly with FastAPI’s multi-threaded worker model.
    *   **Zero-Maintenance Cleanup:** Implements a lazy `ttl_days` cleanup. Every $N$ new sessions created, it automatically purges abandoned and closed tickets older than the configured TTL. No external cron jobs needed.

---

## 🚀 Getting Started

### Prerequisites

1.  Python 3.10+
2.  Install dependencies:
    ```bash
    pip install fastapi uvicorn google-genai python-dotenv
    ```

3.  Configure your credentials:
    Create a `.env` file in the `engine/` directory with your Google API Key:
    ```env
    AI_API=your_actual_api_key_here
    ```

### Starting the Server

Run the API locally using `uvicorn` (FastAPI's recommended ASGI server). We provided a baked-in runner in `api.py`:

```bash
cd engine
python api.py
```

*The server will start on `http://0.0.0.0:8000`.*

---

## 🔌 API Documentation

Once the server is running, you can explore the interactive API documentation provided by FastAPI at `http://localhost:8000/docs`.

### Key Endpoints

#### 1. Start a Session
Initializes a new ticket/chat session.
*   **Method:** `POST /session/start`
*   **Request Body (JSON):**
    ```json
    {
      "customer_email": "user@example.com" // Optional
    }
    ```
*   **Response:**
    ```json
    {
      "session_id": "a1b2c3d4-e5f6..."
    }
    ```

#### 2. Send a Message
Appends a user message to the session, queries the AI with the full conversation history, and returns the AI's response.
*   **Method:** `POST /session/message`
*   **Request Body (JSON):**
    ```json
    {
      "session_id": "a1b2c3d4-e5f6...",
      "message": "I'm having trouble checking out.",
      "customer_email": "user@example.com" // Optional (can be added mid-conversation)
    }
    ```
*   **Response:**
    ```json
    {
      "response": "I'm sorry to hear that! Are you seeing a specific error code?",
      "session_status": "active"
    }
    ```

#### 3. Retrieve History
Fetches the chronological message history for a given session.
*   **Method:** `GET /session/{session_id}/history`
*   **Response:**
    ```json
    {
      "messages": [
        { "role": "user", "content": "I'm having trouble checking out.", "timestamp": "..." },
        { "role": "assistant", "content": "I'm sorry to hear that...", "timestamp": "..." }
      ]
    }
    ```

#### 4. Health Check
Verifies that the engine is running.
*   **Method:** `GET /health`

---

## 🔮 Next Steps (Roadmap)

The foundation is solid. The next components to be integrated into the engine are:

1.  **`chatbot.py`**: A structured orchestrator that sits between `api.py` and `ai.py` to enforce conversational guardrails and collect specific ticket data.
2.  **`router.py`**: The decision engine that evaluates established tickets and routes them to a `Human Queue` or an automated `Normalizer` based on complexity.
