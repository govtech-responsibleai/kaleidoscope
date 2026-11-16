"""Stage 2b: diagnostics that answer the reviewers directly.

Everything here is recomputed from the Stage 1 prediction cache and the grid
produced by :func:`analysis.run_study`; there are no LLM calls. The functions
are deliberately independent of each other so the report can include any
subset.
"""

from __future__ import annotations

from collections import Counter
from typing import Literal

import numpy as np
import pandas as pd
from sklearn.metrics import cohen_kappa_score

from experiments.rubricbench_calibration.analysis import Predictions, aggregate_votes, reliability
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.rubrics import Rubric

TruthStatistic = Literal["kappa", "f1"]

OC_COLUMNS = ["tpr", "fpr", "balanced_accuracy", "n_good", "n_bad"]


def judge_kappa(y_true: list[str], y_pred: list[str | None], best_option: str) -> float:
    """Cohen's κ of a judge against gold labels on the best-option binarisation.

    κ has a null expectation of 0 regardless of label skew, unlike macro-F1,
    which is why it is used to define "truly aligned" out of sample. Pairs with
    a missing prediction are dropped; a constant predictor scores 0.0.

    Args:
        y_true: Gold labels.
        y_pred: Judge labels (``None`` = missing).
        best_option: The rubric's desirable label.

    Returns:
        κ in [-1, 1]; 0.0 when nothing can be compared or the judge is constant.
    """
    pairs = [(t == best_option, p == best_option) for t, p in zip(y_true, y_pred) if p is not None]
    if not pairs:
        return 0.0
    truth, pred = zip(*pairs)
    if len(set(pred)) < 2 or len(set(truth)) < 2:
        return 0.0
    return float(cohen_kappa_score(truth, pred))


def _gold_by_rubric(examples: list[Example], rubrics: list[Rubric]) -> dict[str, dict[str, str]]:
    """Index gold labels as ``{rubric_key: {example_id: label}}``, skipping missing labels.

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics whose keys to index.

    Returns:
        Nested dict of gold labels.
    """
    return {
        r.key: {e.example_id: e.gold[r.key] for e in examples if e.gold[r.key] is not None}
        for r in rubrics
    }


def _predicted(predictions: Predictions, judge: str, rubric_key: str, ids: list[str]) -> list[str | None]:
    """Look up one judge's predictions for a list of example ids.

    Args:
        predictions: Stage 1 cache.
        judge: Judge name.
        rubric_key: Rubric key.
        ids: Example ids.

    Returns:
        One label (or ``None``) per id, in order.
    """
    return [(rec.chosen_option if (rec := predictions.get((judge, rubric_key, i))) else None) for i in ids]


def _truth_statistic(truth: TruthStatistic):
    """Resolve the function that scores a judge for the out-of-sample truth definition.

    Args:
        truth: ``"kappa"`` or ``"f1"``.

    Returns:
        A callable ``(y_true, y_pred, best_option) -> float``.

    Raises:
        ValueError: If ``truth`` is not a known statistic.
    """
    if truth == "kappa":
        return judge_kappa
    if truth == "f1":
        return reliability
    raise ValueError(f"Unknown truth statistic {truth!r}; expected 'kappa' or 'f1'")


