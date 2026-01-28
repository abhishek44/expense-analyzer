"""CSV upload router with file upload and transaction management endpoints."""

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
from app.models import Transaction, ReviewStatus
from app.schemas import UploadResponse, ErrorResponse
from app.services.csv_service import process_transaction_csv

router = APIRouter(prefix="/api", tags=["Transactions"])


# Request/Response Models
class TransactionUpdate(BaseModel):
    """Request model for updating a transaction."""
    Date: Optional[str] = None
    Details: Optional[str] = None
    Debit: Optional[float] = None
    Credit: Optional[float] = None
    Account_name: Optional[str] = None
    Account_type: Optional[str] = None


class ReviewRequest(BaseModel):
    """Request model for reviewing a transaction."""
    Category: str
    Notes: Optional[str] = None


class ManualTransactionRequest(BaseModel):
    """Request model for creating a manual transaction."""
    Date: Optional[str] = None
    Details: str
    Debit: Optional[float] = None
    Credit: Optional[float] = None
    Account_name: str
    Account_type: str
    Category: Optional[str] = None
    Notes: Optional[str] = None


@router.post(
    "/upload-csv",
    response_model=UploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Server error"},
    },
    summary="Upload transaction CSV",
)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to upload"),
    account_name: str = Form(None, description="Account name or number"),
    db: Session = Depends(get_db)
) -> UploadResponse:
    """Upload CSV file to transactions table with account metadata."""
    
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
        result = await process_transaction_csv(
            db=db,
            file_content=content,
            filename=file.filename,
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
    total = db.query(Transaction).count()
    pending = db.query(Transaction).filter(
        Transaction.review_status == ReviewStatus.PENDING.value
    ).count()
    reviewed = db.query(Transaction).filter(
        Transaction.review_status == ReviewStatus.REVIEWED.value
    ).count()
    
    return {
        "tables": [
            {
                "name": "transactions",
                "description": "Transaction records",
                "total": total,
                "pending": pending,
                "reviewed": reviewed,
                "uploadable": True
            }
        ]
    }


@router.get("/transactions", summary="Get all transactions")
async def get_transactions(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[str] = None,
    filename_filter: Optional[str] = None,
    account_name: Optional[str] = None,
    account_type: Optional[str] = None,
    db: Session = Depends(get_db)
) -> dict:
    """Get transactions with pagination and optional filters."""
    query = db.query(Transaction)
    
    if status_filter and status_filter in [s.value for s in ReviewStatus]:
        query = query.filter(Transaction.review_status == status_filter)
    
    if filename_filter:
        query = query.filter(Transaction.filename == filename_filter)

    if account_name:
        query = query.filter(Transaction.Account_name.ilike(f"%{account_name}%"))

    if account_type:
        query = query.filter(Transaction.Account_type.ilike(f"%{account_type}%"))
    
    total = query.count()
    records = query.order_by(Transaction.Id.desc()).offset(skip).limit(limit).all()
    
    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": [r.to_dict() for r in records]
    }


@router.get("/filter-options", summary="Get filter options")
async def get_filter_options(db: Session = Depends(get_db)) -> dict:
    """Get distinct account names and types for filtering."""
    account_names = db.query(Transaction.Account_name).distinct().filter(Transaction.Account_name.isnot(None)).all()
    account_types = db.query(Transaction.Account_type).distinct().filter(Transaction.Account_type.isnot(None)).all()
    
    return {
        "account_names": sorted([r[0] for r in account_names if r[0]]),
        "account_types": sorted([r[0] for r in account_types if r[0]])
    }


