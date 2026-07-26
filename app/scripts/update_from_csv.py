"""
Update the database from an edited transaction CSV.

Steps:
  1. Prune the transactions table (delete all rows).
  2. Sync categories: the CSV's l1/l2 category names are the source of truth.
     - Add new L1/L2 categories found in the CSV but missing from the DB.
     - Fix typos/case in the DB to match the CSV.
     - Archive (or delete) DB categories that are NOT referenced by any CSV row.
  3. Insert all CSV rows as transactions, mapping l1/l2 names -> category IDs.
  4. Merchant mapping is intentionally skipped.

Usage:
    python app/scripts/update_from_csv.py --csv updated_transaction.csv
    python app/scripts/update_from_csv.py --repair-derived-financials
"""

import argparse
import sys
import csv
import math
from datetime import datetime, date
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.append(str(Path.cwd()))

from app.database import SessionLocal, init_db
from app.models import Transaction, Category, ReviewStatus, CategorisedBy
from app.services.csv_service import compute_derived_fields
from app.scripts.seed_categories import CATEGORY_HIERARCHY

DEFAULT_CSV_FILENAMES = ("updated_transaction.csv", "updated_transactions.csv")

# These source columns are needed to rebuild a transaction accurately. Derived
# columns (including amount and flow_direction) are intentionally not imported.
# id,raw_date,raw_details,debit,credit,account_name,account_type,filename,notes,amount,flow_direction,parsed_date,merchant_name,cleaned_details,l1_category_name,l2_category_name,categorised_by,review_status,reviewed_at,statement_date,mapping_date
REQUIRED_COLUMNS = {
    "raw_date", "raw_details", "debit", "credit",
    "account_name", "account_type", "filename"
}

# Supported date formats for flexible parsing
DATE_FORMATS = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%y", "%d-%b-%Y"]


