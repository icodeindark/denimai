# app/agent/state.py
#
# This file defines the "brain state" of your AI agent.
#
# Think of AgentState as a whiteboard that gets passed between every node
# in the LangGraph graph. Each node can READ from it and WRITE to it.
#
# At any millisecond during a conversation, AgentState holds:
#   - The full chat history so far
#   - What items the user wants to buy (their cart)
#   - What the user is currently trying to do (their intent)
#   - Whether a human agent needs to take over
#
# LangGraph's SqliteSaver automatically saves this entire state to disk
# after every message, keyed by thread_id. So if the user comes back
# tomorrow, the agent instantly "remembers" their cart and history.

from typing import TypedDict, Annotated, List
from langgraph.graph.message import add_messages

def trim_messages(existing: list, new: list):
    """
    Automatically keeps the history lean to prevent 429 Rate Limit errors.
    """
    # 1. Combine new messages with the existing ones
    combined = add_messages(existing, new)
    
    # 2. Keep only the last 10 messages (standard for chat bots)
    # This keeps the bot 'smart' but prevents token bloat.
    return combined[-10:]

class AgentState(TypedDict):
    """
    The complete memory snapshot of the agent at any point in time.
    This dict is passed node → node → node through the graph.
    """

    # ── Chat History with trimmed messege for token savings. ──────────────────────────────────────────────────────────
    messages: Annotated[list, trim_messages]

    # ── Shopping Cart ─────────────────────────────────────────────────────────
    # A list of Product IDs the user has added to their cart.
    # e.g. [3, 7] means the user wants Product #3 and Product #7.
    #
    # This lives in LangGraph state (NOT in the database) because:
    #   - It's temporary and session-specific
    #   - The SqliteSaver persists it automatically
    #   - We only write to the products DB when they actually check out
    user_cart: List[int]

    # ── Current Intent ────────────────────────────────────────────────────────
    # What is the user trying to do RIGHT NOW?
    # The router node sets this based on the latest message.
    #
    # Possible values:
    #   "browsing"  → user is asking about products, wants to see options
    #   "checkout"  → user wants to buy what's in their cart
    #   "support"   → user has a complaint, question, or is frustrated
    #   "greeting"  → first message, welcome them
    current_intent: str

    # ── Human Escalation Flag ─────────────────────────────────────────────────
    # When True, the graph routes to the handoff node instead of the AI node.
    # Set to True when:
    #   - User explicitly asks for a human ("let me talk to someone")
    #   - User expresses strong frustration 3+ times
    #   - Agent fails to help after 2 attempts
    requires_human: bool