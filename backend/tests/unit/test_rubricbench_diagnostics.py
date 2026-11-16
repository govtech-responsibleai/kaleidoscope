import dataclasses
import random

import pandas as pd
import pytest

from experiments.rubricbench_calibration.analysis import run_study
from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.diagnostics import (
    SYNTHETIC_COLUMNS,
    baseline_summary,
    constant_majority_f1,
    estimator_noise,
    gate_operating_characteristics,
    judge_kappa,
    live_rubrics,
    majority_baselines,
    summarise_by_class,
    synthetic_gate_pass_rates,
    synthetic_gate_pass_rates_by_rubric,
)
from experiments.rubricbench_calibration.predict import PredictionRecord
from experiments.rubricbench_calibration.rubrics import Rubric, RubricOption

R1 = Rubric("r1", "R1", "c", (RubricOption("good", ""), RubricOption("bad", "")), "good")
R2 = Rubric("r2", "R2", "c", (RubricOption("yes", ""), RubricOption("no", "")), "yes")
RUBRICS = [R1, R2]
PERFECT, RANDOM, INVERTED = "govtech/perfect", "govtech/random", "govtech/inverted"
JUDGES = (PERFECT, RANDOM, INVERTED)


def _examples(n: int = 60) -> list[Example]:
    rng = random.Random(0)
    return [
        Example(str(i), f"q{i}", f"a{i}", {"r1": "good" if i % 3 else "bad", "r2": rng.choice(["yes", "no"])})
        for i in range(n)
    ]


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


@pytest.fixture(scope="module")
def world():
    examples = _examples()
    predictions = _predictions(examples)
    config = StudyConfig(judges=JUDGES, calibration_sizes=(10, 20), thresholds=(0.3, 0.5, 0.7), repeats=5)
    grid = run_study(examples, RUBRICS, predictions, config)
    return examples, predictions, config, grid


@pytest.fixture(scope="module")
def large_world():
    """More repeats than `world`, so per-k synthetic-judge pass rates aren't sampling noise."""
    examples = _examples()
    predictions = _predictions(examples)
    config = StudyConfig(judges=JUDGES, calibration_sizes=(10, 20), thresholds=(0.3, 0.5, 0.7), repeats=40)
    grid = run_study(examples, RUBRICS, predictions, config)
    return examples, predictions, config, grid


class TestJudgeKappa:
    def test_perfect_agreement_is_one(self):
        assert judge_kappa(["good", "bad", "good"], ["good", "bad", "good"], "good") == 1.0

    def test_inverted_is_negative(self):
        assert judge_kappa(["good", "bad", "good", "bad"], ["bad", "good", "bad", "good"], "good") < 0

    def test_constant_prediction_is_zero(self):
        assert judge_kappa(["good", "bad", "good"], ["good", "good", "good"], "good") == 0.0

    def test_missing_predictions_are_dropped(self):
        assert judge_kappa(["good", "bad", "good"], ["good", "bad", None], "good") == 1.0


