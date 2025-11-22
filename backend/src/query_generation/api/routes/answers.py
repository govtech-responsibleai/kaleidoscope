"""
API routes for Answer generation and management.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories.answer_repo import AnswerRepository
from src.common.models.answer import AnswerCreate, AnswerResponse, AnswerListResponse
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


@router.get("/question/{question_id}", response_model=AnswerListResponse)
def get_answers_by_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """Get all answers for a question."""
    answers = AnswerRepository.get_by_question(db, question_id)
    return AnswerListResponse(answers=answers, total=len(answers))


@router.get("/target/{target_id}", response_model=AnswerListResponse)
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
