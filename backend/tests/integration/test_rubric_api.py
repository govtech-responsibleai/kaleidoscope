"""
Integration tests for custom rubric API endpoints.

Covers CRUD, validation, score invalidation on edit,
and annotation completeness gating.
"""

import pytest
from unittest.mock import patch

from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import (
    AnswerScore, Annotation, Judge, TargetRubric,
)
from src.rubric.services.prompt_files import custom_rubric_prompt_path
from src.rubric.services.system_rubrics import ensure_system_rubrics

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("with_provider_bypass")]

class TestRubric:
    """CRUD and scoring lifecycle tests for rubrics."""

    @staticmethod
    def _accuracy_rubric(test_db, target_id: int):
        return TargetRubricRepository.get_by_target(
            test_db, target_id, group="fixed", name="Accuracy"
        )[0]

    def test_create_rubric(self, test_client, sample_target):
        """POST rubric with valid options -> 201, verify response fields."""
        payload = {
            "name": "Clarity",
            "criteria": "Is the response clear?",
            "options": [
                {"option": "Clear", "description": "Easy to understand"},
                {"option": "Unclear", "description": "Hard to understand"},
            ],
            "best_option": "Clear",
        }
        resp = test_client.post(
            f"/api/v1/targets/{sample_target.id}/rubrics",
            json=payload,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Clarity"
        assert data["best_option"] == "Clear"
        assert len(data["options"]) == 2
        assert data["target_id"] == sample_target.id
        assert "id" in data
        assert data["group"] == "custom"

    def test_create_preset_rubric(self, test_client, sample_target):
        payload = {
            "name": "Empathy",
            "criteria": "Does the response show empathy?",
            "options": [
                {"option": "Empathetic", "description": "Shows empathy"},
                {"option": "Not Empathetic", "description": "Lacks empathy"},
            ],
            "best_option": "Empathetic",
            "group": "preset",
        }
        resp = test_client.post(
            f"/api/v1/targets/{sample_target.id}/rubrics",
            json=payload,
        )
        assert resp.status_code == 201
        assert resp.json()["group"] == "preset"
        assert resp.json()["name"] == "Empathy"

    def test_list_rubrics(self, test_client, sample_target, sample_rubric, sample_rubric_second):
        """GET list returns existing rubrics only; it does not bootstrap built-ins on read."""
        resp = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics")
        assert resp.status_code == 200
        rubrics = resp.json()
        assert len(rubrics) == 2
        names = {r["name"] for r in rubrics}
        assert names == {"Tone of Voice", "Response Relevance"}

    def test_list_rubrics_does_not_create_fixed_accuracy_for_bare_target(self, test_client, test_db, sample_target):
        before_count = test_db.query(TargetRubric).filter_by(target_id=sample_target.id).count()
        assert before_count == 0

        resp = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics")
        assert resp.status_code == 200
        assert resp.json() == []

        after_count = test_db.query(TargetRubric).filter_by(target_id=sample_target.id).count()
        assert after_count == 0

    def test_fixed_accuracy_cannot_be_updated(self, test_client, test_db, sample_target):
        ensure_system_rubrics(test_db, sample_target.id)
        fixed = self._accuracy_rubric(test_db, sample_target.id)
        rubrics = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics").json()
        listed_fixed = next(r for r in rubrics if r["id"] == fixed.id)

        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{listed_fixed['id']}",
            json={"name": "Changed Accuracy"},
        )
        assert resp.status_code == 400

    def test_fixed_accuracy_cannot_be_deleted(self, test_client, test_db, sample_target):
        ensure_system_rubrics(test_db, sample_target.id)
        fixed = self._accuracy_rubric(test_db, sample_target.id)
        rubrics = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics").json()
        listed_fixed = next(r for r in rubrics if r["id"] == fixed.id)

        resp = test_client.delete(
            f"/api/v1/targets/{sample_target.id}/rubrics/{listed_fixed['id']}",
        )
        assert resp.status_code == 400

    def test_preset_rubric_cannot_be_updated(self, test_client, test_db, sample_target):
        """Preset (Empathy) rubric update -> 400."""
        from src.common.database.models import TargetRubric
        rubric = TargetRubric(
            target_id=sample_target.id,
            name="Empathy",
            criteria="Does the response show empathy?",
            options=[{"option": "Empathetic", "description": "Shows empathy"}, {"option": "Not empathetic", "description": "Lacks empathy"}],
            best_option="Empathetic",
            group="preset",
            scoring_mode="response_level",
            position=1,
        )
        test_db.add(rubric)
        test_db.commit()
        test_db.refresh(rubric)

        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{rubric.id}",
            json={"name": "Changed Empathy"},
        )
        assert resp.status_code == 400

    def test_preset_rubric_can_be_deleted(self, test_client, test_db, sample_target):
        """Preset (Empathy) rubric delete -> 204."""
        from src.common.database.models import TargetRubric
        rubric = TargetRubric(
            target_id=sample_target.id,
            name="Empathy",
            criteria="Does the response show empathy?",
            options=[{"option": "Empathetic", "description": "Shows empathy"}, {"option": "Not empathetic", "description": "Lacks empathy"}],
            best_option="Empathetic",
            group="preset",
            scoring_mode="response_level",
            position=1,
        )
        test_db.add(rubric)
        test_db.commit()
        test_db.refresh(rubric)

        resp = test_client.delete(
            f"/api/v1/targets/{sample_target.id}/rubrics/{rubric.id}",
        )
        assert resp.status_code == 204

    def test_reserved_custom_name_is_auto_suffixed(self, test_client, test_db, sample_target):
        ensure_system_rubrics(test_db, sample_target.id)
        payload = {
            "name": "Accuracy",
            "criteria": "Custom accuracy-like rubric",
            "options": [
                {"option": "Good", "description": "Good"},
                {"option": "Bad", "description": "Bad"},
            ],
            "best_option": "Good",
        }
        resp = test_client.post(
            f"/api/v1/targets/{sample_target.id}/rubrics",
            json=payload,
        )
        assert resp.status_code == 201
        assert resp.json()["name"].startswith("Accuracy (")

    def test_create_rubric_seeds_judges_for_created_rubric(self, test_client, test_db, sample_target):
        payload = {
            "name": "Clarity",
            "criteria": "Is the response clear?",
            "options": [
                {"option": "Clear", "description": "Easy to understand"},
                {"option": "Unclear", "description": "Hard to understand"},
            ],
            "best_option": "Clear",
        }
        resp = test_client.post(
            f"/api/v1/targets/{sample_target.id}/rubrics",
            json=payload,
        )
        assert resp.status_code == 201
        rubric_id = resp.json()["id"]

        judges = test_db.query(Judge).filter_by(rubric_id=rubric_id).all()
        assert len(judges) == 3
        assert all(judge.target_id == sample_target.id for judge in judges)

    @patch("src.rubric.api.routes.rubrics.generate_judge_prompt")
    def test_create_rubric_writes_generated_prompt_file(
        self,
        mock_generate_judge_prompt,
        test_client,
        sample_target,
    ):
        """Creating a custom rubric should materialize its generated prompt to the managed file location."""
        mock_generate_judge_prompt.return_value = "Custom prompt for {{ Question }} / {{ Answer }}"
        payload = {
            "name": "Clarity",
            "criteria": "Is the response clear?",
            "options": [
                {"option": "Clear", "description": "Easy to understand"},
                {"option": "Unclear", "description": "Hard to understand"},
            ],
            "best_option": "Clear",
        }

        resp = test_client.post(f"/api/v1/targets/{sample_target.id}/rubrics", json=payload)

        assert resp.status_code == 201
        rubric_id = resp.json()["id"]
        assert custom_rubric_prompt_path(rubric_id).read_text(encoding="utf-8") == mock_generate_judge_prompt.return_value

    def test_update_rubric_name(self, test_client, sample_target, sample_rubric):
        """PUT name change -> 200, name updated."""
        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={"name": "Updated Tone"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Tone"

    @patch("src.rubric.api.routes.rubrics.generate_judge_prompt")
    def test_update_rubric_rewrites_generated_prompt_file(
        self,
        mock_generate_judge_prompt,
        test_client,
        sample_target,
        sample_rubric,
    ):
        """Updating a custom rubric should refresh its managed prompt file."""
        initial_prompt = "Initial prompt for {{ Question }}"
        updated_prompt = "Updated prompt for {{ Question }}"
        custom_rubric_prompt_path(sample_rubric.id).parent.mkdir(parents=True, exist_ok=True)
        custom_rubric_prompt_path(sample_rubric.id).write_text(initial_prompt, encoding="utf-8")
        mock_generate_judge_prompt.return_value = updated_prompt

        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={"criteria": "Updated criteria"},
        )

        assert resp.status_code == 200
        assert custom_rubric_prompt_path(sample_rubric.id).read_text(encoding="utf-8") == updated_prompt

    def test_delete_rubric(self, test_client, sample_target, sample_rubric):
        """DELETE removes the custom rubric but preserves backend-owned fixed/preset rubrics."""
        resp = test_client.delete(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
        )
        assert resp.status_code == 204

        list_resp = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics")
        assert list_resp.status_code == 200
        assert list_resp.json() == []

    def test_update_options_deletes_stale_scores(
        self, test_client, test_db, sample_target, sample_rubric,
        sample_answer, sample_judge_claim_based,
    ):
        """Updating rubric options purges existing scores."""
        # Insert a score via ORM
        score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Professional",
            explanation="Good tone",
        )
        test_db.add(score)
        test_db.commit()

        # Verify score exists
        assert test_db.query(AnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 1

        # Update options (should trigger purge)
        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={
                "options": [
                    {"option": "Formal", "description": "Very formal"},
                    {"option": "Informal", "description": "Very informal"},
                ],
                "best_option": "Formal",
            },
        )
        assert resp.status_code == 200

        # Scores should be purged
        test_db.expire_all()
        assert test_db.query(AnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 0

    def test_update_name_preserves_scores(
        self, test_client, test_db, sample_target, sample_rubric,
        sample_answer, sample_judge_claim_based,
    ):
        """Changing only name does NOT purge scores."""
        score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Professional",
            explanation="Good tone",
        )
        test_db.add(score)
        test_db.commit()

        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={"name": "Renamed Rubric"},
        )
        assert resp.status_code == 200

        test_db.expire_all()
        assert test_db.query(AnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 1

    def test_incomplete_when_rubric_annotations_missing(
        self, test_client, test_db, sample_target, sample_snapshot,
        sample_answer, sample_rubric,
    ):
        """Accuracy annotation done but no rubric annotation -> is_complete=False."""
        # Mark answer as selected for annotation
        sample_answer.is_selected_for_annotation = True
        ensure_system_rubrics(test_db, sample_target.id)
        accuracy_rubric = self._accuracy_rubric(test_db, sample_target.id)
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric.id,
                option_value="Accurate",
                notes="ok",
            )
        )
        test_db.commit()

        resp = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/annotations/completion-status",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is False

    def test_complete_when_all_rubric_annotations_present(
        self, test_client, test_db, sample_target, sample_snapshot,
        sample_answer, sample_rubric,
    ):
        """Accuracy + rubric annotations done -> is_complete=True."""
        sample_answer.is_selected_for_annotation = True
        ensure_system_rubrics(test_db, sample_target.id)
        accuracy_rubric = self._accuracy_rubric(test_db, sample_target.id)
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric.id,
                option_value="Accurate",
                notes="ok",
            )
        )
        # Rubric annotation
        rubric_ann = Annotation(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            option_value="Professional",
        )
        test_db.add(rubric_ann)
        test_db.commit()

        resp = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/annotations/completion-status",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is True

    def test_incomplete_when_partial_rubric_annotations(
        self, test_client, test_db, sample_target, sample_snapshot,
        sample_answer, sample_rubric, sample_rubric_second,
    ):
        """2 rubrics, only 1 annotated -> is_complete=False."""
        sample_answer.is_selected_for_annotation = True
        ensure_system_rubrics(test_db, sample_target.id)
        accuracy_rubric = self._accuracy_rubric(test_db, sample_target.id)
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric.id,
                option_value="Accurate",
                notes="ok",
            )
        )
        # Only annotate first rubric, skip second
        rubric_ann = Annotation(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            option_value="Professional",
        )
        test_db.add(rubric_ann)
        test_db.commit()

        resp = test_client.get(
            f"/api/v1/snapshots/{sample_snapshot.id}/annotations/completion-status",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_complete"] is False


class TestRubricValidation:
    """Validation and error-case tests for rubrics."""

    def test_create_rubric_best_option_mismatch(self, test_client, sample_target):
        """best_option not in options -> 400."""
        payload = {
            "name": "Bad Rubric",
            "options": [
                {"option": "A", "description": "option A"},
                {"option": "B", "description": "option B"},
            ],
            "best_option": "C",
        }
        resp = test_client.post(
            f"/api/v1/targets/{sample_target.id}/rubrics",
            json=payload,
        )
        assert resp.status_code == 400

    def test_create_rubric_nonexistent_target(self, test_client):
        """POST to bad target_id -> 404."""
        payload = {
            "name": "Orphan Rubric",
            "options": [
                {"option": "A", "description": "a"},
                {"option": "B", "description": "b"},
            ],
            "best_option": "A",
        }
        resp = test_client.post("/api/v1/targets/99999/rubrics", json=payload)
        assert resp.status_code == 404

    def test_update_rubric_best_option_mismatch(
        self, test_client, sample_target, sample_rubric,
    ):
        """PUT with invalid best_option -> 400."""
        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={"best_option": "NonexistentOption"},
        )
        assert resp.status_code == 400

    # Rubric job start tests removed — /rubric-qa-jobs/start endpoint was
    # removed in the single-QAJob-per-question architecture.
