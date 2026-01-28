"""Database configuration and session management."""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.models import Base

# Create engine with SQLite-specific settings
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=settings.DEBUG,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Dependency to get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database and create all tables."""
    Base.metadata.create_all(bind=engine)
    # Run migrations for existing databases
    migrate_db()


def migrate_db():
    """Migrate from old schema to new transactions schema."""
    with engine.connect() as conn:
        # Check if old credit_card_statements table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='credit_card_statements'"
        ))
        old_table_exists = result.fetchone() is not None
        
        # Check if new transactions table exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='transactions'"
        ))
        new_table_exists = result.fetchone() is not None
        
        if old_table_exists and not new_table_exists:
            print("Migrating from credit_card_statements to transactions schema...")
            
            # Create new transactions table (will be created by Base.metadata.create_all)
            # But we need to migrate data first, so create it manually
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS transactions (
                    Id INTEGER PRIMARY KEY AUTOINCREMENT,
                    Date VARCHAR(50),
                    Details VARCHAR(500),
                    Debit FLOAT,
                    Credit FLOAT,
                    Account_name VARCHAR(100),
                    filename VARCHAR(255),
                    review_status VARCHAR(20) DEFAULT 'pending',
                    review_datetime DATETIME,
                    uploaded_datetime DATETIME,
                    Category VARCHAR(100),
                    Notes VARCHAR(500)
                )
            """))
            
            # Migrate data from old table to new table
            # Convert amount_inr + billing_sign to Debit/Credit
            conn.execute(text("""
                INSERT INTO transactions (
                    Date, Details, Debit, Credit, Account_name, filename,
                    review_status, review_datetime, uploaded_datetime
                )
                SELECT 
                    date,
                    transaction_details,
                    CASE WHEN billing_sign != 'CR' OR billing_sign IS NULL 
                         THEN ABS(amount_inr) ELSE NULL END as Debit,
                    CASE WHEN billing_sign = 'CR' 
                         THEN ABS(amount_inr) ELSE NULL END as Credit,
                    account_name,
                    filename,
                    review_status,
                    reviewed_datetime,
                    uploaded_datetime
                FROM credit_card_statements
            """))
            
            # Drop old table
            conn.execute(text("DROP TABLE credit_card_statements"))
            
            print("Migration completed: credit_card_statements -> transactions")
        
        # Drop expenses table if it exists
        result = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'"
        ))
        if result.fetchone() is not None:
            print("Dropping expenses table...")
            conn.execute(text("DROP TABLE expenses"))
            print("Expenses table dropped")
        
        conn.commit()
