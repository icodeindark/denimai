# app/agent/graph.py
#
# This is the BRAIN of DenimAI — the LangGraph state machine.
#
# A LangGraph "graph" is just a fancy flow diagram made of:
#   - NODES: Python functions that do work (think, search, respond)
#   - EDGES: Connections that say "after node A, go to node B"
#   - CONDITIONAL EDGES: "After node A, go to B or C depending on the state"
#
# Our graph looks like this:
#
#   [START]
#      ↓
#   [router_node]  ← reads the message, decides what to do
#      ↓ (conditional)
#      ├─── "browsing/checkout" ──→ [agent_node] ← LLM thinks + uses tools
#      │                                ↓
#      │                          (conditional: did LLM call a tool?)
#      │                              ├─── YES → [tools_node] → back to [agent_node]
#      │                              └─── NO  → [END]
#      │
#      └─── "human needed" ──→ [handoff_node] → [END]
#
# The SqliteSaver checkpointer saves the ENTIRE AgentState to disk
# after every node execution, keyed by thread_id.

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.agent.state import AgentState
from app.agent.tools import ALL_TOOLS
from app.models.database import MEMORY_DB_PATH
import json
import sqlite3


# =============================================================================
# STEP 1: Initialize the LLM
# =============================================================================
def get_llm():
    from app.core.config import settings

    llm = ChatGroq(
        api_key=settings.groq_api_key,
        # Using the highly stable OSS 20B model available on the free tier
        model="openai/gpt-oss-20b", 
        temperature=0.1,   
        max_tokens=500     
    )

    # Bind tools normally!
    return llm.bind_tools(ALL_TOOLS)


# =============================================================================
# STEP 2: The System Prompt
# This is the LLM's "personality card" — it sets context for every response
# =============================================================================
SYSTEM_PROMPT = """You are DenimAI, a friendly and knowledgeable fashion assistant
for a premium clothing store. You help customers discover outfits, check availability,
manage their cart, and complete purchases — all via chat.

Your personality:
- Warm, concise, and stylish (you know fashion)
- Never make up products — ALWAYS use search_inventory() to check
- Never confirm stock without checking the database first
- If a customer wants to add something, use manage_cart() with action='add'
- If they say 'checkout', 'buy it', or 'place order' → use finalize_order()
- If they ask what's in their cart → use get_cart_summary()
- Keep replies SHORT — this is WhatsApp/Messenger, not an essay

When you search inventory, always mention the product ID when presenting options,
so you can reference it when adding to cart.

You currently know these vibes: Old Money, Minimalist, Streetwear, Smart Casual.
"""


# =============================================================================
# STEP 3: Router Node
# The "traffic cop" — reads the message and sets current_intent
# This runs FIRST before any LLM call
# =============================================================================
def router_node(state: AgentState) -> dict:
    """
    Analyzes the latest user message and sets current_intent.
    This is a simple rule-based router — fast and deterministic.
    No LLM call needed here (saves API tokens).
    """
    # Get the last message the user sent
    last_message = state["messages"][-1]
    text = last_message.content.lower() if hasattr(last_message, 'content') else ""

    print(f"\n🔀 Router analyzing: '{text}'")

    # Check for human escalation signals FIRST (highest priority)
    human_triggers = [
        "human", "real person", "agent", "support", "help me",
        "this is wrong", "i'm frustrated", "frustrated", "angry",
        "not happy", "speak to someone", "talk to someone"
    ]
    if any(trigger in text for trigger in human_triggers):
        print("  ↳ Intent: HUMAN ESCALATION")
        return {"current_intent": "support", "requires_human": True}

    # Check for checkout intent
    checkout_triggers = [
        "checkout", "buy", "purchase", "order", "pay",
        "place order", "buy it", "i'll take it", "confirm"
    ]
    if any(trigger in text for trigger in checkout_triggers):
        print("  ↳ Intent: CHECKOUT")
        return {"current_intent": "checkout", "requires_human": False}

    # Check for cart-related intent
    cart_triggers = ["cart", "what's in my cart", "my cart", "show cart"]
    if any(trigger in text for trigger in cart_triggers):
        print("  ↳ Intent: CART VIEW")
        return {"current_intent": "browsing", "requires_human": False}

    # Default: browsing / product inquiry
    print("  ↳ Intent: BROWSING")
    return {"current_intent": "browsing", "requires_human": False}


# =============================================================================
# STEP 4: Agent Node
# The main LLM node — the AI thinks, reads state, and decides what to do
# =============================================================================
def agent_node(state: AgentState) -> dict:
    """
    The core AI node. The LLM reads the conversation and either:
    A) Responds directly with text
    B) Calls a tool (search_inventory, manage_cart, etc.)

    If it calls a tool, LangGraph automatically routes to ToolNode,
    executes the function, and comes BACK here with the result.
    """
    llm = get_llm()

    # Build the message list: system prompt + full conversation history
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]

    # Add cart context so the LLM always knows what's in the cart
    if state.get("user_cart"):
        cart_context = f"\n[Current cart product IDs: {state['user_cart']}]"
        messages[0] = SystemMessage(content=SYSTEM_PROMPT + cart_context)

    print(f"\n🤖 Agent thinking... (cart: {state.get('user_cart', [])})")

    # This is the actual LLM call — sends messages to Groq API
    response = llm.invoke(messages)

    print(f"  ↳ LLM response type: {'tool_call' if response.tool_calls else 'text'}")

    return {"messages": [response]}


