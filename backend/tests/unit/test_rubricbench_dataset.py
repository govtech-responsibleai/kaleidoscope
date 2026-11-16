import pytest

from experiments.rubricbench_calibration.dataset import (
    ColumnMap,
    Example,
    detect_columns,
    expand_annotations,
    normalise_rows,
    resolve_gold,
)
from experiments.rubricbench_calibration.rubrics import Rubric, RubricOption

FACT = Rubric(
    key="factual_correctness", name="Factual Correctness", criteria="c",
    options=(RubricOption("correct", "a"), RubricOption("incorrect", "b")),
    best_option="correct",
)
BIAS = Rubric(
    key="bias", name="Bias", criteria="c",
    options=(RubricOption("biased", "a"), RubricOption("unbiased", "b")),
    best_option="unbiased",
)
RUBRICS = [FACT, BIAS]


class TestDetectColumns:
    def test_detects_by_rubric_key_and_annotator_suffix(self):
        names = ["id", "question", "response", "factual_correctness_a1", "factual_correctness_a2", "bias_a1", "bias_a2"]
        columns = detect_columns(names, sample_rows=[], rubrics=RUBRICS, overrides={})
        assert columns.id == "id"
        assert columns.question == "question"
        assert columns.answer == "response"
        assert columns.labels["factual_correctness"] == ["factual_correctness_a1", "factual_correctness_a2"]
        assert columns.labels["bias"] == ["bias_a1", "bias_a2"]

    def test_detects_by_label_vocabulary_when_names_do_not_match(self):
        names = ["q", "a", "dim1", "dim2"]
        rows = [
            {"q": "x", "a": "y", "dim1": "correct", "dim2": "unbiased"},
            {"q": "x", "a": "y", "dim1": "incorrect", "dim2": "biased"},
        ]
        columns = detect_columns(names, sample_rows=rows, rubrics=RUBRICS, overrides={"question": "q", "answer": "a"})
        assert columns.labels["factual_correctness"] == ["dim1"]
        assert columns.labels["bias"] == ["dim2"]

    def test_overrides_win(self):
        names = ["question", "answer", "fc_first", "fc_second"]
        columns = detect_columns(
            names, sample_rows=[], rubrics=[FACT],
            overrides={"labels.factual_correctness": ["fc_first", "fc_second"]},
        )
        assert columns.labels["factual_correctness"] == ["fc_first", "fc_second"]

    def test_raises_when_a_rubric_has_no_label_column(self):
        with pytest.raises(ValueError, match="bias"):
            detect_columns(["question", "answer", "factual_correctness"], sample_rows=[], rubrics=RUBRICS, overrides={})

    def test_key_match_requires_whole_tokens(self):
        # "bias" must not match "unbiased_flag"; with no sample rows and no vocab match, detection fails loudly
        names = ["question", "answer", "factual_correctness", "unbiased_flag"]
        with pytest.raises(ValueError, match="bias"):
            detect_columns(names, sample_rows=[], rubrics=RUBRICS, overrides={})

    def test_column_claimed_by_one_rubric_is_not_reused(self):
        # The combined column is claimed by factual_correctness first, so bias cannot silently reuse it
        names = ["question", "answer", "factual_correctness", "factual_correctness_and_bias"]
        with pytest.raises(ValueError, match="bias"):
            detect_columns(names, sample_rows=[], rubrics=RUBRICS, overrides={})


class TestResolveGold:
    def test_exclude_policy_drops_disagreements(self):
        assert resolve_gold(FACT, ["correct", "correct"], "exclude") == "correct"
        assert resolve_gold(FACT, ["correct", "incorrect"], "exclude") is None
        assert resolve_gold(FACT, ["Correct ", None], "exclude") == "correct"
        assert resolve_gold(FACT, [None, None], "exclude") is None

    def test_annotator_policies_pick_one_column(self):
        assert resolve_gold(FACT, ["correct", "incorrect"], "annotator_1") == "correct"
        assert resolve_gold(FACT, ["correct", "incorrect"], "annotator_2") == "incorrect"
        assert resolve_gold(FACT, ["correct"], "annotator_2") is None

    def test_single_adjudicated_column_is_used_directly(self):
        assert resolve_gold(FACT, ["incorrect"], "exclude") == "incorrect"

    def test_unknown_labels_are_treated_as_missing(self):
        assert resolve_gold(FACT, ["maybe", "correct"], "exclude") == "correct"

    def test_resolve_gold_rejects_unknown_policy(self):
        with pytest.raises(ValueError, match="Unknown disagreement policy 'annotator_3'"):
            resolve_gold(FACT, ["correct", "correct"], "annotator_3")


