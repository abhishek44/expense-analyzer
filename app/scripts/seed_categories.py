"""
Seed the categories table with the 2-level hierarchy.
Also contains OLD_TO_NEW_MAPPING for migrating flat category names.

Usage:
    python scripts/seed_categories.py
"""

import sys
import os
import uuid
from datetime import datetime

sys.path.append(os.getcwd())

from app.database import SessionLocal, init_db
from app.models import Category

# Full 2-level hierarchy: { L1_name: { domain, color, children: [L2 names] } }
CATEGORY_HIERARCHY = {
    "Food & Dining": {
        "domain": "NECESSITIES",
        "color": "#FF6B35",
        "children": ["Restaurants", "Delivery", "Coffee/Snacks", "Office Lunch"],
    },
    "Groceries": {
        "domain": "NECESSITIES",
        "color": "#4CAF50",
        "children": ["Supermarket", "Dairy/Milk", "Fruits/Vegetables", "Household Supplies"],
    },
    "Transport": {
        "domain": "NECESSITIES",
        "color": "#2196F3",
        "children": ["Fuel/Petrol", "Cab/Auto", "Public Transit", "Parking"],
    },
    "Shopping": {
        "domain": "LIFESTYLE",
        "color": "#9C27B0",
        "children": ["Clothing", "Electronics", "Home/Kitchen", "Online Marketplace"],
    },
    "Bills & Utilities": {
        "domain": "NECESSITIES",
        "color": "#607D8B",
        "children": ["Electricity", "Internet/Phone", "Water/Gas", "Rent"],
    },
    "Health": {
        "domain": "NECESSITIES",
        "color": "#E91E63",
        "children": ["Doctor/Hospital", "Medicines", "Lab Tests", "Insurance"],
    },
    "Entertainment": {
        "domain": "LIFESTYLE",
        "color": "#FF9800",
        "children": ["Streaming/OTT", "Movies", "Gaming"],
    },
    "Personal": {
        "domain": "LIFESTYLE",
        "color": "#00BCD4",
        "children": ["Salon/Grooming", "Gym/Fitness", "Tobacco & Drinks"],
    },
    "Financial": {
        "domain": "FINANCIAL",
        "color": "#795548",
        "children": ["Credit Card Bill", "EMI", "Investment", "Fees/Charges"],
    },
    "Transfers": {
        "domain": "FINANCIAL",
        "color": "#9E9E9E",
        "children": ["Internal Transfer", "Refund/Cashback", "Loan"],
    },
    "Travel": {
        "domain": "LIFESTYLE",
        "color": "#3F51B5",
        "children": ["Accommodation", "Local Transport", "Activities"],
    },
    "Income": {
        "domain": "INCOME",
        "color": "#1B5E20",
        "children": ["Salary", "Freelance", "Interest/Dividend"],
    },
}

# Maps every old flat Category string to (L1_name, L2_name or None)
OLD_TO_NEW_MAPPING = {
    "Food": ("Food & Dining", "Restaurants"),
    "Grocery": ("Groceries", "Supermarket"),
    "Milk": ("Groceries", "Dairy/Milk"),
    "Transport": ("Transport", "Public Transit"),
    "Petrol": ("Transport", "Fuel/Petrol"),
    "Clothes": ("Shopping", "Clothing"),
    "Home": ("Bills & Utilities", None),
    "Health & Meds": ("Health", "Medicines"),
    "Entertainment": ("Entertainment", None),
    "Personal": ("Personal", None),
    "Self": ("Personal", "Salon/Grooming"),
    "Ciggerate": ("Personal", "Tobacco & Drinks"),
    "Credit card bill": ("Financial", "Credit Card Bill"),
    "Investment": ("Financial", "Investment"),
    "Refund": ("Transfers", "Refund/Cashback"),
    "Cashback": ("Transfers", "Refund/Cashback"),
    "Trip": ("Travel", None),
    "Salary": ("Income", "Salary"),
}


def seed():
    init_db()
    session = SessionLocal()
    try:
        existing = session.query(Category).count()
        if existing > 0:
            print(f"Categories table already has {existing} rows. Skipping seed.")
            print("To re-seed, delete the database first.")
            return

        now = datetime.now()
        l1_count = 0
        l2_count = 0

        for l1_name, info in CATEGORY_HIERARCHY.items():
            l1_id = str(uuid.uuid4())
            l1 = Category(
                id=l1_id,
                name=l1_name,
                level=1,
                parent_id=None,
                domain=info["domain"],
                color_hex=info["color"],
                created_at=now,
                updated_at=now,
            )
            session.add(l1)
            l1_count += 1

            for l2_name in info["children"]:
                l2 = Category(
                    id=str(uuid.uuid4()),
                    name=l2_name,
                    level=2,
                    parent_id=l1_id,
                    domain=info["domain"],
                    color_hex=info["color"],
                    created_at=now,
                    updated_at=now,
                )
                session.add(l2)
                l2_count += 1

        session.commit()
        print(f"Seeded {l1_count} L1 categories and {l2_count} L2 sub-categories.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
