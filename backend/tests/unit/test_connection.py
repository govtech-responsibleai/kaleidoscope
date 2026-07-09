"""
Unit tests for database connection helpers.
"""

import pytest
from unittest.mock import patch
from sqlalchemy import create_engine, inspect, text


@pytest.mark.unit
class TestConnectionPoolConfig:
    """The pool ceiling must come from settings, not be hardcoded.

    Regression: a hardcoded pool_size=20 + max_overflow=10 (ceiling 30) exceeded a
    managed DB role limit of 10, causing "FATAL: too many connections". The ceiling
    must be env-tunable so a deploy can keep it under its role limit.
    """

    def test_engine_pool_uses_configured_size(self):
        from src.common.config import Settings
        from src.common.database.connection import build_engine

        settings = Settings(
            database_url="postgresql://localhost:5432/x",
            db_pool_size=4,
            db_max_overflow=3,
            db_pool_timeout=15,
        )

        engine = build_engine(settings)
        try:
            assert engine.pool.size() == 4
            assert engine.pool._max_overflow == 3
            # Ceiling stays small so it can sit under a low managed-DB role limit.
            assert engine.pool.size() + engine.pool._max_overflow <= 10
        finally:
            engine.dispose()

    def test_default_pool_ceiling_is_conservative(self):
        """The out-of-the-box ceiling must be small enough for low-limit managed DBs."""
        from src.common.config import Settings

        defaults = Settings(database_url="postgresql://localhost:5432/x")
        assert defaults.db_pool_size + defaults.db_max_overflow <= 10


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
