"""
Database seeding functions.

Provides initialization data for the database on startup.
"""

import logging
from pathlib import Path
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.common.database.models import Judge, TargetRubric
from src.common.database.repositories import JudgeRepository

logger = logging.getLogger(__name__)


def run_manual_migrations(engine: Engine) -> None:
    """
    Run manual schema migrations that create_all() cannot handle
    (e.g. adding columns to existing tables).

    Each statement uses IF NOT EXISTS so this is safe to run on every startup.
    """
    migrations = [
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS target_id INTEGER REFERENCES targets(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS ix_judges_target_id ON judges(target_id)",
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS rubric_id INTEGER REFERENCES target_rubrics(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS ix_judges_rubric_id ON judges(rubric_id)",
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
        "UPDATE judges SET created_at = COALESCE(created_at, NOW()), updated_at = COALESCE(updated_at, NOW()) WHERE created_at IS NULL OR updated_at IS NULL",
        "ALTER TABLE judges ALTER COLUMN created_at SET NOT NULL",
        "ALTER TABLE judges ALTER COLUMN updated_at SET NOT NULL",
        """
        CREATE TABLE IF NOT EXISTS target_http_auth_secrets (
            id SERIAL PRIMARY KEY,
            target_id INTEGER NOT NULL UNIQUE REFERENCES targets(id) ON DELETE CASCADE,
            encrypted_secret TEXT NOT NULL,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS ix_target_http_auth_secrets_target_id ON target_http_auth_secrets(target_id)",
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS judge_prompt TEXT",
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS template_key VARCHAR",
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS \"group\" VARCHAR DEFAULT 'custom'",
        # Backfill group from template_key for legacy rubrics before dropping template_key
        "UPDATE target_rubrics SET \"group\" = 'fixed' WHERE \"group\" IS NULL AND (LOWER(template_key) = 'accuracy' OR LOWER(name) = 'accuracy')",
        "UPDATE target_rubrics SET \"group\" = 'preset' WHERE \"group\" IS NULL AND template_key IN ('empathy', 'verbosity')",
        "UPDATE target_rubrics SET \"group\" = COALESCE(\"group\", 'custom') WHERE \"group\" IS NULL",
        "ALTER TABLE target_rubrics DROP COLUMN IF EXISTS template_key",
        """
        CREATE TABLE IF NOT EXISTS answer_label_overrides (
            id SERIAL PRIMARY KEY,
            answer_id INTEGER NOT NULL REFERENCES answers(id) ON DELETE CASCADE,
            rubric_id INTEGER REFERENCES target_rubrics(id) ON DELETE CASCADE,
            metric_key VARCHAR(100),
            edited_value VARCHAR NOT NULL,
            edited_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW() NOT NULL
        )
        """,
        "ALTER TABLE answer_label_overrides ADD COLUMN IF NOT EXISTS rubric_id INTEGER REFERENCES target_rubrics(id) ON DELETE CASCADE",
        "ALTER TABLE answer_label_overrides ADD COLUMN IF NOT EXISTS metric_key VARCHAR(100)",
        "ALTER TABLE answer_label_overrides ADD COLUMN IF NOT EXISTS edited_value VARCHAR",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'answer_label_overrides' AND column_name = 'edited_label'
            ) THEN
                EXECUTE '
                    UPDATE answer_label_overrides
                    SET edited_value = CASE
                        WHEN edited_value IS NOT NULL THEN edited_value
                        WHEN edited_label IS TRUE THEN ''Accurate''
                        ELSE ''Inaccurate''
                    END
                    WHERE edited_value IS NULL
                ';
            END IF;
        END $$;
        """,
        "ALTER TABLE answer_label_overrides ALTER COLUMN edited_value SET NOT NULL",
        "DROP INDEX IF EXISTS ix_answer_label_overrides_answer_id",
        "DROP INDEX IF EXISTS uix_answer_label_override",
        "CREATE INDEX IF NOT EXISTS ix_answer_label_overrides_answer_id ON answer_label_overrides(answer_id)",
        "CREATE INDEX IF NOT EXISTS ix_answer_label_overrides_rubric_id ON answer_label_overrides(rubric_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_answer_label_override ON answer_label_overrides(answer_id, rubric_id)",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_name = 'rubric_label_overrides'
            ) THEN
                INSERT INTO answer_label_overrides (answer_id, metric_key, edited_value, edited_at)
                SELECT rlo.answer_id, 'rubric:' || rlo.rubric_id::text, rlo.edited_option, rlo.edited_at
                FROM rubric_label_overrides rlo
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM answer_label_overrides alo
                    WHERE alo.answer_id = rlo.answer_id
                      AND alo.metric_key = 'rubric:' || rlo.rubric_id::text
                );
            END IF;
        END $$;
        """,
        "DROP TABLE IF EXISTS rubric_label_overrides",
        # Remove judges in deprecated categories when upgrading from the
        # legacy category-routed schema. Newer schemas have already dropped
        # this column, so the cleanup must be conditional.
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'judges' AND column_name = 'category'
            ) THEN
                DELETE FROM judges WHERE category IN ('relevance', 'voice');
            END IF;
        END $$;
        """,
        # Task 1.6: scoring_mode on TargetRubric
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS scoring_mode VARCHAR NOT NULL DEFAULT 'response_level'",
        "UPDATE target_rubrics SET scoring_mode = 'claim_based' WHERE \"group\" = 'fixed' AND name = 'Accuracy'",
        # Unified answer-score storage: add rubric identity and string verdicts
        "ALTER TABLE answer_scores ADD COLUMN IF NOT EXISTS rubric_id INTEGER REFERENCES target_rubrics(id) ON DELETE CASCADE",
        "CREATE INDEX IF NOT EXISTS ix_answer_scores_rubric_id ON answer_scores(rubric_id)",
        "ALTER TABLE answer_scores ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
        "UPDATE answer_scores SET updated_at = COALESCE(updated_at, created_at, NOW()) WHERE updated_at IS NULL",
        "ALTER TABLE answer_scores ALTER COLUMN updated_at SET NOT NULL",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'answer_scores'
                  AND column_name = 'overall_label'
                  AND data_type = 'boolean'
            ) THEN
                ALTER TABLE answer_scores
                ALTER COLUMN overall_label TYPE VARCHAR
                USING CASE
                    WHEN overall_label IS TRUE THEN 'Accurate'
                    ELSE 'Inaccurate'
                END;
            END IF;
        END $$;
        """,
        """
        UPDATE answer_scores s
        SET rubric_id = COALESCE(
            j.rubric_id,
            (
                SELECT tr.id
                FROM answers a
                JOIN snapshots sn ON sn.id = a.snapshot_id
                JOIN target_rubrics tr
                  ON tr.target_id = sn.target_id
                 AND tr."group" = 'fixed'
                 AND tr.name = 'Accuracy'
                WHERE a.id = s.answer_id
                ORDER BY tr.id ASC
                LIMIT 1
            )
        )
        FROM judges j
        WHERE s.judge_id = j.id
          AND s.rubric_id IS NULL
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.tables WHERE table_name = 'rubric_answer_scores'
            ) THEN
                INSERT INTO answer_scores (answer_id, rubric_id, judge_id, overall_label, explanation, created_at, updated_at)
                SELECT ras.answer_id, ras.rubric_id, ras.judge_id, ras.option_chosen, ras.explanation, ras.created_at, ras.updated_at
                FROM rubric_answer_scores ras
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM answer_scores s
                    WHERE s.answer_id = ras.answer_id
                      AND s.rubric_id = ras.rubric_id
                      AND s.judge_id = ras.judge_id
                );
            END IF;
        END $$;
        """,
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uix_answer_judge_score'
            ) THEN
                ALTER TABLE answer_scores DROP CONSTRAINT uix_answer_judge_score;
            END IF;
        END $$;
        """,
        "DROP INDEX IF EXISTS uix_answer_judge_score",
        "DROP INDEX IF EXISTS uix_answer_rubric_judge_score",
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_answer_rubric_judge_score ON answer_scores(answer_id, rubric_id, judge_id)",
        "DROP TABLE IF EXISTS rubric_answer_scores",
        # Task 1.7: unique partial index preventing duplicate fixed Accuracy rubrics per target
        "CREATE UNIQUE INDEX IF NOT EXISTS uix_target_rubric_fixed_accuracy ON target_rubrics(target_id, name) WHERE \"group\" = 'fixed'",
        # Task 2.4: drop judge_type and category from judges (routing moves to rubric.scoring_mode)
        "ALTER TABLE judges DROP COLUMN IF EXISTS judge_type",
        "ALTER TABLE judges DROP COLUMN IF EXISTS category",
        # Task 6.4: drop legacy category from target_rubrics (superseded by group)
        "ALTER TABLE target_rubrics DROP COLUMN IF EXISTS category",
        # Task 3.6: backfill rubric_id from metric_key, then drop metric_key
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'answer_label_overrides' AND column_name = 'metric_key'
            ) THEN
                UPDATE answer_label_overrides alo
                SET rubric_id = (
                    SELECT tr.id FROM target_rubrics tr
                    JOIN answers a ON a.id = alo.answer_id
                    JOIN snapshots s ON s.id = a.snapshot_id
                    WHERE tr.target_id = s.target_id AND tr."group" = 'fixed' AND tr.name = 'Accuracy'
                    LIMIT 1
                )
                WHERE alo.metric_key = 'accuracy' AND alo.rubric_id IS NULL;

                UPDATE answer_label_overrides
                SET rubric_id = CAST(SPLIT_PART(metric_key, ':', 2) AS INTEGER)
                WHERE metric_key LIKE 'rubric:%' AND rubric_id IS NULL;

                DELETE FROM answer_label_overrides WHERE rubric_id IS NULL;

                ALTER TABLE answer_label_overrides ALTER COLUMN rubric_id SET NOT NULL;
                ALTER TABLE answer_label_overrides DROP COLUMN IF EXISTS metric_key;
            END IF;
        END $$;
        """,
    ]
    with engine.connect() as conn:
        for sql in migrations:
            conn.execute(text(sql))
        conn.commit()
    logger.info("✓ Manual migrations applied")


def _load_baseline_prompt() -> str:
    """Load the shared baseline prompt from the templates directory."""
    template_path = Path(__file__).resolve().parents[1] / "prompts" / "templates" / "claim_level_judge.md"
    try:
        return template_path.read_text()
    except OSError as exc:  # pragma: no cover - critical failure if missing template
        raise RuntimeError(f"Baseline prompt template missing: {template_path}") from exc


def _load_response_level_prompt() -> str:
    """Load the response-level judge prompt template."""
    template_path = Path(__file__).resolve().parents[1] / "prompts" / "templates" / "response_level_judge.md"
    try:
        return template_path.read_text()
    except OSError as exc:  # pragma: no cover
        raise RuntimeError(f"Response-level prompt template missing: {template_path}") from exc


BASELINE_PROMPT_TEMPLATE = _load_baseline_prompt()
RESPONSE_LEVEL_PROMPT_TEMPLATE = _load_response_level_prompt()

AVAILABLE_MODELS = [
    {"value": "litellm_proxy/gemini-3.1-flash-lite-preview-global", "label": "Gemini 3.1 Flash Lite"},
    {"value": "litellm_proxy/gemini-3-flash-preview", "label": "Gemini 3.1 Flash"},
    {"value": "litellm_proxy/gemini-3.1-pro-preview-global", "label": "Gemini 3.1 Pro"},
    {"value": "azure/gpt-5-nano-2025-08-07", "label": "GPT-5 nano"},
    {"value": "azure/gpt-5-mini-2025-08-07", "label": "GPT-5 mini"},
    {"value": "azure/gpt-5-2025-08-07", "label": "GPT-5"},
    {"value": "litellm_proxy/claude-haiku-4-5@20251001-global", "label": "Haiku 4.5"},
    {"value": "litellm_proxy/claude-sonnet-4-5@20250929-asia-southeast1", "label": "Sonnet 4.5"},
    {"value": "litellm_proxy/claude-opus-4-5@20251101-asia-southeast1", "label": "Opus 4.5"},
]

AVAILABLE_MODEL_MAP: Dict[str, dict] = {model["value"]: model for model in AVAILABLE_MODELS}


def _require_model(value: str) -> str:
    """Ensure the requested model is defined in AVAILABLE_MODELS."""
    if value not in AVAILABLE_MODEL_MAP:
        raise RuntimeError(f"Model '{value}' is not defined in AVAILABLE_MODELS.")
    return value

# Accuracy (claim-based) models — index 0 = recommended / global baseline
ACCURACY_MODELS = [
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "litellm_proxy/gemini-3-flash-preview",
    "azure/gpt-5-nano-2025-08-07",
]

# Empathy pre-made rubric: Gemini 3 Flash recommended
EMPATHY_MODELS = [
    "litellm_proxy/gemini-3-flash-preview",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3.1-flash-lite-preview-global"
]

# Verbosity pre-made rubric: Gemini 3.1 Flash Lite recommended
VERBOSITY_MODELS = [
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3-flash-preview"
]

# Default (custom) rubric judges: Gemini 3.1 Flash Lite recommended
DEFAULT_RUBRIC_MODELS = [
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3-flash-preview"
]

JUDGE_NAMES = ["Judge 1 (Recommended)", "Judge 2", "Judge 3"]


def _model_pool_to_configs(models: List[str], prompt_template: str, is_baseline_idx: int = 0) -> List[dict]:
    return [
        {
            "name": JUDGE_NAMES[idx],
            "model_name": _require_model(model),
            "model_label": AVAILABLE_MODEL_MAP[model]["label"],
            "prompt_template": prompt_template,
            "is_baseline": idx == is_baseline_idx,
            "is_editable": False,
        }
        for idx, model in enumerate(models)
    ]


def ensure_judges(db: Session, rubric_id: int) -> None:
    """
    Upsert 3 rubric-bound judges for the given rubric.

    Model pool is selected by rubric.group (and rubric.name for presets);
    prompt template is derived from rubric.scoring_mode. Dedup key:
    (rubric_id, model_name). Idempotent — safe to call on every rubric create
    and at startup.

    Args:
        db: Database session
        rubric_id: ID of the TargetRubric to seed judges for
    """
    from src.common.services.system_rubrics import (
        RUBRIC_GROUP_FIXED, RUBRIC_GROUP_PRESET, RUBRIC_GROUP_CUSTOM,
    )

    rubric = db.query(TargetRubric).get(rubric_id)
    if rubric is None:
        return

    if rubric.group == RUBRIC_GROUP_FIXED:
        models: List[str] = ACCURACY_MODELS
    elif rubric.group == RUBRIC_GROUP_PRESET:
        preset_map: Dict[str, List[str]] = {
            "Empathy": EMPATHY_MODELS,
            "Verbosity": VERBOSITY_MODELS,
        }
        models = preset_map.get(str(rubric.name), [])
    elif rubric.group == RUBRIC_GROUP_CUSTOM:
        models = DEFAULT_RUBRIC_MODELS
    else:
        models = []

    if not models:
        return

    is_claim = str(rubric.scoring_mode) == "claim_based"
    prompt_template = BASELINE_PROMPT_TEMPLATE if is_claim else RESPONSE_LEVEL_PROMPT_TEMPLATE
    configs = _model_pool_to_configs(models, prompt_template)

    existing_by_model = {
        j.model_name: j
        for j in db.query(Judge).filter_by(rubric_id=rubric_id, is_editable=False).all()
    }
    for config in configs:
        existing = existing_by_model.get(config["model_name"])
        if existing:
            updates = {
                k: config[k]
                for k in ("name", "model_label", "is_baseline")
                if getattr(existing, k) != config[k]
            }
            if updates:
                JudgeRepository.update(db, int(existing.id), updates)  # type: ignore[arg-type]
        else:
            JudgeRepository.create(db, {**config, "rubric_id": rubric_id, "params": {}})


def ensure_system_judges(db: Session) -> None:
    """
    Sweep all target rubrics and upsert their judges. Idempotent.

    Delegates to ensure_judges() for each rubric, covering fixed, preset,
    and custom groups. Safe to run on every startup and after target creation.

    Args:
        db: Database session
    """
    rubrics = db.query(TargetRubric).all()
    for rubric in rubrics:
        ensure_judges(db, int(rubric.id))  # type: ignore[arg-type]
    logger.info(f"✓ ensure_system_judges: processed {len(rubrics)} rubrics")
