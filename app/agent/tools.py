# app/agent/tools.py
#
# These are the "hands" of your AI agent — the actions it can physically take.
#
# The LLM (Groq/Llama) cannot directly touch your database. Instead, it
# decides WHICH tool to call and with WHAT arguments. LangGraph then
# executes the actual Python function and feeds the result back to the LLM.
#
# Flow:
#   User: "Do you have black jeans?"
#   LLM thinks: "I should call search_inventory(color='Black', category='Bottom')"
#   LangGraph runs: search_inventory(color='Black', category='Bottom')
#   DB returns: [{"id": 5, "name": "Straight Leg Black Jeans", "stock": 40, ...}]
#   LLM reads result and replies: "Yes! We have Straight Leg Black Jeans for $69.99 ✅"
#
# This prevents hallucination — the LLM only tells the customer what's
# actually in the database.
from typing import Optional
from langchain_core.tools import tool
from app.models.database import SessionLocal
from app.models.models import Product, Order, Thread
from datetime import datetime
import json

# =============================================================================
# TOOL 1: search_inventory
# READ operation — queries the products table
# The LLM calls this when the user asks about clothes
# =============================================================================
@tool
def search_inventory(
    category: str = None,
    color: str = None,
    vibe: str = None,
    max_price: float = None
) -> str:
    """
    Search the DenimAI product inventory.
    Use this when a customer asks about available products, styles, or stock.

    CRITICAL INSTRUCTION FOR LLM: 
    If you do not know the value for a parameter, DO NOT include that parameter in your tool call. 
    Omit it completely. Never pass 'null'.

    Args:
        category:  Type of clothing — 'Top', 'Bottom', or 'Outerwear'
        color:     Color filter — e.g. 'Black', 'White', 'Navy'
        vibe:      Style aesthetic — 'Heritage', 'Minimalist', 'Streetwear', 'Smart Casual'
        max_price: Maximum price in USD (optional filter)

    Returns:
        A formatted string listing matching products, or a message if none found.
    """
    db = SessionLocal()
    try:
        # Start with all products
        query = db.query(Product)

        # Apply filters only if the LLM provided them
        # Using ilike() for case-insensitive matching
        # (so "black" and "Black" both work)
        if category:
            query = query.filter(Product.category.ilike(f"%{category}%"))
        if color:
            query = query.filter(Product.color.ilike(f"%{color}%"))
        if vibe:
            query = query.filter(Product.vibe.ilike(f"%{vibe}%"))
        if max_price:
            query = query.filter(Product.price <= max_price)

        products = query.all()

        if not products:
            return (
                "No products found matching those filters. "
                "Try different color, vibe, or category."
            )

        # Format results into a clear string the LLM can read and talk about
        lines = [f"Found {len(products)} product(s):\n"]
        for p in products:
            stock_status = f"{p.stock} in stock" if p.stock > 0 else "❌ OUT OF STOCK"
            lines.append(
                f"  • [ID: {p.id}] {p.name} | {p.color} | {p.vibe} | "
                f"{p.fit} fit | ${p.price:.2f} | {stock_status}"
            )

        return "\n".join(lines)

    finally:
        db.close()


# =============================================================================
# TOOL 2: manage_cart
# UPDATE operation — modifies the cart inside LangGraph state
# Note: This doesn't write to the database at all!
# The cart lives in AgentState and is persisted by the SqliteSaver.
# =============================================================================
@tool
def manage_cart(product_id: int, action: str) -> str:
    """Add or remove a product from the customer's cart."""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(Product.id == product_id).first()

        if not product:
            return json.dumps({"error": f"Product ID {product_id} not found."})

        if action == "add":
            if product.stock == 0:
                return json.dumps({"error": f"{product.name} is out of stock."})
            
            # Return strict JSON so graph.py can parse it flawlessly
            return json.dumps({
                "status": "success",
                "action": "add",
                "product_id": product_id,
                "message": f"✅ Added {product.name} to cart."
            })

        elif action == "remove":
            return json.dumps({
                "status": "success",
                "action": "remove",
                "product_id": product_id,
                "message": f"✅ Removed {product.name} from cart."
            })
    finally:
        db.close()


