# Issue Engine — Complete Architecture & Design Document

**Version:** 0.1  
**Status:** Pre-Build  
**Date:** March 2026  
**Every decision recorded. Every reason documented. Nothing left to chance.**

---

## Table of Contents

1. [Origin — Where This Came From](#1-origin)
2. [The Problem Being Solved](#2-the-problem)
3. [What We Are Building](#3-what-we-are-building)
4. [Why This Is Worth Building](#4-why-this-is-worth-building)
5. [System Architecture — The Big Picture](#5-system-architecture)
6. [Component Deep Dive](#6-component-deep-dive)
7. [Database Design](#7-database-design)
8. [Normalizer — Full Design](#8-normalizer)
9. [Chatbot — Full Design](#9-chatbot)
10. [Routing Logic](#10-routing-logic)
11. [Human Queue & Agent System](#11-human-queue)
12. [Webhook System](#12-webhook-system)
13. [Session Management & Cleanup](#13-session-management)
14. [Ticket & Case Schemas](#14-ticket-and-case-schemas)
15. [API Surface](#15-api-surface)
16. [Developer Setup Flow](#16-developer-setup-flow)
17. [File Structure](#17-file-structure)
18. [Build Status](#18-build-status)
19. [Decisions Log — Every Choice & Why](#19-decisions-log)
20. [Parked — Future Work](#20-parked-future-work)

---

## 1. Origin

This project started as a civic tech tool — a complaint management system for municipal wards in India. Citizens could file complaints about local problems: broken drainage, missing street lights, road damage. The core problem was that local government was working through complaints in the order they arrived — first in, first out — which meant a cosmetic issue filed Monday got resolved before a drainage overflow affecting an entire ward filed Tuesday.

The original issue engine solved this by grouping semantically similar complaints together and tracking weight — how many people had reported the same problem. Five complaints about the same broken drain cluster together. The cluster's weight is 5. One complaint about a missing bench has weight 1. The drain gets fixed first. That is the correct priority.

The engine used SQLite with the sqlite-vec extension for vector similarity search and sentence-transformers (all-MiniLM-L6-v2) for embeddings. No external vector database. No cloud dependency. Everything in one portable file.

The question then became: can this same core engine solve the same problem in a commercial SaaS context? The answer was yes. SaaS companies have the identical problem — support tickets pile up, developers work FIFO, and a critical bug affecting hundreds of users sits buried under low-priority requests. This project takes that engine and builds a complete backend system around it.

---

## 2. The Problem

### Problem 1 — Developers work on the wrong things first

Most ticket systems are FIFO. A developer closes whatever arrived first regardless of impact. A cosmetic UI glitch filed Monday gets resolved before a checkout crash filed Tuesday that is blocking 300 users from completing purchases. The system has no intelligence about what actually matters. The developer is not lazy — the system is giving them no signal about priority.

The issue engine solves this by clustering similar issues and tracking weight. Developers see a prioritized queue ranked by real impact — how many users hit this, how critical is the cluster — not by arrival time.

### Problem 2 — Customer support is slow, expensive, and inconsistent

When a user hits a problem, connecting to a human agent takes time. The agent then has to look up documentation, understand the product context, diagnose whether the issue is something they can solve (billing, account, refund) or something that needs a developer (bug, crash, data issue). This process is slow and expensive. Different agents give different answers. The customer waits.

An AI chatbot loaded with company context can resolve a significant portion of queries instantly — FAQs, basic account questions, policy clarifications. For the rest, it can correctly route without any agent needing to diagnose: customer service issues go to an agent, technical issues go to the developer queue.

### Problem 3 — Customer complaints and developer tickets are completely disconnected

Zendesk handles customer service. Jira handles developer tickets. They do not talk to each other intelligently. A support agent manually copies a bug report into Jira. Nothing clusters similar reports across both systems. Nothing tells the developer that this particular bug has been reported 47 times this week by 47 different customers. The developer has no idea of the real impact.

This system closes that gap. The AI understands the issue from the customer conversation, raises a structured ticket, the engine clusters it with similar issues, and the developer sees the real priority with real weight behind it.

### Problem 4 — Existing solutions are expensive, closed, and over-engineered for small teams

Zendesk, Intercom, Freshdesk — all have AI features now. All are expensive SaaS products. None are self-hostable. None give you access to the clustering logic. A 5-person SaaS startup does not need Zendesk. They need something lightweight, transparent, and cheap. That is what this is.

---

## 3. What We Are Building

A backend engine — open source, self-hostable — that:

- Accepts issue input from any source (API call or chat conversation)
- Runs a customer-facing chatbot that understands the company context
- Classifies the issue as technical or customer service
- For customer service issues: allocates a human agent
- For technical issues: normalizes the description into internal product terminology, clusters it with similar issues, assigns urgency based on volume
- Fires webhooks for every significant event so developers can connect their own email, Slack, or notification systems
- Gives developers a prioritized view of what to fix first

### What this is NOT

- Not a full customer service platform. That is Zendesk's job.
- Not a project management tool. That is Jira's job.
- Not a chat widget product. That is Intercom's job.
- Not an enterprise product. This is open source and developer-first.
- Not a closed system. Every AI call goes through one swappable function. Every database is a portable SQLite file.

### Target User for v1

Developers at small to mid-size SaaS teams — 5 to 20 people — who are drowning in support tickets with no intelligent prioritization. They self-host. They are comfortable with Python and APIs. They do not want vendor lock-in. They want to understand exactly what the system is doing.

---

## 4. Why This Is Worth Building

### The open source angle

The market for AI customer support widgets is saturated. Intercom, Tidio, Crisp, Freshdesk — all have AI chat. You cannot compete with them directly. But none of them open source their clustering and prioritization logic. None of them let you self-host. None of them give developers a transparent, auditable system they can trust with their customer data.

An open source, self-hostable, privacy-first issue clustering engine that developers can inspect, modify, and extend — that is a real gap.

### The monetization path (future)

Open source the core engine unconditionally. This builds credibility and community. Monetize the hosted version, the developer dashboard UI, and managed integrations (Jira sync, Linear sync, Slack alerts). This is the Sentry model, the PostHog model, the Plausible model. It works. But adoption comes before monetization — GitHub traction is the near-term goal, not revenue.

### The defensible part

The chat widget is not the moat. Anyone can build a chat widget. The issue clustering engine — semantically grouping issues, tracking weight, escalating urgency, connecting customer complaints to developer queues — that is the defensible part. That is what gets built and protected.

---

## 5. System Architecture

### Complete Data Flow

```
Customer opens chat
        │
        ▼
[conversations.db] — new session created, session_id returned to client
        │
        ▼
chatbot.py — loaded with company doc context
  — converses with customer
  — tracks resolution state internally on every turn
  — three possible outcomes:
        │
        ├─ RESOLVED — chatbot solved it directly
        │       │
        │       ▼
        │   session closes
        │   webhook: (none, or optional resolved event)
        │   done
        │
        ├─ ESCALATE_HUMAN — customer service issue (billing, refund, account)
        │       │
        │       ▼
        │   chatbot writes conversation_summary to ticket JSON
        │   router.py reads type: "customer_service"
        │   human_queue.py allocates least-loaded agent
        │   case written to [support.db]
        │   webhook: handoff.initiated
        │   session closes
        │
        └─ RAISE_TICKET — technical issue (bug, crash, data problem)
                │
                ▼
            normalizer.py — loaded with product doc context
              — embeds raw_issue
              — vector search against vec_product_doc
              — if score >= 0.65: use section title (no LLM call)
              — if score < 0.65: call_ai.py fallback
              — outputs normalized_issue + doc_reference
                │
                ▼
            router.py passes to issue engine
                │
                ▼
            issue_engine.py
              — embeds normalized_issue
              — searches vec_clusters for similar issues
              — adds to existing cluster OR creates new cluster
              — recalculates weight and urgency
                │
                ▼
            technical_ticket written to [issues.db]
            webhook: ticket.created
            session closes
                │
                ▼
            Developer marks cluster resolved
                │
                ▼
            webhook: ticket.resolved
            customer receives automated email via developer's email service
```

### Three Layers

**Layer 1 — Intake**  
Two input types accepted. Raw JSON API call (structured input from any external source) or a conversation transcript (list of message objects from the chatbot). A normalizer converts both into a standard session before the chatbot processes them. This layer ensures the rest of the system never needs to know where the input came from.

**Layer 2 — Intelligence**  
The chatbot and normalizer. Both call `call_ai.py` — the single swappable AI function. The chatbot uses company doc context. The normalizer uses product doc context. Each component has exactly one document and exactly one job. Neither is overloaded.

**Layer 3 — Processing & Storage**  
The router, issue engine, human queue, and webhook system. Pure data processing. No AI calls here. Reads the structured ticket from Layer 2 and does exactly what it says.

---

## 6. Component Deep Dive

### call_ai.py — The Swappable AI Caller

A single file with a single function: `call_ai(prompt, system_prompt, model_config)`. This is the only place in the entire codebase where an external AI API is called. Every other component imports and calls this function.

Why this matters: developers self-hosting this system may not want to use the same AI provider. Some will use Ollama locally (free, private, no API calls). Some will use Gemini free tier. Some will use OpenRouter. Some will use Claude or GPT. By making this one swappable file, a developer changes their AI provider by editing exactly one function. Nothing else in the codebase changes.

```python
# call_ai.py — the entire contract
def call_ai(prompt: str, system_prompt: str = "", config: dict = {}) -> str:
    # developer points this at whatever they want
    # returns the model's text response
    pass
```

**What gets rejected:** hardcoding any specific provider anywhere in the codebase. Even as a default. The default should be whatever is easiest to get running locally — likely Ollama with a small model.

---

### chatbot.py — Conversation + Classification

Loaded with company doc context on initialization. The company doc is embedded and stored — the chatbot uses it as retrieval context on every turn so it understands what the company does, what its products are, what its policies are, and how to talk to customers.

The chatbot manages a conversation loop. On every turn it does two things simultaneously:

1. Generates a response to the customer in natural, human, short language — not long paragraphs, not formal tone
2. Updates an internal resolution state: `RESOLVING`, `ESCALATE_HUMAN`, or `RAISE_TICKET`

When the state changes from RESOLVING to either escalation path, the chatbot does one final structured reasoning step before closing the conversation. It produces the ticket JSON — with the classification decision already baked in — and passes it to the router.

**Why the chatbot owns classification:**  
The chatbot already has the full conversation context. It knows what the customer said, what was tried, what failed. Making a separate classifier component read the same conversation and make the same decision is a redundant LLM call. Double the latency, double the cost, no added accuracy. The chatbot is already the most informed component in the system — it makes the call.

**What gets rejected:** a separate classifier component that reads the chatbot's conversation output and decides technical vs customer service. This was considered and rejected for the reasons above.

---

### normalizer.py — Terminology Mapping

Loaded with product doc context. Single job: take the raw customer description from the chatbot ticket and map it to internal product terminology.

This is not classification. The chatbot already classified the issue as technical. The normalizer's job is translation — from customer language to developer language.

**Why this matters for clustering:**  
Without normalization, two customers describing the same bug differently produce different embeddings that may not cluster together. "My cart is broken" and "items not showing in checkout" and "cannot see what I added to my bag" are all the same issue. After normalization, all three become "checkout module — cart state sync" and cluster perfectly. The issue engine then does its job accurately.

**Why the normalizer uses product doc and not company doc:**  
Company doc is about the company — what it does, its policies, its tone. Product doc is about the product — its modules, features, technical components, internal naming. The normalizer needs to know that "cart" maps to "checkout module" and "billing" maps to "payment service." That information is in the product doc, not the company doc.

Full normalizer flow is documented in section 8.

---

### router.py — The Decision Point

Reads the structured ticket JSON output from the chatbot. Single job: direct to the correct path based on `type` field.

- `type: "technical"` → normalizer → issue engine → issues.db
- `type: "customer_service"` → human_queue → support.db

The router is the only component that writes to both `conversations.db` (closing the session) and `issues.db` or `support.db` (creating the ticket or case). This is intentional. It is the correct single point of coupling between the conversation system and the processing systems. Every other component touches exactly one database.

---

### issue_engine.py — Clustering + Priority (Existing, Untouched)

The original engine. Takes a normalized issue description, searches for similar existing clusters using cosine similarity on embeddings, either adds the complaint to an existing cluster or creates a new one, and updates weight and urgency.

Urgency model:
- weight 1-2 → normal
- weight 3-4 → urgent  
- weight 5+ → critical

The `category` field replaces `ward` from the original civic version. It maps to the product area or module from the normalizer output. All other logic is identical.

**This file is not touched.** The architecture is designed around preserving it exactly as built.

---

## 7. Database Design

### Decision: Three Separate SQLite Databases

**Decided:** Three databases — `conversations.db`, `issues.db`, `support.db`

**Why:** Different databases have different owners, different access patterns, and different lifetimes. Conversations are temporary and get deleted on TTL. Issues are permanent developer records. Support cases are agent-facing, not developer-facing. Forcing different things into one file creates implicit coupling between systems that have no business touching each other. Each database can be backed up, wiped, or moved independently.

**Rejected:** One database for everything (lazy, creates coupling with no benefit). Two databases with tickets and cases merged (they have different schemas, different owners, different consumers — merging them means half the columns are always null).

---

### conversations.db — Temporary

Owned by the chatbot and session manager. Deleted on TTL. Contains only live and recently closed sessions. This database is intentionally ephemeral.

**sessions table**

| Field | Type | Purpose |
|-------|------|---------|
| id | TEXT UUID | Unique session ID, sent to client as cookie/header |
| status | TEXT | active / closed / escalated |
| customer_email | TEXT | Captured during conversation if customer provides it |
| created_at | TIMESTAMP | Session start time |
| closed_at | TIMESTAMP | Set when session ends, used for TTL calculation |

**messages table**

| Field | Type | Purpose |
|-------|------|---------|
| id | INTEGER | Auto increment |
| session_id | TEXT | Foreign key to sessions |
| role | TEXT | user / assistant |
| content | TEXT | Full message text |
| timestamp | TIMESTAMP | Exact message time |

**webhook_configs table**

| Field | Type | Purpose |
|-------|------|---------|
| id | INTEGER | Auto increment |
| event | TEXT | ticket.created / handoff.initiated / ticket.resolved |
| url | TEXT | Developer's registered webhook endpoint |
| secret | TEXT | Signing secret to verify payload authenticity |

---

### issues.db — Permanent

Owned by the issue engine and developer dashboard. Never deleted. This is the long-term record. The developer's source of truth for what needs to be fixed and in what order.

**technical_tickets table**

| Field | Type | Purpose |
|-------|------|---------|
| id | TEXT UUID | Ticket ID, referenced in customer resolution email |
| session_id | TEXT | Dangling ref after session cleanup — intentional, ticket is self-contained |
| customer_email | TEXT | For automated resolution notification when cluster resolved |
| raw_issue | TEXT | Exactly what the customer said, preserved verbatim |
| normalized_issue | TEXT | Internal product terminology from normalizer |
| conversation_summary | TEXT | One-line summary written by chatbot before session deletes |
| doc_reference | TEXT | Which product doc section this maps to |
| status | TEXT | open / assigned / resolved |
| cluster_id | INTEGER | Foreign key to clusters table |
| created_at | TIMESTAMP | Ticket creation time |
| resolved_at | TIMESTAMP | Set when developer marks resolved |

**clusters table** (existing, minor update)

| Field | Type | Purpose |
|-------|------|---------|
| id | INTEGER | Auto increment |
| summary | TEXT | Dynamic — updates as new tickets add context |
| category | TEXT | Product area or module (replaces ward from civic version) |
| weight | INTEGER | Number of tickets in this cluster |
| urgency | TEXT | normal / urgent / critical — auto-escalates by weight |
| status | TEXT | open / resolved |
| created_at | TIMESTAMP | First ticket time |
| resolved_at | TIMESTAMP | When developer marks cluster resolved |

**vec_clusters table** (existing, virtual sqlite-vec table)  
Stores 384-dimension embeddings for issue similarity search. Untouched.

**vec_product_doc table** (new)  
Separate virtual sqlite-vec table. Stores embeddings of product doc chunks. Kept strictly separate from vec_clusters to prevent contamination of issue similarity searches. If they shared a table, a search for similar issues might accidentally match a product doc section instead of a real cluster.

| Field | Type | Purpose |
|-------|------|---------|
| chunk_id | INTEGER | Auto increment |
| section_title | TEXT | Heading from product doc — this becomes normalized category |
| content | TEXT | Chunk text |
| embedding | float[384] | Vector embedding of chunk content |

---

### support.db — Permanent

Owned by the human agent system. Never deleted. Agent-facing. Developers do not interact with this database — it is entirely for the support team.

**cases table**

| Field | Type | Purpose |
|-------|------|---------|
| id | TEXT UUID | Case identifier |
| session_id | TEXT | Dangling ref after cleanup — intentional |
| customer_email | TEXT | For agent communication |
| issue_type | TEXT | refund / billing / account / other |
| raw_issue | TEXT | Human language — agents need the customer's actual words, not normalized text |
| conversation_summary | TEXT | Written by chatbot before session deletes |
| status | TEXT | pending / active / resolved |
| agent_id | TEXT | Allocated agent |
| agent_notes | TEXT | Agent can add notes during case handling |
| created_at | TIMESTAMP | Case creation time |
| resolved_at | TIMESTAMP | Case close time |

**agents table**

| Field | Type | Purpose |
|-------|------|---------|
| id | TEXT | Agent identifier, registered at setup |
| name | TEXT | Display name |
| status | TEXT | available / offline |
| open_cases | INTEGER | Current active case count — used for allocation |

---

## 8. Normalizer

### Why normalization matters

The issue engine clusters by semantic similarity of text. If two customers describe the same bug in completely different words, their embeddings may be distant enough that the engine creates two separate clusters instead of one. The developer then sees two clusters of weight 1 instead of one cluster of weight 2 — and neither gets the urgency it deserves.

Normalization fixes this by translating customer language into consistent internal product terminology before the engine ever sees it. "My cart is broken," "items not showing in checkout," and "cannot see what I added to my bag" all become "checkout module — cart state sync." The engine clusters them correctly. Weight accumulates on the right cluster. Priority is accurate.

### Product doc preparation — runs once on setup

When the developer uploads their product doc during setup:

1. The doc is read and chunked by section heading — each heading and its content becomes one chunk
2. Each chunk is embedded using the same model as the issue engine (all-MiniLM-L6-v2 for consistency)
3. Embeddings are stored in `vec_product_doc` in issues.db
4. Section titles are stored alongside embeddings as the normalization targets

The choice of what becomes the "normalized" output is the section title from the product doc. This means the quality of normalization depends on how well the product doc is structured and named. A product doc with clear section titles like "Checkout Module," "Payment Processing," "User Authentication" will produce excellent normalization. A poorly structured doc will produce weaker normalization. This is a known limitation and should be documented for users.

### Normalization flow — runs on every technical issue

```
Input: raw_issue text from chatbot ticket JSON

Step 1 — Embed raw_issue using all-MiniLM-L6-v2

Step 2 — Vector similarity search against vec_product_doc
         (cosine distance, same as issue engine)

Step 3 — Get top match and its similarity score

Step 4a (score >= 0.65) — 
  Use that chunk's section_title as normalized_issue category
  No API call. Fast. Free.
  Confidence: high

Step 4b (score < 0.65) — 
  call_ai.py with focused prompt:
  system: "You are a product terminology mapper."
  user: "Given these product doc sections: [top 3 chunks]
         Map this customer issue to the correct internal module:
         [raw_issue]
         Respond only with JSON: 
         {normalized_issue, doc_reference, confidence}"
  Confidence: low (flagged in ticket)

Step 5 — Output added to ticket JSON:
  normalized_issue: "checkout module — cart state not updating"
  doc_reference: "Section 4.2 — Order Management"
  normalization_confidence: "high" | "low"
```

### Threshold reasoning

The normalizer threshold is 0.65, higher than the issue engine's 0.5. The issue engine at 0.5 is deliberately loose — it is grouping complaints that are probably about the same thing, and being slightly wrong is acceptable (clusters can be reviewed). The normalizer at 0.65 is tighter — it is mapping to a specific product section, and a wrong mapping sends the ticket to the wrong cluster permanently. Tighter threshold, more LLM fallbacks, but more accurate results.

### What normalizer does NOT do

- Does not classify the issue. The chatbot already did that.
- Does not route the issue. The router does that.
- Does not create tickets. The router does that.
- Does not talk to the customer. Ever.

---

## 9. Chatbot

### Context loading

The chatbot is initialized with the company doc embedded and available for retrieval. On every turn, it retrieves the most relevant sections of the company doc given the current conversation context. This means a question about refund policy retrieves the refund policy section. A question about technical features retrieves the technical section. The chatbot never holds the entire doc in the prompt — it retrieves what is relevant.

### Conversation loop

On every message received from the customer:

1. Load session messages from `conversations.db` to reconstruct conversation history
2. Retrieve relevant company doc sections for current context
3. Call `call_ai.py` with full history + retrieved context + current message
4. Get response text + internal state update
5. Write new message (both user and assistant) to messages table
6. Check internal state

The LLM has no memory between calls. The conversation history is reconstructed from the database on every single turn. This is how every production chat system works. Stateless AI, stateful database.

### Internal state tracking

The chatbot maintains a resolution state that is NOT shown to the customer. On every turn the model outputs both a customer-facing response and an internal state decision:

```
RESOLVING       — still working on it, continue conversation
ESCALATE_HUMAN  — this is a billing/account/policy issue I cannot resolve
RAISE_TICKET    — this is a technical bug or system issue
```

The state is included in the structured output of every AI call but only the response text is shown to the customer.

### Closing the conversation

When state becomes `ESCALATE_HUMAN` or `RAISE_TICKET`, the chatbot:

1. Sends a closing message to the customer in natural language:
   - Technical: "I've raised a ticket for this issue. You'll receive an email update when it's resolved."
   - Human handoff: "Let me connect you with a team member who can help with this directly."
2. Makes one final structured call to produce the ticket JSON with all required fields
3. Writes `conversation_summary` — one clean sentence describing the issue
4. Passes ticket JSON to router
5. Session status updated to `closed` in conversations.db

### What the chatbot does NOT do

- Does not call the normalizer. Router handles that.
- Does not create database records beyond messages. Router handles that.
- Does not allocate agents. human_queue handles that.
- Does not fire webhooks. webhook.py handles that.

### Tone requirements

Short responses. Not long paragraphs. Natural human language. No "I am an AI assistant" disclaimers. No corporate formality. The chatbot sounds like a knowledgeable, friendly support person.

---

## 10. Routing Logic

The router is the simplest component but the most important one architecturally. It is the seam between the conversation system and the processing system.

```python
def route(ticket: dict):
    if ticket["type"] == "customer_service":
        case = human_queue.create_case(ticket)
        webhook.fire("handoff.initiated", case)
        session_manager.close(ticket["session_id"])
        
    elif ticket["type"] == "technical":
        normalized = normalizer.normalize(ticket)
        cluster_result = issue_engine.process_complaint({
            "complaint_text": normalized["normalized_issue"],
            "category": normalized["doc_reference"],
            ...ticket
        })
        ticket_record = db.create_technical_ticket(normalized, cluster_result)
        webhook.fire("ticket.created", ticket_record)
        session_manager.close(ticket["session_id"])
```

Simple. Linear. No branching logic beyond the type check. Every branch is a clean handoff to a specialized component.

---

## 11. Human Queue

### Agent allocation — least loaded

**Decided:** New case goes to the agent with the lowest `open_cases` count.

**Why:** Round-robin ignores workload entirely. If one agent resolves cases quickly and another is slow, round-robin still distributes evenly — and the slow agent gets buried. Least-loaded is barely more complex to implement but actually respects real workload. It takes one extra query: `SELECT id FROM agents WHERE status='available' ORDER BY open_cases ASC LIMIT 1`.

**Rejected:** Round-robin (ignores workload), presence-based routing (requires real-time agent heartbeat, too complex for v1), random assignment (no logic at all).

### No agents available

If all agents are offline or unavailable, the case is written to `support.db` with `status: pending` and `agent_id: null`. The webhook fires `handoff.initiated` anyway with the full payload — the developer's system can notify agents through Slack, email, or whatever channel they use. This system's responsibility ends at raising the event. It does not manage agent availability or notification.

### Agent open_cases count

When a case is created and assigned, `open_cases` increments by 1 for that agent. When a case is resolved, `open_cases` decrements by 1. This counter is the only metric used for allocation. Simple, always consistent, zero overhead.

---

## 12. Webhook System

### Decision: Webhooks only, no built-in email provider

**Decided:** Fire a signed POST to developer-registered URLs. No email provider bundled.

**Why:** This is open source. Hardcoding SendGrid, Mailgun, or any SMTP provider forces every self-hoster to use that provider or fork the code. Different teams use different email providers. Some use Slack notifications instead. Some have their own internal notification systems. A webhook fires a POST request with the full payload to whatever URL the developer registered — they connect their own system on the other end. One clean boundary. Maximum flexibility.

**Rejected:** Built-in SendGrid integration (vendor lock-in), built-in SMTP (configuration nightmare, security liability), no notifications at all (defeats the purpose of knowing when things are resolved).

### Webhook signing

Every webhook POST includes an `X-Signature` header — an HMAC-SHA256 signature of the payload using the developer's registered secret. The developer verifies this on their end before processing. This ensures that only this system can trigger their webhook handler — not a random attacker who discovers the URL.

### Three webhook events

**ticket.created** — fires when a technical issue is clustered

```json
{
  "event": "ticket.created",
  "ticket_id": "uuid",
  "customer_email": "user@example.com",
  "normalized_issue": "checkout module — cart state not updating",
  "doc_reference": "Section 4.2 — Order Management",
  "cluster_id": 42,
  "cluster_weight": 7,
  "urgency": "critical",
  "time": "2026-03-23T10:00:00Z"
}
```

**handoff.initiated** — fires when a case is assigned to a human agent

```json
{
  "event": "handoff.initiated",
  "case_id": "uuid",
  "customer_email": "user@example.com",
  "issue_type": "refund",
  "agent_id": "agent_03",
  "conversation_summary": "Customer reports duplicate charge on March subscription",
  "time": "2026-03-23T10:00:00Z"
}
```

**ticket.resolved** — fires when developer marks cluster resolved. This is the trigger for the automated customer notification email on the developer's side.

```json
{
  "event": "ticket.resolved",
  "ticket_id": "uuid",
  "customer_email": "user@example.com",
  "normalized_issue": "checkout module — cart state not updating",
  "conversation_summary": "Customer unable to see cart contents after adding items",
  "resolved_at": "2026-03-23T14:00:00Z"
}
```

---

## 13. Session Management

### How sessions work

Every conversation has a session. When a customer opens a chat:
1. `session_manager.py` creates a new row in sessions table
2. Returns a `session_id` (UUID)
3. Client stores this as a cookie or local identifier
4. Every subsequent message includes this `session_id`
5. Session manager loads the full message history for that session on every turn
6. Rebuilds full conversation context for the chatbot

If the customer refreshes the page or disconnects mid-conversation, they send their `session_id` on reconnect and the conversation resumes exactly where it left off. The chatbot reconstructs context from the messages table. Nothing is lost.

### Session TTL and cleanup

**Decided:** Lazy cleanup triggered every 10th new session creation. Delete sessions and messages where `closed_at` is older than configured TTL (default 3 days).

**Why lazy cleanup:** No background jobs. No schedulers. No cron. No additional dependencies. On every 10th session creation, a cleanup query runs: `DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE closed_at < datetime('now', '-3 days') AND status != 'active')` followed by the same for sessions. Zero overhead between cleanups. Self-maintaining. This is a standard pattern in production systems for exactly this reason.

**Why 3 days default:** Enough time to debug any issues with how conversations were handled. Not so long that storage grows significantly. Configurable by the developer — some may want 7 days, some may want 1 day.

**What about open sessions:** Only closed sessions are eligible for cleanup. `status != 'active'` is always in the WHERE clause. A live conversation is never touched.

**What is preserved before deletion:** The `conversation_summary` written to the ticket or case record. The `customer_email`. The `raw_issue`. The ticket in `issues.db` and case in `support.db` are permanent. Only the raw message history — which has served its purpose — is deleted.

### The dangling session_id

After cleanup, `technical_tickets.session_id` and `cases.session_id` will point to sessions that no longer exist. This is intentional and acceptable. The ticket is entirely self-contained — it has `raw_issue`, `normalized_issue`, `conversation_summary`, `customer_email`, `cluster_id`. It does not need the raw message history. The dangling foreign key is a documentation reference, not a functional dependency.

---

## 14. Ticket and Case Schemas

### Technical ticket — full JSON from chatbot

```json
{
  "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "technical",
  "session_id": "session-uuid",
  "customer_email": "user@example.com",
  "raw_issue": "my cart is not showing the items I added",
  "conversation_summary": "Customer unable to see cart contents after adding items. Reproduced on both mobile and desktop.",
  "time": "2026-03-23T10:00:00Z"
}
```

### After normalizer processes it

```json
{
  "ticket_id": "550e8400-e29b-41d4-a716-446655440000",
  "type": "technical",
  "session_id": "session-uuid",
  "customer_email": "user@example.com",
  "raw_issue": "my cart is not showing the items I added",
  "normalized_issue": "checkout module — cart state not updating",
  "doc_reference": "Section 4.2 — Order Management",
  "normalization_confidence": "high",
  "conversation_summary": "Customer unable to see cart contents after adding items. Reproduced on both mobile and desktop.",
  "time": "2026-03-23T10:00:00Z"
}
```

### Customer service case JSON from chatbot

```json
{
  "case_id": "660f9500-f30c-52e5-b827-557766551111",
  "type": "customer_service",
  "session_id": "session-uuid",
  "customer_email": "user@example.com",
  "issue_type": "refund",
  "raw_issue": "I was charged twice for my subscription this month",
  "conversation_summary": "Customer reports duplicate charge on March subscription renewal. Charge appeared twice on March 1st.",
  "time": "2026-03-23T10:00:00Z"
}
```

---

## 15. API Surface

All endpoints exposed via `api.py` using FastAPI.

### Setup endpoints — run once on deployment

```
POST /setup/company-doc
  body: { file: <multipart upload> }
  action: reads doc, embeds content, stores for chatbot retrieval

POST /setup/product-doc
  body: { file: <multipart upload> }
  action: reads doc, chunks by heading, embeds each chunk,
          stores in vec_product_doc

POST /setup/webhook
  body: { event: string, url: string, secret: string }
  action: registers webhook config in conversations.db

POST /setup/agent
  body: { id: string, name: string }
  action: creates agent record in support.db
```

### Conversation endpoints — runtime

```
POST /session/start
  body: {}
  returns: { session_id: string }

POST /session/message
  body: { session_id: string, message: string, customer_email?: string }
  returns: { response: string, session_status: string }
  note: if session_status is "closed", conversation ended

POST /session/end
  body: { session_id: string }
  action: explicitly closes session regardless of state
```

### Developer dashboard endpoints

```
GET /clusters
  returns: clusters ordered by urgency DESC, weight DESC
  this is the developer's priority queue

GET /cluster/:id
  returns: cluster detail + all tickets in that cluster

GET /tickets
  returns: all open technical tickets

POST /ticket/:id/resolve
  action: sets status=resolved, resolved_at=now
          fires ticket.resolved webhook for each customer_email
          in cluster

GET /cases
  returns: all open customer service cases

POST /case/:id/resolve
  action: sets status=resolved, resolved_at=now
          decrements agent open_cases count
```

---

## 16. Developer Setup Flow

The entire system is configured by running one script once. No UI. No account creation. No cloud service. Developers are the target user — they are comfortable with CLI tools.

```bash
python setup.py
```

The script walks through interactively:

```
Issue Engine Setup
──────────────────
Webhook URL: https://your-server.com/webhooks/issue-engine
Webhook signing secret: [your secret]
Company doc path: ./docs/company.pdf
Product doc path: ./docs/product.pdf
Agent IDs (comma separated): agent_01,agent_02,agent_03
Agent names (comma separated): Alice,Bob,Carol
Session TTL in days [default 3]: 3
AI provider config: [points to call_ai.py — edit that file directly]

Initializing databases...
  ✓ conversations.db created
  ✓ issues.db created
  ✓ support.db created
Processing company doc...
  ✓ Embedded and stored
Processing product doc...
  ✓ Chunked into 24 sections
  ✓ All sections embedded
  ✓ Stored in vec_product_doc
Registering webhooks...
  ✓ 3 events registered
Registering agents...
  ✓ Alice (agent_01) registered
  ✓ Bob (agent_02) registered
  ✓ Carol (agent_03) registered

Setup complete. Run: python api.py
```

Then:

```bash
python api.py
# API running on http://localhost:8000
```

That is the entire deployment. One setup run, one server start.

---

## 17. File Structure

```
core/
├── setup.py                ← one-time setup script, run before anything else
├── call_ai.py              ← THE swappable AI caller, single function
│                              developers edit this to change AI provider
├── session_manager.py      ← create/resume sessions
│                              write messages
│                              lazy TTL cleanup every 10th session
├── chatbot.py              ← loads company doc context
│                              manages conversation loop
│                              tracks internal resolution state
│                              outputs structured ticket JSON
│                              owns the classification decision
├── normalizer.py           ← loads product doc context
│                              hybrid vector search (0.65 threshold) + LLM fallback
│                              maps raw_issue to internal product terminology
│                              only runs for technical issues
├── router.py               ← reads ticket JSON type field
│                              routes to normalizer+engine or human_queue
│                              only component touching both databases
├── human_queue.py          ← least-loaded agent allocation
│                              case creation in support.db
│                              open_cases count management
├── webhook.py              ← fires signed POST to registered URLs
│                              HMAC-SHA256 signing
│                              handles ticket.created, handoff.initiated, ticket.resolved
├── api.py                  ← FastAPI entry point
│                              all endpoints documented in section 15
│
└── issue-engine/           ← original engine, completely untouched
    ├── issue_engine.py
    ├── cli.py
    └── test_issue_engine.py

docs/
├── DESIGN.md               ← this file
└── issue-engine-design.md  ← original civic version design
```

---

## 18. Build Status

| Component | Status | Notes |
|-----------|--------|-------|
| issue_engine.py | ✅ Done | Clustering, vector search, urgency escalation working |
| cli.py | ✅ Done | Interactive CLI for testing engine |
| test_issue_engine.py | ✅ Done | Tests passing |
| call_ai.py | 🔲 Planned | Swappable AI caller — own file, single function |
| session_manager.py | 🔲 Planned | Sessions, messages, lazy TTL cleanup |
| chatbot.py | 🔲 Planned | Company doc context, conversation loop, classification |
| normalizer.py | 🔲 Planned | Product doc context, hybrid vector + LLM, terminology mapping |
| router.py | 🔲 Planned | Route by type, single point of coupling |
| human_queue.py | 🔲 Planned | Least-loaded allocation, open_cases tracking |
| webhook.py | 🔲 Planned | Signed POST, three events |
| setup.py | 🔲 Planned | One-time deployment configuration |
| api.py | 🔲 Planned | FastAPI, all endpoints |

---

## 19. Decisions Log

Every significant decision made during design, with the reason and what was rejected.

| Decision | Why | Rejected |
|----------|-----|----------|
| Chatbot owns classification (technical vs customer service) | Chatbot has full conversation context already. Separate classifier = redundant LLM call, double latency, no accuracy gain | Separate classifier component |
| Normalizer uses hybrid vector + LLM fallback | 70% of cases handled without API call. Fast, cheap, works offline. LLM only for ambiguous cases | Pure LLM (expensive at scale), pure vector (brittle for ambiguous customer language) |
| Normalizer threshold 0.65 vs engine threshold 0.5 | Normalizer maps to specific sections — wrong mapping is permanent. Engine groups similar issues — slightly wrong is recoverable. Tighter threshold = more accurate mapping | Same threshold as engine (0.5 too loose for section mapping) |
| vec_product_doc separate from vec_clusters | Prevent contamination of issue similarity searches. Mixed table = search for similar issues might match product doc sections | Shared table with type column |
| Three databases | Different owners, access patterns, lifetimes. Independent backup/wipe. No cross-database coupling | One database (creates implicit coupling), two databases (tickets and cases have too different schemas/owners) |
| Conversations.db is temporary, deleted on TTL | Message history is only needed during active conversation and brief debugging window. Unbounded growth otherwise | Keeping all conversations forever (storage bloat), deleting immediately on close (lose debugging window) |
| Lazy cleanup every 10th session | No background jobs, schedulers, or cron needed. Self-maintaining. Standard production pattern | Background scheduler (adds complexity + dependency), cron job (adds infrastructure requirement) |
| 3 day TTL default | Enough to debug issues. Not enough to bloat storage. Configurable. | 7 days (too long), 1 day (too short for debugging), no TTL (unbounded growth) |
| conversation_summary written to ticket before session deletes | Ticket is self-contained after session cleanup. One sentence preserves the essential context without keeping full message history | Keeping full message history in ticket (redundant with issues.db), no summary (ticket loses all human context) |
| customer_email on ticket | Required for automated resolution notification when developer marks cluster resolved. Without it, customer never knows their issue was fixed | Not storing email (breaks the customer notification loop) |
| Least-loaded agent allocation | Respects real workload. One query difference from round-robin but significantly better in practice | Round-robin (ignores workload), presence-based (requires real-time heartbeat, too complex), random (no logic) |
| Webhooks only, no built-in email | Open source must not impose vendor choice. Developer connects their own email/Slack/notification system | Built-in SendGrid (vendor lock-in), built-in SMTP (security liability + configuration nightmare) |
| HMAC-SHA256 webhook signing | Prevents random attackers from triggering webhook handlers by discovering the URL | No signing (trivially exploitable), OAuth (massively overcomplicated for a webhook) |
| call_ai.py as single swappable file | Open source users should change AI providers without touching business logic. One file, one function | Hardcoding any provider anywhere, provider abstraction class (overcomplicated for one function) |
| SQLite for all databases | Same philosophy as original engine. Portable, no external dependencies, single file per database, self-contained deployment | PostgreSQL (requires server), MongoDB (no benefit for this schema), external vector DB (adds dependency) |
| FastAPI for api.py | Async, modern, automatic OpenAPI docs, type hints, fast. Standard choice for Python APIs | Flask (less modern, no async), Django (massively over-engineered for this), raw ASGI (too low level) |
| setup.py CLI script for configuration | Developers are comfortable with CLI. No UI to build, no account system, no cloud service | Web UI for setup (adds a whole frontend to build), config file only (poor UX, easy to make errors), environment variables only (too many variables) |

---

## 20. Parked — Future Work

These are confirmed future directions. They are not v1 scope. They are documented here so the decisions are not forgotten and so the architecture does not accidentally block them.

### Feedback Mode

The issue engine is domain agnostic — this was designed in from the original civic version. A `mode` flag on the engine switches behaviour from issue clustering to feedback aggregation. Clusters of feedback entries auto-summarize into 2-3 line syntheses for product teams — "what are users actually saying about the checkout experience this month." Same core engine, different output consumer, one extra LLM call per cluster when weight crosses a threshold. Build after v1 ships. This is an extension, not a separate product.

### Integration Layer / Embed Widget

A copy-paste JavaScript snippet that drops a chat widget onto any website. Internally it calls the same backend API. The engine filters requests by originating domain so one deployment handles multiple clients cleanly. This is the eventual path to broad adoption — the "just paste this into your site" experience described in the original product vision. Not v1. Build the backend first, make the widget a thin client on top of the API that already exists.

### Multilingual Support

Swap `all-MiniLM-L6-v2` for `paraphrase-multilingual-MiniLM-L12-v2`. Handles Hindi, Bengali, Tamil, and dozens of other languages instantly. Zero architecture change — one model swap in setup.py and a config flag in the embedding calls. Not v1 because it needs testing to confirm clustering quality across languages, but the architecture already supports it.

### Monetization

Open source the core engine unconditionally. This is the credibility layer — developers need to audit it before they trust it with customer data. Monetize: hosted managed version (no self-hosting required), developer dashboard UI (open source projects rarely have good UI — that is the wedge), and managed integrations (Jira sync, Linear sync, Slack alerts when a cluster hits critical). The Sentry / PostHog model. Adoption precedes monetization — GitHub stars and developer trust are the near-term metrics, not revenue.

### Dashboard UI

A clean developer-facing dashboard showing the prioritized cluster queue, cluster detail views, ticket history, resolution rates, and time-to-resolve trends. The API already supports all of this. The UI is a separate frontend project. Not v1 — API first, UI second.

---

*Issue Engine — Complete Architecture & Design Document*  
*Version 0.1 — Pre-Build — March 2026*  
*Nothing left undiscussed. Nothing left to chance.*
