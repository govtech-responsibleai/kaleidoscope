"""
Database seeding functions.

Provides initialization data for the database on startup.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src.common.database.repositories import JudgeRepository
from src.common.database.models import JudgeTypeEnum

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
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
        "ALTER TABLE judges ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()",
        "UPDATE judges SET created_at = COALESCE(created_at, NOW()), updated_at = COALESCE(updated_at, NOW()) WHERE created_at IS NULL OR updated_at IS NULL",
        "ALTER TABLE judges ALTER COLUMN created_at SET NOT NULL",
        "ALTER TABLE judges ALTER COLUMN updated_at SET NOT NULL",
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS judge_prompt TEXT",
        "ALTER TABLE target_rubrics ADD COLUMN IF NOT EXISTS template_key VARCHAR",
        # Remove all deprecated-category judges (relevance, voice) — these categories
        # are no longer supported; rubric judges are now wired by template_key category.
        # Remove all deprecated-category judges and legacy response_level judges
        # named after their model (old seeds used model labels as judge names).
        "DELETE FROM judges WHERE category IN ('relevance', 'voice')",
        "DELETE FROM judges WHERE judge_type = 'response_level' AND name NOT IN ('Judge 1 (Recommended)', 'Judge 2', 'Judge 3')",
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
    {"value": "litellm_proxy/gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
    {"value": "litellm_proxy/gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"value": "litellm_proxy/gemini-3-flash-preview", "label": "Gemini 3.0 Flash"},
    {"value": "litellm_proxy/gemini-3.1-flash-lite-preview-global", "label": "Gemini 3.1 Flash Lite"},
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
    "litellm_proxy/gemini-2.5-flash-lite",
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "azure/gpt-5-nano-2025-08-07",
]

# Common additional rubric judge models (positions 1 and 2 for all rubric categories)
_RUBRIC_ADDITIONAL = [
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-2.5-flash-lite",
]

# Empathy pre-made rubric: Gemini 3 Flash recommended
EMPATHY_MODELS = ["litellm_proxy/gemini-3-flash-preview"] + _RUBRIC_ADDITIONAL

# Verbosity pre-made rubric: Gemini 3.1 Flash Lite recommended
VERBOSITY_MODELS = ["litellm_proxy/gemini-3.1-flash-lite-preview-global"] + _RUBRIC_ADDITIONAL

# Default (custom) rubric judges: Gemini 3.1 Flash Lite recommended
DEFAULT_RUBRIC_MODELS = ["litellm_proxy/gemini-3.1-flash-lite-preview-global"] + _RUBRIC_ADDITIONAL

# (category, judge_type, model_list)
JUDGE_CATEGORIES: List[Tuple[str, JudgeTypeEnum, List[str]]] = [
    ("accuracy", JudgeTypeEnum.claim_based, ACCURACY_MODELS),
    ("empathy", JudgeTypeEnum.response_level, EMPATHY_MODELS),
    ("verbosity", JudgeTypeEnum.response_level, VERBOSITY_MODELS),
    ("default", JudgeTypeEnum.response_level, DEFAULT_RUBRIC_MODELS),
]

JUDGE_NAMES = ["Judge 1 (Recommended)", "Judge 2", "Judge 3"]

DEFAULT_JUDGES: List[dict] = []
for _category, _judge_type, _models in JUDGE_CATEGORIES:
    _prompt_template = BASELINE_PROMPT_TEMPLATE if _judge_type == JudgeTypeEnum.claim_based else RESPONSE_LEVEL_PROMPT_TEMPLATE
    for _idx, _model in enumerate(_models):
        DEFAULT_JUDGES.append({
            "name": JUDGE_NAMES[_idx],
            "model_name": _require_model(_model),
            "model_label": AVAILABLE_MODEL_MAP[_model]["label"],
            "judge_type": _judge_type,
            "is_baseline": (_category == "accuracy" and _idx == 0),
            "is_editable": False,
            "category": _category,
            "_prompt_template": _prompt_template,
        })


def seed_default_judges(db: Session) -> None:
    """
    Seed default judges into the database.

    This function is idempotent - it will only create judges that don't already exist
    based on their (model_name, category) combination.

    Args:
        db: Database session
    """
    logger.info("Seeding default judges...")

    existing_judges = JudgeRepository.get_all(db)
    system_judges = [j for j in existing_judges if not j.is_editable and j.user_id is None]
    existing_combos = {(judge.model_name, judge.category): judge for judge in system_judges}

    # Sync existing seeded judges to match current config
    for config in DEFAULT_JUDGES:
        combo = (config["model_name"], config["category"])
        existing = existing_combos.get(combo)
        if not existing:
            continue

        updates = {}
        if existing.name != config["name"]:
            updates["name"] = config["name"]
        if existing.model_label != config.get("model_label"):
            updates["model_label"] = config.get("model_label")
        if existing.judge_type != config["judge_type"]:
            updates["judge_type"] = config["judge_type"]
        if existing.is_baseline != config["is_baseline"]:
            updates["is_baseline"] = config["is_baseline"]
        if existing.is_editable != config["is_editable"]:
            updates["is_editable"] = config["is_editable"]

        if updates:
            logger.info(
                f"Syncing seeded judge id={existing.id} for combo={combo}: "
                f"{', '.join(sorted(updates.keys()))}"
            )
            JudgeRepository.update(db, existing.id, updates)

    created_count = 0
    for config in DEFAULT_JUDGES:
        combo = (config["model_name"], config["category"])
        if combo in existing_combos:
            logger.debug(f"Judge '{config['name']}' already exists, skipping")
            continue

        judge_data = {
            "name": config["name"],
            "model_name": config["model_name"],
            "model_label": config.get("model_label"),
            "prompt_template": config.get("_prompt_template", BASELINE_PROMPT_TEMPLATE),
            "params": {},
            "judge_type": config["judge_type"],
            "is_baseline": config["is_baseline"],
            "is_editable": config["is_editable"],
            "category": config["category"],
        }
        JudgeRepository.create(db, judge_data)
        existing_combos[combo] = None
        created_count += 1
        logger.info(f"Created judge: {config['name']}")

    if created_count > 0:
        logger.info(f"✓ Seeded {created_count} default judges")
    else:
        logger.info("✓ All default judges already exist")

    # Clean up stale or duplicate default judges
    current_combos = {(cfg["model_name"], cfg["category"]) for cfg in DEFAULT_JUDGES}
    all_judges = JudgeRepository.get_all(db)
    system_judges = [j for j in all_judges if not j.is_editable and j.user_id is None]

    # Remove judges whose combo is no longer in DEFAULT_JUDGES
    stale_judges = [j for j in system_judges if (j.model_name, j.category) not in current_combos]

    # Remove duplicate judges: for each combo, keep only the newest (highest id)
    from collections import defaultdict
    combo_groups: dict = defaultdict(list)
    for j in system_judges:
        if (j.model_name, j.category) in current_combos:
            combo_groups[(j.model_name, j.category)].append(j)
    duplicate_judges = []
    for combo, judges_in_combo in combo_groups.items():
        if len(judges_in_combo) > 1:
            sorted_judges = sorted(judges_in_combo, key=lambda j: j.id, reverse=True)
            duplicate_judges.extend(sorted_judges[1:])  # keep newest, remove the rest

    to_remove = stale_judges + duplicate_judges
    for judge in to_remove:
        logger.info(
            f"Removing stale/duplicate default judge: id={judge.id}, name='{judge.name}', "
            f"model={judge.model_name}, category={judge.category}"
        )
        JudgeRepository.delete(db, judge.id)

    if to_remove:
        logger.info(f"✓ Removed {len(to_remove)} stale/duplicate default judges")