def gate_operating_characteristics(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    judges: tuple[str, ...],
    truth: TruthStatistic = "kappa",
    cutoff: float = 0.2,
) -> pd.DataFrame:
    """Score the gate itself as a classifier of judges, per ``(k, threshold)``.

    For every grid row, each judge is labelled "truly aligned" if its
    ``truth`` statistic on that row's *evaluation* ids (the complement of the
    calibration draw) is at least ``cutoff``. The gate's decision on the
    calibration draw (the ``retained_judges`` column) is then compared with
    that label. TPR = aligned judges admitted; FPR = misaligned judges
    admitted; balanced accuracy = (TPR + (1 - FPR)) / 2.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        predictions: Stage 1 cache.
        judges: Judge names considered by the gate.
        truth: Statistic that defines "truly aligned" (``"kappa"`` or ``"f1"``).
        cutoff: Minimum value of ``truth`` for a judge to count as aligned.

    Returns:
        Frame indexed by ``(k, threshold)`` with :data:`OC_COLUMNS`. Rows of the
        grid with an empty calibration sample are ignored.
    """
    score = _truth_statistic(truth)
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    best = {r.key: r.best_option for r in rubrics}
    counts: dict[tuple[int, float], Counter] = {}
    truth_cache: dict[tuple[int, int, str], dict[str, bool]] = {}

    for row in grid[grid["n_calibration"] > 0].itertuples(index=False):
        key = (row.repeat, row.k, row.rubric)
        if key not in truth_cache:
            calib = set(row.calibration_ids.split(","))
            gold = gold_by_rubric[row.rubric]
            eval_ids = [i for i in gold if i not in calib]
            y_true = [gold[i] for i in eval_ids]
            truth_cache[key] = {
                j: score(y_true, _predicted(predictions, j, row.rubric, eval_ids), best[row.rubric]) >= cutoff
                for j in judges
            }
        aligned = truth_cache[key]
        retained = set(row.retained_judges.split("|")) if isinstance(row.retained_judges, str) and row.retained_judges else set()
        counter = counts.setdefault((row.k, row.threshold), Counter())
        for j in judges:
            counter[(aligned[j], j in retained)] += 1

    records = []
    for (k, threshold), c in sorted(counts.items()):
        n_good = c[(True, True)] + c[(True, False)]
        n_bad = c[(False, True)] + c[(False, False)]
        tpr = c[(True, True)] / n_good if n_good else np.nan
        fpr = c[(False, True)] / n_bad if n_bad else np.nan
        records.append({
            "k": k, "threshold": threshold, "tpr": tpr, "fpr": fpr,
            "balanced_accuracy": (tpr + (1 - fpr)) / 2 if n_good and n_bad else np.nan,
            "n_good": n_good, "n_bad": n_bad,
        })
    return pd.DataFrame(records, columns=["k", "threshold", *OC_COLUMNS]).set_index(["k", "threshold"])

BASELINES = ("ungated", "single_best", "constant_majority", "random")


def constant_majority_f1(positive_rate: float) -> float:
    """Macro-F1 of a classifier that always predicts the majority class.

    With positive rate ``p``, always-positive scores F1 = 2p/(1+p) on the
    positive class and 0 on the negative class; always-negative is symmetric.
    This is the null a fixed macro-F1 threshold must clear on a skewed rubric.

    Args:
        positive_rate: Share of gold labels equal to the best option.

    Returns:
        Macro-F1 of the better of the two constant predictors.
    """
    p = positive_rate
    always_positive = (2 * p / (1 + p)) / 2 if p > 0 else 0.0
    always_negative = (2 * (1 - p) / (2 - p)) / 2 if p < 1 else 0.0
    return max(always_positive, always_negative)


def majority_baselines(examples: list[Example], rubrics: list[Rubric]) -> pd.DataFrame:
    """Per-rubric label skew and the constant-majority macro-F1 it implies.

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics to tabulate.

    Returns:
        Frame with columns ``rubric, n, positive_rate, constant_majority_f1``.
    """
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    rows = []
    for r in rubrics:
        gold = gold_by_rubric[r.key]
        n = len(gold)
        p = sum(1 for v in gold.values() if v == r.best_option) / n if n else np.nan
        rows.append({"rubric": r.key, "n": n, "positive_rate": p,
                     "constant_majority_f1": constant_majority_f1(p) if n else np.nan})
    return pd.DataFrame(rows, columns=["rubric", "n", "positive_rate", "constant_majority_f1"])


def _vote_f1(gold: dict[str, str], votes_by_id: dict[str, list[str | None]], best_option: str) -> float:
    """Majority-vote F1 over evaluation ids, with the product's tie/pending semantics.

    Args:
        gold: Example id → gold label.
        votes_by_id: Example id → one label per voting judge.
        best_option: The rubric's desirable label.

    Returns:
        Macro-F1 over rows that produced a majority verdict; NaN if none did.
    """
    truth, verdicts = [], []
    for example_id, votes in votes_by_id.items():
        method, value = aggregate_votes(votes)
        if method == "majority":
            truth.append(gold[example_id])
            verdicts.append(value)
    return reliability(truth, verdicts, best_option) if truth else np.nan


