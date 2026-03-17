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
    {"value": "litellm_proxy/gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
    {"value": "litellm_proxy/gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"value": "litellm_proxy/gemini-3.1-flash-lite-preview-global", "label": "Gemini 3.1 Flash Lite Preview"},
    {"value": "litellm_proxy/gemini-3.1-pro-preview-global", "label": "Gemini 3.1 Pro Preview"},
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

BASELINE_MODEL_MAP = {
    0: "litellm_proxy/gemini-2.5-flash-lite", 
    1: "litellm_proxy/gemini-3.1-flash-lite-preview-global", 
    2: "azure/gpt-5-nano-2025-08-07",
    3: "azure/gpt-5-mini-2025-08-07"
}

DEFAULT_JUDGES = [
    {
        "name": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[0]]['label'],
        "model_name": _require_model(BASELINE_MODEL_MAP[0]),
        "model_label": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[0]]['label'],
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": True,
        "is_editable": False,
        "category": "common",
    },
    {
        "name": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[1]]['label'],
        "model_name": _require_model(BASELINE_MODEL_MAP[1]),
        "model_label": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[1]]['label'],
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
        "category": "accuracy",
    },
    {
        "name": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[2]]['label'],
        "model_name": _require_model(BASELINE_MODEL_MAP[2]),
        "model_label": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[2]]['label'],
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
        "category": "common",
    },
    {
        "name": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[3]]['label'],
        "model_name": _require_model(BASELINE_MODEL_MAP[3]),
        "model_label": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[3]]['label'],
        "judge_type": JudgeTypeEnum.response_level,
        "is_baseline": False,
        "is_editable": False,
        "category": "relevance",
    },
    {
        "name": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[1]]['label'],
        "model_name": _require_model(BASELINE_MODEL_MAP[1]),
        "model_label": AVAILABLE_MODEL_MAP[BASELINE_MODEL_MAP[1]]['label'],
        "judge_type": JudgeTypeEnum.response_level,
        "is_baseline": False,
        "is_editable": False,
        "category": "default",
    },
]


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
    existing_combos = {(judge.model_name, judge.category): judge for judge in existing_judges}

    # Sync names of existing non-editable judges to match current config
    for config in DEFAULT_JUDGES:
        combo = (config["model_name"], config["category"])
        existing = existing_combos.get(combo)
        if existing and not existing.is_editable and existing.name != config["name"]:
            logger.info(f"Renaming judge '{existing.name}' -> '{config['name']}'")
            JudgeRepository.update(db, existing.id, {"name": config["name"]})

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
            "prompt_template": BASELINE_PROMPT_TEMPLATE,
            "params": {},
            "judge_type": config["judge_type"],
            "is_baseline": config["is_baseline"],
            "is_editable": config["is_editable"],
            "category": config["category"],
        }
        JudgeRepository.create(db, judge_data)
        existing_combos.add(combo)
        created_count += 1
        logger.info(f"Created judge: {config['name']}")

    if created_count > 0:
        logger.info(f"✓ Seeded {created_count} default judges")
    else:
        logger.info("✓ All default judges already exist")
