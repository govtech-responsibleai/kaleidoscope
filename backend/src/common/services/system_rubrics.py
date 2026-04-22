"""Helpers for fixed and preset rubrics backed by TargetRubric rows."""

from __future__ import annotations

from enum import Enum
from typing import Iterable

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.common.database.models import Target, TargetRubric
from src.common.services.premade_rubrics import get_premade_template, list_premade_templates


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

FIXED_ACCURACY_NAME = "Accuracy"
ACCURACY_CRITERIA = (
    "Are the claims in the response supported by the provided context, or do they contain hallucinations?"
)
ACCURACY_OPTIONS = [
    {"option": "Accurate", "description": "All claims are supported by the provided context."},
    {"option": "Inaccurate", "description": "One or more claims are unsupported or hallucinated."},
]


class FixedAccuracyRubricInvariantError(ValueError):
    """Raised when runtime code expects the fixed accuracy rubric to exist but it does not."""


def reserved_preset_names() -> set[str]:
    return {template["name"] for template in list_premade_templates()}


def reserved_system_names() -> set[str]:
    return {FIXED_ACCURACY_NAME, *reserved_preset_names()}


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


def build_fixed_accuracy_definition() -> dict:
    return {
        "name": FIXED_ACCURACY_NAME,
        "criteria": ACCURACY_CRITERIA,
        "options": ACCURACY_OPTIONS,
        "best_option": "Accurate",
        "judge_prompt": None,
        "group": RubricGroup.fixed.value,
        "scoring_mode": ScoringMode.claim_based.value,
    }


def is_fixed_accuracy_rubric(rubric: TargetRubric | dict | None) -> bool:
    if rubric is None:
        return False
    name = rubric["name"] if isinstance(rubric, dict) else rubric.name
    group = rubric.get("group") if isinstance(rubric, dict) else rubric.group
    return bool(group == RUBRIC_GROUP_FIXED and _name_matches(str(name), FIXED_ACCURACY_NAME))


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

    if isinstance(value, bool):
        return best_option_for_rubric(rubric) if value else negative_option_for_rubric(rubric)

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

    if is_fixed_accuracy_rubric(rubric):
        best_option = best_option_for_rubric(rubric)
        negative_option = negative_option_for_rubric(rubric)
        positive_aliases = {"true", "yes", "supported"}
        negative_aliases = {"false", "no", "unsupported", "hallucinated"}
        lowered = stripped.lower()
        if lowered in positive_aliases:
            return best_option
        if lowered in negative_aliases:
            return negative_option

    return stripped


def accuracy_label_from_bool(label: bool, rubric: TargetRubric | dict | None = None) -> str:
    resolved_rubric = rubric or build_fixed_accuracy_definition()
    return best_option_for_rubric(resolved_rubric) if label else negative_option_for_rubric(resolved_rubric)


def build_preset_definition(name: str) -> dict | None:
    template = next((item for item in list_premade_templates() if _name_matches(item["name"], name)), None)
    if not template:
        return None
    full = get_premade_template(template["name"]) or get_premade_template(name.lower())
    if not full:
        return None
    return {
        "name": full["name"],
        "criteria": full["criteria"],
        "options": full["options"],
        "best_option": full["best_option"],
        "judge_prompt": full["judge_prompt"],
        "group": RubricGroup.preset.value,
        "scoring_mode": ScoringMode.response_level.value,
    }


def get_fixed_accuracy_rubric(db: Session, target_id: int) -> TargetRubric | None:
    return (
        db.query(TargetRubric)
        .filter(
            TargetRubric.target_id == target_id,
            TargetRubric.group == RUBRIC_GROUP_FIXED,
            TargetRubric.name == FIXED_ACCURACY_NAME,
        )
        .order_by(TargetRubric.id.asc())
        .first()
    )


def get_fixed_accuracy_rubric_or_raise(db: Session, target_id: int) -> TargetRubric:
    rubric = get_fixed_accuracy_rubric(db, target_id)
    if rubric is None:
        raise FixedAccuracyRubricInvariantError(
            f"Fixed Accuracy rubric not found for target {target_id}"
        )
    return rubric


