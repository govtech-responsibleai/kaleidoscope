"""Helpers for built-in rubric bootstrap backed by TargetRubric rows."""

from __future__ import annotations

import logging
from enum import Enum
from typing import Dict, Iterable, List

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.common.database.models import Judge, TargetRubric
from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.rubric.services.fixed_rubrics import get_fixed_template, list_fixed_templates
from src.rubric.services.premade_rubrics import get_premade_template, list_premade_templates
from src.rubric.services.prompt_files import load_prompt_template_text

logger = logging.getLogger(__name__)


class RubricGroup(str, Enum):
    fixed = "fixed"
    preset = "preset"
    custom = "custom"


class ScoringMode(str, Enum):
    claim_based = "claim_based"
    response_level = "response_level"


# String aliases kept for callers that compare against raw DB values
RUBRIC_GROUP_FIXED = RubricGroup.fixed.value
RUBRIC_GROUP_PRESET = RubricGroup.preset.value
RUBRIC_GROUP_CUSTOM = RubricGroup.custom.value


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


EMPATHY_MODELS = [
    "litellm_proxy/gemini-3-flash-preview",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
]

VERBOSITY_MODELS = [
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3-flash-preview",
]

DEFAULT_RUBRIC_MODELS = [
    "litellm_proxy/gemini-3.1-flash-lite-preview-global",
    "azure/gpt-5-mini-2025-08-07",
    "litellm_proxy/gemini-3-flash-preview",
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


def reserved_preset_names() -> set[str]:
    return {template["name"] for template in list_premade_templates()}


def reserved_fixed_names() -> set[str]:
    return {template["name"] for template in list_fixed_templates()}


def reserved_system_names() -> set[str]:
    return {*reserved_fixed_names(), *reserved_preset_names()}


def _name_matches(name: str, reserved_name: str) -> bool:
    return name.strip().lower() == reserved_name.strip().lower()


def suffix_reserved_name(name: str, existing_names: Iterable[str]) -> str:
    existing = {item.strip().lower() for item in existing_names}
    if name.strip().lower() not in {reserved.lower() for reserved in reserved_system_names()}:
        return name

    counter = 1
    candidate = f"{name} ({counter})"
    while candidate.strip().lower() in existing:
        counter += 1
        candidate = f"{name} ({counter})"
    return candidate


def rubric_option_values(rubric: TargetRubric | dict) -> list[str]:
    options = rubric["options"] if isinstance(rubric, dict) else rubric.options
    values: list[str] = []
    for option in options or []:
        if isinstance(option, dict):
            value = option.get("option")
        else:
            value = str(option)
        if value is not None:
            values.append(str(value))
    return values


def best_option_for_rubric(rubric: TargetRubric | dict) -> str:
    best_option = rubric.get("best_option") if isinstance(rubric, dict) else rubric.best_option
    if best_option:
        return str(best_option)
    options = rubric_option_values(rubric)
    return options[0] if options else ""


def negative_option_for_rubric(rubric: TargetRubric | dict) -> str:
    best_option = best_option_for_rubric(rubric)
    for option in rubric_option_values(rubric):
        if option != best_option:
            return option
    return best_option


def canonicalize_rubric_option_value(
    rubric: TargetRubric | dict,
    value: str | bool | None,
) -> str | None:
    if value is None:
        return None

    stripped = str(value).strip()
    if not stripped:
        return None

    option_lookup = {
        option.strip().lower(): option
        for option in rubric_option_values(rubric)
        if option.strip()
    }
    matched = option_lookup.get(stripped.lower())
    if matched is not None:
        return matched

    return stripped


def accuracy_label_from_bool(label: bool, rubric: TargetRubric | dict | None = None) -> str:
    resolved_rubric = rubric or get_fixed_template("accuracy")
    if resolved_rubric is None:
        raise RuntimeError("Missing fixed rubric template for accuracy")
    return best_option_for_rubric(resolved_rubric) if label else negative_option_for_rubric(resolved_rubric)


def build_preset_definition(name: str) -> dict | None:
    template = next((item for item in list_premade_templates() if _name_matches(item["name"], name)), None)
    if not template:
        return None
    full = get_premade_template(template["name"]) or get_premade_template(name.lower())
    if not full:
        return None
    judge_prompt_path = full.get("judge_prompt_path")
    return {
        "name": full["name"],
        "criteria": full["criteria"],
        "options": full["options"],
        "best_option": full["best_option"],
        "judge_prompt": load_prompt_template_text(judge_prompt_path) if judge_prompt_path else full.get("judge_prompt"),
        "group": RubricGroup.preset.value,
        "scoring_mode": ScoringMode.response_level.value,
    }


def build_fixed_definition(name: str) -> dict | None:
    full = get_fixed_template(name.lower()) or get_fixed_template(name)
    if not full:
        return None
    judge_prompt_path = full.get("judge_prompt_path")
    return {
        "name": full["name"],
        "criteria": full["criteria"],
        "options": full["options"],
        "best_option": full["best_option"],
        "judge_prompt": load_prompt_template_text(judge_prompt_path) if judge_prompt_path else full.get("judge_prompt"),
        "group": RubricGroup.fixed.value,
        "scoring_mode": full["scoring_mode"],
    }


def ensure_system_rubrics(db: Session, target_id: int) -> None:
    """Bootstrap built-in rubrics for one newly created target."""
    for position, template in enumerate(list_fixed_templates()):
        existing = next(
            iter(
                TargetRubricRepository.get_by_target(
                    db,
                    target_id,
                    group=RUBRIC_GROUP_FIXED,
                    name=template["name"],
                )
            ),
            None,
        )
        definition = build_fixed_definition(template["name"])
        if definition is None:
            continue
        if existing:
            changed = False
            if existing.position != position:
                existing.position = position
                changed = True
            for key, value in definition.items():
                if getattr(existing, key) != value:
                    setattr(existing, key, value)
                    changed = True
            if changed:
                db.commit()
                db.refresh(existing)
            continue

        fixed_rubric = TargetRubric(
            target_id=target_id,
            position=position,
            **definition,
        )
        db.add(fixed_rubric)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if not TargetRubricRepository.get_by_target(
                db,
                target_id,
                group=RUBRIC_GROUP_FIXED,
                name=template["name"],
            ):
                raise


def ensure_judges(db: Session, rubric_id: int) -> None:
    """
    Upsert 3 rubric-bound judges for the given rubric.

    Model pool is selected by rubric.group (and rubric.name for presets);
    prompt template is derived from rubric.scoring_mode. Dedup key:
    (rubric_id, model_name). Idempotent — safe to call when a rubric is created
    or reprocessed inside a target-scoped bootstrap flow.

    Args:
        db: Database session
        rubric_id: ID of the TargetRubric to seed judges for
    """
    rubric = db.query(TargetRubric).get(rubric_id)
    if rubric is None:
        return

    if rubric.group == RUBRIC_GROUP_FIXED:
        fixed_template = get_fixed_template(str(rubric.name))
        models = list(fixed_template.get("judge_models", [])) if fixed_template else []
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

    prompt_template = rubric.judge_prompt or ""
    configs = _model_pool_to_configs(models, prompt_template)

    existing_by_model = {
        judge.model_name: judge
        for judge in db.query(Judge).filter_by(rubric_id=rubric_id, is_editable=False).all()
    }
    for config in configs:
        existing = existing_by_model.get(config["model_name"])
        if existing:
            updates = {
                key: config[key]
                for key in ("name", "model_label", "is_baseline")
                if getattr(existing, key) != config[key]
            }
            if updates:
                JudgeRepository.update(db, int(existing.id), updates)  # type: ignore[arg-type]
        else:
            JudgeRepository.create(
                db,
                {**config, "target_id": rubric.target_id, "rubric_id": rubric_id, "params": {}},
            )


def ensure_system_judges(db: Session, target_id: int) -> None:
    """
    Upsert judges for a target's built-in system rubrics.

    Delegates to ensure_judges() for each fixed/preset rubric on the target.
    Safe to run as part of target creation bootstrap.

    Args:
        db: Database session
        target_id: ID of the Target whose built-in rubric judges should exist
    """
    rubrics = (
        db.query(TargetRubric)
        .filter(
            TargetRubric.target_id == target_id,
            TargetRubric.group.in_([RUBRIC_GROUP_FIXED, RUBRIC_GROUP_PRESET]),
        )
        .all()
    )
    for rubric in rubrics:
        ensure_judges(db, int(rubric.id))  # type: ignore[arg-type]
    logger.info("✓ ensure_system_judges: processed %s rubrics for target %s", len(rubrics), target_id)


def bootstrap_target_rubrics_and_judges(db: Session, target_id: int) -> None:
    """Create the built-in rubric and judge state required for a new target."""
    ensure_system_rubrics(db, target_id)
    ensure_system_judges(db, target_id)
