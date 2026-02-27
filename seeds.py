# seed.py  (lives in your project ROOT, next to main.py)
#
# Run this ONCE to:
#   1. Create the database tables
#   2. Insert sample products into the inventory
#   3. Verify everything looks correct
#
# How to run:
#   python seed.py
#
# You can re-run it safely — it checks before inserting duplicates.

import sys
import os

# Make sure Python can find your app/ package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.models.database import engine, SessionLocal, Base
from app.models.models import Product, Thread, Order

def create_tables():
    """Creates all tables defined in models.py"""
    # Import models so Base registers them before create_all
    Base.metadata.create_all(bind=engine)
    print("✅ Tables created: threads, products, orders")


def seed_products(db):
    """Inserts sample products if the table is empty"""

    # Don't duplicate if already seeded
    existing = db.query(Product).count()
    if existing > 0:
        print(f"ℹ️  Products table already has {existing} items. Skipping seed.")
        return

    products = [
        # ── Heritage / Classic Vibes ──────────────────────────────────────────
        Product(
            name="Raw Selvedge Denim Jeans",
            category="Bottom",
            vibe="Heritage",
            color="Deep Indigo",
            fit="Straight",
            price=129.99,
            stock=30
        ),
        Product(
            name="Classic Trucker Jacket",
            category="Outerwear",
            vibe="Heritage",
            color="Light Blue",
            fit="Regular",
            price=89.99,
            stock=20
        ),
        Product(
            name="Vintage Denim Western Shirt",
            category="Top",
            vibe="Heritage",
            color="Medium Wash",
            fit="Slim",
            price=69.99,
            stock=15
        ),

        # ── Minimalist Vibes ──────────────────────────────────────────────────
        Product(
            name="Essential Black Denim Jeans",
            category="Bottom",
            vibe="Minimalist",
            color="Black",
            fit="Slim",
            price=79.99,
            stock=50
        ),
        Product(
            name="Solid Monochrome Denim Shirt",
            category="Top",
            vibe="Minimalist",
            color="Black",
            fit="Regular",
            price=59.99,
            stock=40
        ),
        Product(
            name="Clean White Denim Jacket",
            category="Outerwear",
            vibe="Minimalist",
            color="White",
            fit="Regular",
            price=99.99,
            stock=35
        ),

        # ── Streetwear Vibes ──────────────────────────────────────────────────
        Product(
            name="Oversized Acid Wash Jacket",
            category="Outerwear",
            vibe="Streetwear",
            color="Acid Wash Grey",
            fit="Oversized",
            price=109.99,
            stock=25
        ),
        Product(
            name="Distressed Carpenter Jeans",
            category="Bottom",
            vibe="Streetwear",
            color="Washed Blue",
            fit="Baggy",
            price=84.99,
            stock=30
        ),

        # ── Smart Casual Vibes ────────────────────────────────────────────────
        Product(
            name="Dark Wash Tapered Jeans",
            category="Bottom",
            vibe="Smart Casual",
            color="Dark Navy",
            fit="Tapered",
            price=89.99,
            stock=0  # ← Out of stock — tests the agent's stock-check logic
        ),
        Product(
            name="Denim Overshirt / Shacket",
            category="Top",
            vibe="Smart Casual",
            color="Indigo",
            fit="Regular",
            price=74.99,
            stock=22
        ),
    ]

    db.add_all(products)
    db.commit()
    print(f"✅ Seeded {len(products)} products into the inventory.")


def verify(db):
    """Prints a summary of what's in the database"""
    print("\n📦 Current Inventory:")
    print(f"{'ID':<4} {'Name':<30} {'Vibe':<15} {'Color':<10} {'Stock':<6} {'Price'}")
    print("-" * 80)
    for p in db.query(Product).all():
        stock_str = str(p.stock) if p.stock > 0 else "❌ OUT"
        print(f"{p.id:<4} {p.name:<30} {p.vibe:<15} {p.color:<10} {stock_str:<6} ${p.price}")


if __name__ == "__main__":
    print("🌱 Starting database seed...\n")

    # Step 1: Create tables
    create_tables()

    # Step 2: Open a session and seed data
    db = SessionLocal()
    try:
        seed_products(db)
        verify(db)
    finally:
        db.close()

    print("\n✅ Done! Your database is ready.")
    print("   Store DB:  denimAI_store.db")
    print("   Run your app: uvicorn app.main:app --reload")