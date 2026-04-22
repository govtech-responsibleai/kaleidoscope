"""Backend-owned rubric-spec resolution helpers."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from src.common.database.repositories.judge_repo import JudgeRepository
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository


@dataclass
class RubricSpecResolutionError(Exception):
    """Raised when a target does not have exactly one baseline judge per rubric."""

    errors: list[dict[str, object]]

    def __str__(self) -> str:
        return "; ".join(str(item.get("message", "")) for item in self.errors)


def resolve_target_rubric_specs(db: Session, target_id: int) -> list[dict[str, int]]:
    """Resolve the baseline rubric spec set for a target."""
    rubrics = TargetRubricRepository.get_by_target(db, target_id)
    errors: list[dict[str, object]] = []
    resolved: list[dict[str, int]] = []

    for rubric in rubrics:
        judges = JudgeRepository.get_for_rubric(db, rubric.id, target_id=target_id)
        baseline_judges = [judge for judge in judges if judge.is_baseline]
        if len(baseline_judges) != 1:
            errors.append(
                {
                    "rubric_id": rubric.id,
                    "rubric_name": rubric.name,
                    "baseline_judge_count": len(baseline_judges),
                    "message": (
                        f'Rubric "{rubric.name}" must have exactly 1 baseline judge; '
                        f"found {len(baseline_judges)}."
                    ),
                }
            )
            continue

        resolved.append({"rubric_id": rubric.id, "judge_id": baseline_judges[0].id})

    if errors:
        raise RubricSpecResolutionError(errors)

    return resolved


def rubric_spec_map(specs: list[dict[str, int]]) -> dict[int, dict[str, int]]:
    """Return rubric specs keyed by rubric_id for API responses."""
    return {spec["rubric_id"]: spec for spec in specs}


def validate_target_rubric_spec(
    db: Session,
    target_id: int,
    rubric_id: int,
    judge_id: int,
) -> dict[str, int] | None:
    """Validate a specific target/rubric/judge tuple."""
    rubric = TargetRubricRepository.get_by_id(db, rubric_id)
    if rubric is None or rubric.target_id != target_id:
        return None

    judges = JudgeRepository.get_for_rubric(db, rubric_id, target_id=target_id)
    if not any(judge.id == judge_id for judge in judges):
        return None

    return {"rubric_id": rubric_id, "judge_id": judge_id}
