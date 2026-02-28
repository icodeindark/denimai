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
    """Insert products only if they don't already exist"""

    products = [
        Product(
            name="Ultra Black Slim Jeans",
            category="Bottom",
            vibe="Minimalist",
            color="Jet Black",
            fit="Slim",
            price=69.99,
            stock=60
        ),
        Product(
            name="Baggy Ripped Street Jeans",
            category="Bottom",
            vibe="Streetwear",
            color="Light Wash",
            fit="Baggy",
            price=89.99,
            stock=38
        ),
        Product(
            name="Japanese Selvedge Indigo Jeans",
            category="Bottom",
            vibe="Heritage",
            color="Indigo",
            fit="Slim Straight",
            price=149.99,
            stock=18
        ),
        Product(
            name="Stretch Business Casual Jeans",
            category="Bottom",
            vibe="Smart Casual",
            color="Dark Blue",
            fit="Slim Tapered",
            price=99.99,
            stock=28
        ),
    ]

    inserted = 0

    for product in products:
        exists = db.query(Product).filter(
            Product.name == product.name
        ).first()

        if not exists:
            db.add(product)
            inserted += 1

    db.commit()
    print(f"✅ Added {inserted} new products (no duplicates).")


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