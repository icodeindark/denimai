# app/models/database.py
#
# This file is the "engine room" for your database.
# It does 3 things:
#   1. Creates the SQLite engine (the actual connection to the .db file)
#   2. Defines Base (the parent class all models inherit from)
#   3. Provides get_db() — a safe way to open and close DB sessions
#
# WHY TWO SQLITE FILES?
# ─────────────────────
# denimAI_store.db   → YOUR business data (products, orders, threads)
#                      Managed by SQLAlchemy. YOU control the schema.
#
# langgraph_memory.db → LangGraph's checkpointer data (chat history, cart state)
#                       Managed automatically by LangGraph's SqliteSaver.
#                       You never write to this directly.
#
# Keeping them separate makes debugging easier — you can wipe chat memory
# without touching your product catalog, and vice versa.

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# ─── Business Database ───────────────────────────────────────────────────────

# "sqlite:///./denimAI_store.db" means:
#   sqlite:///  = use SQLite
#   ./          = in the current working directory (your project root)
#   denimAI_store.db = the filename
#
# connect_args={"check_same_thread": False} is required for SQLite when
# used with FastAPI (which runs async, so multiple threads may share the DB)

STORE_DB_URL = "sqlite:///./denimAI_store.db"

engine = create_engine(
    STORE_DB_URL,
    connect_args={"check_same_thread": False}
)

# SessionLocal is a "session factory" — every time you call SessionLocal()
# you get a fresh database session (like opening a new tab in a browser)
SessionLocal = sessionmaker(
    autocommit=False,   # We manually commit changes (safer, more control)
    autoflush=False,    # Don't auto-save to DB until we say so
    bind=engine
)

# Base is the parent class for all your SQLAlchemy models (Thread, Product, Order)
# When you call Base.metadata.create_all(engine), it reads all classes that
# inherit from Base and creates their tables in the database.
Base = declarative_base()


# ─── LangGraph Memory Database ───────────────────────────────────────────────

# This path is used in graph.py when we create the SqliteSaver.
# We define it here so there's one central place to change it.
MEMORY_DB_PATH = "./langgraph_memory.db"


# ─── Session Helper ──────────────────────────────────────────────────────────

def get_db():
    """
    A generator function that safely opens and closes a DB session.
    
    How to use it in your tools:
    
        db = next(get_db())
        results = db.query(Product).all()
        # ... do your work ...
        db.close()  ← automatically handled by the finally block below
    
    The try/finally pattern guarantees the session is ALWAYS closed,
    even if an error occurs mid-query. Without this, you'd leak connections.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Creates all tables in the database if they don't exist yet.
    Call this once on app startup (from main.py).
    
    SQLAlchemy reads all models that inherit from Base and generates
    the CREATE TABLE SQL for you automatically.
    """
    # Import models here so Base "knows" about them before create_all runs
    from app.models import models  # noqa: F401 — import needed for side effects
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created (or already exist).")