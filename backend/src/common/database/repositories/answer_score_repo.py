"""
Repository for AnswerScore database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerScore, Answer


class AnswerScoreRepository:
    """Repository for AnswerScore CRUD operations."""

    @staticmethod
    def _dedupe_latest(scores: List[AnswerScore]) -> List[AnswerScore]:
        """Keep the latest score per (answer, judge) pair."""
        deduped: dict[tuple[int | None, int | None], AnswerScore] = {}
        for score in sorted(scores, key=lambda s: (s.answer_id or -1, s.judge_id or -1, s.created_at, s.id), reverse=True):
            key = (score.answer_id, score.judge_id)
            if key not in deduped:
                deduped[key] = score
        return list(deduped.values())

    @staticmethod
    def create(db: Session, score_data: dict) -> AnswerScore:
        """Create a new answer score."""
        score = AnswerScore(**score_data)
        db.add(score)
        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def replace_for_answer_and_judge(db: Session, score_data: dict) -> AnswerScore:
        """Replace the canonical score for an (answer, judge) pair."""
        answer_id = score_data["answer_id"]
        judge_id = score_data["judge_id"]
        score = (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.judge_id == judge_id,
            )
            .order_by(AnswerScore.created_at.desc(), AnswerScore.id.desc())
            .first()
        )

        if score is None:
            score = AnswerScore(**score_data)
            db.add(score)
        else:
            for claim_score in list(score.claim_scores):
                db.delete(claim_score)
            for key, value in score_data.items():
                setattr(score, key, value)

        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def create_many(db: Session, scores_data: List[dict]) -> List[AnswerScore]:
        """Create multiple answer scores."""
        scores = [AnswerScore(**data) for data in scores_data]
        db.add_all(scores)
        db.flush()
        db.commit()
        return scores

    @staticmethod
    def get_by_id(db: Session, score_id: int) -> Optional[AnswerScore]:
        """Get answer score by ID."""
        return db.query(AnswerScore).filter(AnswerScore.id == score_id).first()

    @staticmethod
    def get_by_answer_and_judge(
        db: Session,
        answer_id: int,
        judge_id: int
    ) -> Optional[AnswerScore]:
        """Get most recent score for a specific answer and judge combination."""
        return (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.judge_id == judge_id
            )
            .order_by(AnswerScore.created_at.desc())
            .limit(1)
            .first()
        )

    @staticmethod
    def get_by_answer(db: Session, answer_id: int) -> List[AnswerScore]:
        """Get all scores for a specific answer (from different judges)."""
        return (
            db.query(AnswerScore)
            .filter(AnswerScore.answer_id == answer_id)
            .all()
        )

    @staticmethod
    def get_by_snapshot(
        db: Session,
        snapshot_id: int
    ) -> List[AnswerScore]:
        """Get all judge scores for answers that belong to a snapshot."""
        scores = (
            db.query(AnswerScore)
            .join(Answer)
            .filter(Answer.snapshot_id == snapshot_id)
            .all()
        )
        return AnswerScoreRepository._dedupe_latest(scores)

    @staticmethod
    def get_by_snapshot_and_judge(
        db: Session,
        snapshot_id: int,
        judge_id: int
    ) -> List[AnswerScore]:
        """Get all scores for a snapshot evaluated by a specific judge."""
        scores = (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                AnswerScore.judge_id == judge_id
            )
            .all()
        )
        return AnswerScoreRepository._dedupe_latest(scores)

    @staticmethod
    def get_by_snapshot_and_judge_selected(
        db: Session,
        snapshot_id: int,
        judge_id: int
    ) -> List[AnswerScore]:
        """
        Get scores for a judge on answers that are selected for annotation.
        Used for judge alignment metric calculation in service layer.
        """
        scores = (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                AnswerScore.judge_id == judge_id
            )
            .all()
        )
        return AnswerScoreRepository._dedupe_latest(scores)

    @staticmethod
    def delete(db: Session, score_id: int) -> bool:
        """Delete an answer score."""
        score = db.query(AnswerScore).filter(AnswerScore.id == score_id).first()
        if not score:
            return False

        db.delete(score)
        db.commit()
        return True
