"""
Integration tests for custom rubric API endpoints.

Covers CRUD, validation, score invalidation on edit,
and annotation completeness gating.
"""

import pytest

from src.common.database.models import (
    RubricAnswerScore, RubricAnnotation,
)


@pytest.mark.integration
class TestRubric:
    """CRUD and scoring lifecycle tests for rubrics."""

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
        assert "category" in data

    def test_list_rubrics(self, test_client, sample_target, sample_rubric, sample_rubric_second):
        """Create 2 rubrics, GET list -> returns both."""
        resp = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics")
        assert resp.status_code == 200
        rubrics = resp.json()
        assert len(rubrics) == 2
        names = {r["name"] for r in rubrics}
        assert names == {"Tone of Voice", "Response Relevance"}

    def test_update_rubric_name(self, test_client, sample_target, sample_rubric):
        """PUT name change -> 200, name updated."""
        resp = test_client.put(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
            json={"name": "Updated Tone"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Tone"

    def test_delete_rubric(self, test_client, sample_target, sample_rubric):
        """DELETE -> 204, then GET list -> gone."""
        resp = test_client.delete(
            f"/api/v1/targets/{sample_target.id}/rubrics/{sample_rubric.id}",
        )
        assert resp.status_code == 204

        list_resp = test_client.get(f"/api/v1/targets/{sample_target.id}/rubrics")
        assert list_resp.status_code == 200
        assert len(list_resp.json()) == 0

    def test_update_options_deletes_stale_scores(
        self, test_client, test_db, sample_target, sample_rubric,
        sample_answer, sample_judge_claim_based,
    ):
        """Updating rubric options purges existing scores."""
        # Insert a score via ORM
        score = RubricAnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            judge_id=sample_judge_claim_based.id,
            option_chosen="Professional",
            explanation="Good tone",
        )
        test_db.add(score)
        test_db.commit()

        # Verify score exists
        assert test_db.query(RubricAnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 1

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
        assert test_db.query(RubricAnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 0

    def test_update_name_preserves_scores(
        self, test_client, test_db, sample_target, sample_rubric,
        sample_answer, sample_judge_claim_based,
    ):
        """Changing only name does NOT purge scores."""
        score = RubricAnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_rubric.id,
            judge_id=sample_judge_claim_based.id,
            option_chosen="Professional",
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
        assert test_db.query(RubricAnswerScore).filter_by(rubric_id=sample_rubric.id).count() == 1

    def test_incomplete_when_rubric_annotations_missing(
        self, test_client, test_db, sample_target, sample_snapshot,
        sample_answer, sample_rubric,
    ):
        """Accuracy annotation done but no rubric annotation -> is_complete=False."""
        from src.common.database.models import Annotation

        # Mark answer as selected for annotation
        sample_answer.is_selected_for_annotation = True
        test_db.commit()

        # Add accuracy annotation
        ann = Annotation(answer_id=sample_answer.id, label=True, notes="ok")
        test_db.add(ann)
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
        from src.common.database.models import Annotation

        sample_answer.is_selected_for_annotation = True
        test_db.commit()

        # Accuracy annotation
        ann = Annotation(answer_id=sample_answer.id, label=True, notes="ok")
        test_db.add(ann)
        # Rubric annotation
        rubric_ann = RubricAnnotation(
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
        from src.common.database.models import Annotation

        sample_answer.is_selected_for_annotation = True
        test_db.commit()

        # Accuracy annotation
        ann = Annotation(answer_id=sample_answer.id, label=True, notes="ok")
        test_db.add(ann)
        # Only annotate first rubric, skip second
        rubric_ann = RubricAnnotation(
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


@pytest.mark.integration
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
