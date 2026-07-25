"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, Integer, String, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class ReviewStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class FlowDirection(str, Enum):
    DEBIT = "debit"
    CREDIT = "credit"
    TRANSFER = "transfer"


class CategorisedBy(str, Enum):
    RULE = "rule"
    MODEL = "model"
    USER = "user"


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    level = Column(Integer, nullable=False)  # 1 = L1, 2 = L2
    parent_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    domain = Column(String(50), nullable=True)  # NECESSITIES/LIFESTYLE/FINANCIAL/INCOME
    color_hex = Column(String(20), nullable=True)
    is_archived = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    parent = relationship("Category", remote_side=[id], backref="children")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "level": self.level,
            "parent_id": self.parent_id,
            "domain": self.domain,
            "color_hex": self.color_hex,
            "is_archived": self.is_archived,
        }


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Raw ingest — never modified after insert
    raw_date = Column(String(50), nullable=False)
    raw_details = Column(String(500), nullable=False)
    debit = Column(Float, nullable=True)
    credit = Column(Float, nullable=True)
    account_name = Column(String(100), nullable=True)
    account_type = Column(String(50), nullable=True, index=True)
    filename = Column(String(255), nullable=False, index=True)
    uploaded_at = Column(DateTime, nullable=False, default=datetime.now)
    notes = Column(String(500), nullable=True)

    # Derived: financials
    amount = Column(Float, nullable=True)
    flow_direction = Column(String(10), nullable=True)

    # Derived: date features
    parsed_date = Column(String(10), nullable=True, index=True)
    day_of_week = Column(Integer, nullable=True)
    month = Column(Integer, nullable=True)
    is_weekend = Column(Integer, nullable=True)

    # Derived: merchant
    merchant_name = Column(String(200), nullable=True)
    is_platform_merchant = Column(Integer, default=0)
    cleaned_details = Column(String(500), nullable=True)

    # Categorisation
    l1_category_id = Column(String(36), ForeignKey("categories.id"), nullable=True, index=True)
    l2_category_id = Column(String(36), ForeignKey("categories.id"), nullable=True, index=True)
    l2_confidence = Column(Float, nullable=True)
    categorised_by = Column(String(10), nullable=True)

    # Statement metadata
    statement_date = Column(Date, nullable=True)
    mapping_date = Column(Date, nullable=True)
    payment_verification = Column(String(200), nullable=True)

    # Review
    review_status = Column(String(20), default=ReviewStatus.PENDING.value, nullable=False, index=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Relationships
    l1_category = relationship("Category", foreign_keys=[l1_category_id])
    l2_category = relationship("Category", foreign_keys=[l2_category_id])

    def to_dict(self):
        return {
            "id": self.id,
            "raw_date": self.raw_date,
            "raw_details": self.raw_details,
            "debit": self.debit,
            "credit": self.credit,
            "account_name": self.account_name,
            "account_type": self.account_type,
            "filename": self.filename,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "notes": self.notes,
            "amount": self.amount,
            "flow_direction": self.flow_direction,
            "parsed_date": self.parsed_date,
            "day_of_week": self.day_of_week,
            "month": self.month,
            "is_weekend": self.is_weekend,
            "merchant_name": self.merchant_name,
            "is_platform_merchant": self.is_platform_merchant,
            "cleaned_details": self.cleaned_details,
            "l1_category_id": self.l1_category_id,
            "l2_category_id": self.l2_category_id,
            "l1_category_name": self.l1_category.name if self.l1_category else None,
            "l2_category_name": self.l2_category.name if self.l2_category else None,
            "l2_confidence": self.l2_confidence,
            "categorised_by": self.categorised_by,
            "statement_date": self.statement_date.isoformat() if self.statement_date else None,
            "mapping_date": self.mapping_date.isoformat() if self.mapping_date else None,
            "payment_verification": self.payment_verification,
            "review_status": self.review_status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class MerchantMapping(Base):
    __tablename__ = "merchant_mappings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_name = Column(String(200), nullable=False, unique=True)
    default_l1_category_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    default_l2_category_id = Column(String(36), ForeignKey("categories.id"), nullable=True)
    occurrence_count = Column(Integer, default=1)
    last_seen_date = Column(String(10), nullable=True)
    is_ambiguous = Column(Integer, default=0)
    notes_required = Column(Integer, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "merchant_name": self.merchant_name,
            "default_l1_category_id": self.default_l1_category_id,
            "default_l2_category_id": self.default_l2_category_id,
            "occurrence_count": self.occurrence_count,
            "last_seen_date": self.last_seen_date,
            "is_ambiguous": self.is_ambiguous,
            "notes_required": self.notes_required,
        }


class AccountType(str, Enum):
    SAVINGS = "SAVINGS"
    CURRENT = "CURRENT"
    CREDIT_CARD = "CREDIT_CARD"
    CASH = "CASH"
    WALLET = "WALLET"
    INVESTMENT = "INVESTMENT"


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True)
    name = Column(String(100), nullable=False)
    account_type = Column(String(20), nullable=False)
    currency = Column(String(10), nullable=False, default="INR")
    opening_balance = Column(Float, nullable=False, default=0)
    is_archived = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=datetime.now)
    updated_at = Column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "account_type": self.account_type,
            "currency": self.currency,
            "opening_balance": self.opening_balance,
            "is_archived": self.is_archived,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Budget(Base):
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    l1_category_name = Column(String(100), nullable=False)
    amount_limit = Column(Float, nullable=False)
    period = Column(String(20), nullable=False, default="MONTHLY")
    is_active = Column(Integer, nullable=False, default=1)  # 1 = active, 0 = inactive
    rollover = Column(Integer, nullable=False, default=0)   # 1 = yes, 0 = no

    def to_dict(self):
        return {
            "id": self.id,
            "l1_category_name": self.l1_category_name,
            "amount_limit": self.amount_limit,
            "period": self.period,
            "is_active": bool(self.is_active),
            "rollover": bool(self.rollover),
        }
