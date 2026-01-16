"""
Migration: Add source and orig_id columns to questions table

This migration adds columns needed for the question upload feature:
- source: tracks whether question was job_generated or uploaded
- orig_id: stores original ID from user's uploaded file

Run this script manually:
    python -m src.common.database.migrations.005_add_question_upload_columns
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from sqlalchemy import text
from src.common.database.connection import engine


def column_exists(conn, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = conn.execute(text("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = :table_name AND column_name = :column_name
    """), {"table_name": table_name, "column_name": column_name})
    return result.fetchone() is not None


def upgrade():
    """Add source and orig_id columns to questions table."""
    with engine.connect() as conn:
        # Add source column
        if not column_exists(conn, 'questions', 'source'):
            # Create the enum type if it doesn't exist
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'questionsourceenum') THEN
                        CREATE TYPE questionsourceenum AS ENUM ('job_generated', 'uploaded');
                    END IF;
                END
                $$;
            """))

            # Add the column with default value for existing rows
            conn.execute(text("""
                ALTER TABLE questions
                ADD COLUMN source questionsourceenum NOT NULL DEFAULT 'job_generated'
            """))
            conn.commit()
            print("Successfully added source column to questions table")
        else:
            print("Column source already exists in questions table")

        # Add orig_id column
        if not column_exists(conn, 'questions', 'orig_id'):
            conn.execute(text("""
                ALTER TABLE questions
                ADD COLUMN orig_id VARCHAR
            """))
            # Add index for orig_id lookups
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_questions_orig_id ON questions(orig_id)
            """))
            conn.commit()
            print("Successfully added orig_id column to questions table")
        else:
            print("Column orig_id already exists in questions table")


def downgrade():
    """Remove source and orig_id columns from questions table."""
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE questions
            DROP COLUMN IF EXISTS source
        """))
        conn.execute(text("""
            ALTER TABLE questions
            DROP COLUMN IF EXISTS orig_id
        """))
        conn.execute(text("""
            DROP INDEX IF EXISTS ix_questions_orig_id
        """))
        conn.execute(text("""
            DROP TYPE IF EXISTS questionsourceenum
        """))
        conn.commit()
        print("Successfully removed source and orig_id columns from questions table")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database migration")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Downgrade (remove columns) instead of upgrade"
    )
    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
