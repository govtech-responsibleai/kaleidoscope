from pathlib import Path

import pandas as pd

from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.report import StudyTables, summary_markdown, write_outputs
from experiments.rubricbench_calibration.run import build_parser


def _idx(*pairs):
    return pd.MultiIndex.from_tuples(list(pairs), names=["k", "threshold"])


def _idx3(*triples):
    return pd.MultiIndex.from_tuples(list(triples), names=["rubric", "k", "threshold"])


def _synthetic_by_rubric(thresholds=(0.5, 0.6)) -> pd.DataFrame:
    rows = {
        ("r1", 10, 0.5): 0.20, ("r1", 10, 0.6): 0.05, ("r1", 20, 0.5): 0.10, ("r1", 20, 0.6): 0.02,
        ("r2", 10, 0.5): 0.55, ("r2", 10, 0.6): 0.30, ("r2", 20, 0.5): 0.60, ("r2", 20, 0.6): 0.35,
    }
    keys = [k for k in rows if k[2] in thresholds]
    return pd.DataFrame({
        "random_pass_rate": [rows[k] for k in keys], "constant_pass_rate": [0.0] * len(keys),
        "random_mean_f1": [0.4] * len(keys), "constant_mean_f1": [0.3] * len(keys), "n_draws": [10] * len(keys),
    }, index=_idx3(*keys))


def _tables(synthetic_by_rubric: pd.DataFrame | None = None) -> StudyTables:
    summary = pd.DataFrame({
        "mean_f1": [0.61, 0.70, 0.72], "sd_f1": [0.10, 0.05, 0.04], "ci95_f1": [0.02, 0.01, 0.01],
        "mean_f1_penalised": [0.55, 0.65, 0.70], "mean_f1_ties_wrong": [0.60, 0.68, 0.71],
        "avg_judges_retained": [3.0, 2.0, 2.0], "rubric_coverage": [1.0, 0.95, 0.80],
        "tie_rate": [0.0, 0.05, 0.05], "no_judge_rate": [0.0, 0.05, 0.2],
        "one_class_rate": [0.0, 0.0, 0.1], "n_repeats": [5, 5, 5],
    }, index=_idx((10, 0.3), (10, 0.5), (20, 0.5)))
    oc = pd.DataFrame({"tpr": [1.0, 0.8, 0.9], "fpr": [0.9, 0.1, 0.1], "balanced_accuracy": [0.55, 0.85, 0.90],
                       "n_good": [10, 10, 10], "n_bad": [20, 20, 20]}, index=_idx((10, 0.3), (10, 0.5), (20, 0.5)))
    by_class = pd.DataFrame({"mean_f1": [0.7, 0.45, 0.72, 0.44], "mean_f1_ties_wrong": [0.69, 0.45, 0.71, 0.44],
                             "abstain_rate": [0.0, 0.0, 0.0, 0.8], "n_rubrics": [2, 1, 2, 1]},
                            index=pd.MultiIndex.from_tuples([(10, 0.3, "live"), (10, 0.3, "dead"), (10, 0.5, "live"), (10, 0.5, "dead")],
                                                            names=["k", "threshold", "rubric_class"]))
    baselines = pd.DataFrame({"mean_f1": [0.6, 0.65, 0.4, 0.33], "sd_f1": [0.1] * 4},
                             index=pd.MultiIndex.from_tuples([(10, "ungated"), (10, "single_best"), (10, "constant_majority"), (10, "random")],
                                                             names=["k", "baseline"]))
    noise = pd.DataFrame({"sd_calibration_f1": [0.12, 0.08], "bias_calibration_f1": [-0.01, 0.0], "n_pairs": [6, 6]},
                         index=pd.Index([10, 20], name="k"))
    majority = pd.DataFrame({"rubric": ["r1", "r2", "faithfulness"], "n": [60, 60, 60], "positive_rate": [0.9, 0.5, 0.3],
                             "constant_majority_f1": [0.47, 0.33, 0.41]})
    by_rubric = pd.DataFrame({"mean_f1": [0.5], "sd_f1": [0.0], "avg_judges_retained": [1], "rubric_coverage": [1.0],
                              "tie_rate": [0.0], "no_judge_rate": [0.0], "one_class_rate": [0.0]},
                             index=pd.MultiIndex.from_tuples([("r1", 10, 0.5)], names=["rubric", "k", "threshold"]))
    full = pd.DataFrame({"rubric": ["r1"], "judge": ["j"], "macro_f1": [0.5], "n": [10]})
    synthetic = pd.DataFrame({
        "random_pass_rate": [0.85, 0.40, 0.30], "constant_pass_rate": [1.0, 0.0, 0.0],
        "random_mean_f1": [0.45, 0.45, 0.50], "constant_mean_f1": [0.47, 0.47, 0.40], "n_draws": [10, 10, 10],
    }, index=_idx((10, 0.3), (10, 0.5), (20, 0.5)))
    return StudyTables(summary=summary, summary_excluded=summary.iloc[:1], oc_kappa=oc, oc_f1=oc, by_class=by_class,
                       baselines=baselines, noise=noise, majority=majority, by_rubric=by_rubric,
                       full_reliability=full, synthetic=synthetic,
                       synthetic_by_rubric=synthetic_by_rubric if synthetic_by_rubric is not None else _synthetic_by_rubric(),
                       live={"r1", "r2"}, excluded=("faithfulness",))


