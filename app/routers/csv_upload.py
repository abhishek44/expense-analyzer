"""Transaction management endpoints: upload, CRUD, review, export."""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.config import settings
from app.database import get_db
from app.models import Transaction, MerchantMapping, Category, ReviewStatus, CategorisedBy

router = APIRouter(prefix="/api", tags=["Transactions"])


# ── Request Models ─────────────────────────────────────────────────────────────

class ReviewRequest(BaseModel):
    l1_category_id: str
    l2_category_id: Optional[str] = None
    notes: Optional[str] = None
    review_status: str = "approved"


class TransactionUpdate(BaseModel):
    notes: Optional[str] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None


class ManualTransactionRequest(BaseModel):
    Date: Optional[str] = None
    Details: str
    Debit: Optional[float] = None
    Credit: Optional[float] = None
    Account_name: str
    Account_type: str
    l1_category_id: Optional[str] = None
    l2_category_id: Optional[str] = None
    Notes: Optional[str] = None


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload-csv", summary="Upload transaction CSV")
async def upload_csv(
    file: UploadFile = File(...),
    account_name: str = Form(None),
    db: Session = Depends(get_db),
) -> dict:
    """Upload CSV file to transactions table."""
    from app.services.csv_service import process_transaction_csv

    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}")

    content = await file.read()
    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum: {settings.MAX_FILE_SIZE_MB}MB")

    try:
        result = process_transaction_csv(db=db, file_content=content, filename=file.filename, account_name=account_name)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"success": True, "message": f"Uploaded {result['rows_inserted']} rows", "rows_inserted": result["rows_inserted"]}


# ── Tables / Stats ─────────────────────────────────────────────────────────────

@router.get("/tables", summary="Table stats")
async def list_tables(db: Session = Depends(get_db)) -> dict:
    total = db.query(Transaction).count()
    pending = db.query(Transaction).filter(Transaction.review_status == ReviewStatus.PENDING.value).count()
    reviewed = total - pending
    return {
        "tables": [{
            "name": "transactions",
            "total": total,
            "pending": pending,
            "reviewed": reviewed,
            "uploadable": True,
        }]
    }


# ── Transaction List ───────────────────────────────────────────────────────────

@router.get("/transactions", summary="Get transactions")
async def get_transactions(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    filename_filter: Optional[str] = None,
    account_name: Optional[str] = None,
    account_type: Optional[str] = None,
    l1_category_id: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(Transaction)

    if status_filter:
        query = query.filter(Transaction.review_status == status_filter)
    if filename_filter:
        query = query.filter(Transaction.filename == filename_filter)
    if account_name:
        query = query.filter(Transaction.account_name.ilike(f"%{account_name}%"))
    if account_type:
        query = query.filter(Transaction.account_type.ilike(f"%{account_type}%"))
    if l1_category_id:
        query = query.filter(Transaction.l1_category_id == l1_category_id)
    if date_from:
        query = query.filter(Transaction.parsed_date >= date_from)
    if date_to:
        query = query.filter(Transaction.parsed_date <= date_to)

    total = query.count()
    records = query.order_by(Transaction.id.desc()).offset(skip).limit(limit).all()

    return {"total": total, "skip": skip, "limit": limit, "data": [r.to_dict() for r in records]}


@router.get("/filter-options", summary="Get filter options")
async def get_filter_options(db: Session = Depends(get_db)) -> dict:
    account_names = db.query(Transaction.account_name).distinct().filter(Transaction.account_name.isnot(None)).all()
    account_types = db.query(Transaction.account_type).distinct().filter(Transaction.account_type.isnot(None)).all()
    return {
        "account_names": sorted([r[0] for r in account_names if r[0]]),
        "account_types": sorted([r[0] for r in account_types if r[0]]),
    }


# ── Single Transaction ─────────────────────────────────────────────────────────

@router.get("/transactions/{transaction_id}", summary="Get single transaction")
async def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> dict:
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return t.to_dict()


@router.patch("/transactions/{transaction_id}", summary="Update transaction")
async def update_transaction(transaction_id: int, update_data: TransactionUpdate, db: Session = Depends(get_db)) -> dict:
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(t, field, value)

    db.commit()
    db.refresh(t)
    return {"success": True, "data": t.to_dict()}


@router.delete("/transactions/{transaction_id}", summary="Delete transaction")
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)) -> dict:
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")
    db.delete(t)
    db.commit()
    return {"success": True, "message": "Transaction deleted"}


