"""Make users.hashed_password nullable for Google-auth accounts.

Run from backend/:
    uv run python -m src.common.database.migrations.make_user_hashed_password_nullable
"""

import logging

from sqlalchemy import create_engine, text

from src.common.config import get_settings

logger = logging.getLogger(__name__)


def main() -> None:
    """Apply the nullable hashed_password migration."""
    settings = get_settings()
    engine = create_engine(settings.database_url)
    with engine.begin() as connection:
        dialect = connection.dialect.name
        if dialect == "postgresql":
            connection.execute(text("ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL"))
        elif dialect == "sqlite":
            logger.info("SQLite test databases use SQLAlchemy metadata; no migration needed.")
        else:
            raise RuntimeError(f"Unsupported database dialect for migration: {dialect}")
    logger.info("users.hashed_password is nullable")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
