"""
Integration tests for Answer API endpoints.

Tests the claims display and label override features used by the ResultsTable.
"""

import math

import pytest


@pytest.mark.integration
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
            "/api/v1/answers/bulk-selection",
            json={"selections": selections}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["updated_count"] == len(selections)

        for selection in selections:
            answer = test_db.get(Answer, selection["answer_id"])
            assert answer.is_selected_for_annotation == selection["is_selected"]

    def test_toggle_answer_selection_flips_flag(self, test_client, test_db, sample_answer):
        """
        Test PUT /answers/{answer_id}/selection toggles the selection state.
        """
        from src.common.database.models import Answer

        initial_answer = test_db.get(Answer, sample_answer.id)
        assert initial_answer.is_selected_for_annotation is False

        first_toggle = test_client.put(f"/api/v1/answers/{sample_answer.id}/selection")
        assert first_toggle.status_code == 200
        assert first_toggle.json()["is_selected_for_annotation"] is True

        second_toggle = test_client.put(f"/api/v1/answers/{sample_answer.id}/selection")
        assert second_toggle.status_code == 200
        assert second_toggle.json()["is_selected_for_annotation"] is False

        refreshed_answer = test_db.get(Answer, sample_answer.id)
        assert refreshed_answer.is_selected_for_annotation is False


@pytest.mark.integration
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
            judge_id=sample_judge_claim_based.id,
            overall_label=True
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
            params={"judge_id": sample_judge_claim_based.id}
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
            params={"judge_id": sample_judge_claim_based.id}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert len(data["claims"]) == 3

        # All scores should be null since no scoring was done
        for claim in data["claims"]:
            assert claim["score"] is None


@pytest.mark.integration
class TestLabelOverrideAPI:
    """Integration tests for answer label override endpoints."""

    def test_create_label_override(self, test_client, sample_answer):
        """
        Test PUT /answers/{answer_id}/label-override creates an override.
        """
        response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-override",
            json={"edited_label": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["edited_label"] is False

    def test_update_label_override(self, test_client, sample_answer):
        """
        Test PUT /answers/{answer_id}/label-override updates existing override.
        """
        # Create initial override
        test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-override",
            json={"edited_label": False}
        )

        # Update to different value
        response = test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-override",
            json={"edited_label": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["edited_label"] is True

    def test_get_label_override(self, test_client, sample_answer):
        """
        Test GET /answers/{answer_id}/label-override returns the override.
        """
        # Create override first
        test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-override",
            json={"edited_label": True}
        )

        response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/label-override"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["answer_id"] == sample_answer.id
        assert data["edited_label"] is True

    def test_get_label_override_not_found(self, test_client, sample_answer):
        """Test GET /answers/{answer_id}/label-override returns 404 when no override exists."""
        response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/label-override"
        )

        assert response.status_code == 404

    def test_delete_label_override(self, test_client, sample_answer):
        """
        Test DELETE /answers/{answer_id}/label-override removes the override.
        """
        # Create override first
        test_client.put(
            f"/api/v1/answers/{sample_answer.id}/label-override",
            json={"edited_label": True}
        )

        # Delete it
        response = test_client.delete(
            f"/api/v1/answers/{sample_answer.id}/label-override"
        )

        assert response.status_code == 204

        # Verify it's gone
        get_response = test_client.get(
            f"/api/v1/answers/{sample_answer.id}/label-override"
        )
        assert get_response.status_code == 404
