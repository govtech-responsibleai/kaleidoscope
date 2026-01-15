"""
Migration: Add model_label column to judges table

This migration adds a model_label column to store the display label
for the model (e.g., "Gemini 2.5 Flash" instead of "litellm_proxy/gemini-2.5-flash").

Run this script manually:
    python -m src.common.database.migrations.003_add_judge_model_label
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from sqlalchemy import text
from src.common.database.connection import engine


def upgrade():
    """Add model_label column to judges table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'judges' AND column_name = 'model_label'
        """))

        if result.fetchone() is None:
            conn.execute(text("""
                ALTER TABLE judges
                ADD COLUMN model_label VARCHAR
            """))
            conn.commit()
            print("Successfully added model_label column to judges table")
        else:
            print("Column model_label already exists in judges table")


def downgrade():
    """Remove model_label column from judges table."""
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE judges
            DROP COLUMN IF EXISTS model_label
        """))
        conn.commit()
        print("Successfully removed model_label column from judges table")


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