# ── Review ─────────────────────────────────────────────────────────────────────

@router.post("/transactions/{transaction_id}/review", summary="Review transaction")
async def review_transaction(transaction_id: int, review_data: ReviewRequest, db: Session = Depends(get_db)) -> dict:
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    t.l1_category_id = review_data.l1_category_id
    t.l2_category_id = review_data.l2_category_id
    t.notes = review_data.notes
    t.categorised_by = CategorisedBy.USER.value
    t.review_status = review_data.review_status
    t.reviewed_at = datetime.now()
    t.l2_confidence = 1.0

    # Update merchant_mappings
    if t.merchant_name:
        mapping = db.query(MerchantMapping).filter(MerchantMapping.merchant_name == t.merchant_name).first()
        today = datetime.now().strftime("%Y-%m-%d")
        if not mapping:
            mapping = MerchantMapping(
                merchant_name=t.merchant_name,
                default_l1_category_id=review_data.l1_category_id,
                default_l2_category_id=review_data.l2_category_id,
                occurrence_count=1,
                last_seen_date=today,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )
            db.add(mapping)
        elif mapping.default_l1_category_id == review_data.l1_category_id:
            mapping.occurrence_count += 1
            mapping.last_seen_date = today
            mapping.updated_at = datetime.now()
            if review_data.l2_category_id and not mapping.default_l2_category_id:
                mapping.default_l2_category_id = review_data.l2_category_id
        else:
            mapping.is_ambiguous = 1
            mapping.notes_required = 1
            mapping.last_seen_date = today
            mapping.updated_at = datetime.now()

    db.commit()
    db.refresh(t)
    return {"success": True, "message": "Transaction reviewed", "transaction": t.to_dict()}


# ── Merchant Suggestion ────────────────────────────────────────────────────────

@router.get("/merchant-suggestion/{transaction_id}", summary="Get merchant category suggestion")
async def get_merchant_suggestion(transaction_id: int, db: Session = Depends(get_db)) -> dict:
    t = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if not t.merchant_name:
        return {"suggestion": None}

    mapping = db.query(MerchantMapping).filter(MerchantMapping.merchant_name == t.merchant_name).first()
    if not mapping:
        return {"suggestion": None}

    # Get category names for display
    l1_name = None
    l2_name = None
    if mapping.default_l1_category_id:
        cat = db.query(Category).filter(Category.id == mapping.default_l1_category_id).first()
        l1_name = cat.name if cat else None
    if mapping.default_l2_category_id:
        cat = db.query(Category).filter(Category.id == mapping.default_l2_category_id).first()
        l2_name = cat.name if cat else None

    return {
        "suggestion": {
            "l1_category_id": mapping.default_l1_category_id,
            "l1_category_name": l1_name,
            "l2_category_id": mapping.default_l2_category_id,
            "l2_category_name": l2_name,
            "confidence": "deterministic" if not mapping.is_ambiguous else "ambiguous",
            "occurrence_count": mapping.occurrence_count,
            "notes_required": bool(mapping.notes_required),
        }
    }


# ── Manual Transaction ─────────────────────────────────────────────────────────

