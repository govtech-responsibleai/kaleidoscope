"""
Repository for unified AnswerScore database operations.
"""

from typing import List, Optional
from sqlalchemy.orm import Session

from src.common.database.models import AnswerScore, Answer


class AnswerScoreRepository:
    """Repository for unified AnswerScore CRUD operations."""

    @staticmethod
    def _dedupe_latest(scores: List[AnswerScore]) -> List[AnswerScore]:
        """Keep the latest score per (answer, rubric, judge) triple."""
        deduped: dict[tuple[int | None, int | None, int | None], AnswerScore] = {}
        ordered = sorted(
            scores,
            key=lambda s: (
                s.answer_id or -1,
                s.rubric_id or -1,
                s.judge_id or -1,
                s.created_at,
                s.id,
            ),
            reverse=True,
        )
        for score in ordered:
            key = (score.answer_id, score.rubric_id, score.judge_id)
            if key not in deduped:
                deduped[key] = score
        return list(deduped.values())

    @staticmethod
    def _validate_payload(score_data: dict) -> dict:
        payload = dict(score_data)
        overall_label = payload.get("overall_label")
        if overall_label is None or not isinstance(overall_label, str) or not overall_label.strip():
            raise ValueError("overall_label must be a non-empty string")
        return payload

    @staticmethod
    def create(db: Session, score_data: dict) -> AnswerScore:
        """Create a new answer score."""
        score = AnswerScore(**AnswerScoreRepository._validate_payload(score_data))
        db.add(score)
        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def replace_for_answer_judge_rubric_no_commit(db: Session, score_data: dict) -> AnswerScore:
        """Replace the canonical score for an (answer, rubric, judge) triple without committing."""
        payload = AnswerScoreRepository._validate_payload(score_data)
        answer_id = payload["answer_id"]
        judge_id = payload["judge_id"]
        rubric_id = payload.get("rubric_id")
        score = (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.judge_id == judge_id,
                AnswerScore.rubric_id == rubric_id,
            )
            .order_by(AnswerScore.created_at.desc(), AnswerScore.id.desc())
            .first()
        )

        if score is None:
            score = AnswerScore(**payload)
            db.add(score)
        else:
            for claim_score in list(score.claim_scores):
                db.delete(claim_score)
            for key, value in payload.items():
                setattr(score, key, value)

        db.flush()
        return score

    @staticmethod
    def replace_for_answer_judge_rubric(db: Session, score_data: dict) -> AnswerScore:
        """Replace the canonical score for an (answer, rubric, judge) triple."""
        score = AnswerScoreRepository.replace_for_answer_judge_rubric_no_commit(db, score_data)
        db.commit()
        db.refresh(score)
        return score

    @staticmethod
    def replace_for_answer_and_judge(
        db: Session,
        score_data: dict,
        rubric_id: Optional[int] = None,
    ) -> AnswerScore:
        """Backward-compatible wrapper for callers migrating to rubric-scoped identity."""
        payload = dict(score_data)
        payload["rubric_id"] = rubric_id if rubric_id is not None else payload.get("rubric_id")
        return AnswerScoreRepository.replace_for_answer_judge_rubric(db, payload)

    @staticmethod
    def create_many(db: Session, scores_data: List[dict]) -> List[AnswerScore]:
        """Create multiple answer scores."""
        scores = [AnswerScore(**AnswerScoreRepository._validate_payload(data)) for data in scores_data]
        db.add_all(scores)
        db.flush()
        db.commit()
        return scores

    @staticmethod
    def get_by_id(db: Session, score_id: int) -> Optional[AnswerScore]:
        """Get answer score by ID."""
        return db.query(AnswerScore).filter(AnswerScore.id == score_id).first()

    @staticmethod
    def get_by_answer_judge_rubric(
        db: Session,
        answer_id: int,
        judge_id: int,
        rubric_id: int,
    ) -> Optional[AnswerScore]:
        """Get the latest score for a specific (answer, rubric, judge) triple."""
        return (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.judge_id == judge_id,
                AnswerScore.rubric_id == rubric_id,
            )
            .order_by(AnswerScore.created_at.desc(), AnswerScore.id.desc())
            .first()
        )

    @staticmethod
    def get_by_answer_and_judge(
        db: Session,
        answer_id: int,
        judge_id: int,
        rubric_id: int,
    ) -> Optional[AnswerScore]:
        """Get the latest rubric-scoped score for a specific answer/judge pair."""
        return AnswerScoreRepository.get_by_answer_judge_rubric(
            db,
            answer_id=answer_id,
            judge_id=judge_id,
            rubric_id=rubric_id,
        )

    @staticmethod
    def get_by_answer(db: Session, answer_id: int, rubric_id: Optional[int] = None) -> List[AnswerScore]:
        """Get all scores for a specific answer, optionally scoped to one rubric."""
        query = db.query(AnswerScore).filter(AnswerScore.answer_id == answer_id)
        if rubric_id is not None:
            query = query.filter(AnswerScore.rubric_id == rubric_id)
        return query.all()

    @staticmethod
    def get_by_answer_and_rubric(db: Session, answer_id: int, rubric_id: int) -> List[AnswerScore]:
        """Get all rubric-scoped scores for an answer."""
        return (
            db.query(AnswerScore)
            .filter(
                AnswerScore.answer_id == answer_id,
                AnswerScore.rubric_id == rubric_id,
            )
            .all()
        )

    @staticmethod
    def get_by_snapshot(db: Session, snapshot_id: int) -> List[AnswerScore]:
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
        judge_id: int,
        rubric_id: Optional[int] = None,
    ) -> List[AnswerScore]:
        """Get all scores for a snapshot evaluated by a specific judge."""
        query = (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                AnswerScore.judge_id == judge_id,
            )
        )
        if rubric_id is not None:
            query = query.filter(AnswerScore.rubric_id == rubric_id)
        scores = query.all()
        return AnswerScoreRepository._dedupe_latest(scores)

    @staticmethod
    def get_by_snapshot_and_judge_selected(
        db: Session,
        snapshot_id: int,
        judge_id: int,
        rubric_id: Optional[int] = None,
    ) -> List[AnswerScore]:
        """
        Get scores for a judge on answers that are selected for annotation.
        Used for judge alignment metric calculation in service layer.
        """
        query = (
            db.query(AnswerScore)
            .join(Answer)
            .filter(
                Answer.snapshot_id == snapshot_id,
                Answer.is_selected_for_annotation == True,
                AnswerScore.judge_id == judge_id,
            )
        )
        if rubric_id is not None:
            query = query.filter(AnswerScore.rubric_id == rubric_id)
        scores = query.all()
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

    @staticmethod
    def delete_scores_by_rubric(db: Session, rubric_id: int) -> int:
        """Delete all judge scores for a rubric."""
        score_count = (
            db.query(AnswerScore)
            .filter(AnswerScore.rubric_id == rubric_id)
            .delete()
        )
        db.commit()
        return score_count
