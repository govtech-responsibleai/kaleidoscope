"""
API routes for Answer generation and management.
"""

import math
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
from src.common.database.repositories.snapshot_repo import SnapshotRepository
from src.common.database.repositories.annotation_repo import AnnotationRepository
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.models.answer import AnswerCreate, AnswerResponse, AnswerListResponse, AnswerBulkSelection
from src.common.models.answer_score import AnswerScoreResponse
from src.common.models.answer_claim import AnswerClaimResponse
from src.common.models.answer_label_override import AnswerLabelOverrideCreate, AnswerLabelOverrideResponse
from src.query_generation.services.answer_generator import generate_answer_for_question

router = APIRouter()


@router.post("/answers", response_model=AnswerResponse, status_code=201)
def generate_answer(
    request: AnswerCreate,
    db: Session = Depends(get_db)
):
    """Generate an answer for a question using AIBots API."""
    try:
        answer = generate_answer_for_question(db, request.question_id)
        return answer
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate answer: {str(e)}")


@router.get("/answers/{answer_id}", response_model=AnswerResponse)
def get_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """Get an answer by ID."""
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer


@router.get("/question/{question_id}/answers", response_model=AnswerListResponse)
def get_answers_by_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """Get all answers for a question."""
    answers = AnswerRepository.get_by_question(db, question_id)
    return AnswerListResponse(answers=answers, total=len(answers))


@router.get("/target/{target_id}/answers", response_model=AnswerListResponse)
def get_answers_by_target(
    target_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all answers for a target."""
    answers = AnswerRepository.get_by_target(db, target_id, skip, limit)
    total = AnswerRepository.count_by_target(db, target_id)
    return AnswerListResponse(answers=answers, total=total)


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """Delete an answer."""
    deleted = AnswerRepository.delete(db, answer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Answer not found")
    return None

@router.get("/snapshots/{snapshot_id}/answers", response_model=AnswerListResponse)
def list_answers_for_snapshot(
    snapshot_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    List all answers for a snapshot.

    Returns answers with question text and annotation status for the mailbox UI.

    Args:
        snapshot_id: Snapshot ID
        skip: Pagination offset
        limit: Pagination limit
        db: Database session

    Returns:
        List of answers with question text and has_annotation flag

    Raises:
        HTTPException: If snapshot not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Get all answers for the snapshot
    answers = AnswerRepository.get_by_snapshot(db, snapshot_id, skip, limit)

    # Enrich with annotation status
    enriched_answers = []
    for answer in answers:
        annotation = AnnotationRepository.get_by_answer(db, answer.id)
        answer_dict = {
            "id": answer.id,
            "snapshot_id": answer.snapshot_id,
            "question_id": answer.question_id,
            "chat_id": answer.chat_id,
            "message_id": answer.message_id,
            "answer_content": answer.answer_content,
            "model": answer.model,
            "guardrails": answer.guardrails,
            "rag_citations": answer.rag_citations,
            "is_selected_for_annotation": answer.is_selected_for_annotation,
            "created_at": answer.created_at,
            "question_text": answer.question.text if answer.question else None,
            "has_annotation": annotation is not None
        }
        enriched_answers.append(answer_dict)

    total = AnswerRepository.count_by_snapshot(db, snapshot_id)
    return {"answers": enriched_answers, "total": total}


@router.get("/answers/{answer_id}/scores/{judge_id}", response_model=AnswerScoreResponse)
def get_answer_score(
    answer_id: int,
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Get answer score from a specific judge.

    Returns the judge's overall assessment of the answer.

    Args:
        answer_id: Answer ID
        judge_id: Judge ID
        db: Database session

    Returns:
        Answer score with overall label and explanation

    Raises:
        HTTPException: If answer or score not found
    """
    # Verify answer exists
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    # Get score
    score = AnswerScoreRepository.get_by_answer_and_judge(db, answer_id, judge_id)
    if not score:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No score found for answer {answer_id}, judge {judge_id}"
        )

    return score


@router.get("/answers/{answer_id}/claims")
def get_answer_claims_with_scores(
    answer_id: int,
    judge_id: int = Query(..., description="Judge ID to get claim scores from"),
    db: Session = Depends(get_db)
):
    """
    Get answer claims with scores from a specific judge.

    Used for claim highlighting in the annotation UI. Returns each claim
    with its label (accurate/inaccurate) and explanation from the judge.

    Args:
        answer_id: Answer ID
        judge_id: Judge ID to get scores from
        db: Database session

    Returns:
        Dictionary with answer_id and list of claims with scores

    Raises:
        HTTPException: If answer not found
    """
    # Verify answer exists
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    # Get all claims for the answer
    claims = AnswerClaimRepository.get_by_answer(db, answer_id)

    # Get answer score to retrieve claim scores
    answer_score = AnswerScoreRepository.get_by_answer_and_judge(db, answer_id, judge_id)

    if not answer_score:
        # No scores yet - return claims without scores
        return {
            "answer_id": answer_id,
            "claims": [
                {
                    "id": claim.id,
                    "claim_text": claim.claim_text,
                    "claim_index": claim.claim_index,
                    "checkworthy": claim.checkworthy,
                    "score": None
                }
                for claim in claims
            ]
        }

    # Get claim scores
    claim_scores = AnswerClaimScoreRepository.get_by_answer_score(db, answer_score.id)
    claim_score_map = {cs.claim_id: cs for cs in claim_scores}

    # Build response with scores
    claims_with_scores = []
    for claim in claims:
        claim_score = claim_score_map.get(claim.id)
        claims_with_scores.append({
            "id": claim.id,
            "claim_text": claim.claim_text,
            "claim_index": claim.claim_index,
            "checkworthy": claim.checkworthy,
            "score": {
                "label": claim_score.label,
                "explanation": claim_score.explanation
            } if claim_score else None
        })

    return {
        "answer_id": answer_id,
        "claims": claims_with_scores
    }