def normalize_amount(value: str | None, *, field_name: str, row_number: int) -> float | None:
    """Parse a non-negative monetary CSV value without silently masking errors."""
    if not value or not value.strip():
        return None
    try:
        amount = Decimal(value.strip().replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError(
            f"Row {row_number}: {field_name} must be a valid number, got {value!r}"
        ) from exc

    if not amount.is_finite() or amount < 0:
        raise ValueError(
            f"Row {row_number}: {field_name} must be a finite, non-negative number, got {value!r}"
        )
    return float(amount.quantize(Decimal("0.01")))


def validate_transaction_amounts(
    debit: float | None, credit: float | None, *, row_number: int
) -> None:
    """Reject ambiguous rows rather than choosing an arbitrary signed amount."""
    for field_name, value in (("debit", debit), ("credit", credit)):
        if value is not None and (not math.isfinite(value) or value < 0):
            raise ValueError(
                f"Row {row_number}: {field_name} must be a finite, non-negative number"
            )
    if (debit or 0) > 0 and (credit or 0) > 0:
        raise ValueError(
            f"Row {row_number}: Debit and Credit cannot both be greater than zero"
        )


def parse_date_flexible(value: str | None) -> date | None:
    """Parse a date string in any common format and return a date object."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def parse_datetime_flexible(value: str | None) -> datetime | None:
    """Parse a datetime string in any common format."""
    if not value or not value.strip():
        return None
    value = value.strip()
    for fmt in ["%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M:%S", "%d-%m-%Y %H:%M",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def read_csv(path: Path) -> list[dict]:
    """Read the CSV and return rows as list of dicts."""
    if not path.is_file():
        print(f"ERROR: CSV not found at {path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        headers = set(reader.fieldnames or [])
        missing = REQUIRED_COLUMNS - headers
        if missing:
            raise ValueError(f"CSV is missing required columns: {sorted(missing)}")
        rows = list(reader)

    print(f"Read {len(rows)} rows from CSV")
    return rows


def validate_rows(rows: list[dict]) -> None:
    """Validate all financial inputs before a refresh can alter the database."""
    for row_number, row in enumerate(rows, start=2):  # account for CSV header
        debit = normalize_amount(row.get("debit"), field_name="debit", row_number=row_number)
        credit = normalize_amount(row.get("credit"), field_name="credit", row_number=row_number)
        validate_transaction_amounts(debit, credit, row_number=row_number)


def resolve_csv_path(csv_path: str | None) -> Path:
    """Resolve an explicit CSV path or the one supported default file name."""
    if csv_path:
        return Path(csv_path).expanduser().resolve()

    candidates = [Path.cwd() / name for name in DEFAULT_CSV_FILENAMES]
    existing = [path for path in candidates if path.is_file()]
    if len(existing) == 1:
        return existing[0]
    if not existing:
        raise FileNotFoundError(
            "No default CSV found. Pass --csv PATH, or add one of: "
            + ", ".join(DEFAULT_CSV_FILENAMES)
        )
    raise ValueError(
        "More than one default CSV exists. Pass --csv PATH to select the intended file."
    )


def collect_csv_categories(rows: list[dict]) -> dict[str, set[str]]:
    """
    Build a dict of { l1_name: set(l2_names) } from the CSV.

    When the CSV contains case variants of the same name (e.g. 'Others' and 'others'),
    the most frequent spelling wins and all rows are normalised in-place.
    """
    from collections import Counter

    # Count occurrences of each exact L1 and each (L1_lower, L2_exact) pair
    l1_counts: Counter = Counter()
    # For L2, we track per L1 (lowered) to handle per-parent dedup
    l2_counts: dict[str, Counter] = defaultdict(Counter)

    for row in rows:
        l1 = (row.get("l1_category_name") or "").strip()
        l2 = (row.get("l2_category_name") or "").strip()
        if l1:
            l1_counts[l1] += 1
            if l2:
                l2_counts[l1.lower()][l2] += 1

    # Pick canonical (most-frequent) casing for each L1
    l1_canonical: dict[str, str] = {}  # lower -> canonical
    for name, _count in l1_counts.items():
        lower = name.lower()
        if lower not in l1_canonical or l1_counts[name] > l1_counts[l1_canonical[lower]]:
            l1_canonical[lower] = name

    # Pick canonical casing for each L2 (within each L1 group)
    l2_canonical: dict[tuple[str, str], str] = {}  # (l1_lower, l2_lower) -> canonical
    for l1_lower, counter in l2_counts.items():
        for name, count in counter.items():
            key = (l1_lower, name.lower())
            if key not in l2_canonical or count > l2_counts[l1_lower][l2_canonical[key]]:
                l2_canonical[key] = name

    # Normalise rows in-place so insert_transactions sees consistent names
    normalised_l1 = 0
    normalised_l2 = 0
    for row in rows:
        l1 = (row.get("l1_category_name") or "").strip()
        l2 = (row.get("l2_category_name") or "").strip()
        if l1:
            canon_l1 = l1_canonical.get(l1.lower(), l1)
            if canon_l1 != l1:
                row["l1_category_name"] = canon_l1
                normalised_l1 += 1
            if l2:
                canon_l2 = l2_canonical.get((l1.lower(), l2.lower()), l2)
                if canon_l2 != l2:
                    row["l2_category_name"] = canon_l2
                    normalised_l2 += 1

    if normalised_l1 or normalised_l2:
        print(f"  Normalised {normalised_l1} L1 and {normalised_l2} L2 case-variant rows in CSV")

    # Build the final hierarchy from canonical names
    hierarchy: dict[str, set[str]] = defaultdict(set)
    for l1_lower, canon_l1 in l1_canonical.items():
        hierarchy[canon_l1]  # ensure key exists
        for (ll, l2_lower), canon_l2 in l2_canonical.items():
            if ll == l1_lower:
                hierarchy[canon_l1].add(canon_l2)

    return dict(hierarchy)


def sync_categories(session, csv_hierarchy: dict[str, set[str]]):
    """
    Synchronise the categories table so it matches the CSV hierarchy.

    - CSV is the source of truth for category *names*.
    - DB categories not referenced in the CSV are deleted.
    - New categories in the CSV are created.
    - Case / typo differences: the DB is updated to match the CSV.
    """
    print("\n--- Syncing categories ---")

    # ── 1. Load current DB categories ──────────────────────────────
    db_l1s = session.query(Category).filter(Category.level == 1).all()
    db_l2s = session.query(Category).filter(Category.level == 2).all()

    # Build lookup maps (case-insensitive for matching)
    db_l1_by_lower: dict[str, Category] = {c.name.lower(): c for c in db_l1s}
    # L2 keyed by (lower_name, parent_id)
    db_l2_by_lower_parent: dict[tuple[str, str], Category] = {
        (c.name.lower(), c.parent_id): c for c in db_l2s
    }
    # Also keep a quick parent_id -> [l2_cat, ...] index
    db_l2_by_parent: dict[str, list[Category]] = defaultdict(list)
    for c in db_l2s:
        db_l2_by_parent[c.parent_id].append(c)

    # Keep track of DB category IDs that are "used" (present in CSV)
    used_l1_ids: set[str] = set()
    used_l2_ids: set[str] = set()

    # ── 2. Ensure every CSV L1 exists in the DB ────────────────────
    for csv_l1_name, csv_l2_names in csv_hierarchy.items():
        l1_lower = csv_l1_name.lower()
        db_l1 = db_l1_by_lower.get(l1_lower)

        if db_l1:
            # Fix typo / case if needed
            if db_l1.name != csv_l1_name:
                print(f"  L1 rename: '{db_l1.name}' -> '{csv_l1_name}'")
                db_l1.name = csv_l1_name
                db_l1.updated_at = datetime.now()
            used_l1_ids.add(db_l1.id)
            l1_id = db_l1.id
        else:
            # Brand-new L1 — try to get domain/color from seed hierarchy
            seed_info = CATEGORY_HIERARCHY.get(csv_l1_name, {})
            domain = seed_info.get("domain", "LIFESTYLE")
            color = seed_info.get("color", "#9E9E9E")
            import uuid
            l1_id = str(uuid.uuid4())
            new_l1 = Category(
                id=l1_id,
                name=csv_l1_name,
                level=1,
                parent_id=None,
                domain=domain,
                color_hex=color,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            session.add(new_l1)
            print(f"  L1 created: '{csv_l1_name}' (domain={domain})")
            used_l1_ids.add(l1_id)
            # Update lookup for subsequent L2 matching
            db_l1_by_lower[l1_lower] = new_l1

        # ── 3. Ensure every CSV L2 under this L1 exists ────────────
        for csv_l2_name in csv_l2_names:
            l2_lower = csv_l2_name.lower()
            db_l2 = db_l2_by_lower_parent.get((l2_lower, l1_id))

            if db_l2:
                if db_l2.name != csv_l2_name:
                    print(f"  L2 rename: '{db_l2.name}' -> '{csv_l2_name}' (under {csv_l1_name})")
                    db_l2.name = csv_l2_name
                    db_l2.updated_at = datetime.now()
                used_l2_ids.add(db_l2.id)
            else:
                # Maybe L2 exists under this parent with a completely different
                # name that just isn't a typo — we still need to create it.
                import uuid
                seed_info = CATEGORY_HIERARCHY.get(csv_l1_name, {})
                color = seed_info.get("color", "#9E9E9E")
                domain = seed_info.get("domain", "LIFESTYLE")
                l2_id = str(uuid.uuid4())
                new_l2 = Category(
                    id=l2_id,
                    name=csv_l2_name,
                    level=2,
                    parent_id=l1_id,
                    domain=domain,
                    color_hex=color,
                    created_at=datetime.now(),
                    updated_at=datetime.now(),
                )
                session.add(new_l2)
                print(f"  L2 created: '{csv_l2_name}' under '{csv_l1_name}'")
                used_l2_ids.add(l2_id)
                # Update lookup
                db_l2_by_lower_parent[(l2_lower, l1_id)] = new_l2

    # ── 4. Delete DB categories NOT in the CSV ─────────────────────
    # Delete L2s first (foreign key on parent_id)
    deleted_l2 = 0
    for c in db_l2s:
        if c.id not in used_l2_ids:
            print(f"  L2 deleted: '{c.name}' (parent_id={c.parent_id})")
            session.delete(c)
            deleted_l2 += 1

    deleted_l1 = 0
    for c in db_l1s:
        if c.id not in used_l1_ids:
            # Also delete any remaining L2 children (safety net)
            for child in db_l2_by_parent.get(c.id, []):
                if child.id not in used_l2_ids:
                    session.delete(child)
                    deleted_l2 += 1
            print(f"  L1 deleted: '{c.name}'")
            session.delete(c)
            deleted_l1 += 1

    session.flush()  # ensure IDs are settled before we build lookups
    print(f"  Deleted {deleted_l1} L1 and {deleted_l2} L2 categories")


def build_category_lookup(session) -> tuple[dict[str, str], dict[tuple[str, str], str]]:
    """
    After sync, build fast lookup dicts:
      l1_by_name  :  { name -> id }
      l2_by_name_parent : { (name, parent_id) -> id }
    """
    categories = session.query(Category).all()
    l1_by_name = {c.name: c.id for c in categories if c.level == 1}
    l2_by_name_parent = {}
    for c in categories:
        if c.level == 2:
            l2_by_name_parent[(c.name, c.parent_id)] = c.id
    return l1_by_name, l2_by_name_parent


def insert_transactions(session, rows: list[dict],
                        l1_by_name: dict[str, str],
                        l2_by_name_parent: dict[tuple[str, str], str]):
    """Insert all CSV rows into the transactions table."""
    print("\n--- Inserting transactions ---")

    unmapped_pairs: set[tuple[str, str]] = set()
    imported = 0

    for row_number, row in enumerate(rows, start=2):
        raw_date = (row.get("raw_date") or "").strip()
        raw_details = (row.get("raw_details") or "").strip()

        # ── Normalize amounts (round to 2 decimal places) ──
        debit = normalize_amount(row.get("debit"), field_name="debit", row_number=row_number)
        credit = normalize_amount(row.get("credit"), field_name="credit", row_number=row_number)
        validate_transaction_amounts(debit, credit, row_number=row_number)

        # ── Normalize text fields ──
        acc_name = (row.get("account_name") or "").strip() or None
        acc_type_raw = (row.get("account_type") or "").strip()
        acc_type = acc_type_raw.upper() if acc_type_raw else None  # Normalize to UPPERCASE
        filename = (row.get("filename") or "imported").strip()
        notes = (row.get("notes") or "").strip() or None
        payment_verification = (row.get("payment_verification") or "").strip() or None

        # ── Normalize enum fields (lowercase) ──
        review_status = (row.get("review_status") or "").strip().lower()
        categorised_by = (row.get("categorised_by") or "").strip().lower() or None

        l1_name = (row.get("l1_category_name") or "").strip()
        l2_name = (row.get("l2_category_name") or "").strip()

        # Compute derived fields (amount, flow, date features, merchant, cleaned text)
        derived = compute_derived_fields(raw_date, raw_details, debit, credit)

        # ── Normalize derived amount to 2 decimal places ──
        if derived.get("amount") is not None:
            derived["amount"] = round(derived["amount"], 2)

        # ── Normalize flow_direction to lowercase ──
        if derived.get("flow_direction"):
            derived["flow_direction"] = derived["flow_direction"].lower()

        # ── Map categories ──
        l1_id = l1_by_name.get(l1_name) if l1_name else None
        l2_id = None
        if l2_name and l1_id:
            l2_id = l2_by_name_parent.get((l2_name, l1_id))
            if not l2_id and (l1_name, l2_name) not in unmapped_pairs:
                unmapped_pairs.add((l1_name, l2_name))
                print(f"  WARNING: L2 '{l2_name}' not found under L1 '{l1_name}'")
        elif l1_name and not l1_id and (l1_name, l2_name) not in unmapped_pairs:
            unmapped_pairs.add((l1_name, l2_name))
            print(f"  WARNING: L1 '{l1_name}' not found in DB")

        # Determine review state (normalize to known enum values)
        if review_status not in (ReviewStatus.APPROVED.value, ReviewStatus.REJECTED.value):
            review_status = ReviewStatus.PENDING.value

        # Confidence
        l2_confidence = None
        if l1_id and categorised_by == CategorisedBy.USER.value:
            l2_confidence = 1.0

        # ── Normalize dates ──
        reviewed_at = parse_datetime_flexible(row.get("reviewed_at"))
        statement_date = parse_date_flexible(row.get("statement_date"))
        mapping_date = parse_date_flexible(row.get("mapping_date"))

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
            l2_confidence=l2_confidence,
            categorised_by=categorised_by if l1_id else None,
            review_status=review_status,
            reviewed_at=reviewed_at,
            statement_date=statement_date,
            mapping_date=mapping_date,
            payment_verification=payment_verification,
            **derived,
        )
        session.add(t)
        imported += 1

    session.flush()
    print(f"Inserted {imported} transactions")
    if unmapped_pairs:
        print(f"  {len(unmapped_pairs)} unique category pair(s) could not be mapped (see warnings above)")
    return imported


def repair_derived_financials(session) -> int:
    """Correct only inconsistent amount and flow-direction values in existing rows."""
    repaired = 0
    for transaction in session.query(Transaction).yield_per(500):
        validate_transaction_amounts(
            transaction.debit, transaction.credit, row_number=transaction.id
        )
        derived = compute_derived_fields(
            transaction.raw_date,
            transaction.raw_details,
            transaction.debit,
            transaction.credit,
        )
        expected_amount = round(derived["amount"], 2)
        expected_flow_direction = derived["flow_direction"].lower()

        if (
            transaction.amount != expected_amount
            or transaction.flow_direction != expected_flow_direction
        ):
            transaction.amount = expected_amount
            transaction.flow_direction = expected_flow_direction
            repaired += 1

    return repaired


def print_summary(session):
    """Print summary statistics."""
    print("\n--- Summary ---")
    total = session.query(Transaction).count()
    with_l1 = session.query(Transaction).filter(Transaction.l1_category_id.isnot(None)).count()
    with_l2 = session.query(Transaction).filter(Transaction.l2_category_id.isnot(None)).count()
    pending = session.query(Transaction).filter(
        Transaction.review_status == ReviewStatus.PENDING.value
    ).count()
    approved = session.query(Transaction).filter(
        Transaction.review_status == ReviewStatus.APPROVED.value
    ).count()
    l1_cats = session.query(Category).filter(Category.level == 1).count()
    l2_cats = session.query(Category).filter(Category.level == 2).count()

    print(f"  Transactions:  {total}")
    print(f"  With L1 cat:   {with_l1}")
    print(f"  With L2 cat:   {with_l2}")
    print(f"  Pending:       {pending}")
    print(f"  Approved:      {approved}")
    print(f"  L1 categories: {l1_cats}")
    print(f"  L2 categories: {l2_cats}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely refresh transactions from an edited CSV or repair derived financial fields."
    )
    parser.add_argument(
        "--csv",
        help="CSV to import. Required when both supported default filenames are present.",
    )
    parser.add_argument(
        "--repair-derived-financials",
        action="store_true",
        help="Repair amount and flow_direction without replacing transactions.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    print("=" * 60)
    print(
        "Repair derived financials"
        if args.repair_derived_financials
        else "Update from CSV: Prune -> Sync Categories -> Insert Transactions"
    )
    print("=" * 60)

    # ── 0. Init ────────────────────────────────────────────────────
    init_db()
    session = SessionLocal()

    try:
        if args.repair_derived_financials:
            repaired = repair_derived_financials(session)
            session.commit()
            print(f"\nCommitted {repaired} repaired transaction(s).")
            return

        # ── 1. Read CSV ───────────────────────────────────────────
        csv_path = resolve_csv_path(args.csv)
        print(f"Using CSV: {csv_path}")
        rows = read_csv(csv_path)
        validate_rows(rows)
        print("Validated all transaction amounts before refreshing the database.")

        # ── 2. Prune transactions ─────────────────────────────────
        existing = session.query(Transaction).count()
        print(f"\nPruning {existing} existing transactions...")
        session.query(Transaction).delete()
        session.flush()
        print("Transactions table cleared.")

        # ── 3. Sync categories ────────────────────────────────────
        csv_hierarchy = collect_csv_categories(rows)
        print(f"CSV contains {len(csv_hierarchy)} L1 categories with "
              f"{sum(len(v) for v in csv_hierarchy.values())} unique L2 sub-categories")
        sync_categories(session, csv_hierarchy)

        # ── 4. Build lookup & insert ──────────────────────────────
        l1_by_name, l2_by_name_parent = build_category_lookup(session)
        insert_transactions(session, rows, l1_by_name, l2_by_name_parent)

        # ── 5. Commit ─────────────────────────────────────────────
        session.commit()
        print("\nCommitted all changes.")

        # ── 6. Summary ────────────────────────────────────────────
        print_summary(session)

    except Exception as e:
        session.rollback()
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        session.close()

    print("\nDone.")


if __name__ == "__main__":
    main()
