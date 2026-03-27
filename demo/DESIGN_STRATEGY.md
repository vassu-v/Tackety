# Tackety Design Strategy & Direction

## 1. Critical Assessment of the Provided Information
Tackety is positioned as a developer-first, self-hosted issue engine that bridges the gap between customer complaints and developer workflows. The core differentiation is its intelligent normalization and clustering, not just its chat interface. 

**The current design weak points:**
- The existing `index.html` demo uses a highly generic, consumer-grade "AI chat" aesthetic (purple glows, glassmorphism, floating bubbles, bouncy typing indicators). It looks like an out-of-the-box template rather than a serious infrastructure tool.
- It hides the product's true value. Tackety isn't just chatting; it's structuring data, routing, and raising tickets. The UI shouldn't feel like iMessage—it should feel like an intelligence pipeline.
- Developers trust tools that look precise, transparent, and utilitarian (e.g., Linear, Vercel, Stripe). The current glowing aesthetic undermines the "serious, open-source infrastructure" positioning.

## 2. Strategic Design Direction
**Tone:** Utilitarian, precise, transparent, and highly structured.
**Visual Language:** Shift from "friendly consumer AI" to "high-end developer tool." We will replace the dark-mode purples and glassmorphism with a high-contrast, stark monochrome palette (deep grays, crisp whites) with very subtle, functional accents. 
**UX Approach:** The interface should feel less like a human conversation and more like a command center. When the AI processes a message, it shouldn't just respond with text; it should expose its internal state and structuring process, showing developers exactly what the engine is doing under the hood.

## 3. Layout Concept
- **Grounded Console:** Instead of a floating centered window, the chat will take the form of a structured, grounded panel or a split-view terminal.
- **System Activity Stream:** Replace the standard left/right chat bubbles. User inputs are aligned left, but AI responses don't masquerade as chat bubbles. They render as system logs and structured cards.
- **Exposed Metadata:** Show the parsing state. When raising a ticket, display the structured payload (e.g., Priority, Cluster, Type) inline.

## 4. Component Usage
- **Command-Line Inputs:** The input area should feel like a terminal input or a command palette (clean, raw text, subtle border).
- **Execution Blocks:** Replace bouncing typing dots with a monospaced "Processing sequence..." or a flashing block cursor.
- **Structured Ticket Cards:** When the chatbot resolves or escalates, it shouldn't just send a text message. It should render a strictly formatted "Ticket Generated" card with key-value pairs (Issue: Technical, Weight: +1, Cluster: Checkout).

## 5. Styling Guidance
- **Typography:** `Inter` for general UI reading, paired with a monospaced font (`JetBrains Mono`, `Roboto Mono`, or system monospace) for technical data, timestamps, and system states.
- **Color Logic:** 
  - Backgrounds: Very dark, neutral grays (`#09090B`, `#18181B`).
  - Borders: Crisp and thin (`#27272A`).
  - Text: High contrast for readability (`#FAFAFA` for primary, `#A1A1AA` for secondary).
  - Accents: Functional only. Muted amber for routing/processing, muted cyan or green for successfully clustered tickets. Avoid decorative gradients.
- **Spacing:** Dense but highly organized. Use standard 4px/8px grid systems to align key-value pairs perfectly.

## 6. Interaction and Behavior Ideas
- **Progressive Disclosure:** As the user typing, perhaps a subtle hint shows "Tackety engine listening...". When a message is sent, show steps: `[1/3] Normalizing phrase...`, `[2/3] Checking clusters...`, `[3/3] Ticket raised`.
- **Selectable Payloads:** Structured cards should look like code blocks or JSON trees that a developer could theoretically copy, reinforcing the API-first backend nature of the tool.

## 7. Risks, Weak Points, and Stronger Alternatives
- **Risk:** Making it look *too* much like a terminal might alienate the non-technical end-users (customers) who actually use the chat. 
- **Stronger Alternative:** If this demo is meant to show *developers* how the chat looks for *their* end-users while also showing the engine's power, we should offer a "Debug Mode" toggle in the UI. 
  - *Standard Mode:* A clean, highly polished, neutral chat interface (think Stripe support—clean lines, no gimmicks).
  - *Debug Mode (Toggled On):* The UI splits or expands to show what Tackety is doing behind the scenes (the JSON payloads, the normalizer scores, the webhook fires). 
  - *For this execution, we will build the interface to reflect the "clean, high-end SaaS" look, incorporating structured system messages to hint at the backend engine.*
