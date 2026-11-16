import math
import random

import pandas as pd
import pytest

from experiments.rubricbench_calibration.analysis import (
    aggregate_votes,
    full_reliability,
    reliability,
    run_study,
    stratified_split,
    summarise,
    summarise_by_rubric,
)
from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.predict import PredictionRecord
from experiments.rubricbench_calibration.rubrics import Rubric, RubricOption

R1 = Rubric("r1", "R1", "c", (RubricOption("good", ""), RubricOption("bad", "")), "good")
R2 = Rubric("r2", "R2", "c", (RubricOption("yes", ""), RubricOption("no", "")), "yes")
RUBRICS = [R1, R2]
PERFECT, RANDOM, INVERTED = "govtech/perfect", "govtech/random", "govtech/inverted"


def _examples(n: int = 60) -> list[Example]:
    rng = random.Random(0)
    out = []
    for i in range(n):
        out.append(Example(str(i), f"q{i}", f"a{i}", {
            "r1": "good" if i % 3 else "bad",
            "r2": rng.choice(["yes", "no"]),
        }))
    return out


def _predictions(examples: list[Example]) -> dict:
    rng = random.Random(1)
    preds = {}

    def add(judge, rubric, example, label):
        rec = PredictionRecord(judge, rubric.key, example.example_id, label, label, "", 1, 1, 0.0, "m", None)
        preds[rec.key] = rec

    for ex in examples:
        for rubric in RUBRICS:
            gold = ex.gold[rubric.key]
            other = [o for o in rubric.option_values if o != gold][0]
            add(PERFECT, rubric, ex, gold)
            add(INVERTED, rubric, ex, other)
            add(RANDOM, rubric, ex, rng.choice(rubric.option_values))
    return preds


class TestPrimitives:
    def test_reliability_is_macro_f1_on_best_option_and_drops_missing(self):
        assert reliability(["good", "bad", "good", "bad"], ["good", "bad", "good", "bad"], "good") == 1.0
        assert reliability(["good", "bad"], ["bad", "good"], "good") == 0.0
        assert reliability(["good", "bad", "good"], ["good", "bad", None], "good") == 1.0
        assert reliability(["good"], [None], "good") == 0.0

    def test_reliability_ties_wrong_scores_tie_as_wrong(self):
        from experiments.rubricbench_calibration.analysis import TIE, reliability_ties_wrong
        # gold good/bad, judge votes: correct, tie → tie counted as wrong on the 'bad' row.
        # Binarised truth [T, F] vs pred [T, T]: positive-class F1 = 2/3, negative-class
        # F1 = 0 (nothing predicted negative), so macro-F1 = 1/3.
        assert reliability_ties_wrong(["good", "bad"], ["good", TIE], "good") == pytest.approx(1 / 3)
        assert reliability_ties_wrong(["good", "bad"], ["good", "bad"], "good") == 1.0

    def test_aggregate_votes_semantics(self):
        assert aggregate_votes([]) == ("no_aligned_judge", None)
        assert aggregate_votes(["good", None]) == ("pending", None)
        assert aggregate_votes(["good", "bad"]) == ("majority_tied", None)
        assert aggregate_votes(["good", "bad", "good"]) == ("majority", "good")
        assert aggregate_votes(["bad"]) == ("majority", "bad")

    def test_stratified_split_sizes_and_disjointness(self):
        ids = [str(i) for i in range(30)]
        labels = ["a" if i % 2 else "b" for i in range(30)]
        calib, evaluation, stratified = stratified_split(ids, labels, 10, random_state=0)
        assert len(calib) == 10 and len(evaluation) == 20
        assert not set(calib) & set(evaluation)
        assert stratified is True
        assert sorted(l for i, l in zip(ids, labels) if i in calib).count("a") == 5

    def test_stratified_split_falls_back_when_a_class_is_too_small(self):
        ids = [str(i) for i in range(12)]
        labels = ["a"] * 11 + ["b"]
        calib, evaluation, stratified = stratified_split(ids, labels, 4, random_state=0)
        assert len(calib) == 4 and len(evaluation) == 8
        assert stratified is False

    def test_stratified_split_is_deterministic(self):
        ids = [str(i) for i in range(30)]
        labels = ["a" if i % 2 else "b" for i in range(30)]
        assert stratified_split(ids, labels, 10, 7)[0] == stratified_split(ids, labels, 10, 7)[0]

    def test_split_without_stratification_can_produce_one_class_sample(self):
        ids = [str(i) for i in range(40)]
        labels = ["a"] * 38 + ["b"] * 2
        seen_one_class = False
        for seed in range(200):
            calib, _, stratified = stratified_split(ids, labels, 5, seed, stratify=False)
            assert stratified is False and len(calib) == 5
            if all(labels[int(i)] == "a" for i in calib):
                seen_one_class = True
        assert seen_one_class