class TestGateOperatingCharacteristics:
    def test_shape_and_columns(self, world):
        examples, predictions, config, grid = world
        oc = gate_operating_characteristics(grid, examples, RUBRICS, predictions, JUDGES)
        assert list(oc.index.names) == ["k", "threshold"]
        assert len(oc) == 6
        assert list(oc.columns) == ["tpr", "fpr", "balanced_accuracy", "n_good", "n_bad"]

    def test_perfect_judge_counts_as_good_and_inverted_as_bad(self, world):
        examples, predictions, config, grid = world
        # cutoff=0.5: a random judge cannot reach κ 0.5 on ~40 held-out items, so truth is deterministic
        oc = gate_operating_characteristics(grid, examples, RUBRICS, predictions, JUDGES, cutoff=0.5)
        # Every row has exactly one good judge (perfect) and two bad (random, inverted)
        row = oc.loc[(20, 0.5)]
        assert row["n_good"] == 5 * 2          # repeats × rubrics
        assert row["n_bad"] == 5 * 2 * 2

    def test_high_threshold_admits_perfect_and_rejects_inverted(self, world):
        examples, predictions, config, grid = world
        oc = gate_operating_characteristics(grid, examples, RUBRICS, predictions, JUDGES, cutoff=0.5)
        assert oc.loc[(20, 0.7), "tpr"] == 1.0
        assert oc.loc[(20, 0.7), "fpr"] <= 0.5   # random may squeak in; inverted never does
        assert oc.loc[(20, 0.3), "fpr"] > oc.loc[(20, 0.7), "fpr"]

    def test_f1_truth_is_supported(self, world):
        examples, predictions, config, grid = world
        oc = gate_operating_characteristics(grid, examples, RUBRICS, predictions, JUDGES, truth="f1", cutoff=0.5)
        assert 0.0 <= oc["balanced_accuracy"].min() <= oc["balanced_accuracy"].max() <= 1.0

    def test_truth_is_out_of_sample(self, world):
        # A judge that copies gold on the calibration draw and is wrong everywhere
        # else passes the gate (calibration macro-F1 1.0) but must still count as
        # misaligned, because truth is measured on the held-out ids.
        examples, predictions, config, grid = world
        calib_only = "govtech/calib_only"
        row = next(grid[(grid["k"] == 20) & (grid["threshold"] == 0.5) & (grid["rubric"] == "r1")].itertuples())
        calibration_ids = set(row.calibration_ids.split(","))

        rigged = dict(predictions)
        for example in examples:
            for rubric in RUBRICS:
                gold = example.gold[rubric.key]
                other = [o for o in rubric.option_values if o != gold][0]
                label = gold if example.example_id in calibration_ids else other
                record = PredictionRecord(calib_only, rubric.key, example.example_id, label, label, "", 1, 1, 0.0, "m", None)
                rigged[record.key] = record

        judges = (PERFECT, calib_only)
        rigged_config = dataclasses.replace(config, judges=judges)
        rigged_grid = run_study(examples, RUBRICS, rigged, rigged_config)
        single = rigged_grid[(rigged_grid["repeat"] == row.repeat) & (rigged_grid["k"] == 20)
                             & (rigged_grid["threshold"] == 0.5) & (rigged_grid["rubric"] == "r1")]
        assert len(single) == 1
        assert set(single.iloc[0]["calibration_ids"].split(",")) == calibration_ids

        oc = gate_operating_characteristics(single, examples, RUBRICS, rigged, judges, cutoff=0.5)
        stats = oc.loc[(20, 0.5)]
        assert stats["n_good"] == 1        # only the perfect judge is aligned out of sample
        assert stats["n_bad"] == 1         # the calibration-only judge is not
        assert stats["fpr"] == 1.0         # yet the gate admits it: calibration F1 is 1.0

    def test_unknown_truth_rejected(self, world):
        examples, predictions, config, grid = world
        with pytest.raises(ValueError, match="truth"):
            gate_operating_characteristics(grid, examples, RUBRICS, predictions, JUDGES, truth="accuracy")


class TestBaselines:
    def test_constant_majority_f1_matches_closed_form(self):
        # p = 0.9 → always-positive: F1+ = 2*0.9/1.9, F1- = 0 → macro ≈ 0.4737
        assert constant_majority_f1(0.9) == pytest.approx(0.4737, abs=1e-3)
        assert constant_majority_f1(0.5) == pytest.approx(1 / 3, abs=1e-3)
        assert constant_majority_f1(0.1) == pytest.approx(0.4737, abs=1e-3)

    def test_majority_baselines_one_row_per_rubric(self, world):
        examples, *_ = world
        table = majority_baselines(examples, RUBRICS)
        assert list(table.columns) == ["rubric", "n", "positive_rate", "constant_majority_f1"]
        assert set(table["rubric"]) == {"r1", "r2"}
        r1 = table.set_index("rubric").loc["r1"]
        assert r1["positive_rate"] == pytest.approx(40 / 60)

    def test_baseline_summary_orders_perfect_above_random(self, world):
        examples, predictions, config, grid = world
        table = baseline_summary(grid, examples, RUBRICS, predictions, JUDGES)
        assert list(table.index.names) == ["k", "baseline"]
        assert set(table.index.get_level_values("baseline")) == {"ungated", "single_best", "constant_majority", "random"}
        assert table.loc[(20, "single_best"), "mean_f1"] > table.loc[(20, "random"), "mean_f1"]
        # single_best picks the perfect judge on every draw, so it must score 1.0
        assert table.loc[(20, "single_best"), "mean_f1"] == pytest.approx(1.0)


class TestLiveDeadSplit:
    def test_live_rubrics_detects_any_competent_judge(self, world):
        examples, predictions, *_ = world
        assert live_rubrics(examples, RUBRICS, predictions, JUDGES) == {"r1", "r2"}
        assert live_rubrics(examples, RUBRICS, predictions, (RANDOM,)) == set()

    def test_summarise_by_class_shape(self, world):
        examples, predictions, config, grid = world
        table = summarise_by_class(grid, live={"r1"})
        assert list(table.index.names) == ["k", "threshold", "rubric_class"]
        assert set(table.index.get_level_values("rubric_class")) == {"live", "dead"}
        assert list(table.columns) == ["mean_f1", "mean_f1_ties_wrong", "abstain_rate", "n_rubrics"]
        assert table.loc[(20, 0.5, "live"), "n_rubrics"] == 1