# =============================================================================
# STEP 5: Tools Node
# Executes whatever tool the LLM decided to call
# LangGraph's built-in ToolNode handles this automatically
# =============================================================================
# ToolNode takes our list of tools and knows how to:
#   1. Find the right function by name
#   2. Pass the right arguments
#   3. Return the result back into the messages state
tools_node = ToolNode(ALL_TOOLS)


# =============================================================================
# STEP 6: Handoff Node  
# Fires when requires_human = True
# In a real system, this would create a support ticket or notify staff
# =============================================================================
def handoff_node(state: AgentState) -> dict:
    """
    Handles escalation to human support.
    Currently sends a message; in production this would ping your support team.
    """
    print("\n🚨 ESCALATION: Routing to human agent")

    handoff_message = AIMessage(content=(
        "I totally understand, and I want to make sure you get the best help possible. 🙏\n\n"
        "I'm connecting you with a real person from our team right now. "
        "Someone will be with you within a few minutes.\n\n"
        "In the meantime, feel free to describe your issue and they'll have full context."
    ))

    return {"messages": [handoff_message]}


# =============================================================================
# STEP 7: Conditional Edge Functions
# These functions look at the current state and return the NAME of the
# next node to route to. LangGraph uses these to decide where to go next.
# =============================================================================

def route_after_router(state: AgentState) -> str:
    """
    Called after router_node.
    Returns the name of the next node to visit.
    """
    if state.get("requires_human"):
        return "handoff_node"
    return "agent_node"


def route_after_agent(state: AgentState) -> str:
    """
    Called after agent_node.
    If the LLM made tool calls → go execute them.
    If the LLM gave a text reply → we're done.
    """
    last_message = state["messages"][-1]

    # Check if the LLM response includes tool calls
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"

    return END


# =============================================================================
# STEP 8: Cart State Updater
# After tool execution, parse the tool output to update the cart state
# (LangGraph's ToolNode doesn't automatically update custom state fields)
# =============================================================================

def update_cart_state(state: AgentState) -> dict:
    """Deterministically updates the cart by parsing JSON tool outputs."""
    last_message = state["messages"][-1]

    # ToolNode outputs "ToolMessage" objects
    if last_message.type == "tool":
        try:
            # Try to parse the tool output as JSON
            data = json.loads(last_message.content)
            
            if data.get("status") == "success":
                current_cart = state.get("user_cart", [])
                pid = data.get("product_id")
                action = data.get("action")
                
                if action == "add" and pid not in current_cart:
                    return {"user_cart": current_cart + [pid]}
                    
                elif action == "remove" and pid in current_cart:
                    return {"user_cart": [x for x in current_cart if x != pid]}
                    
                # NEW: Clear the cart when checkout is successful!
                elif action == "checkout":
                    print("  ↳ Checkout complete. Clearing cart.")
                    return {"user_cart": []}
                    
        except json.JSONDecodeError:
            # If the tool returned standard text instead of JSON, just ignore it
            pass

    return {}


# =============================================================================
# STEP 9: Build and Compile the Graph
# This is where we wire all nodes together with edges
# =============================================================================
def build_graph():
    """
    Assembles all nodes and edges into the final compiled LangGraph.
    Returns a compiled graph ready to run conversations.
    """

    # Create the graph builder with our state schema
    builder = StateGraph(AgentState)

    # ── Add all nodes ─────────────────────────────────────────────────────────
    builder.add_node("router_node", router_node)
    builder.add_node("agent_node", agent_node)
    builder.add_node("tools_node", tools_node)
    builder.add_node("handoff_node", handoff_node)
    builder.add_node("update_cart", update_cart_state)

    # ── Add edges (the flow) ──────────────────────────────────────────────────

    # Always start at the router
    builder.add_edge(START, "router_node")

    # After router: go to agent OR handoff depending on requires_human
    builder.add_conditional_edges(
        "router_node",
        route_after_router,
        {
            "agent_node": "agent_node",
            "handoff_node": "handoff_node"
        }
    )

    # After agent: go to tools OR end depending on whether LLM called a tool
    builder.add_conditional_edges(
        "agent_node",
        route_after_agent,
        {
            "tools_node": "tools_node",
            END: END
        }
    )

    # After tools execute: update cart state, then go back to agent
    # (The agent will read the tool result and form a reply)
    builder.add_edge("tools_node", "update_cart")
    builder.add_edge("update_cart", "agent_node")

    # Handoff is a terminal node
    builder.add_edge("handoff_node", END)

    # ── Attach the memory checkpointer ───────────────────────────────────────
    # SqliteSaver automatically saves the entire AgentState to disk
    # after every node execution, indexed by thread_id.
    # This is what gives the agent "memory" across messages.
    conn = sqlite3.connect(MEMORY_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)

    # Compile turns the builder into a runnable graph
    graph = builder.compile(checkpointer=checkpointer)

    print("✅ LangGraph compiled successfully.")
    return graph


# Build the graph once when the module loads
# (not on every message — that would be wasteful)
compiled_graph = build_graph()