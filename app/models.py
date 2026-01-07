"""SQLAlchemy ORM models for fixed database tables."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ReviewStatus(str, Enum):
    """Review status for credit card statements."""
    PENDING = "pending"
    REVIEWED = "reviewed"


class CreditCardStatement(Base):
    """Credit card statement records uploaded from CSV files."""
    
    __tablename__ = "credit_card_statements"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String(50))
    sr_no = Column(String(50))
    transaction_details = Column(String(500))
    reward_points = Column(Float, nullable=True)
    intl_amount = Column(Float, nullable=True)
    amount_inr = Column(Float, nullable=True)
    billing_sign = Column(String(10), nullable=True)  # CR for credit
    filename = Column(String(255))
    uploaded_datetime = Column(DateTime, default=datetime.now)
    
    # Account metadata (captured during upload)
    account_type = Column(String(50), nullable=True)  # Credit Card, Savings
    account_name = Column(String(100), nullable=True)  # Account name/number
    
    # Review tracking
    review_status = Column(String(20), default=ReviewStatus.PENDING.value)
    reviewed_datetime = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<CreditCardStatement(id={self.id}, date={self.date}, status={self.review_status})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "date": self.date,
            "sr_no": self.sr_no,
            "transaction_details": self.transaction_details,
            "reward_points": self.reward_points,
            "intl_amount": self.intl_amount,
            "amount_inr": self.amount_inr,
            "billing_sign": self.billing_sign,
            "filename": self.filename,
            "uploaded_datetime": self.uploaded_datetime.isoformat() if self.uploaded_datetime else None,
            "account_type": self.account_type,
            "account_name": self.account_name,
            "review_status": self.review_status,
            "reviewed_datetime": self.reviewed_datetime.isoformat() if self.reviewed_datetime else None,
        }


class Expense(Base):
    """Converted expense records from approved statements."""
    
    __tablename__ = "expenses"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    statement_id = Column(Integer, nullable=True)  # Link to source statement
    time = Column(DateTime, nullable=True)
    type = Column(String(50))  # Income or Expense
    amount = Column(Float)
    category = Column(String(100))
    account = Column(String(100))
    notes = Column(String(500), nullable=True)
    created_datetime = Column(DateTime, default=datetime.now)
    
    def __repr__(self):
        return f"<Expense(id={self.id}, type={self.type}, amount={self.amount})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "statement_id": self.statement_id,
            "time": self.time.isoformat() if self.time else None,
            "type": self.type,
            "amount": self.amount,
            "category": self.category,
            "account": self.account,
            "notes": self.notes,
            "created_datetime": self.created_datetime.isoformat() if self.created_datetime else None,
        }


# Column mapping for CSV headers to model fields
CREDIT_CARD_COLUMN_MAPPING = {
    # Original CSV header -> Model field name
    "Date": "date",
    "Sr.No.": "sr_no",
    "Transaction Details": "transaction_details",
    "Reward Point Header": "reward_points",
    "Intl.Amount": "intl_amount",
    "Amount(in Rs)": "amount_inr",
    "BillingAmountSign": "billing_sign",
}
