"""
Migration: Add answer_label_overrides table

This migration creates the answer_label_overrides table for storing
user-edited labels that override the majority vote from evaluators.

Run this script manually:
    python -m src.database.migrations.001_add_answer_label_overrides
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from sqlalchemy import text
from src.common.database.connection import engine


def upgrade():
    """Create the answer_label_overrides table."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS answer_label_overrides (
                id SERIAL PRIMARY KEY,
                answer_id INTEGER NOT NULL UNIQUE,
                metric_name VARCHAR(50) NOT NULL DEFAULT 'accuracy',
                edited_label BOOLEAN NOT NULL,
                edited_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (answer_id) REFERENCES answers(id) ON DELETE CASCADE
            )
        """))

        # Create index on answer_id for faster lookups
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_answer_label_overrides_answer_id
            ON answer_label_overrides(answer_id)
        """))

        conn.commit()
        print("Successfully created answer_label_overrides table")


def downgrade():
    """Drop the answer_label_overrides table."""
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS answer_label_overrides"))
        conn.commit()
        print("Successfully dropped answer_label_overrides table")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database migration")
    parser.add_argument(
        "--downgrade",
        action="store_true",
        help="Downgrade (drop table) instead of upgrade"
    )
    args = parser.parse_args()

    if args.downgrade:
        downgrade()
    else:
        upgrade()
