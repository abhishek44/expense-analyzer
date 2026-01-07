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
    """Add missing columns to existing tables."""
    with engine.connect() as conn:
        # Check and add account_type column
        try:
            conn.execute(text("SELECT account_type FROM credit_card_statements LIMIT 1"))
        except Exception:
            conn.execute(text("ALTER TABLE credit_card_statements ADD COLUMN account_type VARCHAR(50)"))
            conn.commit()
        
        # Check and add account_name column
        try:
            conn.execute(text("SELECT account_name FROM credit_card_statements LIMIT 1"))
        except Exception:
            conn.execute(text("ALTER TABLE credit_card_statements ADD COLUMN account_name VARCHAR(100)"))
            conn.commit()
