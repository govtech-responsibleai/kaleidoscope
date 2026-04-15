"""
API routes for Target management.
"""

import io
import json
import logging
import zipfile
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import TargetRepository, PersonaRepository, QuestionRepository, TargetRubricRepository, RubricAnswerScoreRepository
from src.common.models import TargetCreate, TargetUpdate, TargetResponse, TargetStats, PersonaResponse, QuestionResponse, QuestionListResponse, TargetRubricCreate, TargetRubricUpdate, TargetRubricResponse, PremadeRubricTemplateResponse
from src.common.database.models import StatusEnum
from src.common.auth import get_current_user_id
from src.common.services.export_service import ExportService, ExportFormat
from src.common.services.premade_rubrics import list_premade_templates, get_premade_template

logger = logging.getLogger(__name__)

router = APIRouter()


def _target_to_response(target) -> TargetResponse:
    """Convert a Target ORM model to TargetResponse with owner_username."""
    return TargetResponse.model_validate(
        target,
        from_attributes=True,
    ).model_copy(update={
        "owner_username": target.owner.username if target.owner else None,
    })


@router.post("", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
def create_target(
    target: TargetCreate,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db)
):
    """
    Create a new target application.

    Args:
        target: Target creation data
        user_id: Current user's ID (injected)
        db: Database session

    Returns:
        Created target
    """
    target_data = target.model_dump()
    target_data["user_id"] = user_id
    created_target = TargetRepository.create(db, target_data)
    return _target_to_response(created_target)


@router.get("", response_model=List[TargetResponse])
def list_targets(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all targets.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        db: Database session

    Returns:
        List of targets
    """
    targets = TargetRepository.get_all(db, skip=skip, limit=limit)
    return [_target_to_response(t) for t in targets]


@router.get("/{target_id}", response_model=TargetResponse)
def get_target(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific target by ID.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        Target details

    Raises:
        HTTPException: If target not found
    """
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )
    return _target_to_response(target)


@router.put("/{target_id}", response_model=TargetResponse)
def update_target(
    target_id: int,
    target_update: TargetUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a target.

    Args:
        target_id: Target ID
        target_update: Fields to update
        db: Database session

    Returns:
        Updated target

    Raises:
        HTTPException: If target not found
    """
    update_data = target_update.model_dump(exclude_unset=True)
    target = TargetRepository.update(db, target_id, update_data)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )
    return _target_to_response(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a target.

    Args:
        target_id: Target ID
        db: Database session

    Raises:
        HTTPException: If target not found
    """
    try:
        success = TargetRepository.delete(db, target_id)
    except Exception as e:
        logger.error(f"Failed to delete target {target_id}: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete target {target_id}"
        )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )


@router.get("/{target_id}/stats", response_model=TargetStats)
def get_target_stats(
    target_id: int,
    db: Session = Depends(get_db)
):
    """
    Get statistics for a target.

    Args:
        target_id: Target ID
        db: Database session

    Returns:
        Target statistics (persona counts, question counts, total cost)

    Raises:
        HTTPException: If target not found
    """
    # Check if target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    stats = TargetRepository.get_stats(db, target_id)
    return stats


