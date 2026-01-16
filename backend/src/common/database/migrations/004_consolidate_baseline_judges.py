"""
Migration: Consolidate baseline judges to use new LiteLLM proxy models

This migration:
1. Updates the oldest baseline evaluators (1, 2, 3) with new model_name and model_label
2. Removes duplicate baseline evaluators, keeping only the oldest ones

Run this script manually:
    python -m src.common.database.migrations.004_consolidate_baseline_judges
"""

import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from sqlalchemy import text
from src.common.database.connection import engine


# New baseline judge configurations
BASELINE_UPDATES = {
    "Baseline Evaluator 1": {
        "model_name": "litellm_proxy/gemini-2.5-flash-lite",
        "model_label": "Gemini 2.5 Flash Lite",
        "is_baseline": True,
    },
    "Baseline Evaluator 2": {
        "model_name": "litellm_proxy/gemini-3-flash-preview",
        "model_label": "Gemini 3 Flash Preview",
        "is_baseline": False,
    },
    "Baseline Evaluator 3": {
        "model_name": "azure/gpt-5-nano-2025-08-07",
        "model_label": "GPT-5 nano",
        "is_baseline": False,
    },
}


def upgrade():
    """Update baseline judges and remove duplicates."""
    with engine.connect() as conn:
        for judge_name, updates in BASELINE_UPDATES.items():
            # Find all judges with this name, ordered by ID (oldest first)
            result = conn.execute(text("""
                SELECT id FROM judges
                WHERE name = :name
                ORDER BY id ASC
            """), {"name": judge_name})

            rows = result.fetchall()

            if not rows:
                print(f"No judge found with name '{judge_name}'")
                continue

            # Keep the oldest one (first ID)
            keep_id = rows[0][0]

            # Update the oldest one with new values
            conn.execute(text("""
                UPDATE judges
                SET model_name = :model_name,
                    model_label = :model_label,
                    is_baseline = :is_baseline
                WHERE id = :id
            """), {
                "id": keep_id,
                "model_name": updates["model_name"],
                "model_label": updates["model_label"],
                "is_baseline": updates["is_baseline"],
            })
            print(f"Updated judge ID {keep_id} ({judge_name}) with new model: {updates['model_name']}")

            # Reassign scores and delete duplicates (all except the oldest)
            if len(rows) > 1:
                duplicate_ids = [row[0] for row in rows[1:]]

                # Reassign answer_scores from duplicates to the kept judge
                conn.execute(text("""
                    UPDATE answer_scores
                    SET judge_id = :keep_id
                    WHERE judge_id = ANY(:duplicate_ids)
                """), {"keep_id": keep_id, "duplicate_ids": duplicate_ids})
                print(f"Reassigned answer_scores from IDs {duplicate_ids} to ID {keep_id}")

                # Now safe to delete the duplicates
                conn.execute(text("""
                    DELETE FROM judges
                    WHERE id = ANY(:ids)
                """), {"ids": duplicate_ids})
                print(f"Deleted {len(duplicate_ids)} duplicate(s) for '{judge_name}': IDs {duplicate_ids}")

        conn.commit()
        print("\nBaseline judges consolidated successfully!")


def show_current_state():
    """Show current baseline judges in the database."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, name, model_name, model_label, is_baseline
            FROM judges
            WHERE name LIKE 'Baseline Evaluator%'
            ORDER BY name, id
        """))

        rows = result.fetchall()
        print("\nCurrent baseline judges:")
        print("-" * 80)
        for row in rows:
            print(f"ID: {row[0]}, Name: {row[1]}, Model: {row[2]}, Label: {row[3]}, Baseline: {row[4]}")
        print("-" * 80)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Consolidate baseline judges")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show current state without making changes"
    )
    args = parser.parse_args()

    if args.dry_run:
        show_current_state()
    else:
        show_current_state()
        print("\nApplying migration...")
        upgrade()
        show_current_state()