# =============================================================================
# TOOL 3: finalize_order
# UPDATE + CREATE operation — the checkout process
# This is the only tool that permanently writes to the database:
#   1. Checks stock one final time (race condition protection)
#   2. Decrements stock for each item in the cart
#   3. Creates an Order record for each item
#   4. Returns a receipt summary
# =============================================================================
@tool
def finalize_order(cart_product_ids: list, thread_id: str) -> str:
    """
    Complete the purchase for all items in the customer's cart.
    Decrements product stock and creates order records.

    Args:
        cart_product_ids: List of product IDs from the cart state
        thread_id:        The user's unique thread ID for linking the order

    Returns:
        A receipt string confirming what was purchased, or an error message.
    """
    if not cart_product_ids:
        return "❌ Your cart is empty. Add some products first!"

    db = SessionLocal()
    try:
        receipt_lines = ["🧾 *Order Confirmation*\n"]
        total = 0.0
        failed_items = []

        for product_id in cart_product_ids:
            product = db.query(Product).filter(Product.id == product_id).first()

            if not product:
                failed_items.append(f"Product ID {product_id} (not found)")
                continue

            if product.stock < 1:
                failed_items.append(f"{product.name} (out of stock)")
                continue

            # ── WRITE: Decrement stock ────────────────────────────────────────
            product.stock -= 1

            # ── WRITE: Create order record ────────────────────────────────────
            order = Order(
                thread_id=thread_id,
                product_id=product.id,
                quantity=1,
                total_price=product.price,
                ordered_at=datetime.utcnow()
            )
            db.add(order)

            total += product.price
            receipt_lines.append(f"  ✅ {product.name} ({product.color}) — ${product.price:.2f}")

        # Commit all changes in one transaction
        # If anything fails, nothing gets saved (atomic operation)
        db.commit()

        if failed_items:
            receipt_lines.append(f"\n⚠️ Couldn't process: {', '.join(failed_items)}")

        receipt_lines.append(f"\n💳 *Total: ${total:.2f}*")
        receipt_lines.append("Thank you for shopping with DenimAI! 🛍️")

        receipt_string = "\n".join(receipt_lines)
        
        return json.dumps({
            "status": "success",
            "action": "checkout",
            "message": receipt_string
        })

    except Exception as e:
        db.rollback()  # If anything goes wrong, undo ALL changes
        return f"❌ Checkout failed: {str(e)}. Please try again."

    finally:
        db.close()


# =============================================================================
# TOOL 4: get_cart_summary
# READ operation — lets the LLM tell the user what's in their cart
# =============================================================================
@tool
def get_cart_summary(cart_product_ids: list) -> str:
    """
    Get a human-readable summary of the items currently in the cart.
    Use this when the customer asks 'what's in my cart?' or before checkout.

    Args:
        cart_product_ids: List of product IDs from the cart state

    Returns:
        A formatted cart summary with items and total price.
    """
    if not cart_product_ids:
        return "Your cart is empty. Want me to help you find something? 👕"

    db = SessionLocal()
    try:
        lines = ["🛒 *Your Cart:*\n"]
        total = 0.0

        for product_id in cart_product_ids:
            product = db.query(Product).filter(Product.id == product_id).first()
            if product:
                lines.append(f"  • {product.name} ({product.color}) — ${product.price:.2f}")
                total += product.price

        lines.append(f"\n*Subtotal: ${total:.2f}*")
        lines.append("Say 'checkout' to complete your order!")

        return "\n".join(lines)

    finally:
        db.close()


# Export all tools as a list for easy import in graph.py
ALL_TOOLS = [search_inventory, manage_cart, finalize_order, get_cart_summary]