"""Database configuration and session management."""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.models import Base

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database — creates all tables from models."""
    Base.metadata.create_all(bind=engine)

    # Migrate: add new columns to existing tables if missing
    with engine.connect() as conn:
        for col_name, col_type in [
            ("statement_date", "DATE"),
            ("mapping_date", "DATE"),
            ("payment_verification", "TEXT"),
        ]:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE transactions ADD COLUMN {col_name} {col_type}"
                    )
                )
                conn.commit()
                logger.info(f"Migration: added column '{col_name}' to transactions table")
            except Exception:
                # Column already exists — ignore
                pass

    # Seed default budgets if table is empty
    from app.models import Budget
    db = SessionLocal()
    try:
        if db.query(Budget).count() == 0:
            default_budgets = [
                {"l1_category_name": "Shopping", "amount_limit": 40000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
                {"l1_category_name": "Personal", "amount_limit": 15000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
                {"l1_category_name": "Groceries", "amount_limit": 10000.00, "period": "MONTHLY", "is_active": 1, "rollover": 1},
                {"l1_category_name": "Travel", "amount_limit": 10000.00, "period": "MONTHLY", "is_active": 1, "rollover": 1},
                {"l1_category_name": "Food & Dining", "amount_limit": 8000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
                {"l1_category_name": "Health", "amount_limit": 8000.00, "period": "MONTHLY", "is_active": 1, "rollover": 1},
                {"l1_category_name": "Transport", "amount_limit": 6000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
                {"l1_category_name": "Bills & Utilities", "amount_limit": 4000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
                {"l1_category_name": "Entertainment", "amount_limit": 2000.00, "period": "MONTHLY", "is_active": 1, "rollover": 0},
            ]
            for b in default_budgets:
                db.add(Budget(**b))
            db.commit()
    except Exception as e:
        logger.error(f"Error seeding default budgets: {e}")
    finally:
        db.close()
