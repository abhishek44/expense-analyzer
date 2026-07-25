"""Quick check of the database state."""
import sys, os, logging
logging.disable(logging.CRITICAL)
sys.path.append(os.getcwd())

from app.database import SessionLocal, init_db
from app.models import Transaction, Category

init_db()
s = SessionLocal()

# Overall counts
total = s.query(Transaction).count()
with_l1 = s.query(Transaction).filter(Transaction.l1_category_id.isnot(None)).count()
with_l2 = s.query(Transaction).filter(Transaction.l2_category_id.isnot(None)).count()
pending = s.query(Transaction).filter(Transaction.review_status == "pending").count()
approved = s.query(Transaction).filter(Transaction.review_status == "approved").count()
no_cat = s.query(Transaction).filter(Transaction.l1_category_id.is_(None)).count()

print("=== DB State ===")
print(f"Total:       {total}")
print(f"With L1:     {with_l1}")
print(f"With L2:     {with_l2}")
print(f"No category: {no_cat}")
print(f"Pending:     {pending}")
print(f"Approved:    {approved}")

# Check a few via to_dict()
print("\n=== Sample transactions (via to_dict) ===")
txns = s.query(Transaction).filter(Transaction.l1_category_id.isnot(None)).limit(3).all()
for t in txns:
    d = t.to_dict()
    print(f"  id={d['id']}  l1_cat_id={d['l1_category_id'][:8]}...  l1_name={d['l1_category_name']}  l2_name={d['l2_category_name']}  review={d['review_status']}")

# Check transactions without categories
print("\n=== Transactions without categories ===")
no_cats = s.query(Transaction).filter(Transaction.l1_category_id.is_(None)).all()
for t in no_cats:
    d = t.to_dict()
    print(f"  id={d['id']}  details={d['raw_details'][:60]}  review={d['review_status']}")

# Check category table
print("\n=== Categories ===")
l1s = s.query(Category).filter(Category.level == 1).order_by(Category.name).all()
for c in l1s:
    children = s.query(Category).filter(Category.parent_id == c.id).all()
    child_names = ", ".join(ch.name for ch in children)
    print(f"  {c.name} (id={c.id[:8]}...) -> [{child_names}]")

# Check if any transaction has a category_id that doesn't match a category in DB
print("\n=== Orphan category references ===")
cat_ids = set(c.id for c in s.query(Category).all())
orphan_l1 = s.query(Transaction).filter(
    Transaction.l1_category_id.isnot(None),
    ~Transaction.l1_category_id.in_(cat_ids)
).count()
orphan_l2 = s.query(Transaction).filter(
    Transaction.l2_category_id.isnot(None),
    ~Transaction.l2_category_id.in_(cat_ids)
).count()
print(f"  Orphan L1 refs: {orphan_l1}")
print(f"  Orphan L2 refs: {orphan_l2}")

s.close()
