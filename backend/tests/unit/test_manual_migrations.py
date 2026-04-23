from unittest.mock import MagicMock

import pytest

from src.common.database.seed import run_manual_migrations


@pytest.mark.unit
def test_run_manual_migrations_drops_legacy_answer_label_override_boolean_column():
    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection

    run_manual_migrations(engine)

    executed_sql = [str(call.args[0]) for call in connection.execute.call_args_list]

    assert any("ALTER TABLE answer_label_overrides DROP COLUMN IF EXISTS edited_label" in sql for sql in executed_sql)
    assert any("ALTER TABLE answer_label_overrides DROP COLUMN IF EXISTS metric_key" in sql for sql in executed_sql)
    connection.commit.assert_called_once()
