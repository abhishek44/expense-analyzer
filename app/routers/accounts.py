"""Accounts router with CRUD endpoints for account management."""

import uuid
from datetime import datetime
from typing import Optional, List
from dateutil import parser as date_parser

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models import Account, AccountType, Transaction

router = APIRouter(prefix="/api", tags=["Accounts"])


# Request/Response Models
class CreateAccountRequest(BaseModel):
    """Request model for creating an account."""
    name: str = Field(..., min_length=2, max_length=100)
    account_type: str
    currency: str = "INR"
    opening_balance: float = 0.0
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        v = v.strip()
        if len(v) < 2:
            raise ValueError('Name must be at least 2 characters')
        return v
    
    @field_validator('account_type')
    @classmethod
    def validate_account_type(cls, v):
        valid_types = [t.value for t in AccountType]
        if v not in valid_types:
            raise ValueError(f'Invalid account type. Must be one of: {", ".join(valid_types)}')
        return v
    
    @field_validator('opening_balance')
    @classmethod
    def validate_opening_balance(cls, v):
        # Round to 2 decimal places
        return round(v, 2)


class UpdateAccountRequest(BaseModel):
    """Request model for updating an account."""
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    account_type: Optional[str] = None
    currency: Optional[str] = None
    opening_balance: Optional[float] = None
    is_archived: Optional[int] = None
    
    @field_validator('name')
    @classmethod
    def validate_name(cls, v):
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError('Name must be at least 2 characters')
        return v
    
    @field_validator('account_type')
    @classmethod
    def validate_account_type(cls, v):
        if v is not None:
            valid_types = [t.value for t in AccountType]
            if v not in valid_types:
                raise ValueError(f'Invalid account type. Must be one of: {", ".join(valid_types)}')
        return v
    
    @field_validator('opening_balance')
    @classmethod
    def validate_opening_balance(cls, v):
        if v is not None:
            return round(v, 2)
        return v


class AccountBatchUpsert(BaseModel):
    """Model for batch upserting accounts from mobile sync."""
    id: str  # UUID from mobile
    name: str
    account_type: str
    currency: str = "INR"
    opening_balance: float = 0.0
    is_archived: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@router.get("/accounts", summary="Get all accounts")
async def get_accounts(
    include_archived: bool = False,
    since: Optional[str] = None,
    db: Session = Depends(get_db)
) -> dict:
    """Get all accounts with computed balances. Use 'since' parameter for incremental sync."""
    query = db.query(Account)
    
    if not include_archived:
        query = query.filter(Account.is_archived == 0)
    
    # Filter by updated_at for incremental sync
    if since:
        try:
            since_dt = date_parser.parse(since)
            query = query.filter(Account.updated_at >= since_dt)
        except (ValueError, TypeError):
            pass  # Ignore invalid date format
    
    accounts = query.order_by(Account.name).all()
    
    # Compute balances for each account
    accounts_with_balances = []
    for account in accounts:
        # Get sum of credits and debits for this account
        credit_sum = db.query(func.sum(Transaction.Credit)).filter(
            Transaction.Account_name == account.name
        ).scalar() or 0
        
        debit_sum = db.query(func.sum(Transaction.Debit)).filter(
            Transaction.Account_name == account.name
        ).scalar() or 0
        
        balance = account.opening_balance + credit_sum - debit_sum
        
        account_dict = account.to_dict()
        account_dict['balance'] = round(balance, 2)
        accounts_with_balances.append(account_dict)
    
    return {
        "accounts": accounts_with_balances,
        "total": len(accounts_with_balances)
    }


