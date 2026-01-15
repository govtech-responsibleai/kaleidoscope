"""
Migration: Add error_message column to qa_jobs table

This migration adds an error_message column to store error details
when a QA job fails during answer generation or scoring.

Run this script manually:
    python -m src.common.database.migrations.002_add_qa_job_error_message
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from sqlalchemy import text
from src.common.database.connection import engine


def upgrade():
    """Add error_message column to qa_jobs table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'qa_jobs' AND column_name = 'error_message'
        """))

        if result.fetchone() is None:
            conn.execute(text("""
                ALTER TABLE qa_jobs
                ADD COLUMN error_message TEXT
            """))
            conn.commit()
            print("Successfully added error_message column to qa_jobs table")
        else:
            print("Column error_message already exists in qa_jobs table")


def downgrade():
    """Remove error_message column from qa_jobs table."""
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE qa_jobs
            DROP COLUMN IF EXISTS error_message
        """))
        conn.commit()
        print("Successfully removed error_message column from qa_jobs table")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database migration")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Downgrade (remove column) instead of upgrade"
    )
    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