def ensure_fixed_accuracy_rubric(db: Session, target_id: int) -> TargetRubric:
    fixed_accuracy = get_fixed_accuracy_rubric(db, target_id)
    definition = build_fixed_accuracy_definition()
    if fixed_accuracy:
        changed = False
        for key, value in definition.items():
            if getattr(fixed_accuracy, key) != value:
                setattr(fixed_accuracy, key, value)
                changed = True
        if changed:
            db.commit()
            db.refresh(fixed_accuracy)
        return fixed_accuracy

    fixed_accuracy = TargetRubric(
        target_id=target_id,
        position=0,
        **definition,
    )
    db.add(fixed_accuracy)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = get_fixed_accuracy_rubric(db, target_id)
        if existing:
            return existing
        raise
    db.refresh(fixed_accuracy)
    return fixed_accuracy


def ensure_system_rubrics(db: Session) -> None:
    targets = db.query(Target).all()
    reserved = reserved_system_names()

    for target in targets:
        ensure_fixed_accuracy_rubric(db, target.id)
        rubrics = (
            db.query(TargetRubric)
            .filter(TargetRubric.target_id == target.id)
            .order_by(TargetRubric.position.asc(), TargetRubric.id.asc())
            .all()
        )

        # Normalize fixed/preset rubrics to canonical content.
        for rubric in rubrics:
            definition = None
            if rubric.group in {RUBRIC_GROUP_FIXED, RUBRIC_GROUP_PRESET}:
                if _name_matches(rubric.name, FIXED_ACCURACY_NAME):
                    definition = build_fixed_accuracy_definition()
                else:
                    definition = build_preset_definition(rubric.name)

            if definition:
                for key, value in definition.items():
                    setattr(rubric, key, value)
                continue

            # Custom rubrics with reserved names are auto-suffixed (case/whitespace-insensitive).
            rubric.group = RUBRIC_GROUP_CUSTOM
            if rubric.name.strip().lower() in {r.lower() for r in reserved}:
                existing_names = [str(item.name) for item in rubrics if item.id != rubric.id]
                rubric.name = suffix_reserved_name(rubric.name.strip(), existing_names)

        db.commit()

        rubrics = (
            db.query(TargetRubric)
            .filter(TargetRubric.target_id == target.id)
            .order_by(TargetRubric.position.asc(), TargetRubric.id.asc())
            .all()
        )

        # Reorder to keep the fixed rubric first.
        ordered = (
            db.query(TargetRubric)
            .filter(TargetRubric.target_id == target.id)
            .order_by(TargetRubric.position.asc(), TargetRubric.id.asc())
            .all()
        )
        fixed = next((rubric for rubric in ordered if rubric.group == RUBRIC_GROUP_FIXED and rubric.name == FIXED_ACCURACY_NAME), None)
        if fixed:
            presets = [rubric for rubric in ordered if rubric.id != fixed.id and rubric.group == RUBRIC_GROUP_PRESET]
            customs = [rubric for rubric in ordered if rubric.id != fixed.id and rubric.group != RUBRIC_GROUP_PRESET]
            ordered = [fixed, *presets, *customs]

            from src.common.database.models import AnswerLabelOverride, AnswerScore, Annotation

            changed = False
            for annotation in db.query(Annotation).filter(Annotation.rubric_id == fixed.id).all():
                canonical = canonicalize_rubric_option_value(fixed, annotation.option_value)
                if canonical and annotation.option_value != canonical:
                    annotation.option_value = canonical
                    changed = True

            for override in db.query(AnswerLabelOverride).filter(AnswerLabelOverride.rubric_id == fixed.id).all():
                canonical = canonicalize_rubric_option_value(fixed, override.edited_value)
                if canonical and override.edited_value != canonical:
                    override.edited_value = canonical
                    changed = True

            for score in db.query(AnswerScore).filter(AnswerScore.rubric_id == fixed.id).all():
                canonical = canonicalize_rubric_option_value(fixed, score.overall_label)
                if canonical and score.overall_label != canonical:
                    score.overall_label = canonical
                    changed = True

            if changed:
                db.commit()
        for index, rubric in enumerate(ordered):
            rubric.position = index
        db.commit()
