"""API routes for rubric management scoped under targets."""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import TargetRepository, TargetRubricRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.models import (
    PremadeRubricTemplateResponse,
    RubricSpec,
    TargetRubricCreate,
    TargetRubricResponse,
    TargetRubricUpdate,
)
from src.rubric.services.premade_rubrics import list_premade_templates
from src.rubric.services.rubric_augmenter import build_fallback_judge_prompt, generate_judge_prompt
from src.rubric.services.rubric_specs import (
    RubricSpecResolutionError,
    resolve_target_rubric_specs,
    rubric_spec_map,
    validate_target_rubric_spec,
)
from src.rubric.services.system_rubrics import (
    RUBRIC_GROUP_CUSTOM,
    RUBRIC_GROUP_FIXED,
    RUBRIC_GROUP_PRESET,
    build_preset_definition,
    ensure_judges,
    suffix_reserved_name,
)

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{target_id}/rubric-specs", response_model=dict[int, RubricSpec])
def get_target_rubric_specs(
    target_id: int,
    db: Session = Depends(get_db),
):
    """Return the backend-owned baseline rubric spec set for a target."""
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    try:
        specs = resolve_target_rubric_specs(db, target_id)
    except RubricSpecResolutionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "Each target rubric must have exactly one baseline judge.",
                "errors": exc.errors,
            },
        ) from exc
    return rubric_spec_map(specs)


@router.get("/{target_id}/rubric-specs/{rubric_id}/judges/{judge_id}", response_model=RubricSpec)
def get_target_rubric_spec(
    target_id: int,
    rubric_id: int,
    judge_id: int,
    db: Session = Depends(get_db),
):
    """Validate and return one rubric/judge spec for a target."""
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found",
        )

    spec = validate_target_rubric_spec(db, target_id, rubric_id, judge_id)
    if spec is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} is not valid for rubric {rubric_id} on target {target_id}",
        )
    return spec


@router.get("/{target_id}/rubrics", response_model=List[TargetRubricResponse])
def list_rubrics(
    target_id: int,
    db: Session = Depends(get_db),
):
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    return TargetRubricRepository.get_by_target(db, target_id)


@router.get("/{target_id}/premade-rubrics", response_model=List[PremadeRubricTemplateResponse])
def list_premade_rubrics(
    target_id: int,
    db: Session = Depends(get_db),
):
    """List available pre-made rubric templates, excluding those already added to this target."""
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    existing_preset_names = {
        rubric.name
        for rubric in TargetRubricRepository.get_by_target(db, target_id)
        if rubric.group == RUBRIC_GROUP_PRESET
    }
    return [template for template in list_premade_templates() if template["name"] not in existing_preset_names]


@router.post("/{target_id}/rubrics", response_model=TargetRubricResponse, status_code=status.HTTP_201_CREATED)
def create_rubric(
    target_id: int,
    rubric: TargetRubricCreate,
    db: Session = Depends(get_db),
):
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")

    existing_rubrics = TargetRubricRepository.get_by_target(db, target_id)
    existing_names = [existing_rubric.name for existing_rubric in existing_rubrics]

    if rubric.group == RUBRIC_GROUP_PRESET:
        definition = build_preset_definition(rubric.name.strip())
        if not definition:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unknown preset rubric template",
            )
        if any(
            existing_rubric.group == RUBRIC_GROUP_PRESET
            and existing_rubric.name.strip().lower() == definition["name"].strip().lower()
            for existing_rubric in existing_rubrics
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Preset rubric already added to this target",
            )
        data = definition
    elif rubric.group == RUBRIC_GROUP_CUSTOM:
        if not rubric.name or not rubric.name.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric name is required")
        if not rubric.criteria or not rubric.criteria.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric criteria is required")
        non_empty_options = [option for option in rubric.options if option.option.strip()]
        if len(non_empty_options) < 2:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least 2 non-empty options are required")
        if not rubric.best_option:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option is required")
        non_empty_names = [option.option.strip() for option in non_empty_options]
        if len(set(name.lower() for name in non_empty_names)) != len(non_empty_names):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Option names must be unique")
        if rubric.best_option.strip() not in non_empty_names:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")

        data = rubric.model_dump()
        data["group"] = RUBRIC_GROUP_CUSTOM
        data["options"] = [option.model_dump() for option in rubric.options if option.option.strip()]
        data["name"] = suffix_reserved_name(rubric.name.strip(), existing_names)

        options_dicts = [option.model_dump() for option in rubric.options if option.option.strip()]
        try:
            data["judge_prompt"] = generate_judge_prompt(
                data["name"], rubric.criteria, options_dicts, rubric.best_option
            )
        except Exception as exc:
            logger.warning("Augmenter failed for rubric '%s', using fallback: %s", rubric.name, exc)
            data["judge_prompt"] = build_fallback_judge_prompt(
                data["name"], rubric.criteria, options_dicts, rubric.best_option
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only custom rubrics can be created through this endpoint",
        )

    created = TargetRubricRepository.create(db, target_id, data)
    ensure_judges(db, int(created.id))  # type: ignore[arg-type]
    return created


