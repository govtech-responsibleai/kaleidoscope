"""
Integration tests for Answer API endpoints.

Tests the claims display and label override features used by the ResultsTable.
"""

import math

import pytest

from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.rubric.services.system_rubrics import ensure_system_rubrics

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("with_provider_bypass")]


def _accuracy_override_path(test_db, sample_answer) -> str:
    ensure_system_rubrics(test_db, sample_answer.snapshot.target_id)
    accuracy_rubric = TargetRubricRepository.get_by_target(
        test_db,
        sample_answer.snapshot.target_id,
        group="fixed",
        name="Accuracy",
    )[0]
    return f"/api/v1/answers/{sample_answer.id}/label-overrides/{accuracy_rubric.id}"


class TestAnswerSelectionAPI:
    """Integration tests for answer selection workflows."""

    def test_select_default_answers_auto_selects_twenty_percent(
        self,
        test_client,
        test_db,
        sample_annotations,
        sample_answer
    ):
        """
        Test POST /snapshots/{snapshot_id}/answers/select-default auto-selects 20% of answers.
        """
        from src.common.database.models import Answer

        # Ensure all answers start unselected so the endpoint performs the selection work
        answers = test_db.query(Answer).filter(Answer.snapshot_id == sample_answer.snapshot_id).all()
        for answer in answers:
            answer.is_selected_for_annotation = False
        test_db.commit()

        response = test_client.post(
            f"/api/v1/snapshots/{sample_answer.snapshot_id}/answers/select-default"
        )

        assert response.status_code == 200
        data = response.json()

        expected_selected = max(1, math.ceil(len(answers) * 0.2))
        assert data["snapshot_id"] == sample_answer.snapshot_id
        assert data["selected_count"] == expected_selected
        assert data["total_answers"] == len(answers)

        selected_count = test_db.query(Answer).filter(
            Answer.snapshot_id == sample_answer.snapshot_id,
            Answer.is_selected_for_annotation == True
        ).count()
        assert selected_count == expected_selected

    def test_bulk_selection_updates_individual_answers(
        self,
        test_client,
        test_db,
        sample_annotations
    ):
        """
        Test POST /answers/bulk-selection updates mixed selections in a single call.
        """
        from src.common.database.models import Answer

        selections = [
            {"answer_id": sample_annotations[0].answer_id, "is_selected": False},
            {"answer_id": sample_annotations[1].answer_id, "is_selected": True},
            {"answer_id": sample_annotations[2].answer_id, "is_selected": False},
            {"answer_id": sample_annotations[3].answer_id, "is_selected": True},
        ]

        response = test_client.post(
            f"/api/v1/snapshots/{sample_annotations[0].answer.snapshot_id}/answers/bulk-selection",
            json={"selections": selections}
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == len(selections)
        returned_ids = {item["id"] for item in data}
        assert returned_ids == {selection["answer_id"] for selection in selections}

        test_db.expire_all()
        for selection in selections:
            answer = test_db.get(Answer, selection["answer_id"])
            assert answer.is_selected_for_annotation == selection["is_selected"]



class TestAnswerClaimsAPI:
    """Integration tests for answer claims endpoints."""

    def test_get_claims_with_scores(
        self, test_client, sample_answer, sample_claims, sample_judge_claim_based, test_db
    ):
        """
        Test GET /answers/{answer_id}/claims returns claims with judge scores.

        Tests:
        1. Returns claims for the answer
        2. Each claim has id, claim_text, claim_index, checkworthy
        3. Claims have score info when scored by judge
        """
        from src.common.database.models import AnswerScore, AnswerClaimScore

        # Create answer score and claim scores for the judge
        answer_score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Accurate"
        )
        test_db.add(answer_score)
        test_db.commit()
        test_db.refresh(answer_score)

        # Create claim scores
        for i, claim in enumerate(sample_claims):
            claim_score = AnswerClaimScore(
                answer_score_id=answer_score.id,
                claim_id=claim.id,
                label=True if i < 2 else False,
                explanation=f"Explanation for claim {i}"
            )
            test_db.add(claim_score)
        test_db.commit()

        response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/claims",
            params={
                "judge_id": sample_judge_claim_based.id,
                "rubric_id": sample_judge_claim_based.rubric_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert len(data["claims"]) == 3

        for claim in data["claims"]:
            assert "id" in claim
            assert "claim_text" in claim
            assert "claim_index" in claim
            assert "checkworthy" in claim
            assert "score" in claim
            if claim["score"]:
                assert "label" in claim["score"]
                assert "explanation" in claim["score"]

    def test_get_claims_without_scores(
        self, test_client, sample_answer, sample_claims, sample_judge_claim_based
    ):
        """
        Test GET /answers/{answer_id}/claims returns claims with null scores when not scored.
        """
        response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/claims",
            params={
                "judge_id": sample_judge_claim_based.id,
                "rubric_id": sample_judge_claim_based.rubric_id,
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert len(data["claims"]) == 3

        # All scores should be null since no scoring was done
        for claim in data["claims"]:
            assert claim["score"] is None


class TestLabelOverrideAPI:
    """Integration tests for answer label override endpoints."""

    def test_create_label_override(self, test_client, test_db, sample_answer):
        """
        Test PUT /answers/{answer_id}/label-overrides/accuracy creates an override.
        """
        response = test_client.put(_accuracy_override_path(test_db, sample_answer), json={"edited_value": "inaccurate"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert isinstance(data["rubric_id"], int)
        assert data["edited_value"] == "Inaccurate"

    def test_update_label_override(self, test_client, test_db, sample_answer):
        """
        Test PUT /answers/{answer_id}/label-overrides/accuracy updates existing override.
        """
        # Create initial override
        path = _accuracy_override_path(test_db, sample_answer)
        test_client.put(path, json={"edited_value": "inaccurate"})

        # Update to different value
        response = test_client.put(path, json={"edited_value": "accurate"})

        assert response.status_code == 200
        data = response.json()
        assert data["edited_value"] == "Accurate"

    def test_get_label_override(self, test_client, test_db, sample_answer):
        """
        Test GET /answers/{answer_id}/label-overrides/accuracy returns the override.
        """
        # Create override first
        path = _accuracy_override_path(test_db, sample_answer)
        test_client.put(path, json={"edited_value": "accurate"})

        response = test_client.get(path)

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["edited_value"] == "Accurate"

    def test_get_label_override_not_found(self, test_client, test_db, sample_answer):
        """Test GET /answers/{answer_id}/label-overrides/accuracy returns 404 when no override exists."""
        response = test_client.get(_accuracy_override_path(test_db, sample_answer))

        assert response.status_code == 404

    def test_delete_label_override(self, test_client, test_db, sample_answer):
        """
        Test DELETE /answers/{answer_id}/label-overrides/accuracy removes the override.
        """
        # Create override first
        path = _accuracy_override_path(test_db, sample_answer)
        test_client.put(path, json={"edited_value": "accurate"})

        # Delete it
        response = test_client.delete(path)

        assert response.status_code == 204

        # Verify it's gone
        get_response = test_client.get(path)
        assert get_response.status_code == 404

    def test_create_label_override_rejects_unknown_rubric(self, test_client, sample_answer):
        """Test PUT /answers/{answer_id}/label-overrides/{rubric_id} returns 404 for missing rubric."""
        response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-overrides/999999",
            json={"edited_value": "Accurate"},
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Rubric 999999 not found"

    def test_create_label_override_rejects_invalid_rubric_option(
        self,
        test_client,
        sample_answer,
        sample_rubric,
    ):
        """Test PUT /answers/{answer_id}/label-overrides/{rubric_id} returns 400 for invalid option."""
        response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-overrides/{sample_rubric.id}",
            json={"edited_value": "Unsupported label"},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == (
            f"edited_value must match one of the rubric options for rubric {sample_rubric.id}"
        )


class TestLabelOverrideReliability:
    """Tests that label overrides affect judge reliability via alignment calculation."""

    def test_override_does_not_modify_annotation(self, test_client, test_db, sample_answer):
        """Label override should not create or modify annotations."""
        from src.common.database.models import Annotation

        test_client.put(_accuracy_override_path(test_db, sample_answer), json={"edited_value": "inaccurate"})

        annotation = test_db.query(Annotation).filter(
            Annotation.answer_id == sample_answer.id
        ).first()
        assert annotation is None

    def test_delete_override_preserves_annotation(self, test_client, test_db, sample_answer):
        """Deleting a label override should not touch the original annotation."""
        from src.common.database.models import Annotation

        # Create rubric-backed annotation directly (as if from Annotations tab)
        accuracy_rubric_id = int(_accuracy_override_path(test_db, sample_answer).rsplit("/", 1)[-1])
        annotation = Annotation(
            answer_id=sample_answer.id,
            rubric_id=accuracy_rubric_id,
            option_value="Inaccurate",
            notes="Original notes",
        )
        test_db.add(annotation)
        test_db.commit()

        # Create and delete override
        path = _accuracy_override_path(test_db, sample_answer)
        test_client.put(path, json={"edited_value": "accurate"})
        test_client.delete(path)

        # Annotation should still exist with original values
        test_db.refresh(annotation)
        assert annotation.option_value == "Inaccurate"
        assert annotation.notes == "Original notes"

    def test_override_takes_precedence_in_alignment(
        self, test_client, test_db, sample_answer, sample_judge_claim_based
    ):
        """
        Override should take precedence over rubric-native annotation in judge alignment.
        Rubric annotation says Inaccurate, override says Accurate, judge says Accurate
        → alignment should use override (match).
        """
        from src.common.database.models import AnswerScore, Annotation

        sample_answer.is_selected_for_annotation = True
        test_db.commit()

        # Rubric annotation: Inaccurate
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=sample_judge_claim_based.rubric_id,
                option_value="Inaccurate",
            )
        )

        # Judge: Accurate
        score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Accurate",
            explanation="Judge thinks accurate"
        )
        test_db.add(score)
        test_db.commit()

        # Without override: judge (True) vs annotation (False) = mismatch
        response = test_client.get(
            f"/api/v1/snapshots/{sample_answer.snapshot_id}/judges/{sample_judge_claim_based.id}/rubrics/{sample_judge_claim_based.rubric_id}/alignment"
        )
        assert response.status_code == 200
        assert response.json()["accuracy"] == 0.0

        # Override to Accurate (True) — now matches judge
        test_client.put(_accuracy_override_path(test_db, sample_answer), json={"edited_value": "accurate"})

        response = test_client.get(
            f"/api/v1/snapshots/{sample_answer.snapshot_id}/judges/{sample_judge_claim_based.id}/rubrics/{sample_judge_claim_based.rubric_id}/alignment"
        )
        assert response.status_code == 200
        assert response.json()["accuracy"] == 1.0

    def test_override_on_unselected_answer_no_reliability_impact(
        self, test_client, test_db, sample_answer, sample_judge_claim_based
    ):
        """
        Override on unselected answer should not affect reliability
        (no annotation exists for alignment, and answer is not selected).
        """
        from src.common.database.models import AnswerScore

        sample_answer.is_selected_for_annotation = False
        test_db.commit()

        score = AnswerScore(
            answer_id=sample_answer.id,
            rubric_id=sample_judge_claim_based.rubric_id,
            judge_id=sample_judge_claim_based.id,
            overall_label="Accurate",
            explanation="Judge thinks accurate"
        )
        test_db.add(score)
        test_db.commit()

        test_client.put(_accuracy_override_path(test_db, sample_answer), json={"edited_value": "inaccurate"})

        # No selected annotations exist → 400
        response = test_client.get(
            f"/api/v1/snapshots/{sample_answer.snapshot_id}/judges/{sample_judge_claim_based.id}/rubrics/{sample_judge_claim_based.rubric_id}/alignment"
        )
        assert response.status_code == 400


class TestLegacyAnnotationStorage:
    """Regression coverage for the rubric-native annotation bridge behind legacy endpoints."""

    def test_create_annotation_persists_rubric_native_row(self, test_client, test_db, sample_answer):
        """POST /annotations should write the requested rubric annotation row."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])

        response = test_client.post(
            "/api/v1/annotations",
            json={
                "answer_id": sample_answer.id,
                "rubric_id": accuracy_rubric_id,
                "option_value": "Accurate",
                "notes": "Reviewed",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["rubric_id"] == accuracy_rubric_id
        assert data["option_value"] == "Accurate"

        rubric_annotations = test_db.query(Annotation).filter(Annotation.answer_id == sample_answer.id).all()
        assert len(rubric_annotations) == 1
        assert rubric_annotations[0].option_value == "Accurate"

    def test_answer_annotations_list_returns_all_rubric_backed_rows(self, test_client, test_db, sample_answer, sample_rubric):
        """Canonical answer annotation list should return all rubric-backed rows for the answer."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric_id,
                option_value="Inaccurate",
                notes="Human review",
            )
        )
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=sample_rubric.id,
                option_value="Professional",
                notes="Tone review",
            )
        )
        test_db.commit()

        response = test_client.get(f"/api/v1/answers/{sample_answer.id}/annotations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert {annotation["rubric_id"] for annotation in data} == {accuracy_rubric_id, sample_rubric.id}

    def test_get_annotation_for_answer_reads_exact_rubric_row(self, test_client, test_db, sample_answer):
        """Canonical answer annotation read should require both answer_id and rubric_id."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric_id,
                option_value="Inaccurate",
                notes="Human review",
            )
        )
        test_db.commit()

        response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/annotations/{accuracy_rubric_id}"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["rubric_id"] == accuracy_rubric_id
        assert data["option_value"] == "Inaccurate"
        assert data["notes"] == "Human review"

    def test_rubric_annotations_route_family_is_removed(self, test_client, test_db, sample_answer):
        """Legacy rubric-annotation routes should no longer be registered."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric_id,
                option_value="Inaccurate",
            )
        )
        test_db.commit()

        list_response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/rubric-annotations"
        )
        read_response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/rubric-annotations/{accuracy_rubric_id}"
        )
        write_response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/rubric-annotations/{accuracy_rubric_id}",
            json={"option_value": "Accurate"},
        )

        assert list_response.status_code == 404
        assert read_response.status_code == 404
        assert write_response.status_code == 404

    def test_annotation_update_modifies_rubric_native_row(self, test_client, test_db, sample_answer):
        """PUT /annotations/{id} should update the scoped rubric annotation row."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric_id,
                option_value="Inaccurate",
                notes="Initial notes",
            )
        )
        test_db.commit()

        annotation_id = test_db.query(Annotation.id).filter(
            Annotation.answer_id == sample_answer.id,
            Annotation.rubric_id == accuracy_rubric_id,
        ).scalar()

        response = test_client.put(
            f"/api/v1/annotations/{annotation_id}",
            json={
                "rubric_id": accuracy_rubric_id,
                "option_value": "Accurate",
                "notes": "Updated notes",
            },
        )

        assert response.status_code == 200
        updated = test_db.query(Annotation).filter(Annotation.id == annotation_id).one()
        assert updated.option_value == "Accurate"
        assert updated.notes == "Updated notes"

    def test_annotation_delete_removes_rubric_native_row(self, test_client, test_db, sample_answer):
        """DELETE /annotations/{id} should delete the scoped rubric annotation row."""
        from src.common.database.models import Annotation

        path = _accuracy_override_path(test_db, sample_answer)
        accuracy_rubric_id = int(path.rsplit("/", 1)[-1])
        test_db.add(
            Annotation(
                answer_id=sample_answer.id,
                rubric_id=accuracy_rubric_id,
                option_value="Accurate",
                notes="To be deleted",
            )
        )
        test_db.commit()

        annotation_id = test_db.query(Annotation.id).filter(
            Annotation.answer_id == sample_answer.id,
            Annotation.rubric_id == accuracy_rubric_id,
        ).scalar()

        response = test_client.delete(
            f"/api/v1/annotations/{annotation_id}",
            params={"rubric_id": accuracy_rubric_id},
        )

        assert response.status_code == 204
        remaining = test_db.query(Annotation).filter(Annotation.id == annotation_id).count()
        assert remaining == 0

    def test_canonical_upsert_annotation_route_writes_rubric_row(self, test_client, test_db, sample_answer, sample_rubric):
        """Canonical answer annotation upsert should use /answers/{answer_id}/annotations/{rubric_id}."""
        response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/annotations/{sample_rubric.id}",
            json={"option_value": "Professional", "notes": "Reviewed"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["rubric_id"] == sample_rubric.id
        assert data["option_value"] == "Professional"
        assert data["notes"] == "Reviewed"
