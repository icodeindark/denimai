

# 👖 DenimAI: E-Commerce AI Orchestration Engine

DenimAI is a robust AI-driven shopping assistant designed to live where customers already are: **WhatsApp, Instagram, and Facebook Messenger**.

Instead of a simple chatbot, this is a **State Machine** architecture that manages inventory, user carts, and platform-specific messaging via a unified AI "Brain."

---

## 🏗️ System Architecture

The project is built with a modular approach to separate messaging logic from AI reasoning.

### 1. The Integration Layer (Social Media)

* **`app/api/webhook.py`**: A high-performance FastAPI endpoint that receives real-time events from Meta's Webhooks.
* **`app/services/normalization.py`**: The "Translation Layer." It takes platform-specific JSON (WhatsApp vs. Instagram) and converts it into a standardized internal dictionary.
* **`app/services/meta_client.py`**: An asynchronous HTTP client that handles sending replies back to the respective Meta APIs.

### 2. The Orchestration Layer (LangGraph)

* **`app/agent/graph.py`**: Defines the logical flow. It uses nodes (Python functions) and edges to determine if the bot should search inventory, update a cart, or hand off to a human.
* **`app/agent/state.py`**: The "Whiteboard." It tracks chat history, the current shopping cart, and the user's intent.
* **`app/agent/tools.py`**: Specialized functions (tools) that the AI calls to search the SQLite database or calculate order totals.

### 3. The Persistence Layer (Database)

* **`denimAI_store.db`**: Stores products, stock levels, and order history.
* **`langgraph_memory.db`**: A checkpointing database that saves the state of every conversation. This allows a user to "abandon" a cart on Instagram and return the next day without losing their items.

---

## 🛠️ The "Non-Breakable" Features

1. **History Trimming (Token Efficiency):** In `app/agent/state.py`, I implemented a custom reducer (`trim_messages`). It prunes the conversation history to the last 10 messages, preventing "Token Bloat" and ensuring we never hit 429 Rate Limits on the Groq API.
2. **Semantic Routing:** The `router_node` in `graph.py` uses rule-based logic to catch "human escalation" or "checkout" intents immediately, reducing unnecessary LLM calls and providing instant response times for critical actions.
3. **Atomic Cart Updates:** Carts are managed within the AI state first. Database writes only occur in the `finalize_order` tool using `with_for_update()` to prevent race conditions during high-traffic shopping.

---

## 📁 Project Structure

```text
.
├── app
│   ├── agent          # AI Logic (LangGraph, Tools, State)
│   ├── api            # Webhook endpoints
│   ├── core           # App configuration & environment keys
│   ├── models         # SQLAlchemy database schemas
│   └── services       # Meta API clients & Message normalization
├── denimAI_store.db   # Main Product/Order database
├── langgraph_memory.db # Session & Memory persistence
├── main.py            # FastAPI Entry point
└── seeds.py           # Database initializer with sample inventory

```

---

## 🚀 Quick Start

1. **Install Dependencies:**
```bash
pip install -r requirements.txt

```


2. **Set Environment Variables:**
Create a `.env` file with your `GROQ_API_KEY`, `META_PAGE_ACCESS_TOKEN`, and `META_VERIFY_TOKEN`.
3. **Initialize Database:**
```bash
python seeds.py

```


4. **Run Server:**
```bash
uvicorn app.main:app --reload

```



---

