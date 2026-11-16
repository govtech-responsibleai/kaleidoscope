"""Write study outputs: CSVs plus Markdown tables in the feedback's format."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from experiments.rubricbench_calibration.config import StudyConfig


def _fmt(value: float, digits: int = 3) -> str:
    """Format a metric value for Markdown, with a stable ``n/a`` fallback.

    Args:
        value: Value to format; ``None`` or NaN renders as ``n/a``.
        digits: Number of decimal places.

    Returns:
        The formatted string.
    """
    return "n/a" if value is None or (isinstance(value, float) and math.isnan(value)) else f"{value:.{digits}f}"


@dataclass(frozen=True)
class StudyTables:
    """Every table the report renders, in one place.

    Attributes:
        summary: :func:`analysis.summarise` over headline rubrics.
        summary_excluded: The same over ``excluded`` rubrics (appendix).
        oc_kappa: :func:`diagnostics.gate_operating_characteristics` with κ truth.
        oc_f1: The same with held-out macro-F1 ≥ 0.5 on the same draw as truth (sensitivity).
        by_class: :func:`diagnostics.summarise_by_class`.
        baselines: :func:`diagnostics.baseline_summary`.
        noise: :func:`diagnostics.estimator_noise`.
        majority: :func:`diagnostics.majority_baselines`.
        by_rubric: :func:`analysis.summarise_by_rubric` over all rubrics.
        full_reliability: :func:`analysis.full_reliability`.
        synthetic: :func:`diagnostics.synthetic_gate_pass_rates`.
        synthetic_by_rubric: :func:`diagnostics.synthetic_gate_pass_rates_by_rubric`.
        live: Rubric keys with at least one competent judge.
        excluded: Rubric keys kept out of the headline tables.
    """

    summary: pd.DataFrame
    summary_excluded: pd.DataFrame
    oc_kappa: pd.DataFrame
    oc_f1: pd.DataFrame
    by_class: pd.DataFrame
    baselines: pd.DataFrame
    noise: pd.DataFrame
    majority: pd.DataFrame
    by_rubric: pd.DataFrame
    full_reliability: pd.DataFrame
    synthetic: pd.DataFrame
    synthetic_by_rubric: pd.DataFrame
    live: set[str]
    excluded: tuple[str, ...]


def _prescribed_lines(summary: pd.DataFrame, coverage_floor: float) -> list[str]:
    """The feedback document's rule: highest mean F1 among thresholds with coverage ≥ floor.

    Printed for completeness; it treats abstention as failure, so it prefers
    thresholds that emit verdicts on rubrics where no judge has signal.

    Args:
        summary: Headline summary indexed by ``(k, threshold)``.
        coverage_floor: Minimum rubric coverage for eligibility.

    Returns:
        One Markdown bullet per ``k``.
    """
    lines = []
    for k in summary.index.get_level_values("k").unique():
        block = summary.xs(k, level="k", drop_level=False)
        eligible = block[block["rubric_coverage"] >= coverage_floor]
        if eligible.empty:
            lines.append(f"- k={k}: no threshold reaches coverage ≥ {coverage_floor:.2f}")
            continue
        t = eligible["mean_f1"].idxmax()[1]
        best = eligible.loc[(k, t)]
        lines.append(f"- k={k}: best threshold {t} (mean F1 {_fmt(best['mean_f1'])} ± {_fmt(best['sd_f1'])}, coverage {_fmt(best['rubric_coverage'], 2)})")
    return lines


def _recommended_lines(oc: pd.DataFrame) -> list[str]:
    """Recommended threshold per ``k``: the one whose gate has the highest balanced accuracy.

    Args:
        oc: Gate operating characteristics indexed by ``(k, threshold)``.

    Returns:
        One Markdown bullet per ``k``.
    """
    lines = []
    for k in oc.index.get_level_values("k").unique():
        block = oc.xs(k, level="k", drop_level=False)
        if block["balanced_accuracy"].isna().all():
            lines.append(f"- k={k}: no threshold has a defined gate balanced accuracy")
            continue
        t = block["balanced_accuracy"].idxmax()[1]
        row = block.loc[(k, t)]
        lines.append(f"- k={k}: recommended threshold {t} (gate balanced accuracy {_fmt(row['balanced_accuracy'], 2)}, "
                     f"TPR {_fmt(row['tpr'], 2)}, FPR {_fmt(row['fpr'], 2)})")
    return lines


def _summary_table(summary: pd.DataFrame) -> list[str]:
    """Render a k × threshold summary table (no CI column).

    Args:
        summary: :func:`analysis.summarise` output.

    Returns:
        Markdown lines.
    """
    header = ("| Calibration size | Reliability threshold | Mean multi-judge macro-F1 (ties dropped) | SD over repeats "
              "| Mean F1 (ties wrong) | Mean F1 (no-verdict rubrics = 0) | Avg. judges retained | Rubric coverage | Tie rate | No-judge rate | Repeats "
              "| One-class sample rate |\n"
              "|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = [
        f"| {k} | {t} | {_fmt(r['mean_f1'])} | {_fmt(r['sd_f1'])} | {_fmt(r['mean_f1_ties_wrong'])} | {_fmt(r['mean_f1_penalised'])} "
        f"| {_fmt(r['avg_judges_retained'], 2)} | {_fmt(r['rubric_coverage'], 2)} | {_fmt(r['tie_rate'])} | {_fmt(r['no_judge_rate'])} | {int(r['n_repeats'])} "
        f"| {_fmt(r['one_class_rate'])} |"
        for (k, t), r in summary.iterrows()
    ]
    return [header, *rows]


def _oc_table(oc: pd.DataFrame) -> list[str]:
    """Render a gate operating-characteristics table.

    Args:
        oc: Indexed by ``(k, threshold)`` with ``tpr, fpr, balanced_accuracy, n_good, n_bad``.

    Returns:
        Markdown lines.
    """
    lines = ["| k | threshold | TPR (aligned admitted) | FPR (misaligned admitted) | Balanced accuracy | n aligned | n misaligned |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {k} | {t} | {_fmt(r['tpr'], 2)} | {_fmt(r['fpr'], 2)} | {_fmt(r['balanced_accuracy'], 2)} | {int(r['n_good'])} | {int(r['n_bad'])} |"
              for (k, t), r in oc.iterrows()]
    return lines


def _noise_table(noise: pd.DataFrame) -> list[str]:
    """Render the reliability-estimate noise table.

    Args:
        noise: :func:`diagnostics.estimator_noise` output, indexed by ``k`` with
            ``sd_calibration_f1, bias_calibration_f1, n_pairs``.

    Returns:
        Markdown lines.
    """
    lines = ["| k | SD of a judge's calibration macro-F1 across repeats | Mean bias vs full-data F1 | judge×rubric pairs |",
             "|---|---|---|---|"]
    lines += [f"| {k} | {_fmt(r['sd_calibration_f1'])} | {_fmt(r['bias_calibration_f1'])} | {int(r['n_pairs'])} |"
              for k, r in noise.iterrows()]
    return lines


def _by_class_table(by_class: pd.DataFrame) -> list[str]:
    """Render the live-vs-dead rubric table.

    Args:
        by_class: :func:`diagnostics.summarise_by_class` output, indexed by
            ``(k, threshold, rubric_class)``.

    Returns:
        Markdown lines.
    """
    lines = ["| k | threshold | class | mean F1 (ties dropped) | mean F1 (ties wrong) | abstain rate | rubrics |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {k} | {t} | {c} | {_fmt(r['mean_f1'])} | {_fmt(r['mean_f1_ties_wrong'])} | {_fmt(r['abstain_rate'])} | {int(r['n_rubrics'])} |"
              for (k, t, c), r in by_class.iterrows()]
    return lines


def _baselines_table(baselines: pd.DataFrame) -> list[str]:
    """Render the baseline comparison table.

    Args:
        baselines: :func:`diagnostics.baseline_summary` output, indexed by
            ``(k, baseline)``.

    Returns:
        Markdown lines.
    """
    lines = ["| k | baseline | mean F1 | SD |", "|---|---|---|---|"]
    lines += [f"| {k} | {b} | {_fmt(r['mean_f1'])} | {_fmt(r['sd_f1'])} |" for (k, b), r in baselines.iterrows()]
    return lines


def _majority_table(majority: pd.DataFrame) -> list[str]:
    """Render the per-rubric constant-majority baseline table.

    Args:
        majority: :func:`diagnostics.majority_baselines` output with columns
            ``rubric, n, positive_rate, constant_majority_f1``.

    Returns:
        Markdown lines.
    """
    lines = ["| rubric | n | share of best option | constant-majority macro-F1 |", "|---|---|---|---|"]
    lines += [f"| {r['rubric']} | {int(r['n'])} | {_fmt(r['positive_rate'], 2)} | {_fmt(r['constant_majority_f1'])} |"
              for _, r in majority.iterrows()]
    return lines


def _synthetic_table(synthetic: pd.DataFrame) -> list[str]:
    """Render the null-judge gate pass rate table.

    Args:
        synthetic: :func:`diagnostics.synthetic_gate_pass_rates` output, indexed
            by ``(k, threshold)``.

    Returns:
        Markdown lines.
    """
    lines = ["| k | threshold | random judge pass rate | constant-majority judge pass rate | random mean F1 | constant mean F1 | draws |",
             "|---|---|---|---|---|---|---|"]
    lines += [f"| {k} | {t} | {_fmt(r['random_pass_rate'], 2)} | {_fmt(r['constant_pass_rate'], 2)} "
              f"| {_fmt(r['random_mean_f1'])} | {_fmt(r['constant_mean_f1'])} | {int(r['n_draws'])} |"
              for (k, t), r in synthetic.iterrows()]
    return lines


def _synthetic_by_rubric_table(synthetic_by_rubric: pd.DataFrame, majority: pd.DataFrame) -> list[str]:
    """Render the per-rubric random-judge-only pass rate table at the smallest and largest k.

    The pooled table (:func:`_synthetic_table`) hides which rubrics drive a
    null judge through the gate; this shows the two ends of the calibration
    range side by side, ordered by how skewed the rubric's gold labels are.

    Args:
        synthetic_by_rubric: :func:`diagnostics.synthetic_gate_pass_rates_by_rubric`
            output, indexed by ``(rubric, k, threshold)``.
        majority: :func:`diagnostics.majority_baselines` output, for each
            rubric's ``positive_rate`` (share of the best option).

    Returns:
        Markdown lines, or an empty list when thresholds 0.5 and 0.6 are not
        both present in ``synthetic_by_rubric``.
    """
    thresholds = set(synthetic_by_rubric.index.get_level_values("threshold"))
    if not {0.5, 0.6}.issubset(thresholds):
        return []
    ks = synthetic_by_rubric.index.get_level_values("k")
    k_min, k_max = ks.min(), ks.max()
    share_by_rubric = majority.set_index("rubric")["positive_rate"]
    rubrics = sorted(synthetic_by_rubric.index.get_level_values("rubric").unique(),
                     key=lambda r: share_by_rubric.get(r, math.nan))
    lines = ["Per rubric, random judge only, smallest and largest k:", "",
             "| rubric | share of best option | pass rate t=0.5 @ k=min | pass rate t=0.5 @ k=max "
             "| pass rate t=0.6 @ k=min | pass rate t=0.6 @ k=max |",
             "|---|---|---|---|---|---|"]
    lines += [
        f"| {rubric} | {_fmt(share_by_rubric.get(rubric, math.nan), 2)} "
        f"| {_fmt(synthetic_by_rubric.loc[(rubric, k_min, 0.5), 'random_pass_rate'], 2)} "
        f"| {_fmt(synthetic_by_rubric.loc[(rubric, k_max, 0.5), 'random_pass_rate'], 2)} "
        f"| {_fmt(synthetic_by_rubric.loc[(rubric, k_min, 0.6), 'random_pass_rate'], 2)} "
        f"| {_fmt(synthetic_by_rubric.loc[(rubric, k_max, 0.6), 'random_pass_rate'], 2)} |"
        for rubric in rubrics
    ]
    return lines


def summary_markdown(tables: StudyTables, config: StudyConfig) -> str:
    """Render ``summary.md``: headline gate diagnostics first, the prescribed table after.

    Args:
        tables: All study tables.
        config: Study configuration (for the coverage floor, truth cutoff and exclusions).

    Returns:
        Markdown text.
    """
    excluded = ", ".join(tables.excluded) if tables.excluded else "none"
    headline_rubrics = set(tables.by_rubric.index.get_level_values("rubric")) - set(tables.excluded)
    dead = sorted(headline_rubrics - tables.live)
    by_rubric_table = _synthetic_by_rubric_table(tables.synthetic_by_rubric, tables.majority)
    parts = [
        "# RubricBench calibration study — summary", "",
        f"_Headline tables cover {len(tables.live | headline_rubrics)} rubrics. "
        f"Excluded from headline: {excluded} (the product judge prompt has no knowledge-base slot, so these judges never saw the source they are asked about; see appendix). "
        f"Rubrics with no judge at κ ≥ {config.truth_cutoff}: {', '.join(dead) or 'none'}._", "",
        "## Gate operating characteristics", "",
        f"Truth = judge's Cohen's κ ≥ {config.truth_cutoff} on the held-out evaluation ids of the same draw (out of sample).", "",
        *_oc_table(tables.oc_kappa), "",
        "Sensitivity: truth = held-out macro-F1 ≥ 0.5 on the same draw (same statistic as the gate; optimistic).", "",
        *_oc_table(tables.oc_f1), "",
        "## Null judges through the gate", "",
        "Pass rate = share of calibration draws on which a judge with no signal reaches the threshold. "
        "random = uniform over the rubric's options; constant = always the calibration draw's majority label. "
        "A threshold with power must send both to ~0.", "",
        *_synthetic_table(tables.synthetic), "",
        *by_rubric_table, *([""] if by_rubric_table else []),
        "## Recommended threshold per calibration size (argmax gate balanced accuracy, κ truth)", "",
        *_recommended_lines(tables.oc_kappa), "",
        "## Reliability-estimate noise", "",
        *_noise_table(tables.noise), "",
        "## Live vs dead rubrics", "",
        f"Live = at least one judge with full-data κ ≥ {config.truth_cutoff}. Abstain rate = share of rubric×repeat cells with no judge retained.", "",
        *_by_class_table(tables.by_class), "",
        "## Baselines", "",
        "Same calibration draws. `ungated` = all judges vote; `single_best` = highest calibration-F1 judge alone; "
        "`constant_majority` = always the calibration majority label; `random` = uniform over options.", "",
        *_baselines_table(tables.baselines), "",
        "## Constant-majority baseline per rubric", "",
        *_majority_table(tables.majority), "",
        "## Prescribed table (k × threshold, headline rubrics)", "",
        *_summary_table(tables.summary), "",
        f"### prescribed criterion (highest mean F1 with coverage ≥ {config.coverage_floor:.2f}; treats abstention as failure)", "",
        *_prescribed_lines(tables.summary, config.coverage_floor), "",
        "## Appendix: rubrics excluded from headline", "",
        *(_summary_table(tables.summary_excluded) if not tables.summary_excluded.empty else ["_none_"]), "",
        "_Coverage is the share of (rubric, repeat) cells with at least one judge retained. "
        "Mean F1 (ties dropped) skips tied, pending and no-judge rows, so it is conditional on coverage; "
        "'ties wrong' scores a tied verdict as the wrong label; the penalised column counts a rubric with no verdict as 0. "
        "SD is the spread over repeated calibration draws a single user would experience._",
    ]
    return "\n".join(parts) + "\n"


def by_rubric_markdown(by_rubric: pd.DataFrame) -> str:
    """Render one table per rubric from :func:`analysis.summarise_by_rubric`.

    Args:
        by_rubric: Output of :func:`analysis.summarise_by_rubric`, indexed by
            ``(rubric, k, threshold)``.

    Returns:
        Markdown text with one ``### <rubric>`` section per rubric.
    """
    parts = ["# RubricBench calibration study — per-rubric breakdown", ""]
    for rubric, block in by_rubric.groupby(level="rubric"):
        parts += [f"### {rubric}", "",
                  "| k | threshold | mean F1 | SD | Avg. judges retained | Coverage | Tie rate | No-judge rate | One-class calib. rate |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for (_, k, t), r in block.iterrows():
            parts.append(f"| {k} | {t} | {_fmt(r['mean_f1'])} | {_fmt(r['sd_f1'])} | {_fmt(r['avg_judges_retained'], 2)} "
                         f"| {_fmt(r['rubric_coverage'], 2)} | {_fmt(r['tie_rate'])} | {_fmt(r['no_judge_rate'])} "
                         f"| {_fmt(r['one_class_rate'])} |")
        parts.append("")
    return "\n".join(parts)


def write_outputs(grid: pd.DataFrame, tables: StudyTables, output_dir: Path, config: StudyConfig) -> list[Path]:
    """Write every output file and return their paths.

    Args:
        grid: Output of :func:`analysis.run_study`.
        tables: All study tables.
        output_dir: Directory to write into; created if missing.
        config: Study configuration.

    Returns:
        Paths of every file written, in write order.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    written = {
        "results_grid.csv": lambda p: grid.to_csv(p, index=False),
        "summary.csv": lambda p: tables.summary.to_csv(p),
        "summary.md": lambda p: p.write_text(summary_markdown(tables, config), encoding="utf-8"),
        "by_rubric.md": lambda p: p.write_text(by_rubric_markdown(tables.by_rubric), encoding="utf-8"),
        "judge_reliability_full.csv": lambda p: tables.full_reliability.to_csv(p, index=False),
        "gate_operating_characteristics.csv": lambda p: tables.oc_kappa.to_csv(p),
        "baselines.csv": lambda p: tables.baselines.to_csv(p),
        "synthetic_gate_pass_rates.csv": lambda p: tables.synthetic.to_csv(p),
        "synthetic_gate_pass_rates_by_rubric.csv": lambda p: tables.synthetic_by_rubric.to_csv(p),
    }
    paths = []
    for name, writer in written.items():
        path = output_dir / name
        writer(path)
        paths.append(path)
    return paths
