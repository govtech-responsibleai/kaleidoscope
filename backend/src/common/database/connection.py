"""
Database connection management.

Provides SQLAlchemy engine and session factory.
"""

import logging

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from src.common.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()

# Create SQLAlchemy engine.
# pool_size must be large enough to cover concurrent background jobs + their
# per-phase sub-sessions + incoming API request handlers simultaneously.
# Rule of thumb: batch_max_concurrent_jobs(3) * sessions_per_job(~5) + api_buffer(10) = ~25
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=20,        # Base connections to keep open
    max_overflow=10,     # Additional burst connections (total max: 30)
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


# Columns added after the original schema was created. `Base.metadata.create_all`
# creates missing tables but never alters existing ones, and this repo has no
# migration tooling configured, so `ensure_columns()` bridges the gap idempotently.
# Each entry: table name -> list of (column name, SQL type) tuples. Use portable
# types (e.g. VARCHAR) so this works on both SQLite (dev/test) and Postgres.
_EXPECTED_ADDED_COLUMNS = {
    "questions": [("language", "VARCHAR")],
}


def ensure_columns():
    """
    Add columns introduced after a table's original creation.

    Idempotent: inspects each table's existing columns and only issues
    `ALTER TABLE ... ADD COLUMN` for the ones that are missing. Safe to run on
    every startup, on both fresh DBs (no-op) and existing dev DBs.
    """
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    for table, columns in _EXPECTED_ADDED_COLUMNS.items():
        if table not in existing_tables:
            # Table doesn't exist yet; create_all() will build it with all columns.
            continue
        existing_columns = {col["name"] for col in inspector.get_columns(table)}
        for column_name, column_type in columns:
            if column_name in existing_columns:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}")
                    )
                logger.info("Added missing column %s.%s (%s)", table, column_name, column_type)
            except Exception as exc:  # noqa: BLE001 - never block startup on this
                logger.warning(
                    "Could not add column %s.%s: %s", table, column_name, exc
                )


def init_db():
    """
    Initialize database by creating all tables.

    Should be called on application startup.
    """
    from src.common.database.models import Target, Job, Persona, Question, User
    Base.metadata.create_all(bind=engine)
    ensure_columns()
