import pytest
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.common.database.models import Judge, TargetRubric
from src.rubric.services.premade_rubrics import get_premade_template
from src.rubric.services.system_rubrics import (
    ensure_system_rubrics,
    ensure_system_judges,
)
from src.rubric.services.prompt_files import load_prompt_template_text


@pytest.mark.unit
def test_ensure_system_rubrics_bootstraps_only_requested_target(test_db, sample_target, other_target):
    accuracy_name = get_premade_template("accuracy")["name"]
    ensure_system_rubrics(test_db, sample_target.id)
    test_db.expire_all()

    sample_target_rubrics = test_db.query(TargetRubric).filter_by(target_id=sample_target.id).all()
    other_target_rubrics = test_db.query(TargetRubric).filter_by(target_id=other_target.id).all()

    assert len(sample_target_rubrics) == 1
    assert sample_target_rubrics[0].name == accuracy_name
    assert sample_target_rubrics[0].group == "preset"
    assert other_target_rubrics == []


@pytest.mark.unit
def test_ensure_system_rubrics_is_idempotent_for_existing_accuracy(test_db, sample_target):
    accuracy_name = get_premade_template("accuracy")["name"]
    ensure_system_rubrics(test_db, sample_target.id)
    ensure_system_rubrics(test_db, sample_target.id)

    rubrics = test_db.query(TargetRubric).filter_by(target_id=sample_target.id).all()

    assert len(rubrics) == 1
    assert rubrics[0].name == accuracy_name


@pytest.mark.unit
def test_ensure_system_rubrics_loads_accuracy_prompt_from_template_file(test_db, sample_target):
    """Accuracy rubric should persist the canonical template file content."""
    ensure_system_rubrics(test_db, sample_target.id)

    rubric = TargetRubricRepository.get_by_target(
        test_db,
        sample_target.id,
        group="preset",
        name=get_premade_template("accuracy")["name"],
    )[0]

    assert rubric.judge_prompt == load_prompt_template_text("accuracy_judge.md")


@pytest.mark.unit
def test_ensure_system_judges_scopes_to_target_system_rubrics(
    test_db,
    sample_target,
    other_target,
    test_user,
    provider_settings,
):
    # Give both targets a user so _select_seed_models can resolve providers
    sample_target.user_id = test_user.id
    other_target.user_id = test_user.id
    test_db.commit()

    accuracy_name = get_premade_template("accuracy")["name"]
    with provider_settings(
        gemini_api_key="test-gemini-key",
    ):
        ensure_system_rubrics(test_db, sample_target.id)
        ensure_system_rubrics(test_db, other_target.id)
        sample_accuracy = TargetRubricRepository.get_by_target(
            test_db, sample_target.id, group="preset", name=accuracy_name
        )[0]
        other_accuracy = TargetRubricRepository.get_by_target(
            test_db, other_target.id, group="preset", name=accuracy_name
        )[0]

        sample_empathy = TargetRubric(
            target_id=sample_target.id,
            name="Empathy",
            criteria="Evaluate empathy",
            options=[
                {"option": "Empathetic", "description": "Shows empathy"},
                {"option": "Not Empathetic", "description": "Lacks empathy"},
            ],
            best_option="Empathetic",
            group="preset",
            scoring_mode="response_level",
            position=1,
        )
        other_custom = TargetRubric(
            target_id=other_target.id,
            name="Tone",
            criteria="Evaluate tone",
            options=[
                {"option": "Professional", "description": "Formal"},
                {"option": "Casual", "description": "Informal"},
            ],
            best_option="Professional",
            group="custom",
            scoring_mode="response_level",
            position=1,
        )
        test_db.add_all([sample_empathy, other_custom])
        test_db.commit()
        test_db.refresh(sample_empathy)
        test_db.refresh(other_custom)

        ensure_system_judges(test_db, sample_target.id)
        test_db.expire_all()

    sample_accuracy_judges = test_db.query(Judge).filter_by(rubric_id=sample_accuracy.id).all()
    sample_empathy_judges = test_db.query(Judge).filter_by(rubric_id=sample_empathy.id).all()
    other_accuracy_judges = test_db.query(Judge).filter_by(rubric_id=other_accuracy.id).all()
    other_custom_judges = test_db.query(Judge).filter_by(rubric_id=other_custom.id).all()

    assert len(sample_accuracy_judges) == 1
    assert len(sample_empathy_judges) == 1
    assert all(judge.target_id == sample_target.id for judge in sample_accuracy_judges + sample_empathy_judges)
    assert other_accuracy_judges == []
    assert other_custom_judges == []
