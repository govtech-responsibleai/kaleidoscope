"""
Service for exporting data (personas, questions, snapshots) in various formats.
"""

import csv
import io
import json
import logging
import zipfile
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Tuple, Union

from sqlalchemy.orm import Session

from src.common.database.repositories.persona_repo import PersonaRepository
from src.common.database.repositories.question_repo import QuestionRepository
from src.common.database.repositories.snapshot_repo import SnapshotRepository
from src.common.database.repositories.target_repo import TargetRepository
from src.common.database.repositories.answer_score_repo import AnswerScoreRepository
from src.common.database.repositories.answer_repo import AnswerRepository
from src.scoring.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class ExportFormat(str, Enum):
    """Supported export formats."""
    CSV = "csv"
    JSON = "json"


def _format_label(label: bool | None) -> str:
    """Format boolean label as human-readable string."""
    if label is None:
        return "Pending"
    return "Accurate" if label else "Inaccurate"


class ExportService:
    """Service for exporting data in various formats."""

    def __init__(self, db: Session):
        """
        Initialize export service.

        Args:
            db: Database session
        """
        self.db = db
        self.metrics_service = MetricsService(db)

    def export_personas(
        self,
        target_id: int,
        format: ExportFormat = ExportFormat.CSV
    ) -> Union[str, List[Dict]]:
        """
        Export all personas for a target.

        Args:
            target_id: Target ID
            format: Export format (csv or json)

        Returns:
            CSV string or list of dicts depending on format

        Raises:
            ValueError: If target not found or no personas exist
        """
        target = TargetRepository.get_by_id(self.db, target_id)
        if not target:
            raise ValueError(f"Target {target_id} not found")

        personas = PersonaRepository.get_by_target(self.db, target_id, limit=10000)
        if not personas:
            raise ValueError(f"No personas found for target {target_id}")

        export_data = []
        for persona in personas:
            export_data.append({
                "id": persona.id,
                "title": persona.title,
                "info": persona.info or "",
                "style": persona.style or "",
                "use_case": persona.use_case or "",
                "status": persona.status.value if persona.status else "",
                "source": persona.source.value if persona.source else "",
                "created_at": persona.created_at.isoformat() if persona.created_at else "",
            })

        if format == ExportFormat.JSON:
            logger.info(f"Exported {len(export_data)} personas for target {target_id} as JSON")
            return export_data

        # CSV format
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "info", "style", "use_case", "status", "source", "created_at"])

        for row in export_data:
            writer.writerow([
                row["id"], row["title"], row["info"], row["style"],
                row["use_case"], row["status"], row["source"], row["created_at"],
            ])

        csv_content = output.getvalue()
        output.close()

        logger.info(f"Exported {len(export_data)} personas for target {target_id} as CSV")
        return csv_content

    def export_questions(
        self,
        target_id: int,
        format: ExportFormat = ExportFormat.CSV
    ) -> Union[str, List[Dict]]:
        """
        Export all questions for a target.

        Args:
            target_id: Target ID
            format: Export format (csv or json)

        Returns:
            CSV string or list of dicts depending on format

        Raises:
            ValueError: If target not found or no questions exist
        """
        target = TargetRepository.get_by_id(self.db, target_id)
        if not target:
            raise ValueError(f"Target {target_id} not found")

        questions = QuestionRepository.get_by_target(self.db, target_id, limit=10000)
        if not questions:
            raise ValueError(f"No questions found for target {target_id}")

        export_data = []
        for question in questions:
            export_data.append({
                "id": question.id,
                "persona_id": question.persona_id or "",
                "persona_title": question.persona.title if question.persona else "",
                "text": question.text,
                "type": question.type.value if question.type else "",
                "scope": question.scope.value if question.scope else "",
                "status": question.status.value if question.status else "",
                "source": question.source.value if question.source else "",
                "orig_id": question.orig_id or "",
                "created_at": question.created_at.isoformat() if question.created_at else "",
            })

        if format == ExportFormat.JSON:
            logger.info(f"Exported {len(export_data)} questions for target {target_id} as JSON")
            return export_data

        # CSV format
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "id", "persona_id", "persona_title", "text", "type",
            "scope", "status", "source", "orig_id", "created_at"
        ])

        for row in export_data:
            writer.writerow([
                row["id"], row["persona_id"], row["persona_title"], row["text"],
                row["type"], row["scope"], row["status"], row["source"],
                row["orig_id"], row["created_at"],
            ])

        csv_content = output.getvalue()
        output.close()

        logger.info(f"Exported {len(export_data)} questions for target {target_id} as CSV")
        return csv_content

    def export_snapshot(
        self,
        snapshot_id: int,
        format: ExportFormat = ExportFormat.CSV,
        include_evaluators: bool = False
    ) -> Tuple[Union[str, List[Dict]], Optional[List[Dict]]]:
        """
        Export snapshot results including answers, annotations, and judge scores.

        Args:
            snapshot_id: Snapshot ID
            format: Export format (csv or json)

        Returns:
            Tuple of (main export, evaluator payload). Evaluator payload is a list
            of judge exports when include_evaluators=True, otherwise None.

        Raises:
            ValueError: If snapshot not found or no answers exist
        """
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        # Get aggregated results from metrics service (includes annotations)
        results, _ = self.metrics_service.get_aggregated_results(snapshot_id)
        evaluator_payload: Optional[List[Dict]] = None

        if format == ExportFormat.JSON:
            main_export: Union[str, List[Dict]] = [r.model_dump() for r in results]
        else:
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Question_ID", "Question", "Answer_ID", "Answer",
                "Human_Label", "Human_Notes", "Aggregated_Accuracy", "Judge_Metadata"
            ])

            for row in results:
                agg = row.aggregated_accuracy
                writer.writerow([
                    row.question_id,
                    row.question_text or "",
                    row.answer_id,
                    row.answer_content,
                    _format_label(row.human_label),
                    row.human_notes or "",
                    _format_label(agg.label),
                    " | ".join(agg.metadata),
                ])

            csv_content = output.getvalue()
            output.close()
            main_export = csv_content

        if include_evaluators:
            evaluator_payload = self._build_evaluator_exports(snapshot_id, results)

        if isinstance(main_export, list):
            logger.info(f"Exported {len(results)} results for snapshot {snapshot_id} as JSON")
        else:
            logger.info(f"Exported {len(results)} results for snapshot {snapshot_id} as CSV")

        return main_export, evaluator_payload

    def export_aibots_responses(
        self,
        snapshot_id: int,
    ) -> List[Dict]:
        """
        Export full AIBots responses for a snapshot as JSON.
        Each entry contains the complete response including all metadata, citations, etc.

        Args:
            snapshot_id: Snapshot ID

        Returns:
            List of dicts containing full AIBots responses

        Raises:
            ValueError: If snapshot not found
        """
        snapshot = SnapshotRepository.get_by_id(self.db, snapshot_id)
        if not snapshot:
            raise ValueError(f"Snapshot {snapshot_id} not found")

        # Fetch answers directly with eager-loaded questions instead of going through metrics
        answers = AnswerRepository.get_by_snapshot(self.db, snapshot_id, eager_load=True)

        export_rows: List[Dict] = []

        for answer in answers:
            question = answer.question
            question_id = answer.question_id
            question_text = question.text if question else ""

            # Build the full AIBots response object
            aibots_response = {
                "answer_id": answer.id,
                "question_id": question_id,
                "question_text": question_text,
                "snapshot_id": answer.snapshot_id,
                "chat_id": answer.chat_id,
                "message_id": answer.message_id,
                "answer_content": answer.answer_content,
                "system_prompt": answer.system_prompt,
                "model": answer.model,
                "guardrails": answer.guardrails if answer.guardrails else {},
                "rag_citations": answer.rag_citations if answer.rag_citations else [],
                "raw_response": answer.raw_response if answer.raw_response else {},
                "is_selected_for_annotation": answer.is_selected_for_annotation,
                "created_at": answer.created_at.isoformat() if answer.created_at else None,
            }

            export_rows.append(aibots_response)

        logger.info(f"Exported {len(export_rows)} full AIBots responses for snapshot {snapshot_id}")
        return export_rows

    def _build_evaluator_exports(self, snapshot_id: int, aggregated_results: Optional[List] = None) -> List[Dict]:
        """
        Build judge-level export payload including metrics and raw scores.
        """
        scores = AnswerScoreRepository.get_by_snapshot(self.db, snapshot_id)
        if not scores:
            return []

        judge_map = {score.judge_id: score.judge for score in scores if score.judge_id is not None}

        scores_by_judge: Dict[int, List[Dict]] = defaultdict(list)
        for score in scores:
            answer = score.answer
            scores_by_judge[score.judge_id].append({
                "answer_id": score.answer_id,
                "question_id": answer.question_id if answer else None,
                "overall_label": score.overall_label,
                "explanation": score.explanation or "",
                "claim_scores": [
                    {
                        "claim_index": cs.claim.claim_index,
                        "claim_text": cs.claim.claim_text,
                        "checkworthy": cs.claim.checkworthy,
                        "label": cs.label,
                        "explanation": cs.explanation,
                    }
                    for cs in score.claim_scores
                ] if score.claim_scores else [],
                "created_at": score.created_at.isoformat() if score.created_at else None,
            })

        evaluator_exports: List[Dict] = []
        for judge_id, judge_scores in scores_by_judge.items():
            judge = judge_map.get(judge_id)

            try:
                accuracy = self.metrics_service.calculate_accuracy(snapshot_id, judge_id)
            except ValueError:
                accuracy = None

            try:
                alignment = self.metrics_service.calculate_judge_alignment(snapshot_id, judge_id)
            except ValueError:
                alignment = None

            evaluator_exports.append({
                "judge_id": judge_id,
                "judge_name": getattr(judge, "name", None) if judge else None,
                "judge_model": getattr(judge, "model_name", None) if judge else None,
                "judge_accuracy": accuracy.model_dump() if accuracy else None,
                "judge_alignment": alignment.model_dump() if alignment else None,
                "judge_scores": judge_scores,
            })

        return evaluator_exports

    def export_all(
        self,
        target_id: int,
        format: ExportFormat = ExportFormat.CSV
    ) -> bytes:
        """
        Export all data for a target as a ZIP file.

        Contains:
        - personas.csv (or .json)
        - questions.csv (or .json)
        - snapshot_{id}_{name}.csv (or .json) for each snapshot
        - snapshot_{id}_{name}_aibots_responses.json for each snapshot (full AIBots responses)
        - snapshot_{id}_{name}_evaluators.json for each snapshot

        Args:
            target_id: Target ID
            format: Export format for individual files (csv or json)

        Returns:
            ZIP file as bytes

        Raises:
            ValueError: If target not found
        """
        target = TargetRepository.get_by_id(self.db, target_id)
        if not target:
            raise ValueError(f"Target {target_id} not found")

        snapshots = SnapshotRepository.get_by_target(self.db, target_id)

        zip_buffer = io.BytesIO()
        file_ext = "json" if format == ExportFormat.JSON else "csv"

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Export personas
            try:
                data = self.export_personas(target_id, format)
                content = json.dumps(data, indent=2) if format == ExportFormat.JSON else data
                zip_file.writestr(f"personas.{file_ext}", content)
            except ValueError as e:
                logger.warning(f"Skipping personas export: {e}")

            # Export questions
            try:
                data = self.export_questions(target_id, format)
                content = json.dumps(data, indent=2) if format == ExportFormat.JSON else data
                zip_file.writestr(f"questions.{file_ext}", content)
            except ValueError as e:
                logger.warning(f"Skipping questions export: {e}")

            # Export each snapshot
            for snapshot in snapshots:
                try:
                    snapshot_content, evaluator_payload = self.export_snapshot(
                        snapshot.id,
                        format,
                        include_evaluators=True
                    )
                    content = json.dumps(snapshot_content, indent=2) if format == ExportFormat.JSON else snapshot_content
                    zip_file.writestr(f"snapshot_{snapshot.id}_{snapshot.name}.{file_ext}", content)

                    if evaluator_payload:
                        evaluator_filename = f"snapshot_{snapshot.id}_{snapshot.name}_evaluators.json"
                        zip_file.writestr(
                            evaluator_filename,
                            json.dumps(evaluator_payload, indent=2)
                        )
                except ValueError as e:
                    logger.warning(f"Skipping snapshot {snapshot.id} export: {e}")

                try:
                    aibots_responses = self.export_aibots_responses(snapshot.id)
                    zip_file.writestr(
                        f"snapshot_{snapshot.id}_{snapshot.name}_aibots_responses.json",
                        json.dumps(aibots_responses, indent=2)
                    )
                except ValueError as e:
                    logger.warning(f"Skipping AIBots responses export for snapshot {snapshot.id}: {e}")

        zip_buffer.seek(0)
        zip_bytes = zip_buffer.getvalue()

        logger.info(f"Exported all data for target {target_id}: {len(snapshots)} snapshots ({len(zip_bytes)} bytes)")
        return zip_bytes