class TestEstimatorNoise:
    def test_noise_falls_with_k_and_bias_is_small(self, world):
        examples, predictions, config, grid = world
        table = estimator_noise(grid, examples, RUBRICS, predictions, JUDGES)
        assert list(table.columns) == ["sd_calibration_f1", "bias_calibration_f1", "n_pairs"]
        assert table.loc[10, "sd_calibration_f1"] >= table.loc[20, "sd_calibration_f1"]
        assert abs(table.loc[20, "bias_calibration_f1"]) < 0.1
        assert table.loc[20, "n_pairs"] == len(JUDGES) * len(RUBRICS)

class TestSyntheticGatePassRates:
    def test_shape_and_columns(self, world):
        examples, predictions, config, grid = world
        synth = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        assert list(synth.index.names) == ["k", "threshold"]
        assert len(synth) == len(config.calibration_sizes) * len(config.thresholds)
        assert list(synth.columns) == SYNTHETIC_COLUMNS

    def test_n_draws_equals_repeats_times_rubrics(self, world):
        examples, predictions, config, grid = world
        synth = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        for k in config.calibration_sizes:
            assert synth.loc[(k, config.thresholds[0]), "n_draws"] == config.repeats * len(RUBRICS)

    def test_constant_judge_never_passes_high_threshold(self, world):
        examples, predictions, config, grid = world
        synth = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        for k in config.calibration_sizes:
            assert synth.loc[(k, 0.7), "constant_pass_rate"] == 0.0

    def test_random_judge_pass_rate_by_threshold(self, large_world):
        examples, predictions, config, grid = large_world
        synth = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        for k in config.calibration_sizes:
            assert synth.loc[(k, 0.3), "random_pass_rate"] > 0.75
            assert synth.loc[(k, 0.7), "random_pass_rate"] < 0.25

    def test_reproducible_with_same_seed(self, world):
        examples, predictions, config, grid = world
        a = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds, seed=7)
        b = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds, seed=7)
        pd.testing.assert_frame_equal(a, b)

    def test_pooled_frame_unchanged_by_the_by_rubric_refactor(self, world):
        # Values recorded from the pre-refactor implementation of synthetic_gate_pass_rates
        # on this exact fixture (seed=0, the default), to pin the refactor to the same numbers.
        examples, predictions, config, grid = world
        synth = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        expected = {
            (10, 0.3): (0.7, 1.0, 0.4052569653, 0.3808823529, 10),
            (10, 0.5): (0.1, 0.0, 0.4052569653, 0.3808823529, 10),
            (10, 0.7): (0.0, 0.0, 0.4052569653, 0.3808823529, 10),
            (20, 0.3): (1.0, 1.0, 0.5276717099, 0.3743890518, 10),
            (20, 0.5): (0.6, 0.0, 0.5276717099, 0.3743890518, 10),
            (20, 0.7): (0.0, 0.0, 0.5276717099, 0.3743890518, 10),
        }
        for (k, t), (random_pass, constant_pass, random_f1, constant_f1, n_draws) in expected.items():
            row = synth.loc[(k, t)]
            assert row["random_pass_rate"] == pytest.approx(random_pass)
            assert row["constant_pass_rate"] == pytest.approx(constant_pass)
            assert row["random_mean_f1"] == pytest.approx(random_f1, abs=1e-9)
            assert row["constant_mean_f1"] == pytest.approx(constant_f1, abs=1e-9)
            assert row["n_draws"] == n_draws


class TestSyntheticGatePassRatesByRubric:
    def test_index_and_columns(self, world):
        examples, predictions, config, grid = world
        by_rubric = synthetic_gate_pass_rates_by_rubric(grid, examples, RUBRICS, config.thresholds)
        assert list(by_rubric.index.names) == ["rubric", "k", "threshold"]
        assert set(by_rubric.index.get_level_values("rubric")) == {"r1", "r2"}
        assert list(by_rubric.columns) == SYNTHETIC_COLUMNS
        assert len(by_rubric) == len(RUBRICS) * len(config.calibration_sizes) * len(config.thresholds)

    def test_pooled_pass_rate_is_the_draw_weighted_mean_of_per_rubric_rates(self, world):
        examples, predictions, config, grid = world
        pooled = synthetic_gate_pass_rates(grid, examples, RUBRICS, config.thresholds)
        by_rubric = synthetic_gate_pass_rates_by_rubric(grid, examples, RUBRICS, config.thresholds)
        for k in config.calibration_sizes:
            for threshold in config.thresholds:
                r1 = by_rubric.loc[("r1", k, threshold)]
                r2 = by_rubric.loc[("r2", k, threshold)]
                # The fixture draws an equal number of calibration samples per rubric at
                # each k, so the weighted mean is an exact, unambiguous check.
                assert r1["n_draws"] == r2["n_draws"]
                expected = (r1["random_pass_rate"] * r1["n_draws"] + r2["random_pass_rate"] * r2["n_draws"]) / (
                    r1["n_draws"] + r2["n_draws"]
                )
                assert pooled.loc[(k, threshold), "random_pass_rate"] == pytest.approx(expected)
