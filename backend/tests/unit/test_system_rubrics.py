import pytest

from src.common.database.models import AnswerLabelOverride, AnswerScore, Annotation, Snapshot, TargetRubric, Answer
from src.common.services.system_rubrics import ensure_system_rubrics


@pytest.mark.unit
def test_ensure_system_rubrics_canonicalizes_fixed_accuracy_storage(test_db, sample_target, sample_question):
    legacy_accuracy = TargetRubric(
        target_id=sample_target.id,
        name="Accuracy",
        criteria="Legacy accuracy rubric",
        options=[{"option": "accurate"}, {"option": "inaccurate"}],
        best_option="accurate",
        group="fixed",
        scoring_mode="claim_based",
        position=0,
    )
    snapshot = Snapshot(target_id=sample_target.id, name="legacy snapshot", description="legacy")
    test_db.add_all([legacy_accuracy, snapshot])
    test_db.commit()
    test_db.refresh(legacy_accuracy)
    test_db.refresh(snapshot)

    answer = Answer(
        question_id=sample_question.id,
        snapshot_id=snapshot.id,
        answer_content="Legacy answer",
        chat_id="legacy-chat",
        message_id="legacy-message",
        is_selected_for_annotation=True,
    )
    test_db.add(answer)
    test_db.commit()
    test_db.refresh(answer)

    test_db.add_all(
        [
            AnswerScore(
                answer_id=answer.id,
                rubric_id=legacy_accuracy.id,
                judge_id=123,
                overall_label="accurate",
                explanation="legacy score",
            ),
            Annotation(
                answer_id=answer.id,
                rubric_id=legacy_accuracy.id,
                option_value="inaccurate",
                notes="legacy annotation",
            ),
            AnswerLabelOverride(
                answer_id=answer.id,
                rubric_id=legacy_accuracy.id,
                edited_value="accurate",
            ),
        ]
    )
    test_db.commit()

    ensure_system_rubrics(test_db)
    test_db.expire_all()

    rubric = test_db.get(TargetRubric, legacy_accuracy.id)
    score = test_db.query(AnswerScore).filter(AnswerScore.rubric_id == legacy_accuracy.id).one()
    annotation = test_db.query(Annotation).filter(Annotation.rubric_id == legacy_accuracy.id).one()
    override = test_db.query(AnswerLabelOverride).filter(AnswerLabelOverride.rubric_id == legacy_accuracy.id).one()

    assert rubric.best_option == "Accurate"
    assert rubric.options == [
        {"option": "Accurate", "description": "All claims are supported by the provided context."},
        {"option": "Inaccurate", "description": "One or more claims are unsupported or hallucinated."},
    ]
    assert score.overall_label == "Accurate"
    assert annotation.option_value == "Inaccurate"
    assert override.edited_value == "Accurate"