class TestRunStudy:
    @pytest.fixture
    def grid(self):
        examples = _examples()
        config = StudyConfig(
            judges=(PERFECT, RANDOM, INVERTED),
            calibration_sizes=(10, 20),
            thresholds=(0.3, 0.5, 0.7),
            repeats=5,
            seed=3,
        )
        return run_study(examples, RUBRICS, _predictions(examples), config)

    def test_grid_shape_and_columns(self, grid):
        assert len(grid) == 5 * 2 * 3 * 2
        assert {"repeat", "k", "threshold", "rubric", "n_calibration", "n_eval", "n_judges_retained",
                "has_sufficient_judges", "multi_judge_f1", "tie_rate", "no_judge_rate", "stratified",
                "retained_judges", "n_calib_positive", "n_calib_negative"} <= set(grid.columns)

    def test_calib_positive_negative_counts_sum_to_n_calibration(self, grid):
        assert (grid["n_calib_positive"] + grid["n_calib_negative"] == grid["n_calibration"]).all()

    def test_perfect_judge_always_retained_and_inverted_never_at_high_threshold(self, grid):
        assert grid["retained_judges"].str.contains("perfect").all()
        high = grid[grid["threshold"] >= 0.5]
        assert not high["retained_judges"].str.contains("inverted").any()

    def test_f1_is_one_when_only_perfect_judge_survives(self, grid):
        solo = grid[grid["retained_judges"] == PERFECT]
        assert len(solo) > 0
        assert (solo["multi_judge_f1"] == 1.0).all()
        assert (solo["tie_rate"] == 0.0).all()

    def test_ties_appear_when_two_disagreeing_judges_survive(self, grid):
        pair = grid[grid["n_judges_retained"] == 2]
        assert len(pair) > 0
        assert (pair["tie_rate"] > 0).any()
        both = grid[grid["retained_judges"] == f"{PERFECT}|{RANDOM}"]
        assert len(both) > 0
        # All non-tied rows resolve to gold (PERFECT is always right, and a
        # majority of 2 only forms when RANDOM agrees with it), so an
        # implementation that folded tied rows into the F1 computation would
        # fail this.
        assert (both["multi_judge_f1"] == 1.0).all()
        assert 0.25 < both["tie_rate"].mean() < 0.75

    def test_reproducible_under_same_seed(self):
        examples = _examples()
        config = StudyConfig(judges=(PERFECT, RANDOM), calibration_sizes=(10,), thresholds=(0.5,), repeats=3, seed=9)
        a = run_study(examples, RUBRICS, _predictions(examples), config)
        b = run_study(examples, RUBRICS, _predictions(examples), config)
        pd.testing.assert_frame_equal(a, b)

    def test_shared_sampling_uses_same_ids_across_rubrics(self):
        # r2 has no gold label for ids "0".."9", so the fully-labelled
        # intersection the shared draw must come from is ids "10".."59".
        rng = random.Random(0)
        examples = []
        for i in range(60):
            r2_label = None if i < 10 else rng.choice(["yes", "no"])
            examples.append(Example(str(i), f"q{i}", f"a{i}", {"r1": "good" if i % 3 else "bad", "r2": r2_label}))
        config = StudyConfig(judges=(PERFECT,), calibration_sizes=(10,), thresholds=(0.5,), repeats=2, seed=1, sampling="shared")
        grid = run_study(examples, RUBRICS, _predictions(examples), config)
        for (_, _), rows in grid.groupby(["repeat", "k"]):
            assert rows["calibration_ids"].nunique() == 1
            calib_ids = rows["calibration_ids"].iloc[0].split(",")
            assert all(int(i) >= 10 for i in calib_ids)
        assert (grid["n_calibration"] == 10).all()
        r1 = grid[grid["rubric"] == "r1"]
        r2 = grid[grid["rubric"] == "r2"]
        assert (r1["n_eval"] == 50).all()
        assert (r2["n_eval"] == 40).all()

    def test_missing_predictions_count_as_no_judge(self):
        examples = _examples()
        preds = _predictions(examples)
        for ex in examples[:6]:
            del preds[(PERFECT, "r1", ex.example_id)]
        config = StudyConfig(judges=(PERFECT,), calibration_sizes=(10,), thresholds=(0.5,), repeats=3)
        grid = run_study(examples, RUBRICS, preds, config)
        r1 = grid[grid["rubric"] == "r1"]
        r2 = grid[grid["rubric"] == "r2"]
        assert (r1["no_judge_rate"] > 0).all()
        assert (r1["n_judges_retained"] == 1).all()
        assert (r2["no_judge_rate"] == 0.0).all()

    def test_skips_rubric_when_k_exceeds_labelled_examples(self):
        examples = _examples(12)
        config = StudyConfig(judges=(PERFECT,), calibration_sizes=(20,), thresholds=(0.5,), repeats=1)
        grid = run_study(examples, RUBRICS, _predictions(examples), config)
        assert grid["multi_judge_f1"].isna().all()

    def test_ties_wrong_column_is_at_most_conditional_f1(self, grid):
        rows = grid[grid["multi_judge_f1"].notna()]
        assert "multi_judge_f1_ties_wrong" in grid.columns
        assert (rows["multi_judge_f1_ties_wrong"] <= rows["multi_judge_f1"] + 1e-9).all()

    def test_ties_wrong_equals_conditional_when_no_ties(self, grid):
        rows = grid[(grid["tie_rate"] == 0) & grid["multi_judge_f1"].notna()]
        assert not rows.empty
        assert (rows["multi_judge_f1_ties_wrong"] == rows["multi_judge_f1"]).all()

    def test_summary_has_ties_wrong_column(self, grid):
        assert "mean_f1_ties_wrong" in summarise(grid).columns

    def test_unstratified_mode_reports_one_class_rate(self):
        examples = _examples()
        predictions = _predictions(examples)
        config = StudyConfig(judges=(PERFECT, RANDOM, INVERTED), calibration_sizes=(5,), thresholds=(0.5,),
                             repeats=30, sampling="unstratified")
        grid = run_study(examples, RUBRICS, predictions, config)
        assert (grid["stratified"] == False).all()  # noqa: E712
        by_rubric = summarise_by_rubric(grid)
        assert by_rubric["one_class_rate"].max() > 0
        summary_rate = summarise(grid)["one_class_rate"]
        assert 0.0 <= summary_rate.min() <= summary_rate.max() <= 1.0


