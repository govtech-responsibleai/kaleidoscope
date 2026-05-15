"""
Unit tests for database connection helpers.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine, inspect, text


@pytest.mark.unit
class TestEnsureColumns:
    """Tests for the idempotent ensure_columns() schema-evolution helper."""

    def test_adds_missing_column_and_is_idempotent(self, tmp_path):
        """A missing column is added once; re-running is a safe no-op."""
        from src.common.database import connection

        temp_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
        # Create a 'questions' table WITHOUT the new 'language' column.
        with temp_engine.begin() as conn:
            conn.execute(text("CREATE TABLE questions (id INTEGER PRIMARY KEY, text TEXT)"))

        with patch.object(connection, "engine", temp_engine):
            connection.ensure_columns()
            cols_first = {c["name"] for c in inspect(temp_engine).get_columns("questions")}
            assert "language" in cols_first

            # Running again must not raise and must not change the schema.
            connection.ensure_columns()
            cols_second = {c["name"] for c in inspect(temp_engine).get_columns("questions")}
            assert cols_second == cols_first

    def test_noop_when_table_does_not_exist(self, tmp_path):
        """ensure_columns() silently skips tables that don't exist yet."""
        from src.common.database import connection

        temp_engine = create_engine(f"sqlite:///{tmp_path / 'empty.db'}")
        with patch.object(connection, "engine", temp_engine):
            # No 'questions' table — create_all() would build it; helper just no-ops.
            connection.ensure_columns()

    def test_noop_when_column_already_present(self, tmp_path):
        """ensure_columns() leaves an already-correct schema untouched."""
        from src.common.database import connection

        temp_engine = create_engine(f"sqlite:///{tmp_path / 'present.db'}")
        with temp_engine.begin() as conn:
            conn.execute(
                text("CREATE TABLE questions (id INTEGER PRIMARY KEY, language VARCHAR)")
            )

        with patch.object(connection, "engine", temp_engine):
            connection.ensure_columns()
            cols = {c["name"] for c in inspect(temp_engine).get_columns("questions")}
            assert "language" in cols
