from src.common.database.models import Judge, Target
from src.common.database.repositories.target_rubric_repo import TargetRubricRepository
from src.rubric.services.system_rubrics import ensure_judges, ensure_system_rubrics


class TestSystemRubricProviderSeeding:
    def test_fixed_rubric_prefers_recommended_provider_then_falls_back(self, test_db, test_user, provider_settings):
        target = Target(name="Target", user_id=test_user.id)
        test_db.add(target)
        test_db.commit()
        test_db.refresh(target)

        with provider_settings(
            openai_api_key="shared-openai-key",
            gemini_api_key="shared-gemini-key",
        ):
            ensure_system_rubrics(test_db, target.id)
            accuracy_rubric = TargetRubricRepository.get_by_target(
                test_db,
                target.id,
                group="fixed",
                name="Accuracy",
            )[0]

            ensure_judges(test_db, accuracy_rubric.id)
            judges = (
                test_db.query(Judge)
                .filter(Judge.rubric_id == accuracy_rubric.id)
                .order_by(Judge.name.asc())
                .all()
            )

        assert len(judges) == 2
        assert judges[0].name == "Judge 1 (Recommended)"
        assert judges[0].model_name == "gemini/gemini-3.1-flash-lite-preview"
        assert judges[1].model_name == "openai/gpt-5.4-nano"
