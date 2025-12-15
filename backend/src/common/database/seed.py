"""
Database seeding functions.

Provides initialization data for the database on startup.
"""

import logging
from pathlib import Path
from typing import Dict

from sqlalchemy.orm import Session

from src.common.database.repositories import JudgeRepository
from src.common.database.models import JudgeTypeEnum

logger = logging.getLogger(__name__)


def _load_baseline_prompt() -> str:
    """Load the shared baseline prompt from the templates directory."""
    template_path = Path(__file__).resolve().parents[1] / "prompts" / "templates" / "claim_level_judge.md"
    try:
        return template_path.read_text()
    except OSError as exc:  # pragma: no cover - critical failure if missing template
        raise RuntimeError(f"Baseline prompt template missing: {template_path}") from exc


BASELINE_PROMPT_TEMPLATE = _load_baseline_prompt()

AVAILABLE_MODELS = [
    {"value": "gemini/gemini-2.0-flash-lite-001", "label": "Gemini 2.0 Flash Lite"},
    {"value": "gemini/gemini-2.0-flash-001", "label": "Gemini 2.0 Flash"},
    {"value": "gemini/gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
    {"value": "gemini/gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"value": "azure/gpt-5-nano-2025-08-07", "label": "GPT-5 nano"},
    {"value": "azure/gpt-5-mini-2025-08-07", "label": "GPT-5 mini"},
    {"value": "azure/gpt-5-2025-08-07", "label": "GPT-5"},
    {"value": "vertex_ai/claude-haiku-4-5", "label": "Haiku 4.5"},
    {"value": "vertex_ai/claude-sonnet-4-5", "label": "Sonnet 4.5"},
    {"value": "vertex_ai/claude-opus-4-5", "label": "Opus 4.5"},
]

AVAILABLE_MODEL_MAP: Dict[str, dict] = {model["value"]: model for model in AVAILABLE_MODELS}


def _require_model(value: str) -> str:
    """Ensure the requested model is defined in AVAILABLE_MODELS."""
    if value not in AVAILABLE_MODEL_MAP:
        raise RuntimeError(f"Model '{value}' is not defined in AVAILABLE_MODELS.")
    return value


DEFAULT_JUDGES = [
    {
        "name": "Baseline Judge 1",
        "model_name": _require_model("gemini/gemini-2.0-flash-lite-001"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": True,
        "is_editable": False,
    },
    {
        "name": "Baseline Judge 2",
        "model_name": _require_model("gemini/gemini-2.0-flash-001"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
    },
    {
        "name": "Baseline Judge 3",
        "model_name": _require_model("azure/gpt-5-nano-2025-08-07"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
    },
]


def seed_default_judges(db: Session) -> None:
    """
    Seed default judges into the database.

    This function is idempotent - it will only create judges that don't already exist
    based on their model_name.

    Args:
        db: Database session
    """
    logger.info("Seeding default judges...")

    existing_judges = JudgeRepository.get_all(db)
    existing_models = {judge.model_name for judge in existing_judges}

    created_count = 0
    for config in DEFAULT_JUDGES:
        if config["model_name"] in existing_models:
            logger.debug(f"Judge '{config['name']}' already exists, skipping")
            continue

        judge_data = {
            "name": config["name"],
            "model_name": config["model_name"],
            "prompt_template": BASELINE_PROMPT_TEMPLATE,
            "params": {},
            "judge_type": config["judge_type"],
            "is_baseline": config["is_baseline"],
            "is_editable": config["is_editable"],
        }
        JudgeRepository.create(db, judge_data)
        existing_models.add(config["model_name"])
        created_count += 1
        logger.info(f"Created judge: {config['name']}")

    if created_count > 0:
        logger.info(f"✓ Seeded {created_count} default judges")
    else:
        logger.info("✓ All default judges already exist")
