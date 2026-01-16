"""
API routes for Question management.
"""

import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import QuestionRepository, TargetRepository, PersonaRepository
from src.common.database.models import StatusEnum, QuestionTypeEnum, QuestionScopeEnum, QuestionSourceEnum
from src.common.models import (
    QuestionResponse,
    QuestionUpdate,
    QuestionBulkApprove,
    SimilarQuestionsRequest,
    SimilarQuestionsResponse,
    SimilarQuestion,
    QuerySimilarQuestions
)
from src.query_generation.services import find_similar_questions_batch, QuestionFileParser

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/{question_id}", response_model=QuestionResponse)
def get_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific question by ID.

    Args:
        question_id: Question ID
        db: Database session

    Returns:
        Question details
    """
    question = QuestionRepository.get_by_id(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found"
        )
    return question


@router.put("/{question_id}", response_model=QuestionResponse)
def update_question(
    question_id: int,
    question_update: QuestionUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a question's text.

    Args:
        question_id: Question ID
        question_update: Fields to update
        db: Database session

    Returns:
        Updated question
    """
    update_data = question_update.model_dump(exclude_unset=True)
    question = QuestionRepository.update(db, question_id, update_data)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found"
        )
    return question


@router.post("/{question_id}/approve", response_model=QuestionResponse)
def approve_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """
    Approve a question.

    Args:
        question_id: Question ID
        db: Database session

    Returns:
        Approved question
    """
    question = QuestionRepository.approve(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found"
        )
    return question


@router.post("/{question_id}/reject", response_model=QuestionResponse)
def reject_question(
    question_id: int,
    db: Session = Depends(get_db)
):
    """
    Reject a question.

    Args:
        question_id: Question ID
        db: Database session

    Returns:
        Rejected question
    """
    question = QuestionRepository.reject(db, question_id)
    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Question {question_id} not found"
        )
    return question


@router.post("/bulk-approve", response_model=List[QuestionResponse])
def bulk_approve_questions(
    request: QuestionBulkApprove,
    db: Session = Depends(get_db)
):
    """
    Approve multiple questions at once.

    Args:
        request: List of question IDs to approve
        db: Database session

    Returns:
        List of approved questions
    """
    questions = QuestionRepository.bulk_approve(db, request.question_ids)
    return questions