class TestNormaliseRows:
    def test_builds_examples_with_string_ids(self):
        columns = ColumnMap(id="id", question="q", answer="a", context=None,
                            labels={"factual_correctness": ["f1", "f2"], "bias": ["b"]})
        rows = [
            {"id": 7, "q": "Q1", "a": "A1", "f1": "correct", "f2": "correct", "b": "unbiased"},
            {"id": 8, "q": "Q2", "a": "A2", "f1": "correct", "f2": "incorrect", "b": "biased"},
        ]
        examples = normalise_rows(rows, RUBRICS, columns, "exclude")
        assert examples == [
            Example(example_id="7", question="Q1", answer="A1", gold={"factual_correctness": "correct", "bias": "unbiased"}),
            Example(example_id="8", question="Q2", answer="A2", gold={"factual_correctness": None, "bias": "biased"}),
        ]

    def test_falls_back_to_row_index_when_no_id_column(self):
        columns = ColumnMap(id=None, question="q", answer="a", context=None, labels={"factual_correctness": ["f"], "bias": ["b"]})
        rows = [{"q": "Q", "a": "A", "f": "correct", "b": "biased"}]
        assert normalise_rows(rows, RUBRICS, columns, "exclude")[0].example_id == "0"


class TestExpandAnnotations:
    def test_repr_dict_cell_yields_one_label_per_annotator(self):
        cell = "{'annotator1': {'label': 'correct', 'comments': 'ok'}, 'annotator2': {'label': 'incorrect', 'comments': None}}"
        assert expand_annotations(cell) == ["correct", "incorrect"]

    def test_json_dict_cell_is_accepted(self):
        cell = '{"annotator1": {"label": "biased"}, "annotator2": {"label": "unbiased"}}'
        assert expand_annotations(cell) == ["biased", "unbiased"]

    def test_missing_annotator_entry_becomes_none(self):
        assert expand_annotations("{'annotator1': {'label': 'clear'}, 'annotator2': None}") == ["clear", None]

    def test_plain_values_pass_through(self):
        assert expand_annotations("correct") == ["correct"]
        assert expand_annotations(None) == [None]
        assert expand_annotations("{not a dict") == ["{not a dict"]

    def test_rubricbench_layout_end_to_end(self):
        columns = ColumnMap(id="id", question="Question", answer="Answer", context="All_Citations",
                            labels={"factual_correctness": ["Factual Correctness"], "bias": ["Bias"]})
        rows = [
            {"id": "id-1", "Question": "Q", "Answer": "A", "All_Citations": "[1] source",
             "Factual Correctness": "{'annotator1': {'label': 'incorrect', 'comments': 'x'}, 'annotator2': {'label': 'incorrect', 'comments': None}}",
             "Bias": "{'annotator1': {'label': 'unbiased', 'comments': None}, 'annotator2': {'label': 'biased', 'comments': 'y'}}"},
        ]
        example = normalise_rows(rows, RUBRICS, columns, "exclude")[0]
        assert example.gold == {"factual_correctness": "incorrect", "bias": None}
        assert example.context == "[1] source"
        assert normalise_rows(rows, RUBRICS, columns, "annotator_2")[0].gold["bias"] == "biased"

    def test_vocabulary_fallback_sees_expanded_labels(self):
        names = ["q", "a", "dim"]
        rows = [{"q": "x", "a": "y", "dim": "{'annotator1': {'label': 'correct'}, 'annotator2': {'label': 'incorrect'}}"}]
        columns = detect_columns(names, sample_rows=rows, rubrics=[FACT], overrides={"question": "q", "answer": "a"})
        assert columns.labels["factual_correctness"] == ["dim"]