@router.post("/transactions", summary="Create manual transaction")
async def create_transaction(data: ManualTransactionRequest, db: Session = Depends(get_db)) -> dict:
    from app.services.csv_service import compute_derived_fields

    raw_date = data.Date or datetime.now().strftime("%Y-%m-%d")
    raw_details = data.Details
    debit = data.Debit
    credit = data.Credit

    derived = compute_derived_fields(raw_date, raw_details, debit, credit)

    t = Transaction(
        raw_date=raw_date,
        raw_details=raw_details,
        debit=debit,
        credit=credit,
        account_name=data.Account_name,
        account_type=data.Account_type,
        filename="manual_entry",
        uploaded_at=datetime.now(),
        notes=data.Notes,
        l1_category_id=data.l1_category_id,
        l2_category_id=data.l2_category_id,
        categorised_by=CategorisedBy.USER.value if data.l1_category_id else None,
        review_status=ReviewStatus.APPROVED.value if data.l1_category_id else ReviewStatus.PENDING.value,
        reviewed_at=datetime.now() if data.l1_category_id else None,
        **derived,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return {"success": True, "transaction": t.to_dict()}


# ── File Management ────────────────────────────────────────────────────────────

@router.get("/uploaded-files", summary="List uploaded files")
async def get_uploaded_files(db: Session = Depends(get_db)) -> dict:
    files = db.query(
        Transaction.filename,
        func.count(Transaction.id).label("record_count"),
        func.min(Transaction.uploaded_at).label("uploaded_at"),
        func.sum(case((Transaction.review_status == "pending", 1), else_=0)).label("pending_count"),
        func.sum(case((Transaction.review_status != "pending", 1), else_=0)).label("reviewed_count"),
    ).group_by(Transaction.filename).all()

    return {
        "files": [{
            "filename": f.filename,
            "record_count": f.record_count,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
            "pending_count": f.pending_count or 0,
            "reviewed_count": f.reviewed_count or 0,
        } for f in files]
    }


@router.delete("/uploaded-files/{filename}", summary="Delete file records")
async def delete_file_records(filename: str, db: Session = Depends(get_db)) -> dict:
    count = db.query(Transaction).filter(Transaction.filename == filename).count()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"No records found for '{filename}'")
    db.query(Transaction).filter(Transaction.filename == filename).delete()
    db.commit()
    return {"success": True, "message": f"Deleted {count} records for '{filename}'"}


@router.delete("/tables/{table_name}/clear", summary="Clear table")
async def clear_table(table_name: str, db: Session = Depends(get_db)) -> dict:
    if table_name != "transactions":
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")
    count = db.query(Transaction).count()
    db.query(Transaction).delete()
    db.commit()
    return {"success": True, "message": f"Deleted {count} records"}


# ── Export ─────────────────────────────────────────────────────────────────────

EXPORT_HEADERS = [
    "id", "raw_date", "raw_details", "Debit", "Credit", "AccountName", "AccountType",
    "filename", "notes", "amount", "flow_direction", "parsed_date",
    "merchant_name", "cleaned_details", "l1_category_name", "l2_category_name",
    "categorised_by", "review_status", "reviewed_at",
]


@router.get("/export-transactions", summary="Export transactions as CSV")
async def export_transactions(db: Session = Depends(get_db)):
    transactions = db.query(Transaction).order_by(Transaction.id.asc()).all()
    if not transactions:
        raise HTTPException(status_code=404, detail="No transactions to export")

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(EXPORT_HEADERS)

    for t in transactions:
        l1_name = t.l1_category.name if t.l1_category else ""
        l2_name = t.l2_category.name if t.l2_category else ""
        writer.writerow([
            t.id,
            t.raw_date or "",
            t.raw_details or "",
            t.debit if t.debit is not None else "",
            t.credit if t.credit is not None else "",
            t.account_name or "",
            t.account_type or "",
            t.filename or "",
            t.notes or "",
            t.amount if t.amount is not None else "",
            t.flow_direction or "",
            t.parsed_date or "",
            t.merchant_name or "",
            t.cleaned_details or "",
            l1_name,
            l2_name,
            t.categorised_by or "",
            t.review_status or "",
            t.reviewed_at.strftime("%Y-%m-%d %H:%M") if t.reviewed_at else "",
        ])

    output.seek(0)
    filename = f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Import/Overwrite ──────────────────────────────────────────────────────────

