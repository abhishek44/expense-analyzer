
import sys
import os
import uuid
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.append(os.getcwd())

from app.database import SessionLocal
from app.models import Category, Transaction

def migrate():
    session = SessionLocal()
    try:
        # Get unique categories from transactions that aren't empty
        # We filter out empty strings or None
        transactions = session.query(Transaction).filter(Transaction.Category != None, Transaction.Category != "").all()
        
        unique_names = set()
        for t in transactions:
            if t.Category:
                unique_names.add(t.Category.strip())
        
        print(f"Found {len(unique_names)} unique categories in transactions.")
        
        created_count = 0
        updated_transactions = 0
        
        for name in unique_names:
            # Check if exists
            cat = session.query(Category).filter(Category.name == name).first()
            if not cat:
                print(f"Creating new category: {name}")
                cat = Category(
                    id=str(uuid.uuid4()),
                    name=name,
                    type="EXPENSE", # Default to EXPENSE
                    is_archived=0,
                    created_at=datetime.now(),
                    updated_at=datetime.now()
                )
                session.add(cat)
                created_count += 1
                session.flush() # Ensure cat.id is available if generated (we gen it manually though)
            
            # Backfill transactions that have this category name but no category_id
            # Or ensuring they link to this category
            trxs_to_update = session.query(Transaction).filter(
                Transaction.Category == name,
                (Transaction.category_id == None) | (Transaction.category_id == "")
            ).all()
            
            for t in trxs_to_update:
                t.category_id = cat.id
                updated_transactions += 1
                
        session.commit()
        print(f"Migration completed.")
        print(f"Created {created_count} new categories.")
        print(f"Updated {updated_transactions} transactions with category_id.")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    migrate()
