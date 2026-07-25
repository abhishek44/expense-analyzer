"""
Re-import transactions from the backup CSV into the new schema.
Maps old flat Category names to L1/L2 category IDs.

Usage:
    python scripts/reimport_data.py
"""

import sys
import os
import csv
from datetime import datetime
from collections import defaultdict

sys.path.append(os.getcwd())

from app.database import SessionLocal, init_db
from app.models import Transaction, Category, MerchantMapping, ReviewStatus, CategorisedBy
from app.services.csv_service import compute_derived_fields
from app.scripts.seed_categories import OLD_TO_NEW_MAPPING

BACKUP_CSV = os.path.join(os.getcwd(), "data_backup.csv")


def reimport():
    init_db()
    session = SessionLocal()

    try:
        existing = session.query(Transaction).count()
        if existing > 0:
            print(f"Transactions table already has {existing} rows. Aborting.")
            print("Delete the database first if you want to re-import.")
            return

        # Build category lookup: (name, parent_id) -> id
        categories = session.query(Category).all()
        l1_by_name = {c.name: c.id for c in categories if c.level == 1}
        l2_by_name_parent = {}
        for c in categories:
            if c.level == 2:
                l2_by_name_parent[(c.name, c.parent_id)] = c.id

        def resolve_category(old_cat_name):
            """Map old flat category name to (l1_id, l2_id)."""
            if not old_cat_name or not old_cat_name.strip():
                return None, None

            old_cat_name = old_cat_name.strip()
            mapping = OLD_TO_NEW_MAPPING.get(old_cat_name)
            if not mapping:
                return None, None

            l1_name, l2_name = mapping
            l1_id = l1_by_name.get(l1_name)
            l2_id = None
            if l2_name and l1_id:
                l2_id = l2_by_name_parent.get((l2_name, l1_id))

            return l1_id, l2_id

        # Read backup CSV
        if not os.path.exists(BACKUP_CSV):
            print(f"Backup CSV not found at {BACKUP_CSV}")
            sys.exit(1)

        with open(BACKUP_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Read {len(rows)} rows from backup CSV")

        imported = 0
        for row in rows:
            raw_date = (row.get("Date") or "").strip()
            raw_details = (row.get("Details") or "").strip()
            debit_str = (row.get("Debit") or "").strip()
            credit_str = (row.get("Credit") or "").strip()
            acc_name = (row.get("AccountName") or "").strip() or None
            acc_type = (row.get("AccountType") or "").strip() or None
            old_category = (row.get("Category") or "").strip()
            notes = (row.get("Notes") or "").strip() or None
            review_status_str = (row.get("ReviewStatus") or "").strip()
            review_dt_str = (row.get("ReviewdateTime") or "").strip()
            filename = (row.get("Filename") or "imported").strip()

            # Parse amounts
            debit = None
            credit = None
            if debit_str:
                try:
                    debit = float(debit_str.replace(",", ""))
                except ValueError:
                    pass
            if credit_str:
                try:
                    credit = float(credit_str.replace(",", ""))
                except ValueError:
                    pass

            # Compute derived fields
            derived = compute_derived_fields(raw_date, raw_details, debit, credit)

            # Map category
            l1_id, l2_id = resolve_category(old_category)

            # Determine review state
            was_reviewed = review_status_str == "reviewed"
            review_status = ReviewStatus.APPROVED.value if was_reviewed else ReviewStatus.PENDING.value
            categorised_by = CategorisedBy.USER.value if (was_reviewed and l1_id) else None

            # Parse review datetime
            reviewed_at = None
            if review_dt_str:
                for fmt in ["%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"]:
                    try:
                        reviewed_at = datetime.strptime(review_dt_str, fmt)
                        break
                    except ValueError:
                        continue

            t = Transaction(
                raw_date=raw_date,
                raw_details=raw_details,
                debit=debit,
                credit=credit,
                account_name=acc_name,
                account_type=acc_type,
                filename=filename,
                uploaded_at=datetime.now(),
                notes=notes,
                l1_category_id=l1_id,
                l2_category_id=l2_id,
                l2_confidence=1.0 if (was_reviewed and l1_id) else None,
                categorised_by=categorised_by,
                review_status=review_status,
                reviewed_at=reviewed_at,
                **derived,
            )
            session.add(t)
            imported += 1

        session.commit()
        print(f"Imported {imported} transactions")

        # Stats
        with_l1 = session.query(Transaction).filter(Transaction.l1_category_id.isnot(None)).count()
        pending = session.query(Transaction).filter(Transaction.review_status == ReviewStatus.PENDING.value).count()
        print(f"  With L1 category: {with_l1}")
        print(f"  Pending review: {pending}")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


def rebuild_merchant_mappings():
    """Rebuild merchant_mappings from reviewed transactions."""
    session = SessionLocal()
    try:
        reviewed = session.query(Transaction).filter(
            Transaction.review_status != ReviewStatus.PENDING.value,
            Transaction.l1_category_id.isnot(None),
            Transaction.merchant_name.isnot(None),
            Transaction.merchant_name != "",
        ).all()

        print(f"\nRebuilding merchant_mappings from {len(reviewed)} reviewed transactions...")

        merchant_data = defaultdict(list)
        for t in reviewed:
            merchant_data[t.merchant_name].append({
                "l1_id": t.l1_category_id,
                "l2_id": t.l2_category_id,
                "date": t.parsed_date,
            })

        created = 0
        for merchant_name, entries in merchant_data.items():
            existing = session.query(MerchantMapping).filter(MerchantMapping.merchant_name == merchant_name).first()
            if existing:
                continue

            l1_ids = set(e["l1_id"] for e in entries)
            is_ambiguous = 1 if len(l1_ids) > 1 else 0

            # Most common L1
            from collections import Counter
            l1_counts = Counter(e["l1_id"] for e in entries)
            most_common_l1 = l1_counts.most_common(1)[0][0]
            # Get L2 from first entry with this L1
            l2_id = next((e["l2_id"] for e in entries if e["l1_id"] == most_common_l1 and e["l2_id"]), None)

            dates = [e["date"] for e in entries if e["date"]]
            last_seen = max(dates) if dates else None

            mapping = MerchantMapping(
                merchant_name=merchant_name,
                default_l1_category_id=most_common_l1,
                default_l2_category_id=l2_id,
                occurrence_count=len(entries),
                last_seen_date=last_seen,
                is_ambiguous=is_ambiguous,
                notes_required=is_ambiguous,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(mapping)
            created += 1

        session.commit()
        ambiguous = sum(1 for entries in merchant_data.values() if len(set(e["l1_id"] for e in entries)) > 1)
        print(f"Created {created} merchant mappings ({ambiguous} ambiguous)")

    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Re-import: Backup CSV -> New Schema")
    print("=" * 60)

    reimport()
    rebuild_merchant_mappings()

    print("\nDone.")