@router.get("/accounts/{account_id}", summary="Get single account")
async def get_account(account_id: str, db: Session = Depends(get_db)) -> dict:
    """Get a single account by ID with computed balance."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    
    # Compute balance
    credit_sum = db.query(func.sum(Transaction.Credit)).filter(
        Transaction.Account_name == account.name
    ).scalar() or 0
    
    debit_sum = db.query(func.sum(Transaction.Debit)).filter(
        Transaction.Account_name == account.name
    ).scalar() or 0
    
    balance = account.opening_balance + credit_sum - debit_sum
    
    account_dict = account.to_dict()
    account_dict['balance'] = round(balance, 2)
    
    return account_dict


@router.post("/accounts", summary="Create account")
async def create_account(
    account_data: CreateAccountRequest,
    db: Session = Depends(get_db)
) -> dict:
    """Create a new account."""
    # Check if account with same name exists
    existing = db.query(Account).filter(Account.name == account_data.name.strip()).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with name '{account_data.name}' already exists"
        )
    
    now = datetime.now()
    account = Account(
        id=str(uuid.uuid4()),
        name=account_data.name.strip(),
        account_type=account_data.account_type,
        currency=account_data.currency,
        opening_balance=account_data.opening_balance,
        is_archived=0,
        created_at=now,
        updated_at=now
    )
    
    db.add(account)
    db.commit()
    db.refresh(account)
    
    account_dict = account.to_dict()
    account_dict['balance'] = account.opening_balance
    
    return {
        "success": True,
        "message": "Account created successfully",
        "account": account_dict
    }


@router.post("/accounts/batch", summary="Batch upsert accounts")
async def upsert_accounts(
    accounts: List[AccountBatchUpsert],
    db: Session = Depends(get_db)
) -> dict:
    """Batch upsert accounts for sync. Updates existing or inserts new."""
    results = []
    
    for acc_data in accounts:
        existing = db.query(Account).filter(Account.id == acc_data.id).first()
        
        if existing:
            # Update if mobile version is newer
            mobile_updated = None
            if acc_data.updated_at:
                try:
                    mobile_updated = date_parser.parse(acc_data.updated_at)
                except (ValueError, TypeError):
                    mobile_updated = None
            
            # Update if mobile has newer timestamp or no timestamp comparison possible
            if mobile_updated is None or existing.updated_at is None or mobile_updated > existing.updated_at:
                existing.name = acc_data.name
                existing.account_type = acc_data.account_type
                existing.currency = acc_data.currency
                existing.opening_balance = acc_data.opening_balance
                existing.is_archived = acc_data.is_archived
                existing.updated_at = datetime.now()
            results.append(existing)
        else:
            # Insert new
            now = datetime.now()
            account = Account(
                id=acc_data.id,
                name=acc_data.name,
                account_type=acc_data.account_type,
                currency=acc_data.currency,
                opening_balance=acc_data.opening_balance,
                is_archived=acc_data.is_archived,
                created_at=now,
                updated_at=now
            )
            db.add(account)
            results.append(account)
    
    db.commit()
    for acc in results:
        db.refresh(acc)
    
    return {
        "success": True,
        "message": f"Synced {len(results)} accounts",
        "accounts": [a.to_dict() for a in results]
    }


@router.patch("/accounts/{account_id}", summary="Update account")
async def update_account(
    account_id: str,
    update_data: UpdateAccountRequest,
    db: Session = Depends(get_db)
) -> dict:
    """Update an account."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    
    # Check for duplicate name if name is being updated
    if update_data.name is not None:
        existing = db.query(Account).filter(
            Account.name == update_data.name.strip(),
            Account.id != account_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Account with name '{update_data.name}' already exists"
            )
    
    # Update only provided fields
    update_dict = update_data.model_dump(exclude_unset=True)
    for field, value in update_dict.items():
        if value is not None:
            setattr(account, field, value)
    
    account.updated_at = datetime.now()
    
    db.commit()
    db.refresh(account)
    
    # Compute balance
    credit_sum = db.query(func.sum(Transaction.Credit)).filter(
        Transaction.Account_name == account.name
    ).scalar() or 0
    
    debit_sum = db.query(func.sum(Transaction.Debit)).filter(
        Transaction.Account_name == account.name
    ).scalar() or 0
    
    balance = account.opening_balance + credit_sum - debit_sum
    
    account_dict = account.to_dict()
    account_dict['balance'] = round(balance, 2)
    
    return {
        "success": True,
        "message": "Account updated successfully",
        "account": account_dict
    }


@router.delete("/accounts/{account_id}", summary="Delete account")
async def delete_account(account_id: str, db: Session = Depends(get_db)) -> dict:
    """Delete an account."""
    account = db.query(Account).filter(Account.id == account_id).first()
    
    if not account:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    
    db.delete(account)
    db.commit()
    
    return {
        "success": True,
        "message": f"Account '{account.name}' deleted successfully"
    }


@router.get("/account-types", summary="Get available account types")
async def get_account_types() -> dict:
    """Get list of available account types."""
    return {
        "account_types": [
            {"value": t.value, "label": t.value.replace("_", " ").title()}
            for t in AccountType
        ]
    }
