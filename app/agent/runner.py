# app/agent/runner.py
#
# This file is the BRIDGE between your webhook and the LangGraph engine.
# It exposes one single function: run_agent()
#
# Webhook calls run_agent(thread_id, user_message)  →  returns reply string
#
# That's all webhook.py needs to know. The webhook doesn't care about
# LangGraph internals, nodes, or state — it just sends a message and
# gets a reply back. Clean separation of concerns.

from langchain_core.messages import HumanMessage
from app.agent.graph import compiled_graph
from app.agent.state import AgentState
from app.models.database import SessionLocal
from app.models.models import Thread
from datetime import datetime


def upsert_thread(thread_id: str, platform: str, user_name: str):
    """
    Creates a new Thread record if this user hasn't messaged before.
    Updates last_active if they have.

    This is the "persistent identity" feature:
    - First message → INSERT new Thread row
    - Return visit → UPDATE last_active timestamp

    Args:
        thread_id: Unique key e.g. "whatsapp_918138894448"
        platform:  "whatsapp", "messenger", or "instagram"
        user_name: Name from webhook payload
    """
    db = SessionLocal()
    try:
        existing = db.query(Thread).filter(Thread.thread_id == thread_id).first()

        if existing:
            # Returning customer — just update the timestamp
            existing.last_active = datetime.utcnow()
            db.commit()
            print(f"  ↳ Returning customer: {user_name} ({thread_id})")
        else:
            # New customer — create a record
            new_thread = Thread(
                thread_id=thread_id,
                platform=platform,
                user_name=user_name,
                last_active=datetime.utcnow()
            )
            db.add(new_thread)
            db.commit()
            print(f"  ↳ New customer registered: {user_name} ({thread_id})")

    finally:
        db.close()


async def run_agent(thread_id: str, user_message: str, platform: str, user_name: str) -> str:
    """
    The main entry point for processing a user message through LangGraph.

    What happens here:
    1. Register/update the user in the Thread table
    2. Package the message as a HumanMessage
    3. Pass it to the compiled LangGraph with the thread_id config
    4. LangGraph hydrates state from SqliteSaver (loads their history + cart)
    5. Graph runs: router → agent → (tools?) → agent → end
    6. Extract the final AI reply from the output state
    7. Return the reply text to webhook.py

    Args:
        thread_id:    Unique user key e.g. "whatsapp_918138894448"
        user_message: Raw text the user sent
        platform:     "whatsapp", "messenger", or "instagram"
        user_name:    User's name from webhook

    Returns:
        The AI's reply as a plain string
    """
    print(f"\n{'='*60}")
    print(f"🚀 run_agent() called")
    print(f"   Thread:   {thread_id}")
    print(f"   Platform: {platform}")
    print(f"   Message:  '{user_message}'")
    print(f"{'='*60}")

    # ── Step 1: Register user in business DB ─────────────────────────────────
    upsert_thread(thread_id, platform, user_name)

    # ── Step 2: Build the input for LangGraph ────────────────────────────────
    # LangGraph expects a dict matching our AgentState schema.
    # We only need to provide the NEW message — the checkpointer
    # will automatically load the previous messages from disk.
    input_state = {
        "messages": [HumanMessage(content=user_message)],
        # user_cart, current_intent, requires_human are loaded from checkpointer
        # We provide defaults only for the VERY FIRST message
    }

    # ── Step 3: The config tells LangGraph WHICH thread's state to load ──────
    # This is the magic: same thread_id = same memory, same cart, same history
    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    # ── Step 4: Run the graph ─────────────────────────────────────────────────
    try:
        # .invoke() runs the graph synchronously from START to END
        # and returns the FINAL state after all nodes have executed
        final_state = compiled_graph.invoke(input_state, config=config)

        # ── Step 5: Extract the last AI message as the reply ─────────────────
        # messages[-1] is always the most recent message
        # After the graph runs, that's the AI's response
        last_message = final_state["messages"][-1]

        # Get the text content of the reply
        reply = last_message.content if hasattr(last_message, 'content') else str(last_message)

        print(f"\n✅ Agent reply: '{reply[:100]}...' " if len(reply) > 100 else f"\n✅ Agent reply: '{reply}'")

        return reply

    except Exception as e:
        # If the agent crashes for any reason, send a safe fallback message
        # Don't expose error details to the customer
        print(f"\n❌ Agent error: {type(e).__name__}: {e}")
        return (
            "Sorry, I'm having a little trouble right now. 😅 "
            "Please try again in a moment, or type 'human' if you need immediate help."
        )