@router.post("/similar", response_model=SimilarQuestionsResponse)
def find_similar_questions_endpoint(
    request: SimilarQuestionsRequest,
    db: Session = Depends(get_db)
):
    """
    Find semantically similar questions using Gemini embeddings and cosine similarity.

    Given a target_id and multiple question_ids, this endpoint:
    1. Gets embeddings for all query questions using Gemini text-embedding-004 (1 batch call)
    2. Gets embeddings for all other APPROVED questions in the target
    3. Uses matrix multiplication to calculate all similarities at once
    4. Returns question IDs with similarity >= threshold (default 0.7) for each query

    For M query questions and N candidate questions:
    - Makes 1 batch API call (instead of M separate calls)
    - Computes M×N similarity matrix with single matrix multiplication
    - Only compares against approved questions (status == 'approved')

    Args:
        request: Request with target_id, question_ids (list), and optional similarity_threshold
        db: Database session

    Returns:
        Results for each query question with similar APPROVED question IDs and scores (sorted descending)
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, request.target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {request.target_id} not found"
        )

    # Get all query questions and verify they exist
    query_questions = []
    for question_id in request.question_ids:
        query_question = QuestionRepository.get_by_id(db, question_id)
        if not query_question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question {question_id} not found"
            )

        # Verify question belongs to target
        if query_question.target_id != request.target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Question {question_id} does not belong to target {request.target_id}"
            )

        query_questions.append(query_question)

    # Get all approved questions for the target (only compare against approved questions)
    all_questions = QuestionRepository.get_by_target(
        db,
        request.target_id,
        status=StatusEnum.approved,  # Only approved questions
        skip=0,
        limit=10000  # High limit to get all questions
    )

    # Prepare query and candidate texts
    query_texts = [(q.id, q.text) for q in query_questions]

    # Filter out query questions from candidates
    query_ids_set = set(request.question_ids)
    candidate_texts = [
        (q.id, q.text)
        for q in all_questions
        if q.id not in query_ids_set
    ]

    if not candidate_texts:
        # No other questions to compare with
        return SimilarQuestionsResponse(
            results=[
                QuerySimilarQuestions(
                    query_question_id=q.id,
                    similar_questions=[]
                )
                for q in query_questions
            ]
        )

    logger.info(f"Finding similar questions for {len(request.question_ids)} queries in target {request.target_id}")
    logger.info(f"Comparing against {len(candidate_texts)} candidate questions")

    # Find similar questions using batch processing
    try:
        similar_results = find_similar_questions_batch(
            query_texts=query_texts,
            candidate_texts=candidate_texts,
            threshold=request.similarity_threshold
        )

        logger.info(f"Completed similarity search for {len(request.question_ids)} queries")

        # Build response
        results = []
        for query_id in request.question_ids:
            similar_question_tuples = similar_results.get(query_id, [])

            similar_questions = [
                SimilarQuestion(
                    question_id=question_id,
                    similarity_score=similarity_score
                )
                for question_id, similarity_score in similar_question_tuples
            ]

            results.append(QuerySimilarQuestions(
                query_question_id=query_id,
                similar_questions=similar_questions
            ))

        return SimilarQuestionsResponse(results=results)

    except Exception as e:
        logger.error(f"Failed to find similar questions: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar questions: {str(e)}"
        )


@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_questions(
    target_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload questions from a file (CSV, JSON, or Excel).

    Accepts files with the following fields:
    - question (mapped to 'text') [REQUIRED]
    - id (mapped to 'orig_id')
    - persona (mapped to persona title lookup)
    - type (mapped to 'type': typical or edge)
    - scope (mapped to 'scope': in_kb or out_kb)

    All other fields are discarded.

    Args:
        target_id: Target ID to associate questions with
        file: File to upload (CSV, JSON, or Excel)
        db: Database session

    Returns:
        Success message with count of questions created

    Raises:
        HTTPException: If target not found, file format not supported, or saving fails
    """
    # Verify target exists
    target = TargetRepository.get_by_id(db, target_id)
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target {target_id} not found"
        )

    # Read file content
    try:
        file_content = await file.read()
    except Exception as e:
        logger.error(f"Failed to read file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {str(e)}"
        )

    # Parse file
    try:
        parsed_questions = QuestionFileParser.parse_file(
            file_content=file_content,
            content_type=file.content_type or "application/octet-stream",
            filename=file.filename or "unknown"
        )
        logger.info(f"Parsed {len(parsed_questions)} questions from {file.filename}")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to parse file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}"
        )

    # Process and validate each question
    questions_to_create = []
    for idx, parsed_q in enumerate(parsed_questions):
        try:
            # Build question data
            question_data = {
                "target_id": target_id,
                "text": parsed_q["text"],
                "source": QuestionSourceEnum.uploaded,
                "status": StatusEnum.pending,
                "job_id": None,  # No job for uploaded questions
                "persona_id": None,  # Will be set if persona_title is provided
            }

            # Add orig_id if provided
            if "orig_id" in parsed_q:
                question_data["orig_id"] = parsed_q["orig_id"]

            # Lookup persona by title if provided
            if "persona_title" in parsed_q:
                persona = PersonaRepository.get_by_title(
                    db, target_id, parsed_q["persona_title"]
                )
                if persona:
                    question_data["persona_id"] = persona.id
                else:
                    logger.warning(
                        f"Question {idx+1}: Persona '{parsed_q['persona_title']}' not found for target {target_id}"
                    )

            # Set type (null if not provided or invalid)
            if "type" in parsed_q:
                try:
                    type_value = str(parsed_q["type"]).lower()
                    if type_value in ["typical", "edge"]:
                        question_data["type"] = QuestionTypeEnum[type_value]
                    else:
                        logger.warning(
                            f"Question {idx+1}: Invalid type '{parsed_q['type']}', setting to null"
                        )
                        question_data["type"] = None
                except Exception:
                    logger.warning(
                        f"Question {idx+1}: Invalid type '{parsed_q['type']}', setting to null"
                    )
                    question_data["type"] = None
            else:
                question_data["type"] = None

            # Set scope (null if not provided or invalid)
            if "scope" in parsed_q:
                try:
                    scope_value = str(parsed_q["scope"]).lower()
                    if scope_value in ["in_kb", "out_kb"]:
                        question_data["scope"] = QuestionScopeEnum[scope_value]
                    else:
                        logger.warning(
                            f"Question {idx+1}: Invalid scope '{parsed_q['scope']}', setting to null"
                        )
                        question_data["scope"] = None
                except Exception:
                    logger.warning(
                        f"Question {idx+1}: Invalid scope '{parsed_q['scope']}', setting to null"
                    )
                    question_data["scope"] = None
            else:
                question_data["scope"] = None

            questions_to_create.append(question_data)

        except Exception as e:
            logger.error(f"Failed to process question {idx+1}: {e}", exc_info=True)
            # Continue processing other questions

    if not questions_to_create:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid questions to create"
        )

    # Save to database
    try:
        created_questions = QuestionRepository.create_many(db, questions_to_create)
        logger.info(f"Successfully created {len(created_questions)} questions for target {target_id}")

        return {
            "message": "Questions uploaded successfully",
            "count": len(created_questions),
            "target_id": target_id
        }

    except Exception as e:
        logger.error(f"Failed to save questions to database: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save questions: {str(e)}"
        )