@router.get("/transactions/{transaction_id}", summary="Get single transaction")
async def get_transaction(transaction_id: int, db: Session = Depends(get_db)) -> dict:
    """Get a single transaction by ID."""
    transaction = db.query(Transaction).filter(Transaction.Id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    return transaction.to_dict()


@router.patch("/transactions/{transaction_id}", summary="Update transaction")
async def update_transaction(
    transaction_id: int,
    update_data: TransactionUpdate,
    db: Session = Depends(get_db)
) -> dict:
    """Update a transaction."""
    transaction = db.query(Transaction).filter(Transaction.Id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        setattr(transaction, field, value)
    
    db.commit()
    db.refresh(transaction)
    
    return {"success": True, "message": "Transaction updated", "data": transaction.to_dict()}


@router.post("/transactions/{transaction_id}/review", summary="Review transaction")
async def review_transaction(
    transaction_id: int,
    review_data: ReviewRequest,
    db: Session = Depends(get_db)
) -> dict:
    """
    Review a transaction and mark it as reviewed.
    
    - Marks the transaction as reviewed
    - Updates Category and Notes fields
    """
    transaction = db.query(Transaction).filter(Transaction.Id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    # Allow re-reviewing (editing)
    # previously: if transaction.review_status == ReviewStatus.REVIEWED.value: ...
    
    # Update transaction with review data
    transaction.Category = review_data.Category
    transaction.Notes = review_data.Notes
    transaction.review_status = ReviewStatus.REVIEWED.value
    transaction.review_datetime = datetime.now()
    
    db.commit()
    db.refresh(transaction)
    
    return {
        "success": True,
        "message": "Transaction reviewed successfully",
        "transaction": transaction.to_dict()
    }


@router.delete("/transactions/{transaction_id}", summary="Delete a transaction")
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)) -> dict:
    """Delete a single transaction."""
    transaction = db.query(Transaction).filter(Transaction.Id == transaction_id).first()
    
    if not transaction:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    
    db.delete(transaction)
    db.commit()
    
    return {"success": True, "message": "Transaction deleted successfully"}


@router.delete("/tables/{table_name}/clear", summary="Clear all records from a table")
async def clear_table(table_name: str, db: Session = Depends(get_db)) -> dict:
    """Delete all records from specified table."""
    if table_name == "transactions":
        count = db.query(Transaction).count()
        db.query(Transaction).delete()
        db.commit()
        return {"success": True, "message": f"Deleted {count} records from transactions"}
    else:
        raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")


@router.get("/uploaded-files", summary="List unique uploaded files")
async def get_uploaded_files(db: Session = Depends(get_db)) -> dict:
    """Get list of unique filenames with record counts and metadata."""
    from sqlalchemy import case
    
    files = db.query(
        Transaction.filename,
        func.count(Transaction.Id).label("record_count"),
        func.min(Transaction.uploaded_datetime).label("uploaded_at"),
        func.sum(case(
            (Transaction.review_status == "pending", 1),
            else_=0
        )).label("pending_count"),
        func.sum(case(
            (Transaction.review_status == "reviewed", 1),
            else_=0
        )).label("reviewed_count")
    ).group_by(
        Transaction.filename
    ).all()
    
    return {
        "files": [
            {
                "filename": f.filename,
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
    """Delete all transaction records associated with a filename."""
    count = db.query(Transaction).filter(Transaction.filename == filename).count()
    if count == 0:
        raise HTTPException(status_code=404, detail=f"No records found for file '{filename}'")
    
    db.query(Transaction).filter(Transaction.filename == filename).delete()
    db.commit()
    return {"success": True, "message": f"Deleted {count} records for file '{filename}'"}


@router.post("/transactions", summary="Create manual transaction")
async def create_transaction(transaction_data: ManualTransactionRequest, db: Session = Depends(get_db)) -> dict:
    """Create a transaction record manually (not from CSV)."""
    transaction_date = None
    if transaction_data.Date:
        try:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"]:
                try:
                    transaction_date = datetime.strptime(transaction_data.Date, fmt)
                    break
                except ValueError:
                    continue
        except:
            pass
    
    # Use current date if not provided or invalid
    if not transaction_date:
        transaction_date = datetime.now()
    
    transaction = Transaction(
        Date=transaction_date.strftime("%Y-%m-%d"),
        Details=transaction_data.Details,
        Debit=transaction_data.Debit,
        Credit=transaction_data.Credit,
        Account_name=transaction_data.Account_name,
        Account_type=transaction_data.Account_type,
        filename="manual_entry",
        Category=transaction_data.Category,
        Notes=transaction_data.Notes,
        review_status=ReviewStatus.REVIEWED.value if transaction_data.Category else ReviewStatus.PENDING.value,
        review_datetime=datetime.now() if transaction_data.Category else None,
        uploaded_datetime=datetime.now()
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    
    return {"success": True, "message": "Transaction created", "transaction": transaction.to_dict()}
