"""CSV processing service for transaction ingestion."""

import csv
import io
import re
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Transaction
from ml_model.preprocessing import extract_merchant, normalize_merchant, clean_transaction_text

REQUIRED_CSV_COLUMNS = {"Date", "Details", "Debit", "Credit", "AccountName", "AccountType"}

PLATFORM_MERCHANTS = frozenset([
    "amazon", "flipkart", "myntra", "swiggy", "zomato", "zepto",
    "blinkit", "bigbasket", "meesho", "ajio", "nykaa", "tatacliq",
])


def parse_csv_content(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content and return headers and rows."""
    for encoding in ["utf-8", "utf-8-sig", "latin-1", "cp1252"]:
        try:
            text_content = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Unable to decode CSV file with supported encodings")

    reader = csv.DictReader(io.StringIO(text_content))
    headers = reader.fieldnames or []
    rows = list(reader)
    return headers, rows


def parse_float(value: str) -> float | None:
    if not value or not value.strip():
        return None
    try:
        return float(value.strip().replace(",", ""))
    except ValueError:
        return None


def parse_date_to_iso(date_str: str) -> str | None:
    """Parse various date formats to YYYY-MM-DD."""
    if not date_str or not date_str.strip():
        return None
    date_str = date_str.strip()
    for fmt in ["%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def detect_flow_direction(details: str, debit: float | None, credit: float | None) -> str:
    """Detect flow direction. 'transfer' for internal moves, else debit/credit."""
    if details:
        upper = details.upper()
        transfer_signals = ["CREDIT CARD BILL", "CC BILL", "OWN ACCOUNT", "SELF TRANSFER"]
        if any(s in upper for s in transfer_signals):
            return "transfer"
    if debit is not None:
        return "debit"
    return "credit"


def detect_transaction_type(details: str) -> str | None:
    """Detect payment method from transaction text."""
    if not details:
        return None
    text = details.upper()
    if "UPI/" in text or "UPI-" in text:
        return "UPI"
    if "NEFT" in text:
        return "NEFT"
    if "IMPS" in text:
        return "IMPS"
    if "POS" in text or "SWIPE" in text:
        return "CARD"
    if "ATM" in text or "WDL" in text:
        return "ATM"
    if "NACH" in text or "ECS" in text:
        return "AUTO_DEBIT"
    return None


def compute_derived_fields(raw_date: str, raw_details: str, debit: float | None, credit: float | None) -> dict:
    """Compute all derived fields for a transaction row."""
    # Amount (signed)
    if debit is not None:
        amount = -abs(debit)
    elif credit is not None:
        amount = abs(credit)
    else:
        amount = None

    # Flow direction
    flow_direction = detect_flow_direction(raw_details, debit, credit)

    # Date features
    parsed_date = parse_date_to_iso(raw_date)
    day_of_week = None
    month_val = None
    is_weekend = None
    if parsed_date:
        dt = datetime.strptime(parsed_date, "%Y-%m-%d")
        day_of_week = dt.weekday()  # 0=Mon, 6=Sun
        month_val = dt.month
        is_weekend = 1 if day_of_week >= 5 else 0

    # Merchant
    merchant = extract_merchant(raw_details)
    merchant_name = normalize_merchant(merchant) if merchant else None
    is_platform = 1 if merchant_name and merchant_name.lower() in PLATFORM_MERCHANTS else 0

    # Cleaned text
    cleaned = clean_transaction_text(raw_details) or None

    return {
        "amount": amount,
        "flow_direction": flow_direction,
        "parsed_date": parsed_date,
        "day_of_week": day_of_week,
        "month": month_val,
        "is_weekend": is_weekend,
        "merchant_name": merchant_name,
        "is_platform_merchant": is_platform,
        "cleaned_details": cleaned,
    }


def validate_headers(headers: list[str]) -> bool:
    """Check all required columns are present."""
    return REQUIRED_CSV_COLUMNS.issubset(set(headers))


def process_transaction_csv(
    db: Session,
    file_content: bytes,
    filename: str,
    account_name: str | None = None,
) -> dict[str, Any]:
    """Process a bank CSV and insert transactions."""
    headers, rows = parse_csv_content(file_content)

    if not headers:
        raise ValueError("CSV file has no headers")
    if not rows:
        raise ValueError("CSV file has no data rows")
    if not validate_headers(headers):
        raise ValueError(f"Invalid CSV format. Required columns: {', '.join(sorted(REQUIRED_CSV_COLUMNS))}")

    upload_time = datetime.now()
    transactions_to_insert = []

    for row in rows:
        raw_date = (row.get("Date") or "").strip()
        raw_details = (row.get("Details") or "").strip()
        debit = parse_float(row.get("Debit", ""))
        credit = parse_float(row.get("Credit", ""))
        acc_name = (row.get("AccountName") or "").strip() or account_name or None
        acc_type = (row.get("AccountType") or "").strip() or None

        derived = compute_derived_fields(raw_date, raw_details, debit, credit)

        transactions_to_insert.append({
            "raw_date": raw_date,
            "raw_details": raw_details,
            "debit": debit,
            "credit": credit,
            "account_name": acc_name,
            "account_type": acc_type,
            "filename": filename,
            "uploaded_at": upload_time,
            **derived,
        })

    # Sort by parsed_date ascending
    transactions_to_insert.sort(key=lambda t: t.get("parsed_date") or "0000-00-00")

    for data in transactions_to_insert:
        db.add(Transaction(**data))

    db.commit()

    return {
        "rows_inserted": len(transactions_to_insert),
    }
