from pathlib import Path

import pytest

from experiments.rubricbench_calibration.config import EXPERIMENT_DIR, StudyConfig
from experiments.rubricbench_calibration.rubrics import Rubric, RubricOption, load_rubrics


class TestRubricDefinitions:
    def test_loads_fourteen_binary_rubrics(self):
        rubrics = load_rubrics()
        assert len(rubrics) == 14
        assert len({r.key for r in rubrics}) == 14
        for rubric in rubrics:
            assert len(rubric.options) == 2
            assert rubric.best_option in rubric.option_values
            assert rubric.criteria.strip()

    def test_expected_keys_and_best_options(self):
        by_key = {r.key: r for r in load_rubrics()}
        assert by_key["factual_correctness"].best_option == "correct"
        assert by_key["bias"].best_option == "unbiased"
        assert by_key["verbosity"].best_option == "concise"
        assert by_key["structure"].option_values == ("well-structured", "poorly-structured")

    def test_canonicalize_matches_case_and_whitespace(self):
        rubric = Rubric(
            key="k", name="K", criteria="c",
            options=(RubricOption("not recalled", "a"), RubricOption("recalled", "b")),
            best_option="recalled",
        )
        assert rubric.canonicalize("  Recalled ") == "recalled"
        assert rubric.canonicalize("NOT RECALLED") == "not recalled"
        assert rubric.canonicalize("maybe") is None
        assert rubric.canonicalize(None) is None

    def test_options_as_dicts_matches_prompt_template_shape(self):
        rubric = load_rubrics()[0]
        first = rubric.options_as_dicts()[0]
        assert set(first) == {"option", "description"}

    def test_load_rubrics_rejects_best_option_not_in_options(self, tmp_path: Path):
        bad = tmp_path / "rubrics.yaml"
        bad.write_text(
            "rubrics:\n"
            "  - key: k\n"
            "    name: K\n"
            "    criteria: c\n"
            "    best_option: missing\n"
            "    options:\n"
            "      - option: a\n"
            "        description: A\n"
            "      - option: b\n"
            "        description: B\n",
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="best_option 'missing'"):
            load_rubrics(bad)


class TestStudyConfig:
    def test_defaults_match_spec(self):
        config = StudyConfig()
        assert config.judges == (
            "govtech/gpt-5.6-luna",
            "govtech/bedrock.claude-haiku-4-5",
            "govtech/gemini-3.5-flash-lite",
        )
        assert config.calibration_sizes == (10, 20, 30, 40, 50)
        assert config.thresholds == (0.3, 0.4, 0.5, 0.6, 0.7)
        assert config.repeats == 200
        assert config.sampling == "per_rubric"
        assert config.disagreement_policy == "exclude"
        assert config.temperature == 0.0
        assert config.predictions_path == EXPERIMENT_DIR / "outputs" / "predictions.jsonl"