def test_summary_markdown_sections_and_selection_rules():
    text = summary_markdown(_tables(), StudyConfig())
    assert "## Gate operating characteristics" in text
    assert "| 10 | 0.5 | 0.80 | 0.10 | 0.85 |" in text
    assert "## Baselines" in text and "single_best" in text
    assert "## Live vs dead rubrics" in text
    assert "## Reliability-estimate noise" in text
    assert "## Constant-majority baseline per rubric" in text
    assert "95% CI" not in text
    # recommended = argmax balanced accuracy; prescribed rule still printed with its caveat
    assert "k=10: recommended threshold 0.5 (gate balanced accuracy 0.85" in text
    assert "prescribed criterion" in text and "k=10: best threshold 0.5" in text
    assert "faithfulness" in text and "excluded from headline" in text.lower()
    assert "## Null judges through the gate" in text
    assert "| 10 | 0.3 | 0.85 | 1.00 | 0.450 | 0.470 | 10 |" in text
    sensitivity_idx = text.index("Sensitivity: truth = held-out macro-F1")
    null_idx = text.index("## Null judges through the gate")
    recommended_idx = text.index("## Recommended threshold per calibration size")
    assert sensitivity_idx < null_idx < recommended_idx
    assert "Per rubric, random judge only, smallest and largest k:" in text
    assert "| r2 | 0.50 | 0.55 | 0.60 | 0.30 | 0.35 |" in text
    per_rubric_idx = text.index("Per rubric, random judge only")
    assert null_idx < per_rubric_idx < recommended_idx


def test_per_rubric_table_omitted_when_thresholds_incomplete():
    text = summary_markdown(_tables(synthetic_by_rubric=_synthetic_by_rubric(thresholds=(0.5,))), StudyConfig())
    assert "Per rubric, random judge only" not in text


def test_write_outputs_creates_all_files(tmp_path: Path):
    grid = pd.DataFrame({"repeat": [0], "k": [10], "threshold": [0.5], "rubric": ["r1"], "multi_judge_f1": [0.5]})
    paths = write_outputs(grid, _tables(), tmp_path, StudyConfig())
    assert {p.name for p in paths} == {"results_grid.csv", "summary.csv", "summary.md", "by_rubric.md",
                                       "judge_reliability_full.csv", "gate_operating_characteristics.csv", "baselines.csv",
                                       "synthetic_gate_pass_rates.csv", "synthetic_gate_pass_rates_by_rubric.csv"}
    assert all(p.exists() for p in paths)


def test_parser_subcommands_and_overrides():
    parser = build_parser()
    args = parser.parse_args(["analyze", "--repeats", "5", "--sampling", "unstratified", "--seed", "1", "--sizes", "5", "10"])
    assert args.command == "analyze" and args.repeats == 5 and args.sampling == "unstratified" and args.seed == 1
    assert args.sizes == [5, 10]
    args = parser.parse_args(["predict", "--judge", "govtech/x", "--judge", "govtech/y", "--limit", "3"])
    assert args.judge == ["govtech/x", "govtech/y"] and args.limit == 3
    assert build_parser().parse_args(["inspect"]).command == "inspect"
    assert build_parser().parse_args(["all"]).command == "all"


def test_config_from_args_routes_non_default_sampling_to_subdir():
    from experiments.rubricbench_calibration.run import _config_from_args
    args = build_parser().parse_args(["analyze", "--sampling", "unstratified", "--sizes", "5", "20"])
    config = _config_from_args(args)
    assert config.sampling == "unstratified"
    assert config.calibration_sizes == (5, 20)
    assert config.output_dir.name == "unstratified"
    assert config.predictions_path.parent.name == "outputs"
