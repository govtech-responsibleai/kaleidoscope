"""
Database connection management.

Provides SQLAlchemy engine and session factory.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from src.common.config import get_settings

settings = get_settings()

# Create SQLAlchemy engine
# Note: Airbase limits each app to ~10 connections, recommend 5-8 for app use
# pool_size + max_overflow = 3 + 4 = 7 connections (leaves 3 for admin)
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=3,         # Base connections to keep open
    max_overflow=4,      # Additional connections when needed (total max: 7)
    pool_timeout=30,     # Wait up to 30s for a connection before failing
    pool_recycle=1800,   # Recycle connections after 30 minutes
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create declarative base for ORM models
Base = declarative_base()


def get_db():
    """
    Dependency for FastAPI routes to get database session.

    Usage:
        @app.get("/items")
        def read_items(db: Session = Depends(get_db)):
            return db.query(Item).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Initialize database by creating all tables.

    Should be called on application startup.
    """
    from src.common.database.models import Target, Job, Persona, Question, User
    Base.metadata.create_all(bind=engine)
