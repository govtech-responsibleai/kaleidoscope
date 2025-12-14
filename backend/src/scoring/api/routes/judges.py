"""
API routes for Judge management.
"""

from pathlib import Path
from typing import Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.common.database.connection import get_db
from src.common.database.repositories import JudgeRepository
from src.common.database.models import JudgeTypeEnum
from src.common.models import (
    JudgeCreate,
    JudgeUpdate,
    JudgeResponse
)

router = APIRouter()


def _load_baseline_prompt() -> str:
    """Load the shared baseline prompt from the templates directory."""
    template_path = Path(__file__).resolve().parents[3] / "common" / "prompts" / "templates" / "claim_level_judge.md"
    try:
        return template_path.read_text()
    except OSError as exc:  # pragma: no cover - critical failure if missing template
        raise RuntimeError(f"Baseline prompt template missing: {template_path}") from exc


BASELINE_PROMPT_TEMPLATE = _load_baseline_prompt()

AVAILABLE_MODELS = [
    {"value": "gemini/gemini-2.0-flash-lite-001", "label": "Gemini 2.0 Flash Lite"},
    {"value": "gemini/gemini-2.0-flash-001", "label": "Gemini 2.0 Flash"},
    {"value": "gemini/gemini-2.5-flash-lite", "label": "Gemini 2.5 Flash Lite"},
    {"value": "gemini/gemini-2.5-flash", "label": "Gemini 2.5 Flash"},
    {"value": "azure/gpt-5-nano-2025-08-07", "label": "GPT-5 nano"},
    {"value": "azure/gpt-5-mini-2025-08-07", "label": "GPT-5 mini"},
    {"value": "azure/gpt-5-2025-08-07", "label": "GPT-5"},
    {"value": "vertex_ai/claude-haiku-4-5", "label": "Haiku 4.5"},
    {"value": "vertex_ai/claude-sonnet-4-5", "label": "Sonnet 4.5"},
    {"value": "vertex_ai/claude-opus-4-5", "label": "Opus 4.5"},
]

AVAILABLE_MODEL_MAP: Dict[str, dict] = {model["value"]: model for model in AVAILABLE_MODELS}


def _require_model(value: str) -> str:
    """Ensure the requested model is defined in AVAILABLE_MODELS."""
    if value not in AVAILABLE_MODEL_MAP:
        raise RuntimeError(f"Model '{value}' is not defined in AVAILABLE_MODELS.")
    return value

DEFAULT_JUDGES = [
    {
        "name": "Baseline Gemini Flash Lite",
        "model_name": _require_model("gemini/gemini-2.0-flash-lite-001"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": True,
        "is_editable": False,
    },
    {
        "name": "Gemini Flash",
        "model_name": _require_model("gemini/gemini-2.0-flash-001"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
    },
    {
        "name": "GPT-5 Nano",
        "model_name": _require_model("azure/gpt-5-nano-2025-08-07"),
        "judge_type": JudgeTypeEnum.claim_based,
        "is_baseline": False,
        "is_editable": False,
    },
]


@router.post("/judges/seed", response_model=List[JudgeResponse])
def seed_default_judges(
    db: Session = Depends(get_db)
):
    """Create the default set of judges if they do not already exist."""
    existing_judges = JudgeRepository.get_all(db)
    existing_models = {judge.model_name for judge in existing_judges}

    for config in DEFAULT_JUDGES:
        if config["model_name"] in existing_models:
            continue

        judge_data = {
            "name": config["name"],
            "model_name": config["model_name"],
            "prompt_template": BASELINE_PROMPT_TEMPLATE,
            "params": {},
            "judge_type": config["judge_type"],
            "is_baseline": config["is_baseline"],
            "is_editable": config["is_editable"],
        }
        JudgeRepository.create(db, judge_data)
        existing_models.add(config["model_name"])

    # Return the full list so the frontend can refresh its cache
    return JudgeRepository.get_all(db)


@router.post("/judges", response_model=JudgeResponse, status_code=status.HTTP_201_CREATED)
def create_judge(
    judge: JudgeCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new judge configuration.

    Args:
        judge: Judge creation data
        db: Database session

    Returns:
        Created judge
    """
    judge_data = judge.model_dump()
    created_judge = JudgeRepository.create(db, judge_data)
    return created_judge


@router.get("/judges", response_model=List[JudgeResponse])
def list_judges(
    db: Session = Depends(get_db)
):
    """
    List all judges.

    Args:
        db: Database session

    Returns:
        List of all judges
    """
    judges = JudgeRepository.get_all(db)
    return judges


@router.get("/judges/baseline", response_model=JudgeResponse)
def get_baseline_judge(
    db: Session = Depends(get_db)
):
    """
    Get the baseline judge configuration.

    Args:
        db: Database session

    Returns:
        Baseline judge

    Raises:
        HTTPException: If baseline judge not found
    """
    judge = JudgeRepository.get_baseline(db)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Baseline judge not found"
        )
    return judge


@router.get("/judges/available-models")
def list_available_models():
    """
    Return the static list of available judge models.
    """
    return AVAILABLE_MODELS


@router.get("/judges/{judge_id}", response_model=JudgeResponse)
def get_judge(
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific judge by ID.

    Args:
        judge_id: Judge ID
        db: Database session

    Returns:
        Judge details

    Raises:
        HTTPException: If judge not found
    """
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )
    return judge


@router.put("/judges/{judge_id}", response_model=JudgeResponse)
def update_judge(
    judge_id: int,
    judge_update: JudgeUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a judge configuration.

    Only editable judges (is_editable=True) can be updated.

    Args:
        judge_id: Judge ID
        judge_update: Fields to update
        db: Database session

    Returns:
        Updated judge

    Raises:
        HTTPException: If judge not found or not editable
    """
    # Check if judge exists and is editable
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    if not judge.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Judge {judge_id} is not editable"
        )

    update_data = judge_update.model_dump(exclude_unset=True)
    updated_judge = JudgeRepository.update(db, judge_id, update_data)
    return updated_judge


@router.delete("/judges/{judge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_judge(
    judge_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a judge.

    Only editable judges (is_editable=True) can be deleted.

    Args:
        judge_id: Judge ID
        db: Database session

    Raises:
        HTTPException: If judge not found or not editable
    """
    # Check if judge exists and is editable
    judge = JudgeRepository.get_by_id(db, judge_id)
    if not judge:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Judge {judge_id} not found"
        )

    if not judge.is_editable:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Judge {judge_id} is not editable and cannot be deleted"
        )

    success = JudgeRepository.delete(db, judge_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete judge {judge_id}"
        )