def baseline_summary(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    judges: tuple[str, ...],
    seed: int = 0,
) -> pd.DataFrame:
    """Reference points for the gated aggregate, on the same calibration draws.

    For each ``(repeat, k, rubric)`` draw in the grid (thresholds collapse, the
    draw is shared): ``ungated`` = majority vote of all judges; ``single_best`` =
    the one judge with the highest calibration macro-F1 (ties → first in
    ``judges``); ``constant_majority`` = always the majority gold label of the
    calibration draw; ``random`` = uniform over the rubric's options.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        predictions: Stage 1 cache.
        judges: Judge names.
        seed: Seed for the random-judge baseline.

    Returns:
        Frame indexed by ``(k, baseline)`` with columns ``mean_f1, sd_f1``:
        F1 is averaged over rubrics within a repeat, then mean/SD over repeats.
    """
    rng = np.random.default_rng(seed)
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    rubric_by_key = {r.key: r for r in rubrics}
    draws = grid[grid["n_calibration"] > 0].drop_duplicates(["repeat", "k", "rubric"])
    rows = []
    for row in draws.itertuples(index=False):
        rubric = rubric_by_key[row.rubric]
        gold = gold_by_rubric[row.rubric]
        calib = row.calibration_ids.split(",")
        eval_ids = [i for i in gold if i not in set(calib)]
        calib_f1 = {j: reliability([gold[i] for i in calib], _predicted(predictions, j, rubric.key, calib), rubric.best_option) for j in judges}
        best_judge = max(judges, key=lambda j: (calib_f1[j], -judges.index(j)))
        majority_label = Counter(gold[i] for i in calib).most_common(1)[0][0]
        per_judge = {j: dict(zip(eval_ids, _predicted(predictions, j, rubric.key, eval_ids))) for j in judges}
        scored = {
            "ungated": _vote_f1(gold, {i: [per_judge[j][i] for j in judges] for i in eval_ids}, rubric.best_option),
            "single_best": _vote_f1(gold, {i: [per_judge[best_judge][i]] for i in eval_ids}, rubric.best_option),
            "constant_majority": reliability([gold[i] for i in eval_ids], [majority_label] * len(eval_ids), rubric.best_option),
            "random": reliability([gold[i] for i in eval_ids], list(rng.choice(rubric.option_values, size=len(eval_ids))), rubric.best_option),
        }
        for name, f1 in scored.items():
            rows.append({"repeat": row.repeat, "k": row.k, "rubric": row.rubric, "baseline": name, "f1": f1})
    frame = pd.DataFrame(rows)
    per_repeat = frame.groupby(["k", "baseline", "repeat"])["f1"].mean()
    return per_repeat.groupby(["k", "baseline"]).agg(mean_f1="mean", sd_f1=lambda s: s.std(ddof=1))


def live_rubrics(
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    judges: tuple[str, ...],
    cutoff: float = 0.2,
) -> set[str]:
    """Rubrics on which at least one judge has full-data κ ≥ ``cutoff``.

    On a "dead" rubric no judge has signal, so the correct gate behaviour is
    to withhold; reporting those rubrics separately stops abstention from
    being scored as failure.

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics to classify.
        predictions: Stage 1 cache.
        judges: Judge names.
        cutoff: Minimum κ for a judge to count as competent.

    Returns:
        The set of live rubric keys.
    """
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    live = set()
    for r in rubrics:
        gold = gold_by_rubric[r.key]
        ids = list(gold)
        if any(judge_kappa([gold[i] for i in ids], _predicted(predictions, j, r.key, ids), r.best_option) >= cutoff for j in judges):
            live.add(r.key)
    return live


def summarise_by_class(grid: pd.DataFrame, live: set[str]) -> pd.DataFrame:
    """Roll the grid up per ``(k, threshold, rubric_class)`` with abstention shown explicitly.

    The means here pool over rubric × repeat cells in one pass, unlike
    :func:`analysis.summarise`, which averages across rubrics within a repeat
    first, so these live/dead means can differ slightly from the prescribed
    table even on the same rows.

    Args:
        grid: Output of :func:`analysis.run_study` (must include ``multi_judge_f1_ties_wrong``).
        live: Rubric keys with at least one competent judge; all others are ``dead``.

    Returns:
        Frame indexed by ``(k, threshold, rubric_class)`` with columns
        ``mean_f1`` (ties dropped), ``mean_f1_ties_wrong``, ``abstain_rate``
        (share of rubric×repeat cells with no judge retained) and ``n_rubrics``.
    """
    rows = grid[grid["n_calibration"] > 0].copy()
    rows["rubric_class"] = np.where(rows["rubric"].isin(live), "live", "dead")
    rows["abstain"] = ~rows["has_sufficient_judges"]
    grouped = rows.groupby(["k", "threshold", "rubric_class"])
    return grouped.agg(
        mean_f1=("multi_judge_f1", "mean"),
        mean_f1_ties_wrong=("multi_judge_f1_ties_wrong", "mean"),
        abstain_rate=("abstain", "mean"),
        n_rubrics=("rubric", "nunique"),
    )

