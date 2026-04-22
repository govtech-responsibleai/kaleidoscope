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
from src.common.database.repositories import TargetRepository, PersonaRepository, QuestionRepository, TargetRubricRepository
from src.common.models import TargetCreate, TargetUpdate, TargetResponse, TargetStats, PersonaResponse, QuestionResponse, QuestionListResponse, TestConnectionRequest, TestConnectionResponse, ProbeRequest, ProbeResponse
from src.common.connectors.base import TargetHttpError
from src.common.connectors.http_auth import prepare_http_config_for_storage, persist_http_auth_secret
from src.common.database.models import StatusEnum
from src.common.auth import get_current_user_id
from src.common.connectors.registry import get_registered_types, get_connector, validate_connector_config
from src.common.services.export_service import ExportService, ExportFormat
from src.rubric.services.system_rubrics import bootstrap_target_rubrics_and_judges

logger = logging.getLogger(__name__)

router = APIRouter()


def _normalize_target_payload_for_storage(
    endpoint_type: Optional[str],
    endpoint_config: Optional[dict],
    *,
    has_existing_auth_secret: bool,
) -> tuple[Optional[dict], Optional[str], bool]:
    """Prepare endpoint_config for persistence and extract transient auth state."""
    if endpoint_type != "http" or endpoint_config is None:
        return endpoint_config, None, False
    return prepare_http_config_for_storage(endpoint_config, has_existing_auth_secret)


def _target_to_response(target) -> TargetResponse:
    """Convert a Target ORM model to TargetResponse with owner_username."""
    return TargetResponse.model_validate(
        target,
        from_attributes=True,
    ).model_copy(update={
        "owner_username": target.owner.username if target.owner else None,
    })


def _authorized_target_for_secret_reuse(
    db: Session,
    *,
    user_id: int,
    target_id: Optional[int],
):
    """Return the target only when the current user may reuse its saved auth."""
    if target_id is None:
        return None

    target = TargetRepository.get_by_id(db, target_id)
    if not target or target.user_id != user_id:
        return None

    return target


@router.get("/connector-types", response_model=List[str])
def list_connector_types(user_id: int = Depends(get_current_user_id)):
    """Return the registered connector type strings."""
    return get_registered_types()


@router.post("/test-connection", response_model=TestConnectionResponse)
async def test_connection(
    request: TestConnectionRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Test a connector configuration by sending a probe message.

    Args:
        request: Endpoint type, URL, and config to test.
        user_id: Current user's ID (injected via auth).

    Returns:
        TestConnectionResponse with success/error details.
    """
    try:
        validate_connector_config(request.endpoint_type, request.endpoint_config)
    except ValueError as e:
        return TestConnectionResponse(success=False, error=str(e))

    try:
        from types import SimpleNamespace
        authorized_target = _authorized_target_for_secret_reuse(
            db,
            user_id=user_id,
            target_id=request.target_id,
        )
        target_stub = SimpleNamespace(
            endpoint_type=request.endpoint_type,
            api_endpoint=request.api_endpoint,
            endpoint_config=request.endpoint_config,
            id=authorized_target.id if authorized_target else "test",
        )
        connector = get_connector(target_stub, db=db)
        result = await connector.send_message(request.prompt)
        return TestConnectionResponse(
            success=True,
            content=result.content[:200] if result.content else None,
            model=result.model,
        )
    except Exception as e:
        return TestConnectionResponse(success=False, error=str(e))


@router.post("/probe", response_model=ProbeResponse)
async def probe_endpoint(
    request: ProbeRequest,
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Probe a target endpoint and return the raw response body.

    Unlike /test-connection, this route does NOT run connector-specific config
    validation — so callers can hit the endpoint before declaring an extraction
    path and inspect the actual response shape. 4xx/5xx responses are returned
    as success=false with the response body preserved in raw_body.

    Args:
        request: Endpoint type, URL, config, and probe prompt.
        user_id: Current user's ID (injected via auth).

    Returns:
        ProbeResponse with status_code, raw_body, headers, or error.
    """
    if request.endpoint_type not in get_registered_types():
        raise HTTPException(
            status_code=400,
            detail=f"Unknown endpoint type '{request.endpoint_type}'. See GET /targets/connector-types.",
        )

    from types import SimpleNamespace
    authorized_target = _authorized_target_for_secret_reuse(
        db,
        user_id=user_id,
        target_id=request.target_id,
    )
    target_stub = SimpleNamespace(
        endpoint_type=request.endpoint_type,
        api_endpoint=request.api_endpoint,
        endpoint_config=request.endpoint_config,
        id=authorized_target.id if authorized_target else "probe",
    )

    try:
        connector = get_connector(target_stub, db=db)
        raw = await connector.probe(request.prompt)
        return ProbeResponse(
            success=True,
            status_code=200,
            raw_body=raw,
        )
    except TargetHttpError as e:
        try:
            parsed_body = json.loads(e.body) if e.body else None
        except (ValueError, json.JSONDecodeError):
            parsed_body = e.body
        return ProbeResponse(
            success=False,
            status_code=e.status_code,
            raw_body=parsed_body,
            headers=e.headers,
            error=f"Target endpoint returned HTTP {e.status_code}",
        )
    except Exception as e:
        return ProbeResponse(success=False, error=str(e))


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
    try:
        endpoint_config, pending_secret_value, should_keep_secret = _normalize_target_payload_for_storage(
            target_data.get("endpoint_type"),
            target_data.get("endpoint_config"),
            has_existing_auth_secret=False,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    target_data["endpoint_config"] = endpoint_config
    target_data["user_id"] = user_id
    created_target = TargetRepository.create(db, target_data)
    bootstrap_target_rubrics_and_judges(db, int(created_target.id))  # type: ignore[arg-type]
    if target_data.get("endpoint_type") == "http":
        persist_http_auth_secret(
            db,
            created_target.id,
            secret_value=pending_secret_value,
            should_keep_secret=should_keep_secret,
        )
        db.commit()
        db.refresh(created_target)
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
    existing_target = TargetRepository.get_by_id(db, target_id)
    if not existing_target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    update_data = target_update.model_dump(exclude_unset=True)
    if "endpoint_config" in update_data or "endpoint_type" in update_data:
        next_endpoint_type = update_data.get("endpoint_type", existing_target.endpoint_type)
        next_endpoint_config = update_data.get("endpoint_config", existing_target.endpoint_config)
        try:
            endpoint_config, pending_secret_value, should_keep_secret = _normalize_target_payload_for_storage(
                next_endpoint_type,
                next_endpoint_config,
                has_existing_auth_secret=existing_target.http_auth_secret is not None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        update_data["endpoint_config"] = endpoint_config
    else:
        pending_secret_value = None
        should_keep_secret = existing_target.http_auth_secret is not None

    target = TargetRepository.update(db, target_id, update_data)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    next_endpoint_type = target.endpoint_type
    if next_endpoint_type == "http":
        persist_http_auth_secret(
            db,
            target.id,
            secret_value=pending_secret_value,
            should_keep_secret=should_keep_secret,
        )
    else:
        persist_http_auth_secret(db, target.id, secret_value=None, should_keep_secret=False)
    db.commit()
    db.refresh(target)
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
    rubric_id: int = Query(...),
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
            format=format,
            include_evaluators=include_evaluators,
            rubric_id=rubric_id,
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