@router.get("/{target_id}/personas", response_model=List[PersonaResponse])
def list_personas_for_target(
    target_id: int,
    status_filter: Optional[StatusEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all personas for a target.

    Args:
        target_id: Target ID
        status_filter: Optional filter by status
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of personas
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    personas = PersonaRepository.get_by_target(db, target_id, status_filter, skip, limit)
    return personas


@router.get("/{target_id}/questions", response_model=QuestionListResponse)
def list_questions_for_target(
    target_id: int,
    status_filter: Optional[StatusEnum] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all questions for a target.

    Args:
        target_id: Target ID
        status_filter: Optional filter by status
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        Paginated list of questions with persona titles
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    questions = QuestionRepository.get_by_target(db, target_id, status_filter, skip, limit)
    total = QuestionRepository.count_by_target(db, target_id, status_filter)

    # Add persona_title to each question
    response = []
    for question in questions:
        question_dict = {
            "id": question.id,
            "source": question.source,
            "job_id": question.job_id,
            "persona_id": question.persona_id,
            "target_id": question.target_id,
            "orig_id": question.orig_id,
            "text": question.text,
            "type": question.type,
            "scope": question.scope,
            "status": question.status,
            "created_at": question.created_at,
            "updated_at": question.updated_at,
            "persona_title": question.persona.title if question.persona else None
        }
        response.append(question_dict)

    return {
        "items": response,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/{target_id}/personas/export")
def export_personas(
    target_id: int,
    format: ExportFormat = Query(ExportFormat.CSV),
    db: Session = Depends(get_db)
):
    """
    Export all personas for a target.

    Args:
        target_id: Target ID
        format: Export format (csv or json)
        db: Database session

    Returns:
        CSV or JSON file with all personas

    Raises:
        HTTPException: If target not found or no personas exist
    """
    try:
        export_service = ExportService(db)
        data = export_service.export_personas(target_id, format)

        if format == ExportFormat.JSON:
            return data

        return Response(
            content=data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=target_{target_id}_personas.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{target_id}/questions/export")
def export_questions(
    target_id: int,
    format: ExportFormat = Query(ExportFormat.CSV),
    db: Session = Depends(get_db)
):
    """
    Export all questions for a target.

    Args:
        target_id: Target ID
        format: Export format (csv or json)
        db: Database session

    Returns:
        CSV or JSON file with all questions

    Raises:
        HTTPException: If target not found or no questions exist
    """
    try:
        export_service = ExportService(db)
        data = export_service.export_questions(target_id, format)

        if format == ExportFormat.JSON:
            return data

        return Response(
            content=data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=target_{target_id}_questions.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/snapshots/{snapshot_id}/export")
def export_snapshot(
    snapshot_id: int,
    format: ExportFormat = Query(ExportFormat.CSV),
    include_evaluators: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Export snapshot results including answers, annotations, and judge scores.

    Args:
        snapshot_id: Snapshot ID
        format: Export format (csv or json)
        db: Database session

    Returns:
        CSV or JSON file with results

    Raises:
        HTTPException: If snapshot not found or no answers available
    """
    try:
        export_service = ExportService(db)
        results_data, evaluator_payload = export_service.export_snapshot(
            snapshot_id,
            format,
            include_evaluators=include_evaluators
        )

        if format == ExportFormat.JSON:
            if include_evaluators:
                return {
                    "results": results_data,
                    "evaluator_exports": evaluator_payload or []
                }
            return results_data

        if include_evaluators:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                zip_file.writestr(
                    f"snapshot_{snapshot_id}_results.csv",
                    results_data
                )
                evaluator_content = json.dumps(evaluator_payload or [], indent=2)
                zip_file.writestr(
                    f"snapshot_{snapshot_id}_evaluators.json",
                    evaluator_content
                )

            zip_buffer.seek(0)
            return Response(
                content=zip_buffer.getvalue(),
                media_type="application/zip",
                headers={
                    "Content-Disposition": f"attachment; filename=snapshot_{snapshot_id}_results.zip"
                }
            )

        return Response(
            content=results_data,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=snapshot_{snapshot_id}_results.csv"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{target_id}/rubrics", response_model=List[TargetRubricResponse])
def list_rubrics(
    target_id: int,
    db: Session = Depends(get_db)
):
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    return TargetRubricRepository.get_by_target(db, target_id)


@router.get("/{target_id}/premade-rubrics", response_model=List[PremadeRubricTemplateResponse])
def list_premade_rubrics(
    target_id: int,
    db: Session = Depends(get_db)
):
    """List available pre-made rubric templates, excluding those already added to this target."""
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    existing_keys = {
        r.template_key
        for r in TargetRubricRepository.get_by_target(db, target_id)
        if r.template_key
    }
    return [t for t in list_premade_templates() if t["key"] not in existing_keys]


@router.post("/{target_id}/rubrics", response_model=TargetRubricResponse, status_code=status.HTTP_201_CREATED)
def create_rubric(
    target_id: int,
    rubric: TargetRubricCreate,
    db: Session = Depends(get_db)
):
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")

    # Pre-made template path
    if rubric.template_key:
        tmpl = get_premade_template(rubric.template_key)
        if not tmpl:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown template key: {rubric.template_key}")
        data = {
            "name": tmpl["name"],
            "criteria": tmpl["criteria"],
            "options": tmpl["options"],
            "best_option": tmpl["best_option"],
            "judge_prompt": tmpl["judge_prompt"],
            "template_key": rubric.template_key,
        }
        return TargetRubricRepository.create(db, target_id, data)

    # Custom rubric path — validate completeness
    if not rubric.name or not rubric.name.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric name is required")
    if not rubric.criteria or not rubric.criteria.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Rubric criteria is required")
    non_empty_options = [o for o in rubric.options if o.option.strip()]
    if len(non_empty_options) < 2:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least 2 non-empty options are required")
    if not rubric.best_option:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option is required")
    non_empty_names = [o.option.strip() for o in non_empty_options]
    if len(set(n.lower() for n in non_empty_names)) != len(non_empty_names):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Option names must be unique")
    if rubric.best_option.strip() not in non_empty_names:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")

    data = rubric.model_dump()
    data["options"] = [o.model_dump() for o in rubric.options if o.option.strip()]

    # Generate judge prompt via LLM augmenter, fall back to template if it fails
    from src.common.services.rubric_augmenter import generate_judge_prompt, build_fallback_judge_prompt
    options_dicts = [o.model_dump() for o in rubric.options if o.option.strip()]
    try:
        data["judge_prompt"] = generate_judge_prompt(
            rubric.name, rubric.criteria, options_dicts, rubric.best_option
        )
    except Exception as e:
        logger.warning(f"Augmenter failed for rubric '{rubric.name}', using fallback: {e}")
        data["judge_prompt"] = build_fallback_judge_prompt(
            rubric.name, rubric.criteria, options_dicts, rubric.best_option
        )

    return TargetRubricRepository.create(db, target_id, data)


@router.put("/{target_id}/rubrics/{rubric_id}", response_model=TargetRubricResponse)
def update_rubric(
    target_id: int,
    rubric_id: int,
    rubric_update: TargetRubricUpdate,
    db: Session = Depends(get_db)
):
    existing_rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if not existing_rubric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")

    # Block editing of pre-made rubric content
    if existing_rubric.template_key:
        editable_fields = {"name", "criteria", "options", "best_option", "judge_prompt", "template_key"}
        changed = rubric_update.model_dump(exclude_unset=True)
        if any(k in changed for k in editable_fields):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pre-made rubrics cannot be edited")

    data = rubric_update.model_dump(exclude_unset=True)

    # Normalise options to plain dicts once — data["options"] comes from model_dump so
    # it's already dicts, but existing_rubric.options may be ORM objects or JSON dicts.
    def _to_dict(o) -> dict:
        return o if isinstance(o, dict) else {"option": o.option, "description": o.description}

    if "options" in data and data["options"] is not None:
        data["options"] = [_to_dict(o) for o in data["options"]]

    existing_options: list[dict] = [_to_dict(o) for o in existing_rubric.options]

    # Validate no duplicate option names
    if "options" in data and data["options"] is not None:
        non_empty_names = [o["option"].strip() for o in data["options"] if o["option"].strip()]
        if len(set(n.lower() for n in non_empty_names)) != len(non_empty_names):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Option names must be unique")

    # Validate best_option consistency (against non-empty options, same casing)
    if "best_option" in data and data["best_option"] is not None:
        merged_options = data.get("options", existing_options)
        non_empty_merged = [o["option"].strip() for o in merged_options if o["option"].strip()]
        if data["best_option"].strip() not in non_empty_merged:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")

    # Invalidate existing scores when options change
    if "options" in data and data["options"] is not None:
        old_option_names = {o["option"] for o in existing_options}
        new_option_names = {o["option"] for o in data["options"]}
        if old_option_names != new_option_names:
            deleted = RubricAnswerScoreRepository.delete_scores_by_rubric(db, rubric_id)
            if deleted:
                logger.info(f"Rubric {rubric_id} options changed — purged {deleted} stale scores")

    # Regenerate judge prompt if rubric content changed (custom rubrics only)
    content_changed = any(k in data for k in ("name", "criteria", "options"))
    if content_changed and not existing_rubric.template_key:
        from src.common.services.rubric_augmenter import generate_judge_prompt, build_fallback_judge_prompt
        name = data.get("name", existing_rubric.name)
        criteria = data.get("criteria", existing_rubric.criteria)
        options = data.get("options", existing_options)
        best_option = data.get("best_option", existing_rubric.best_option)
        non_empty_options = [o for o in options if o.get("option", "").strip()]
        try:
            data["judge_prompt"] = generate_judge_prompt(name, criteria, non_empty_options, best_option)
        except Exception as e:
            logger.warning(f"Augmenter failed for rubric {rubric_id}, using fallback: {e}")
            data["judge_prompt"] = build_fallback_judge_prompt(name, criteria, non_empty_options, best_option)

    rubric = TargetRubricRepository.update(db, rubric_id, data)
    if not rubric:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
    return rubric


@router.delete("/{target_id}/rubrics/{rubric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_rubric(
    target_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    success = TargetRubricRepository.delete(db, rubric_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")


@router.get("/{target_id}/export-all")
def export_all(
    target_id: int,
    format: ExportFormat = Query(ExportFormat.CSV),
    db: Session = Depends(get_db)
):
    """
    Export all data for a target as a ZIP file.

    Contains personas, questions, and all snapshot results.

    Args:
        target_id: Target ID
        format: Export format for individual files (csv or json)
        db: Database session

    Returns:
        ZIP file containing all data

    Raises:
        HTTPException: If target not found
    """
    try:
        export_service = ExportService(db)
        zip_bytes = export_service.export_all(target_id, format)

        return Response(
            content=zip_bytes,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename=target_{target_id}_export.zip"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