SYNTHETIC_COLUMNS = ["random_pass_rate", "constant_pass_rate", "random_mean_f1", "constant_mean_f1", "n_draws"]


def _synthetic_draw_scores(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    seed: int,
) -> pd.DataFrame:
    """Score a null random judge and a null constant judge on every calibration draw.

    Shared by :func:`synthetic_gate_pass_rates` and
    :func:`synthetic_gate_pass_rates_by_rubric` so both are computed from the
    same per-draw scores (same seed, same rng draw order): on each calibration
    draw in the grid, ``random`` draws uniformly over the rubric's options and
    ``constant`` always predicts the calibration draw's majority gold label,
    scored against gold on the calibration ids only via
    :func:`analysis.reliability`.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        seed: Seed for the random judge, drawn once for the whole call.

    Returns:
        One row per draw with columns ``repeat, k, rubric, random_f1, constant_f1``.
    """
    rng = np.random.default_rng(seed)
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    rubric_by_key = {r.key: r for r in rubrics}
    draws = grid[grid["n_calibration"] > 0].drop_duplicates(["repeat", "k", "rubric"])
    rows = []
    for row in draws.itertuples(index=False):
        rubric = rubric_by_key[row.rubric]
        gold = gold_by_rubric[row.rubric]
        calib = row.calibration_ids.split(",")
        truth = [gold[i] for i in calib]
        random_pred = list(rng.choice(rubric.option_values, size=len(calib)))
        majority_label = Counter(truth).most_common(1)[0][0]
        constant_pred = [majority_label] * len(calib)
        rows.append({
            "repeat": row.repeat,
            "k": row.k,
            "rubric": row.rubric,
            "random_f1": reliability(truth, random_pred, rubric.best_option),
            "constant_f1": reliability(truth, constant_pred, rubric.best_option),
        })
    return pd.DataFrame(rows, columns=["repeat", "k", "rubric", "random_f1", "constant_f1"])


def _synthetic_pass_rates(frame: pd.DataFrame, group_cols: list[str], thresholds: tuple[float, ...]) -> pd.DataFrame:
    """Aggregate :func:`_synthetic_draw_scores` output into pass rates per group × threshold.

    Args:
        frame: Output of :func:`_synthetic_draw_scores`.
        group_cols: Columns of ``frame`` to group draws by (``["k"]`` for the
            pooled table, ``["rubric", "k"]`` for the by-rubric table).
        thresholds: Reliability thresholds to test.

    Returns:
        Frame indexed by ``(*group_cols, threshold)`` with :data:`SYNTHETIC_COLUMNS`.
    """
    per_group = frame.groupby(group_cols).agg(
        random_mean_f1=("random_f1", "mean"),
        constant_mean_f1=("constant_f1", "mean"),
        n_draws=("random_f1", "size"),
    )
    records = []
    for key, r in per_group.iterrows():
        keys = key if isinstance(key, tuple) else (key,)
        mask = pd.Series(True, index=frame.index)
        for col, value in zip(group_cols, keys):
            mask &= frame[col] == value
        group_frame = frame[mask]
        for threshold in thresholds:
            records.append({
                **dict(zip(group_cols, keys)),
                "threshold": threshold,
                "random_pass_rate": (group_frame["random_f1"] >= threshold).mean(),
                "constant_pass_rate": (group_frame["constant_f1"] >= threshold).mean(),
                "random_mean_f1": r["random_mean_f1"],
                "constant_mean_f1": r["constant_mean_f1"],
                "n_draws": int(r["n_draws"]),
            })
    return pd.DataFrame(records, columns=[*group_cols, "threshold", *SYNTHETIC_COLUMNS]).set_index([*group_cols, "threshold"])