@router.put("/answers/{answer_id}/selection")
def toggle_answer_selection(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """
    Toggle the is_selected_for_annotation flag for an answer.

    Args:
        answer_id: Answer ID
        db: Database session

    Returns:
        Updated answer

    Raises:
        HTTPException: If answer not found
    """
    # Get answer
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    # Toggle selection flag
    new_value = not answer.is_selected_for_annotation
    updated_answer = AnswerRepository.update(
        db,
        answer_id,
        {"is_selected_for_annotation": new_value}
    )

    return {
        "answer_id": answer_id,
        "is_selected_for_annotation": updated_answer.is_selected_for_annotation
    }


@router.post("/answers/bulk-selection")
def bulk_update_answer_selection(
    request: AnswerBulkSelection,
    db: Session = Depends(get_db)
):
    """
    Bulk update is_selected_for_annotation for multiple answers with individual values.

    Allows selecting/deselecting multiple answers at once with different values per answer
    (e.g., from checkboxes in the UI where some are checked and some unchecked).

    Args:
        request: Request with selections list containing answer_id and is_selected per answer
        db: Database session

    Returns:
        Count of updated answers and their selection details

    Raises:
        HTTPException: If any answer not found
    """
    # Extract answer IDs for validation
    answer_ids = [s["answer_id"] for s in request.selections]

    # Verify all answers exist
    for answer_id in answer_ids:
        answer = AnswerRepository.get_by_id(db, answer_id)
        if not answer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Answer {answer_id} not found"
            )

    # Use repository method to bulk update with per-answer selections
    updated_answers = AnswerRepository.update_annotation_selection(
        db,
        request.selections
    )

    return {
        "updated_count": len(updated_answers),
        "selections": request.selections
    }


@router.post("/snapshots/{snapshot_id}/answers/select-default")
def select_default_answers(
    snapshot_id: int,
    db: Session = Depends(get_db)
):
    """
    Auto-select 20% of answers (minimum 1) for annotation.

    This sets is_selected_for_annotation=True for the first 20% of answers
    in the snapshot, with a minimum of 1 answer selected.

    Args:
        snapshot_id: Snapshot ID
        db: Database session

    Returns:
        Count of selected answers

    Raises:
        HTTPException: If snapshot not found
    """
    # Verify snapshot exists
    snapshot = SnapshotRepository.get_by_id(db, snapshot_id)
    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found"
        )

    # Get all answers for snapshot
    answers = AnswerRepository.get_by_snapshot(db, snapshot_id, skip=0, limit=1000)

    # Select 20% of answers (minimum 1)
    count_to_select = max(1, math.ceil(len(answers) * 0.2))
    selected_count = 0

    for i in range(count_to_select):
        answer = answers[i]
        AnswerRepository.update(
            db,
            answer.id,
            {"is_selected_for_annotation": True}
        )
        selected_count += 1

    return {
        "snapshot_id": snapshot_id,
        "selected_count": selected_count,
        "total_answers": len(answers)
    }


@router.get("/answers/{answer_id}/label-override", response_model=AnswerLabelOverrideResponse)
def get_label_override(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """
    Get label override for a specific answer.

    Args:
        answer_id: Answer ID
        db: Database session

    Returns:
        Label override for the answer

    Raises:
        HTTPException: If answer or override not found
    """
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    override = AnswerLabelOverrideRepository.get_by_answer(db, answer_id)
    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No label override found for answer {answer_id}"
        )

    return override


@router.put("/answers/{answer_id}/label-override", response_model=AnswerLabelOverrideResponse)
def create_or_update_label_override(
    answer_id: int,
    override_data: AnswerLabelOverrideCreate,
    db: Session = Depends(get_db)
):
    """
    Create or update a label override for an answer.

    This allows users to manually override the aggregated accuracy label
    that was determined by majority vote from evaluators.

    Args:
        answer_id: Answer ID to override
        override_data: The new label value
        db: Database session

    Returns:
        Created or updated label override

    Raises:
        HTTPException: If answer not found
    """
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    override = AnswerLabelOverrideRepository.create_or_update(
        db,
        answer_id=answer_id,
        edited_label=override_data.edited_label
    )
    return override


@router.delete("/answers/{answer_id}/label-override", status_code=status.HTTP_204_NO_CONTENT)
def delete_label_override(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a label override (reset to evaluator suggestion).

    Args:
        answer_id: Answer ID whose override should be deleted
        db: Database session

    Raises:
        HTTPException: If answer or override not found
    """
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    success = AnswerLabelOverrideRepository.delete(db, answer_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No label override found for answer {answer_id}"
        )