class TestSummaries:
    def test_summarise_columns_and_ci(self):
        examples = _examples()
        config = StudyConfig(judges=(PERFECT, RANDOM, INVERTED), calibration_sizes=(10,), thresholds=(0.5,), repeats=4)
        grid = run_study(examples, RUBRICS, _predictions(examples), config)
        summary = summarise(grid)
        row = summary.loc[(10, 0.5)]
        for col in ("mean_f1", "sd_f1", "ci95_f1", "mean_f1_penalised", "avg_judges_retained",
                    "rubric_coverage", "tie_rate", "no_judge_rate", "n_repeats"):
            assert col in summary.columns
        assert row["n_repeats"] == 4
        assert math.isclose(row["ci95_f1"], 1.96 * row["sd_f1"] / math.sqrt(4), rel_tol=1e-9) or row["sd_f1"] == 0

    def test_summarise_by_rubric_index(self):
        examples = _examples()
        config = StudyConfig(judges=(PERFECT,), calibration_sizes=(10,), thresholds=(0.5,), repeats=2)
        by_rubric = summarise_by_rubric(run_study(examples, RUBRICS, _predictions(examples), config))
        assert list(by_rubric.index.names) == ["rubric", "k", "threshold"]
        assert set(by_rubric.index.get_level_values("rubric")) == {"r1", "r2"}

    def test_summarise_averages_rubrics_before_repeats(self):
        # repeat 0: r1=1.0, r2=0.0 -> rubric-mean 0.5; repeat 1: r1=0.0, r2=1.0 -> rubric-mean 0.5.
        # Averaging within repeat first gives sd=0 across repeats; a flat sd over
        # the four raw rows would instead be ~0.577.
        common = {"k": 10, "threshold": 0.5, "n_eval": 20, "n_judges_retained": 1, "has_sufficient_judges": True,
                  "tie_rate": 0.0, "no_judge_rate": 0.0, "n_calibration": 10, "n_calib_positive": 5,
                  "n_calib_negative": 5}
        grid = pd.DataFrame([
            {**common, "repeat": 0, "rubric": "r1", "multi_judge_f1": 1.0, "multi_judge_f1_ties_wrong": 1.0},
            {**common, "repeat": 0, "rubric": "r2", "multi_judge_f1": 0.0, "multi_judge_f1_ties_wrong": 0.0},
            {**common, "repeat": 1, "rubric": "r1", "multi_judge_f1": 0.0, "multi_judge_f1_ties_wrong": 0.0},
            {**common, "repeat": 1, "rubric": "r2", "multi_judge_f1": 1.0, "multi_judge_f1_ties_wrong": 1.0},
        ])
        row = summarise(grid).loc[(10, 0.5)]
        assert row["sd_f1"] == 0.0
        assert row["mean_f1"] == 0.5
        assert row["n_repeats"] == 2

    def test_summarise_penalised_f1_counts_no_verdict_rubrics_as_zero(self):
        # r1 has a verdict (n_eval > 0, multi_judge_f1 present); r2 had eval rows
        # but produced no verdict at all (n_eval > 0, multi_judge_f1 NaN) - a
        # rubric that "dropped out" of the unpenalised average; r3 is structural
        # (n_eval == 0, k too large for the rubric) and must stay NaN in both.
        common = {"k": 10, "threshold": 0.5, "repeat": 0, "n_judges_retained": 1,
                  "has_sufficient_judges": True, "tie_rate": 0.0, "no_judge_rate": 0.0,
                  "n_calibration": 10, "n_calib_positive": 5, "n_calib_negative": 5}
        grid = pd.DataFrame([
            {**common, "rubric": "r1", "multi_judge_f1": 1.0, "multi_judge_f1_ties_wrong": 1.0, "n_eval": 20},
            {**common, "rubric": "r2", "multi_judge_f1": math.nan, "multi_judge_f1_ties_wrong": math.nan, "n_eval": 20},
            {**common, "rubric": "r3", "multi_judge_f1": math.nan, "multi_judge_f1_ties_wrong": math.nan, "n_eval": 0},
        ])
        row = summarise(grid).loc[(10, 0.5)]
        assert row["mean_f1"] == 1.0
        assert row["mean_f1_penalised"] == 0.5

    def test_full_reliability_table(self):
        examples = _examples()
        table = full_reliability(examples, RUBRICS, _predictions(examples), (PERFECT, INVERTED))
        perfect = table[(table["judge"] == PERFECT) & (table["rubric"] == "r1")].iloc[0]
        assert perfect["macro_f1"] == 1.0 and perfect["n"] == 60
        inverted = table[(table["judge"] == INVERTED) & (table["rubric"] == "r1")].iloc[0]
        assert inverted["macro_f1"] == 0.0