@router.post("/import-transactions", summary="Import and overwrite transactions from edited CSV")
async def import_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Import a previously exported CSV that was edited externally.
    Rows with an 'id' column are matched and overwritten. Rows without an id are inserted as new.
    This re-derives computed fields and resolves category names to IDs.
    """
    from app.services.csv_service import compute_derived_fields, parse_csv_content, parse_float

    content = await file.read()
    headers, rows = parse_csv_content(content)

    if not rows:
        raise HTTPException(status_code=400, detail="CSV has no data rows")

    # Build category name → id lookup
    all_cats = db.query(Category).all()
    l1_by_name = {c.name.lower(): c.id for c in all_cats if c.level == 1}
    l2_by_name_parent = {}
    for c in all_cats:
        if c.level == 2:
            parent = next((p for p in all_cats if p.id == c.parent_id), None)
            if parent:
                l2_by_name_parent[(c.name.lower(), parent.name.lower())] = c.id

    updated = 0
    inserted = 0

    for row in rows:
        row_id = row.get("id", "").strip()
        raw_date = (row.get("raw_date") or "").strip()
        raw_details = (row.get("raw_details") or "").strip()
        debit = parse_float(row.get("Debit", ""))
        credit = parse_float(row.get("Credit", ""))
        acc_name = (row.get("AccountName") or "").strip() or None
        acc_type = (row.get("AccountType") or "").strip() or None
        notes = (row.get("notes") or "").strip() or None
        filename = (row.get("filename") or "imported").strip()
        l1_cat_name = (row.get("l1_category_name") or "").strip()
        l2_cat_name = (row.get("l2_category_name") or "").strip()
        categorised_by = (row.get("categorised_by") or "").strip() or None
        review_status = (row.get("review_status") or "pending").strip()
        reviewed_at_str = (row.get("reviewed_at") or "").strip()

        # Resolve category names to IDs
        l1_id = l1_by_name.get(l1_cat_name.lower()) if l1_cat_name else None
        l2_id = l2_by_name_parent.get((l2_cat_name.lower(), l1_cat_name.lower())) if (l2_cat_name and l1_cat_name) else None

        # Parse reviewed_at
        reviewed_at = None
        if reviewed_at_str:
            for fmt in ["%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"]:
                try:
                    reviewed_at = datetime.strptime(reviewed_at_str, fmt)
                    break
                except ValueError:
                    continue

        # Recompute derived fields
        derived = compute_derived_fields(raw_date, raw_details, debit, credit)

        if row_id and row_id.isdigit():
            # Update existing record
            t = db.query(Transaction).filter(Transaction.id == int(row_id)).first()
            if t:
                t.raw_date = raw_date
                t.raw_details = raw_details
                t.debit = debit
                t.credit = credit
                t.account_name = acc_name
                t.account_type = acc_type
                t.filename = filename
                t.notes = notes
                t.l1_category_id = l1_id
                t.l2_category_id = l2_id
                t.categorised_by = categorised_by
                t.review_status = review_status
                t.reviewed_at = reviewed_at
                t.l2_confidence = 1.0 if (l1_id and categorised_by == "user") else None
                for k, v in derived.items():
                    setattr(t, k, v)
                updated += 1
                continue

        # Insert new record
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
            categorised_by=categorised_by,
            review_status=review_status,
            reviewed_at=reviewed_at,
            l2_confidence=1.0 if (l1_id and categorised_by == "user") else None,
            **derived,
        )
        db.add(t)
        inserted += 1

    db.commit()
    return {
        "success": True,
        "message": f"Updated {updated} records, inserted {inserted} new records",
        "updated": updated,
        "inserted": inserted,
    }
