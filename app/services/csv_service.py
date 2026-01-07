"""CSV processing service for fixed table schema with column mapping."""

import csv
import io
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    CreditCardStatement,
    CREDIT_CARD_COLUMN_MAPPING,
)


def parse_csv_content(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    """Parse CSV content and return headers and rows."""
    # Try different encodings
    for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
        try:
            text_content = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("Unable to decode CSV file with supported encodings")
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(text_content))
    headers = reader.fieldnames or []
    rows = list(reader)
    
    return headers, rows


def parse_float(value: str) -> float | None:
    """Parse float value from string, handling empty and formatted strings."""
    if not value or not value.strip():
        return None
    try:
        return float(value.strip().replace(',', ''))
    except ValueError:
        return None


def map_csv_to_credit_card_statement(
    row: dict[str, str],
    headers: list[str],
    filename: str,
    upload_time: datetime
) -> dict[str, Any]:
    """
    Map CSV row to CreditCardStatement model fields.
    
    Handles column name variations and converts values to appropriate types.
    """
    mapped_data = {
        "filename": filename,
        "uploaded_datetime": upload_time,
    }
    
    # Try to map each expected column
    for csv_header, model_field in CREDIT_CARD_COLUMN_MAPPING.items():
        # Try exact match first
        if csv_header in row:
            value = row[csv_header].strip()
        else:
            # Try case-insensitive match
            value = None
            for h in headers:
                if h.lower().replace(" ", "").replace(".", "") == csv_header.lower().replace(" ", "").replace(".", ""):
                    value = row.get(h, "").strip()
                    break
            if value is None:
                value = ""
        
        # Convert to appropriate type based on field
        if model_field in ["reward_points", "intl_amount", "amount_inr"]:
            mapped_data[model_field] = parse_float(value)
        else:
            mapped_data[model_field] = value if value else None
    
    return mapped_data


def is_credit_card_statement_format(headers: list[str]) -> bool:
    """
    Check if CSV headers match credit card statement format.
    
    Returns True if at least 4 expected columns are found.
    """
    expected_columns = set(CREDIT_CARD_COLUMN_MAPPING.keys())
    normalized_headers = {h.lower().replace(" ", "").replace(".", "") for h in headers}
    normalized_expected = {c.lower().replace(" ", "").replace(".", "") for c in expected_columns}
    
    matches = normalized_headers & normalized_expected
    return len(matches) >= 4  # At least 4 matching columns


def convert_to_credit_card_format(
    row: dict[str, str],
    headers: list[str]
) -> dict[str, Any]:
    """
    Convert CSV row with different structure to credit card statement format.
    
    Attempts to intelligently map columns based on common patterns.
    """
    result = {}
    
    # Mapping heuristics for common column name patterns
    column_patterns = {
        "date": ["date", "time", "datetime", "transaction_date"],
        "sr_no": ["sr_no", "serial", "id", "ref", "reference"],
        "transaction_details": ["details", "description", "transaction", "narration", "particulars"],
        "reward_points": ["reward", "points", "bonus"],
        "intl_amount": ["intl", "international", "foreign"],
        "amount_inr": ["amount", "inr", "rs", "value", "sum"],
        "billing_sign": ["sign", "type", "cr", "dr", "credit", "debit"],
    }
    
    # Normalize all headers
    header_lower_map = {h.lower(): h for h in headers}
    
    for model_field, patterns in column_patterns.items():
        value = None
        for pattern in patterns:
            for header_lower, header_orig in header_lower_map.items():
                if pattern in header_lower:
                    value = row.get(header_orig, "").strip()
                    break
            if value:
                break
        
        if model_field in ["reward_points", "intl_amount", "amount_inr"]:
            result[model_field] = parse_float(value) if value else None
        else:
            result[model_field] = value if value else None
    
    return result


async def process_credit_card_csv(
    db: Session,
    file_content: bytes,
    filename: str,
    account_type: str | None = None,
    account_name: str | None = None
) -> dict[str, Any]:
    """
    Process credit card statement CSV and insert into fixed table.
    
    - If CSV matches expected format, maps columns directly
    - If CSV has different structure, converts to match schema
    """
    headers, rows = parse_csv_content(file_content)
    
    if not headers:
        raise ValueError("CSV file has no headers")
    
    if not rows:
        raise ValueError("CSV file has no data rows")
    
    upload_time = datetime.now()
    inserted_count = 0
    is_native_format = is_credit_card_statement_format(headers)
    
    for row in rows:
        if is_native_format:
            mapped_data = map_csv_to_credit_card_statement(row, headers, filename, upload_time)
        else:
            mapped_data = convert_to_credit_card_format(row, headers)
            mapped_data["filename"] = filename
            mapped_data["uploaded_datetime"] = upload_time
        
        # Add account metadata
        mapped_data["account_type"] = account_type
        mapped_data["account_name"] = account_name
        
        # Create and add record
        statement = CreditCardStatement(**mapped_data)
        db.add(statement)
        inserted_count += 1
    
    db.commit()
    
    return {
        "table_name": "credit_card_statements",
        "rows_inserted": inserted_count,
        "columns": list(CREDIT_CARD_COLUMN_MAPPING.values()) + ["filename", "uploaded_datetime", "account_type", "account_name"],
        "format_converted": not is_native_format,
    }