def synthetic_gate_pass_rates(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    thresholds: tuple[float, ...],
    seed: int = 0,
) -> pd.DataFrame:
    """How often a judge with no signal clears the gate, at every calibration size.

    Answers the reviewers' claim directly: on each calibration draw in the
    grid, two judges with no real signal are scored against gold on the
    calibration ids only, using the same :func:`analysis.reliability` the gate
    itself uses. ``random`` draws uniformly over the rubric's options;
    ``constant`` always predicts the calibration draw's majority gold label. A
    judge "passes" a threshold when its calibration macro-F1 is ``>=`` that
    threshold, exactly the comparison :func:`analysis._evaluate` makes.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        thresholds: Reliability thresholds to test.
        seed: Seed for the random judge, drawn once for the whole call.

    Returns:
        Frame indexed by ``(k, threshold)`` with :data:`SYNTHETIC_COLUMNS`:
        the two pass-rate columns are the share of draws that pass; the two
        mean-F1 columns are the mean calibration F1 over draws (repeating
        across thresholds for a given ``k``, like ``one_class_rate`` in
        :func:`analysis.summarise`); ``n_draws`` is the number of draws for
        that ``k``.
    """
    frame = _synthetic_draw_scores(grid, examples, rubrics, seed)
    return _synthetic_pass_rates(frame, ["k"], thresholds)


def synthetic_gate_pass_rates_by_rubric(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    thresholds: tuple[float, ...],
    seed: int = 0,
) -> pd.DataFrame:
    """:func:`synthetic_gate_pass_rates`, split out per rubric.

    The pooled table hides the effect that matters: on a near-balanced rubric
    a random judge's expected macro-F1 approaches 0.5, so it clears a 0.5 gate
    about half the time regardless of ``k``, while on a skewed rubric it is
    excluded. Computed from the same per-draw scores as the pooled function
    (same seed, same rng draw order), so the pooled table's numbers are the
    draw-count-weighted mean of this table's, rubric by rubric.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        thresholds: Reliability thresholds to test.
        seed: Seed for the random judge, drawn once for the whole call.

    Returns:
        Frame indexed by ``(rubric, k, threshold)`` with :data:`SYNTHETIC_COLUMNS`.
    """
    frame = _synthetic_draw_scores(grid, examples, rubrics, seed)
    return _synthetic_pass_rates(frame, ["rubric", "k"], thresholds)

def estimator_noise(
    grid: pd.DataFrame,
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    judges: tuple[str, ...],
) -> pd.DataFrame:
    """How noisy a judge's reliability estimate is at each calibration size.

    Recomputes each judge's calibration macro-F1 on every draw in the grid and
    reports, per ``k``, the SD of that estimate across repeats (averaged over
    judge×rubric pairs) and its mean bias against the judge's full-data
    macro-F1. This is the quantity a minimum calibration size is derived from.

    Args:
        grid: Output of :func:`analysis.run_study`.
        examples: Examples with gold labels.
        rubrics: Rubrics in the grid.
        predictions: Stage 1 cache.
        judges: Judge names.

    Returns:
        Frame indexed by ``k`` with columns ``sd_calibration_f1``,
        ``bias_calibration_f1`` and ``n_pairs``.
    """
    gold_by_rubric = _gold_by_rubric(examples, rubrics)
    best = {r.key: r.best_option for r in rubrics}
    full = {
        (r.key, j): reliability(list(gold_by_rubric[r.key].values()), _predicted(predictions, j, r.key, list(gold_by_rubric[r.key])), r.best_option)
        for r in rubrics for j in judges
    }
    draws = grid[grid["n_calibration"] > 0].drop_duplicates(["repeat", "k", "rubric"])
    rows = []
    for row in draws.itertuples(index=False):
        calib = row.calibration_ids.split(",")
        gold = gold_by_rubric[row.rubric]
        for j in judges:
            f1 = reliability([gold[i] for i in calib], _predicted(predictions, j, row.rubric, calib), best[row.rubric])
            rows.append({"k": row.k, "rubric": row.rubric, "judge": j, "f1": f1, "full": full[(row.rubric, j)]})
    frame = pd.DataFrame(rows)
    per_pair = frame.groupby(["k", "rubric", "judge"]).agg(sd=("f1", lambda s: s.std(ddof=1)), mean=("f1", "mean"), full=("full", "first"))
    per_pair["bias"] = per_pair["mean"] - per_pair["full"]
    return per_pair.groupby("k").agg(sd_calibration_f1=("sd", "mean"), bias_calibration_f1=("bias", "mean"), n_pairs=("sd", "size"))
