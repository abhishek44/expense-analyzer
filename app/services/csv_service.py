"""CSV processing service for fixed table schema with column mapping."""

import csv
import io
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models import (
    Transaction,
    TRANSACTION_COLUMN_MAPPING,
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


def validate_headers(headers: list[str]) -> bool:
    """
    Validate that CSV headers strictly match the expected schema.
    Returns True if valid, False otherwise.
    """
    expected_columns = set(TRANSACTION_COLUMN_MAPPING.keys())
    # Check if all expected columns are present in headers
    # We require exact matches
    current_headers = set(headers)
    return expected_columns.issubset(current_headers)


def process_transaction_csv(
    db: Session,
    file_content: bytes,
    filename: str,
    account_name: str | None = None
) -> dict[str, Any]:
    """
    Process transaction CSV and insert into transactions table.
    Enforces strict schema compliance.
    """
    headers, rows = parse_csv_content(file_content)
    
    if not headers:
        raise ValueError("CSV file has no headers")
    
    if not rows:
        raise ValueError("CSV file has no data rows")
    
    # Strict validation
    if not validate_headers(headers):
        expected_list = ", ".join(TRANSACTION_COLUMN_MAPPING.keys())
        raise ValueError(f"Invalid CSV format. Strictly required columns: {expected_list}")
    
    upload_time = datetime.now()
    inserted_count = 0
    transactions_to_insert = []
    
    for row in rows:
        # strict mapping
        mapped_data = {
            "filename": filename,
            "uploaded_datetime": upload_time,
        }
        
        for csv_header, model_field in TRANSACTION_COLUMN_MAPPING.items():
            value = row.get(csv_header, "").strip()
            
            if model_field in ["Debit", "Credit"]:
                mapped_data[model_field] = parse_float(value)
            elif model_field == "review_datetime" and value:
                try:
                    for fmt in ["%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]:
                        try:
                            mapped_data[model_field] = datetime.strptime(value, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        mapped_data[model_field] = None
                except Exception:
                     mapped_data[model_field] = None
            else:
                mapped_data[model_field] = value if value else None

        # Override account name if provided in upload (optional feature, but keeping as fallback/overwrite?)
        # User asked for "AccountName" column. If API passes account_name, we might want to prioritize it or ignore it.
        # But for now, let's keep the existing logic: if passed, it overrides (or fills). 
        # Actually user said "AccountName" is mandatory in CSV.
        # So we should probably trust the CSV. 
        # However, the `account_name` arg comes from the API form data.
        # If the user uploads with the form, they might expect it to be used.
        # But strict schema implies the CSV data is the source of truth.
        # I will prioritize the CSV data, but if it's somehow missing/empty (which shouldn't happen with strict checks but value could be empty string), use the form.
        
        if not mapped_data.get("Account_name") and account_name:
             mapped_data["Account_name"] = account_name

        transactions_to_insert.append(mapped_data)
    
    # Sort transactions by date in ascending order
    def parse_date_for_sort(transaction_data):
        date_str = transaction_data.get("Date", "")
        if not date_str:
            return datetime.min
        try:
            for fmt in ["%d-%b-%y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return datetime.min
        except:
            return datetime.min
    
    transactions_to_insert.sort(key=parse_date_for_sort)
    
    # Insert sorted transactions
    for mapped_data in transactions_to_insert:
        transaction = Transaction(**mapped_data)
        db.add(transaction)
        inserted_count += 1
    
    db.commit()
    
    return {
        "table_name": "transactions",
        "rows_inserted": inserted_count,
        "columns": list(TRANSACTION_COLUMN_MAPPING.values()) + ["filename", "uploaded_datetime"],
        "format_converted": False,
    }
