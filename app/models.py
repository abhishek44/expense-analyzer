"""SQLAlchemy ORM models for fixed database tables."""

from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ReviewStatus(str, Enum):
    """Review status for transactions."""
    PENDING = "pending"
    REVIEWED = "reviewed"


class Transaction(Base):
    """Transaction records uploaded from CSV files."""
    
    __tablename__ = "transactions"
    
    Id = Column(Integer, primary_key=True, autoincrement=True)
    Date = Column(String(50))
    Details = Column(String(500))
    Debit = Column(Float, nullable=True)
    Credit = Column(Float, nullable=True)
    Account_name = Column(String(100), nullable=True)
    Account_type = Column(String(50), nullable=True)
    filename = Column(String(255))
    review_status = Column(String(20), default=ReviewStatus.PENDING.value)
    review_datetime = Column(DateTime, nullable=True)
    uploaded_datetime = Column(DateTime, default=datetime.now)
    Category = Column(String(100), nullable=True)
    Notes = Column(String(500), nullable=True)
    
    def __repr__(self):
        return f"<Transaction(Id={self.Id}, Date={self.Date}, status={self.review_status})>"
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "Id": self.Id,
            "Date": self.Date,
            "Details": self.Details,
            "Debit": self.Debit,
            "Credit": self.Credit,
            "Account_name": self.Account_name,
            "Account_type": self.Account_type,
            "filename": self.filename,
            "review_status": self.review_status,
            "review_datetime": self.review_datetime.isoformat() if self.review_datetime else None,
            "uploaded_datetime": self.uploaded_datetime.isoformat() if self.uploaded_datetime else None,
            "Category": self.Category,
            "Notes": self.Notes,
        }


# Column mapping for CSV headers to model fields
# Strict Column mapping for CSV headers to model fields
TRANSACTION_COLUMN_MAPPING = {
    "Date": "Date",
    "Details": "Details",
    "Debit": "Debit",
    "Credit": "Credit",
    "AccountName": "Account_name",
    "AccountType": "Account_type",
    "Category": "Category",
    "Notes": "Notes",
    "ReviewStatus": "review_status",
    "ReviewdateTime": "review_datetime",
}
