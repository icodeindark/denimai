# app/models/models.py
#
# This file defines the "shape" of your database tables using SQLAlchemy.
# Think of each class here as a blueprint for one table.
# SQLAlchemy reads these blueprints and creates the actual tables for you.
#
# We have 3 tables:
#   1. Thread  — tracks every unique user (one row per person per platform)
#   2. Product — your store's inventory (the clothes you sell)
#   3. Order   — a log of every successful purchase

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

# Base is the "parent class" all our table models inherit from.
# SQLAlchemy uses it to track all the tables we define.
from app.models.database import Base


# =============================================================================
# TABLE 1: Thread
# Tracks every unique user who messages you on any platform.
# One row = one unique person.
# The thread_id is their unique fingerprint (e.g. "whatsapp_918138894448")
# =============================================================================
class Thread(Base):
    __tablename__ = "threads"

    id            = Column(Integer, primary_key=True, index=True)
    thread_id     = Column(String, unique=True, index=True, nullable=False)
    # e.g. "whatsapp_918138894448" — this is the LangGraph memory key too

    platform      = Column(String, nullable=False)
    # e.g. "whatsapp", "messenger", "instagram"

    user_name     = Column(String, default="Customer")
    # Name from the webhook payload (WhatsApp provides it, others don't always)

    last_active   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Auto-updates every time the user sends a message — useful for analytics

    # Link this thread to all orders placed by this user
    orders = relationship("Order", back_populates="thread")

    def __repr__(self):
        return f"<Thread {self.thread_id} | {self.platform}>"


# =============================================================================
# TABLE 2: Product
# Your store's clothing inventory.
# The agent queries THIS table (not its own memory) for real stock info.
# This is what prevents the LLM from hallucinating products.
# =============================================================================
class Product(Base):
    __tablename__ = "products"

    id       = Column(Integer, primary_key=True, index=True)
    name     = Column(String, nullable=False)
    # e.g. "Classic Oxford Shirt"

    category = Column(String, nullable=False)
    # e.g. "Top", "Bottom", "Outerwear"

    vibe     = Column(String, nullable=False)
    # e.g. "Old Money", "Minimalist", "Streetwear"
    # This is a DenimAI-specific filter — lets users say "show me Old Money fits"

    color    = Column(String, nullable=False)
    # e.g. "Black", "White", "Navy"

    fit      = Column(String, nullable=True)
    # e.g. "Slim", "Regular", "Oversized"

    price    = Column(Float, nullable=False)
    # In USD e.g. 49.99

    stock    = Column(Integer, default=0)
    # Number of units available. Decremented on checkout.
    # If 0, the agent should tell the customer it's out of stock.

    # Link this product to all orders that include it
    orders = relationship("Order", back_populates="product")

    def __repr__(self):
        return f"<Product #{self.id} | {self.name} | {self.color} | Stock: {self.stock}>"


# =============================================================================
# TABLE 3: Order
# A permanent log of every successful checkout.
# Created when finalize_order() is called and payment/stock check passes.
# =============================================================================
class Order(Base):
    __tablename__ = "orders"

    id         = Column(Integer, primary_key=True, index=True)

    # Foreign key: links this order to the user who placed it
    thread_id  = Column(String, ForeignKey("threads.thread_id"), nullable=False)

    # Foreign key: links this order to the specific product bought
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    quantity   = Column(Integer, default=1)
    # How many units of this product were ordered

    total_price = Column(Float, nullable=False)
    # Snapshot of (product.price × quantity) at time of purchase
    # Stored separately so price changes don't affect order history

    ordered_at  = Column(DateTime, default=datetime.utcnow)
    # Timestamp of the purchase — immutable record

    # Relationships: lets you do order.thread and order.product in Python
    thread  = relationship("Thread", back_populates="orders")
    product = relationship("Product", back_populates="orders")

    def __repr__(self):
        return f"<Order #{self.id} | Thread: {self.thread_id} | Product: {self.product_id}>"