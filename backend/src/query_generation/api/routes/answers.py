"""
API routes for Answer generation and management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_claim_repo import AnswerClaimRepository
from src.common.database.repositories.answer_claim_score_repo import AnswerClaimScoreRepository
from src.common.database.repositories.answer_label_override_repo import AnswerLabelOverrideRepository
from src.common.models.answer import (
    AnswerCreate, AnswerResponse,
)
from src.common.models.answer_score import AnswerScoreResponse, AnswerClaimScoreResponse
from src.common.models.answer_claim import AnswerClaimResponse, AnswerClaimsWithScoresResponse
from src.common.models.answer_label_override import AnswerLabelOverrideCreate, AnswerLabelOverrideResponse
from src.query_generation.services.answer_generator import generate_answer_for_question

router = APIRouter()


@router.post("", response_model=AnswerResponse, status_code=201)
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


@router.get("/{answer_id}", response_model=AnswerResponse)
def get_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """Get an answer by ID."""
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    return answer


@router.delete("/{answer_id}", status_code=204)
def delete_answer(
    answer_id: int,
    db: Session = Depends(get_db)
):
    """Delete an answer."""
    deleted = AnswerRepository.delete(db, answer_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Answer not found")
    return None

@router.get("/{answer_id}/scores/{judge_id}", response_model=AnswerScoreResponse)
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


@router.get("/{answer_id}/claims", response_model=AnswerClaimsWithScoresResponse)
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
        AnswerClaimsWithScoresResponse with answer_id and list of claims with scores

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

    claim_score_map = {}
    if answer_score:
        claim_scores = AnswerClaimScoreRepository.get_by_answer_score(db, answer_score.id)
        claim_score_map = {cs.claim_id: cs for cs in claim_scores}

    # Build typed response
    claim_responses = [
        AnswerClaimResponse(
            id=claim.id,
            answer_id=claim.answer_id,
            claim_index=claim.claim_index,
            claim_text=claim.claim_text,
            checkworthy=claim.checkworthy,
            created_at=claim.created_at,
            checked_at=claim.checked_at,
            score=AnswerClaimScoreResponse.model_validate(claim_score_map[claim.id]) if claim.id in claim_score_map else None,
        )
        for claim in claims
    ]

    return AnswerClaimsWithScoresResponse(answer_id=answer_id, claims=claim_responses)

@router.get("/{answer_id}/label-overrides/{rubric_id}", response_model=AnswerLabelOverrideResponse)
def get_label_override(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    override = AnswerLabelOverrideRepository.get_by_answer_and_rubric(db, answer_id, rubric_id)
    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No label override found for answer {answer_id} and rubric {rubric_id}"
        )

    return override


@router.put("/{answer_id}/label-overrides/{rubric_id}", response_model=AnswerLabelOverrideResponse)
def create_or_update_label_override(
    answer_id: int,
    rubric_id: int,
    override_data: AnswerLabelOverrideCreate,
    db: Session = Depends(get_db)
):
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    override = AnswerLabelOverrideRepository.create_or_update(
        db,
        answer_id=answer_id,
        rubric_id=rubric_id,
        edited_value=override_data.edited_value,
    )

    return override


@router.delete("/{answer_id}/label-overrides/{rubric_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_label_override(
    answer_id: int,
    rubric_id: int,
    db: Session = Depends(get_db)
):
    answer = AnswerRepository.get_by_id(db, answer_id)
    if not answer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Answer {answer_id} not found"
        )

    success = AnswerLabelOverrideRepository.delete(db, answer_id, rubric_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No label override found for answer {answer_id} and rubric {rubric_id}"
        )
