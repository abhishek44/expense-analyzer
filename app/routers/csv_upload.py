"""CSV upload router with file upload and statement management endpoints."""

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.config import settings
from app.database import get_db
from app.models import CreditCardStatement, Expense, ReviewStatus
from app.schemas import UploadResponse, ErrorResponse
from app.services.csv_service import process_credit_card_csv

router = APIRouter(prefix="/api", tags=["CSV Upload"])


# Request/Response Models
class StatementUpdate(BaseModel):
    """Request model for updating a statement."""
    date: Optional[str] = None
    transaction_details: Optional[str] = None
    reward_points: Optional[float] = None
    intl_amount: Optional[float] = None
    amount_inr: Optional[float] = None
    billing_sign: Optional[str] = None


class ApproveRequest(BaseModel):
    """Request model for approving a statement and creating expense."""
    time: Optional[str] = None  # Date string to be parsed
    type: str = "(-) Expense"  # "(+) Income" or "(-) Expense"
    amount: Optional[float] = None
    category: str
    account: str = "Credit Card"
    notes: Optional[str] = None


@router.post(
    "/upload-csv",
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
    summary="Upload credit card statement CSV",
)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload"),
    account_type: str = Form(None, description="Account type (Credit Card, Savings)"),
    account_name: str = Form(None, description="Account name or number"),
    db: Session = Depends(get_db)
) -> UploadResponse:
    """Upload CSV file to credit_card_statements table with account metadata."""
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")
    
    file_ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )
    
    try:
        content = await file.read()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error reading file: {str(e)}")
    
    max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    if len(content) > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
        )
    
    try:
        result = await process_credit_card_csv(
            db=db,
            file_content=content,
            filename=file.filename,
            account_type=account_type,
            account_name=account_name
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error processing CSV: {str(e)}")
    
    message = f"Successfully uploaded {result['rows_inserted']} rows"
    if result.get('format_converted'):
        message += " (CSV format was converted)"
    
    return UploadResponse(
        success=True,
        message=message,
        table_name=result['table_name'],
        rows_inserted=result['rows_inserted'],
        columns=result['columns']
    )


@router.get("/tables", summary="List all tables")
async def list_tables(db: Session = Depends(get_db)) -> dict:
    """List all tables with row counts and status breakdown."""
    credit_total = db.query(CreditCardStatement).count()
    credit_pending = db.query(CreditCardStatement).filter(
        CreditCardStatement.review_status == ReviewStatus.PENDING.value
    ).count()
    credit_reviewed = db.query(CreditCardStatement).filter(
        CreditCardStatement.review_status == ReviewStatus.REVIEWED.value
    ).count()
    expense_count = db.query(Expense).count()
    
    return {
        "tables": [
            {
                "name": "credit_card_statements",
                "description": "Credit card statement uploads",
                "total": credit_total,
                "pending": credit_pending,
                "reviewed": credit_reviewed,
                "uploadable": True
            },
            {
                "name": "expenses",
                "description": "Approved expense records",
                "total": expense_count,
                "uploadable": False
            }
        ]
    }


@router.get("/credit-card-statements", summary="Get all statements")
async def get_credit_card_statements(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    filename_filter: Optional[str] = None,
    db: Session = Depends(get_db)
) -> dict:
    """Get credit card statements with pagination and optional filters."""
    query = db.query(CreditCardStatement)
    
    if status_filter and status_filter in [s.value for s in ReviewStatus]:
        query = query.filter(CreditCardStatement.review_status == status_filter)
    
    if filename_filter:
        query = query.filter(CreditCardStatement.filename == filename_filter)
    
    total = query.count()
    records = query.order_by(CreditCardStatement.id.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [r.to_dict() for r in records]
    }


@router.get("/credit-card-statements/{statement_id}", summary="Get single statement")
async def get_statement(statement_id: int, db: Session = Depends(get_db)) -> dict:
    """Get a single credit card statement by ID."""
    statement = db.query(CreditCardStatement).filter(CreditCardStatement.id == statement_id).first()
    
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    
    return statement.to_dict()


@router.patch("/credit-card-statements/{statement_id}", summary="Update statement")
async def update_statement(
    statement_id: int,
    update_data: StatementUpdate,
    db: Session = Depends(get_db)
) -> dict:
    """Update a credit card statement."""
    statement = db.query(CreditCardStatement).filter(CreditCardStatement.id == statement_id).first()
    
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(statement, field, value)
    
    db.commit()
    db.refresh(statement)
    
    return {"success": True, "message": "Statement updated", "data": statement.to_dict()}


@router.post("/credit-card-statements/{statement_id}/approve", summary="Approve and create expense")
async def approve_statement(
    statement_id: int,
    approve_data: ApproveRequest,
    db: Session = Depends(get_db)
) -> dict:
    """
    Approve a statement and create an expense record.
    
    - Marks the statement as reviewed
    - Creates a new expense record in the expenses table
    """
    statement = db.query(CreditCardStatement).filter(CreditCardStatement.id == statement_id).first()
    
    if not statement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statement not found")
    
    if statement.review_status == ReviewStatus.REVIEWED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Statement already reviewed")
    
    # Determine expense type - use provided or infer from billing sign
    if approve_data.type:
        expense_type = approve_data.type
    else:
        is_credit = statement.billing_sign and statement.billing_sign.upper() == "CR"
        expense_type = "(+) Income" if is_credit else "(-) Expense"
    
    # Parse date - use provided time or statement date
    expense_time = None
    date_str = approve_data.time or statement.date
    if date_str:
        try:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%m/%d/%Y"]:
                try:
                    expense_time = datetime.strptime(date_str, fmt)
                    break
                except ValueError:
                    continue
        except:
            pass
    
    # Use provided amount or statement amount
    expense_amount = approve_data.amount if approve_data.amount is not None else abs(statement.amount_inr or 0)
    
    # Create expense record
    expense = Expense(
        statement_id=statement.id,
        time=expense_time or datetime.now(),
        type=expense_type,
        amount=expense_amount,
        category=approve_data.category,
        account=approve_data.account,
        notes=approve_data.notes or statement.transaction_details,
    )
    db.add(expense)
    
    # Mark statement as reviewed
    statement.review_status = ReviewStatus.REVIEWED.value
    statement.reviewed_datetime = datetime.now()
    
    db.commit()
    db.refresh(expense)
    
    return {
        "success": True,
        "message": "Statement approved and expense created",
        "statement": statement.to_dict(),
        "expense": expense.to_dict()
    }


@router.get("/expenses", summary="Get all expenses")
async def get_expenses(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> dict:
    """Get expense records with pagination."""
    total = db.query(Expense).count()
    records = db.query(Expense).order_by(Expense.id.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [r.to_dict() for r in records]
    }


# ============ New Endpoints ============

class ManualExpenseRequest(BaseModel):
    """Request model for creating a manual expense."""
    time: Optional[str] = None
    type: str = "(-) Expense"
    amount: float
    category: str
    account: str
    notes: Optional[str] = None


@router.delete("/tables/{table_name}/clear", summary="Clear all records from a table")
async def clear_table(table_name: str, db: Session = Depends(get_db)) -> dict:
    """Delete all records from specified table."""
    if table_name == "credit_card_statements":
        count = db.query(CreditCardStatement).count()
        db.query(CreditCardStatement).delete()
        db.commit()
        return {"success": True, "message": f"Deleted {count} records from credit_card_statements"}
    elif table_name == "expenses":
        count = db.query(Expense).count()
        db.query(Expense).delete()
        db.commit()
        return {"success": True, "message": f"Deleted {count} records from expenses"}
    else:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")


@router.get("/uploaded-files", summary="List unique uploaded files")
async def get_uploaded_files(db: Session = Depends(get_db)) -> dict:
    """Get list of unique filenames with record counts and metadata."""
    from sqlalchemy import case
    
    files = db.query(
        CreditCardStatement.filename,
        CreditCardStatement.account_type,
        CreditCardStatement.account_name,
        func.count(CreditCardStatement.id).label("record_count"),
        func.min(CreditCardStatement.uploaded_datetime).label("uploaded_at"),
        func.sum(case(
            (CreditCardStatement.review_status == "pending", 1),
            else_=0
        )).label("pending_count"),
        func.sum(case(
            (CreditCardStatement.review_status == "reviewed", 1),
            else_=0
        )).label("reviewed_count")
    ).group_by(
        CreditCardStatement.filename,
        CreditCardStatement.account_type,
        CreditCardStatement.account_name
    ).all()
    
    return {
        "files": [
            {
                "filename": f.filename,
                "account_type": f.account_type,
                "account_name": f.account_name,
                "record_count": f.record_count,
                "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
                "pending_count": f.pending_count or 0,
                "reviewed_count": f.reviewed_count or 0
            }
            for f in files
        ]
    }


@router.delete("/uploaded-files/{filename}", summary="Delete all records for a file")
async def delete_file_records(filename: str, db: Session = Depends(get_db)) -> dict:
    """Delete all statement records associated with a filename."""
    count = db.query(CreditCardStatement).filter(CreditCardStatement.filename == filename).count()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"No records found for file '{filename}'")
    
    db.query(CreditCardStatement).filter(CreditCardStatement.filename == filename).delete()
    db.commit()
    return {"success": True, "message": f"Deleted {count} records for file '{filename}'"}


@router.post("/expenses", summary="Create manual expense")
async def create_expense(expense_data: ManualExpenseRequest, db: Session = Depends(get_db)) -> dict:
    """Create an expense record manually (not from CSV)."""
    expense_time = None
    if expense_data.time:
        try:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"]:
                try:
                    expense_time = datetime.strptime(expense_data.time, fmt)
                    break
                except ValueError:
                    continue
        except:
            pass
    
    expense = Expense(
        statement_id=None,  # No linked statement for manual entry
        time=expense_time or datetime.now(),
        type=expense_data.type,
        amount=expense_data.amount,
        category=expense_data.category,
        account=expense_data.account,
        notes=expense_data.notes,
    )
    db.add(expense)
    db.commit()
    db.refresh(expense)
    
    return {"success": True, "message": "Expense created", "expense": expense.to_dict()}


@router.get("/expenses/export", summary="Export expenses as CSV")
async def export_expenses(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Export expense records as CSV with optional date filters."""
    query = db.query(Expense)
    
    # Apply date filters
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            query = query.filter(Expense.time >= start)
        except ValueError:
            pass
    
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d")
            # Include the entire end date
            end = end.replace(hour=23, minute=59, second=59)
            query = query.filter(Expense.time <= end)
        except ValueError:
            pass
    
    records = query.order_by(Expense.time.desc()).all()
    
    # Create CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Time", "Type", "Amount", "Category", "Account", "Notes", "Created"])
    
    for r in records:
        writer.writerow([
            r.id,
            r.time.strftime("%Y-%m-%d %H:%M") if r.time else "",
            r.type,
            r.amount,
            r.category,
            r.account,
            r.notes or "",
            r.created_datetime.strftime("%Y-%m-%d %H:%M") if r.created_datetime else ""
        ])
    
    output.seek(0)
    
    filename = f"expenses_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
