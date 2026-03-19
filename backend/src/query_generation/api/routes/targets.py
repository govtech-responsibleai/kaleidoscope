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
from src.common.models import TargetCreate, TargetUpdate, TargetResponse, TargetStats, PersonaResponse, QuestionResponse, TargetRubricCreate, TargetRubricUpdate, TargetRubricResponse
from src.common.database.models import StatusEnum
from src.common.auth import get_current_user_id
from src.common.services.export_service import ExportService, ExportFormat
from src.common.services.rubric_classifier import classify_rubric

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
    success = TargetRepository.delete(db, target_id)
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


@router.get("/{target_id}/questions", response_model=List[QuestionResponse])
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
        List of questions with persona titles
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    questions = QuestionRepository.get_by_target(db, target_id, status_filter, skip, limit)

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

    return response


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


@router.post("/{target_id}/rubrics", response_model=TargetRubricResponse, status_code=status.HTTP_201_CREATED)
def create_rubric(
    target_id: int,
    rubric: TargetRubricCreate,
    db: Session = Depends(get_db)
):
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Target {target_id} not found")
    data = rubric.model_dump()
    data["options"] = [o.model_dump() for o in rubric.options]
    data["category"] = classify_rubric(rubric.name, rubric.criteria)
    # Validate best_option consistency (completeness enforced at scoring time)
    if data.get("best_option") and len(data["options"]) > 0:
        option_names = [o["option"] for o in data["options"]]
        if data["best_option"] not in option_names:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")
    return TargetRubricRepository.create(db, target_id, data)


@router.put("/{target_id}/rubrics/{rubric_id}", response_model=TargetRubricResponse)
def update_rubric(
    target_id: int,
    rubric_id: int,
    rubric_update: TargetRubricUpdate,
    db: Session = Depends(get_db)
):
    data = rubric_update.model_dump(exclude_unset=True)
    if "options" in data and data["options"] is not None:
        data["options"] = [o.model_dump() if hasattr(o, "model_dump") else o for o in data["options"]]
    # Validate best_option consistency (don't block incremental edits — completeness is enforced at scoring time)
    if "best_option" in data and data["best_option"] is not None:
        existing = TargetRubricRepository.get_by_id(db, rubric_id)
        if not existing:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
        merged_options = data.get("options", [o if isinstance(o, dict) else {"option": o.option, "description": o.description} for o in existing.options])
        option_names = [o["option"] if isinstance(o, dict) else o.option for o in merged_options]
        if data["best_option"] not in option_names:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="best_option must match one of the option names")
    # Invalidate existing scores when options change (old option_chosen values become stale)
    if "options" in data and data["options"] is not None:
        existing_rubric = TargetRubricRepository.get_by_id(db, rubric_id)
        if not existing_rubric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
        old_options = {o.option if hasattr(o, "option") else o["option"] for o in existing_rubric.options}
        new_options = {o["option"] for o in data["options"]}
        if old_options != new_options:
            deleted = RubricAnswerScoreRepository.delete_scores_and_jobs_by_rubric(db, rubric_id)
            if deleted:
                logger.info(f"Rubric {rubric_id} options changed — purged {deleted} stale scores and associated jobs")

    if "name" in data or "criteria" in data:
        # Need to fetch existing rubric to get current name/criteria for classification
        existing_rubric = TargetRubricRepository.get_by_id(db, rubric_id)
        if not existing_rubric:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Rubric {rubric_id} not found")
        name = data.get("name", existing_rubric.name)
        criteria = data.get("criteria", existing_rubric.criteria)
        data["category"] = classify_rubric(name, criteria)
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
