"""CLI for the RubricBench calibration study.

Usage (from ``backend/``)::

    uv run python -m experiments.rubricbench_calibration.run inspect
    uv run python -m experiments.rubricbench_calibration.run predict [--judge M ...] [--limit N]
    uv run python -m experiments.rubricbench_calibration.run analyze [--repeats N] [--sampling MODE] [--seed S] [--sizes K ...] [--policy POLICY]
    uv run python -m experiments.rubricbench_calibration.run all
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import logging
import sys

import dotenv

from experiments.rubricbench_calibration.analysis import full_reliability, run_study, summarise, summarise_by_rubric
from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example, describe_dataset, load_rubricbench
from experiments.rubricbench_calibration.diagnostics import (
    baseline_summary,
    estimator_noise,
    gate_operating_characteristics,
    live_rubrics,
    majority_baselines,
    summarise_by_class,
    synthetic_gate_pass_rates,
    synthetic_gate_pass_rates_by_rubric,
)
from experiments.rubricbench_calibration.predict import load_predictions, run_predictions, write_label_cache
from experiments.rubricbench_calibration.report import StudyTables, write_outputs
from experiments.rubricbench_calibration.rubrics import Rubric, load_rubrics

logger = logging.getLogger("rubricbench_calibration")


def build_parser() -> argparse.ArgumentParser:
    """Command-line interface definition.

    Returns:
        The configured argument parser with ``inspect``, ``predict``,
        ``analyze``, and ``all`` subcommands.
    """
    parser = argparse.ArgumentParser(prog="rubricbench_calibration", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("inspect", help="Print the dataset schema and detected columns")

    predict = sub.add_parser("predict", help="Stage 1: collect judge predictions")
    predict.add_argument("--judge", action="append", help="Catalog model name; repeatable. Default: all judges.")
    predict.add_argument("--limit", type=int, default=None, help="Only score the first N examples (smoke test).")

    analyze = sub.add_parser("analyze", help="Stage 2: run the k × threshold sweep")
    run_all = sub.add_parser("all", help="predict then analyze")
    for sub_parser in (analyze, run_all):
        sub_parser.add_argument("--repeats", type=int, default=None)
        sub_parser.add_argument("--sampling", choices=["per_rubric", "shared", "unstratified"], default=None)
        sub_parser.add_argument("--seed", type=int, default=None)
        sub_parser.add_argument("--sizes", type=int, nargs="+", default=None,
                                help="Calibration sizes k, e.g. --sizes 5 10 20.")
        sub_parser.add_argument("--policy", choices=["exclude", "annotator_1", "annotator_2"], default=None,
                                help="Disagreement policy for gold labels (default: exclude examples the two annotators disagree on).")
    return parser


def _config_from_args(args: argparse.Namespace) -> StudyConfig:
    """Build a :class:`StudyConfig` with any CLI overrides applied.

    Args:
        args: Parsed command-line arguments.

    Returns:
        A ``StudyConfig`` with ``repeats``, ``sampling``, ``seed``,
        ``disagreement_policy`` (from ``--policy``), and ``calibration_sizes``
        (from ``--sizes``) overridden wherever the corresponding argument was
        supplied. Reports are routed starting from the default
        ``StudyConfig().output_dir``: a ``policy_<policy>`` segment is
        appended first when ``disagreement_policy`` is not the default
        (``exclude``), then a ``<sampling>`` segment when ``sampling`` is not
        the default (``per_rubric``), so different policies and sampling
        modes never overwrite each other's output.
    """
    overrides = {name: getattr(args, name) for name in ("repeats", "sampling", "seed")
                 if getattr(args, name, None) is not None}
    if getattr(args, "sizes", None):
        overrides["calibration_sizes"] = tuple(args.sizes)
    if getattr(args, "policy", None) is not None:
        overrides["disagreement_policy"] = args.policy
    config = dataclasses.replace(StudyConfig(), **overrides)
    output_dir = StudyConfig().output_dir
    if config.disagreement_policy != "exclude":
        output_dir = output_dir / f"policy_{config.disagreement_policy}"
    if config.sampling != "per_rubric":
        output_dir = output_dir / config.sampling
    return dataclasses.replace(config, output_dir=output_dir)


def _analyze(config: StudyConfig, rubrics: list[Rubric], examples: list[Example]) -> None:
    """Run Stage 2 and the diagnostics over cached predictions and write every output file.

    Args:
        config: Study configuration.
        rubrics: Rubrics to evaluate.
        examples: Examples with gold labels.

    Raises:
        SystemExit: If no predictions have been cached yet.
    """
    predictions = load_predictions(config.predictions_path, fallback=config.labels_path)
    if not predictions:
        raise SystemExit(f"No predictions at {config.predictions_path} or {config.labels_path}; run `predict` first.")
    n_labels = write_label_cache(predictions, config.labels_path)
    logger.info("wrote %d label rows to %s", n_labels, config.labels_path)
    grid = run_study(examples, rubrics, predictions, config)
    excluded = tuple(r for r in config.headline_exclude if r in {x.key for x in rubrics})
    headline = grid[~grid["rubric"].isin(excluded)]
    headline_rubrics = [r for r in rubrics if r.key not in excluded]
    live = live_rubrics(examples, headline_rubrics, predictions, config.judges, config.truth_cutoff)
    headline_summary = summarise(headline)
    tables = StudyTables(
        summary=headline_summary,
        summary_excluded=summarise(grid[grid["rubric"].isin(excluded)]) if excluded else headline_summary.iloc[0:0],
        oc_kappa=gate_operating_characteristics(headline, examples, headline_rubrics, predictions, config.judges, "kappa", config.truth_cutoff),
        oc_f1=gate_operating_characteristics(headline, examples, headline_rubrics, predictions, config.judges, "f1", 0.5),
        by_class=summarise_by_class(headline, live),
        baselines=baseline_summary(headline, examples, headline_rubrics, predictions, config.judges, config.seed),
        noise=estimator_noise(headline, examples, headline_rubrics, predictions, config.judges),
        majority=majority_baselines(examples, rubrics),
        by_rubric=summarise_by_rubric(grid),
        full_reliability=full_reliability(examples, rubrics, predictions, config.judges),
        synthetic=synthetic_gate_pass_rates(headline, examples, headline_rubrics, config.thresholds, config.seed),
        synthetic_by_rubric=synthetic_gate_pass_rates_by_rubric(headline, examples, headline_rubrics, config.thresholds, config.seed),
        live=live,
        excluded=excluded,
    )
    for path in write_outputs(grid, tables, config.output_dir, config):
        logger.info("wrote %s", path)
    print((config.output_dir / "summary.md").read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: Command-line arguments, excluding the program name; defaults to
            ``sys.argv[1:]``.

    Returns:
        Process exit code (always ``0`` on success).
    """
    dotenv.load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("LiteLLM").setLevel(logging.ERROR)
    args = build_parser().parse_args(argv)
    config = _config_from_args(args)
    rubrics = load_rubrics()

    if args.command == "inspect":
        print(describe_dataset(config, rubrics))
        return 0

    from src.common.llm.pricing import register_catalog_pricing
    register_catalog_pricing()

    examples = load_rubricbench(config, rubrics)
    if args.command in ("predict", "all"):
        subset = examples[: args.limit] if getattr(args, "limit", None) else examples
        judges = tuple(args.judge) if getattr(args, "judge", None) else None
        asyncio.run(run_predictions(config, rubrics, subset, config.predictions_path, judges=judges))
    if args.command in ("analyze", "all"):
        _analyze(config, rubrics, examples)
    return 0


if __name__ == "__main__":
    sys.exit(main())