@router.put("/{target_id}/rubrics/{rubric_id}", response_model=TargetRubricResponse)
def update_rubric(
    target_id: int,
    rubric_id: int,
    rubric_update: TargetRubricUpdate,
    db: Session = Depends(get_db),
):
    existing_rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not existing_rubric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")

    if existing_rubric.group != RUBRIC_GROUP_CUSTOM:
        editable_fields = {"name", "criteria", "options", "best_option", "judge_prompt", "group"}
        changed = rubric_update.model_dump(exclude_unset=True)
        if any(key in changed for key in editable_fields):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fixed and preset rubrics cannot be edited")

    data = rubric_update.model_dump(exclude_unset=True)

    def _to_dict(option) -> dict:
        return option if isinstance(option, dict) else {"option": option.option, "description": option.description}

    if "options" in data and data["options"] is not None:
        data["options"] = [_to_dict(option) for option in data["options"]]

    existing_options: list[dict] = [_to_dict(option) for option in existing_rubric.options]

    if "options" in data and data["options"] is not None:
        non_empty_names = [option["option"].strip() for option in data["options"] if option["option"].strip()]
        if len(set(name.lower() for name in non_empty_names)) != len(non_empty_names):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Option names must be unique")

    if "best_option" in data and data["best_option"] is not None:
        merged_options = data.get("options", existing_options)
        non_empty_merged = [option["option"].strip() for option in merged_options if option["option"].strip()]
        if data["best_option"].strip() not in non_empty_merged:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")

    if "options" in data and data["options"] is not None:
        old_option_names = {option["option"] for option in existing_options}
        new_option_names = {option["option"] for option in data["options"]}
        if old_option_names != new_option_names:
            deleted = AnswerScoreRepository.delete_scores_by_rubric(db, rubric_id)
            if deleted:
                logger.info("Rubric %s options changed; purged %s stale scores", rubric_id, deleted)

    content_changed = any(key in data for key in ("name", "criteria", "options"))
    if content_changed and existing_rubric.group == RUBRIC_GROUP_CUSTOM:
        name = data.get("name", existing_rubric.name)
        criteria = data.get("criteria", existing_rubric.criteria)
        options = data.get("options", existing_options)
        best_option = data.get("best_option", existing_rubric.best_option)
        non_empty_options = [option for option in options if option.get("option", "").strip()]
        try:
            data["judge_prompt"] = generate_judge_prompt(name, criteria, non_empty_options, best_option)
        except Exception as exc:
            logger.warning("Augmenter failed for rubric %s, using fallback: %s", rubric_id, exc)
            data["judge_prompt"] = build_fallback_judge_prompt(name, criteria, non_empty_options, best_option)

    rubric = TargetRubricRepository.update(db, rubric_id, data)
    if not rubric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
    return rubric


@router.delete("/{target_id}/rubrics/{rubric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    target_id: int,
    rubric_id: int,
    db: Session = Depends(get_db),
):
    existing_rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not existing_rubric or existing_rubric.target_id != target_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
    if existing_rubric.group == RUBRIC_GROUP_FIXED:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fixed rubrics cannot be deleted")
    success = TargetRubricRepository.delete(db, rubric_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
