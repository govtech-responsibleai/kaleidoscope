"""Stage 2: calibration-size × threshold sweep over cached judge predictions.

No LLM calls and no database. The reliability metric and the majority-vote
semantics deliberately mirror ``MetricsService.calculate_judge_alignment`` and
``_resolve_row_aggregate`` in the product so the study measures what
Kaleidoscope actually does.
"""

from __future__ import annotations

import math
from collections import Counter

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score
from sklearn.model_selection import train_test_split

from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.predict import PredictionKey, PredictionRecord
from experiments.rubricbench_calibration.rubrics import Rubric

Predictions = dict[PredictionKey, PredictionRecord]

TIE = "__tie__"

GRID_COLUMNS = [
    "repeat", "k", "threshold", "rubric", "n_calibration", "n_eval",
    "n_calib_positive", "n_calib_negative", "stratified",
    "n_judges_retained", "retained_judges", "has_sufficient_judges",
    "multi_judge_f1", "multi_judge_f1_ties_wrong", "tie_rate", "no_judge_rate", "calibration_ids",
]


def reliability(y_true: list[str], y_pred: list[str | None], best_option: str) -> float:
    """Macro-F1 of a judge against gold labels, positive class = ``best_option``.

    Pairs with a missing prediction are dropped, matching the product.

    Args:
        y_true: Gold labels.
        y_pred: Judge labels (``None`` = missing).
        best_option: The rubric's desirable label.

    Returns:
        Macro-F1 in [0, 1]; 0.0 when nothing can be compared.
    """
    pairs = [(t == best_option, p == best_option) for t, p in zip(y_true, y_pred) if p is not None]
    if not pairs:
        return 0.0
    truth, pred = zip(*pairs)
    return float(f1_score(truth, pred, average="macro", zero_division=0))


def reliability_ties_wrong(y_true: list[str], y_pred: list[str], best_option: str, tie_marker: str = TIE) -> float:
    """Macro-F1 where a tied verdict is scored as the wrong label.

    A tie is a row on which the product would ask a human; counting it as
    wrong gives a lower bound that does not reward the gate for discarding
    hard cases. Rows are never dropped here, so pass only rows that have a
    verdict or a tie (not pending/no-judge rows).

    Args:
        y_true: Gold labels.
        y_pred: Verdicts, with ``tie_marker`` for tied rows.
        best_option: The rubric's desirable label.

    Returns:
        Macro-F1 in [0, 1]; 0.0 when empty.
    """
    if not y_true:
        return 0.0
    truth = [t == best_option for t in y_true]
    pred = [(not truth[i]) if p == tie_marker else (p == best_option) for i, p in enumerate(y_pred)]
    return float(f1_score(truth, pred, average="macro", zero_division=0))


def aggregate_votes(votes: list[str | None]) -> tuple[str, str | None]:
    """Majority vote with the product's tie and missing-score semantics.

    Args:
        votes: One label per retained judge (``None`` = missing score).

    Returns:
        ``(method, value)`` where method is one of ``no_aligned_judge``,
        ``pending``, ``majority_tied``, ``majority``.
    """
    if not votes:
        return "no_aligned_judge", None
    if any(v is None for v in votes):
        return "pending", None
    ranked = Counter(votes).most_common()
    if len(ranked) > 1 and ranked[0][1] == ranked[1][1]:
        return "majority_tied", None
    return "majority", ranked[0][0]


def stratified_split(
    ids: list[str],
    labels: list[str],
    k: int,
    random_state: int,
    stratify: bool = True,
) -> tuple[list[str], list[str], bool]:
    """Split ids into a calibration set of size ``k`` and the remainder.

    Tries a label-stratified split first and falls back to a plain random split
    when a class is too small to stratify. With ``stratify=False`` the split is
    plain random from the start, which is what an annotator labelling whatever
    comes produces.

    Args:
        ids: Example ids to split.
        labels: Gold label for each id, same order as ``ids``.
        k: Size of the calibration split.
        random_state: Seed passed to ``train_test_split``.
        stratify: Whether to attempt a stratified split.

    Returns:
        ``(calibration_ids, evaluation_ids, stratified)``.
    """
    if stratify:
        try:
            calib, evaluation = train_test_split(ids, train_size=k, stratify=labels, random_state=random_state)
            return list(calib), list(evaluation), True
        except ValueError:
            pass
    calib, evaluation = train_test_split(ids, train_size=k, random_state=random_state)
    return list(calib), list(evaluation), False


def _label(predictions: Predictions, judge: str, rubric: str, example_id: str) -> str | None:
    """Look up one judge's prediction for one example, or ``None`` if missing.

    Args:
        predictions: Stage 1 prediction cache.
        judge: Judge name.
        rubric: Rubric key.
        example_id: Example id.

    Returns:
        The judge's chosen option, or ``None`` if no record exists.
    """
    record = predictions.get((judge, rubric, example_id))
    return record.chosen_option if record else None


def _labelled_ids(examples: list[Example], rubric: Rubric) -> tuple[list[str], list[str]]:
    """Collect ids and gold labels for examples that have a gold label for ``rubric``.

    Args:
        examples: Examples to filter.
        rubric: Rubric whose gold labels to read.

    Returns:
        ``(ids, labels)`` in matching order, restricted to non-``None`` gold labels.
    """
    ids = [e.example_id for e in examples if e.gold[rubric.key] is not None]
    labels = [e.gold[rubric.key] for e in examples if e.gold[rubric.key] is not None]
    return ids, labels


def _shared_candidate_ids(examples: list[Example], rubrics: list[Rubric]) -> tuple[list[str], list[str]]:
    """Collect ids that have a gold label for every rubric, for ``shared`` sampling.

    Drawing the shared calibration sample only from ids labelled on all rubrics
    guarantees every rubric can actually calibrate on ``k`` examples; drawing from
    one rubric's ids and filtering per-rubric afterwards (the previous approach)
    could silently shrink a sparser rubric's calibration set below ``k``.

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics that must all have a gold label for a candidate id.

    Returns:
        ``(ids, labels)`` in ``examples`` order, restricted to ids labelled for
        every rubric; ``labels`` is the first rubric's gold label for each id,
        used to stratify the shared draw.
    """
    ids = [e.example_id for e in examples if all(e.gold[r.key] is not None for r in rubrics)]
    labels = [e.gold[rubrics[0].key] for e in examples if all(e.gold[r.key] is not None for r in rubrics)]
    return ids, labels


def _evaluate(
    rubric: Rubric,
    gold: dict[str, str],
    predictions: Predictions,
    judges: tuple[str, ...],
    calib_ids: list[str],
    eval_ids: list[str],
    threshold: float,
) -> dict:
    """Score one (rubric, k-sample, threshold) cell of the grid.

    Args:
        rubric: Rubric being evaluated.
        gold: Example id to gold label, for this rubric.
        predictions: Stage 1 prediction cache.
        judges: Judge names to consider for retention.
        calib_ids: Example ids used to measure each judge's reliability.
        eval_ids: Example ids used to measure the resulting multi-judge F1.
        threshold: Minimum calibration reliability for a judge to be retained.

    Returns:
        A dict of grid metric columns (everything except the ``base`` identity
        columns and ``n_calibration``/``n_eval``/``stratified``/``calibration_ids``),
        including ``n_calib_positive`` and ``n_calib_negative``: counts of
        ``calib_ids`` whose gold label equals / does not equal ``rubric.best_option``
        (a one-class calibration sample has one of these at 0).
    """
    scores = {
        judge: reliability(
            [gold[i] for i in calib_ids],
            [_label(predictions, judge, rubric.key, i) for i in calib_ids],
            rubric.best_option,
        )
        for judge in judges
    }
    retained = tuple(j for j in judges if scores[j] >= threshold)
    ties = no_judge = 0
    truth: list[str] = []
    verdicts: list[str] = []
    truth_with_ties: list[str] = []
    verdicts_with_ties: list[str] = []
    for example_id in eval_ids:
        method, value = aggregate_votes([_label(predictions, j, rubric.key, example_id) for j in retained])
        if method == "majority":
            truth.append(gold[example_id])
            verdicts.append(value)
            truth_with_ties.append(gold[example_id])
            verdicts_with_ties.append(value)
        elif method == "majority_tied":
            ties += 1
            truth_with_ties.append(gold[example_id])
            verdicts_with_ties.append(TIE)
        else:
            no_judge += 1
    n_eval = len(eval_ids)
    n_calib_positive = sum(1 for i in calib_ids if gold[i] == rubric.best_option)
    return {
        "n_judges_retained": len(retained),
        "retained_judges": "|".join(retained),
        "has_sufficient_judges": bool(retained),
        "multi_judge_f1": reliability(truth, verdicts, rubric.best_option) if truth else math.nan,
        "multi_judge_f1_ties_wrong": reliability_ties_wrong(truth_with_ties, verdicts_with_ties, rubric.best_option) if truth_with_ties else math.nan,
        "tie_rate": ties / n_eval if n_eval else math.nan,
        "no_judge_rate": no_judge / n_eval if n_eval else math.nan,
        "n_calib_positive": n_calib_positive,
        "n_calib_negative": len(calib_ids) - n_calib_positive,
    }


def run_study(
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    config: StudyConfig,
) -> pd.DataFrame:
    """Run the full repeat × k × threshold × rubric grid.

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics to evaluate.
        predictions: Stage 1 cache.
        config: Study configuration.

    In ``shared`` sampling, the calibration sample of size ``k`` is drawn once per
    ``(repeat, k)`` from the ids that carry a gold label for *every* rubric (see
    :func:`_shared_candidate_ids`), so every rubric always calibrates on exactly
    ``k`` examples. Each rubric then evaluates on all of its own labelled ids that
    were not drawn into that shared calibration sample (which may include ids
    other rubrics lack a label for).

    Returns:
        One row per ``(repeat, k, threshold, rubric)`` with :data:`GRID_COLUMNS`.
    """
    rows: list[dict] = []
    gold_by_rubric = {r.key: {e.example_id: e.gold[r.key] for e in examples if e.gold[r.key] is not None} for r in rubrics}
    for repeat in range(config.repeats):
        rng = np.random.default_rng(config.seed + repeat)
        for k in config.calibration_sizes:
            shared_split: tuple[list[str], list[str], bool] | None = None
            if config.sampling == "shared":
                candidate_ids, candidate_labels = _shared_candidate_ids(examples, rubrics)
                if k < len(candidate_ids):
                    shared_split = stratified_split(candidate_ids, candidate_labels, k, int(rng.integers(0, 2**31 - 1)))
            for rubric in rubrics:
                gold = gold_by_rubric[rubric.key]
                ids, labels = _labelled_ids(examples, rubric)
                if config.sampling == "shared":
                    if shared_split is None:
                        split = None
                    else:
                        calib = shared_split[0]
                        calib_set = set(calib)
                        evaluation = [i for i in ids if i not in calib_set]
                        split = (calib, evaluation, shared_split[2])
                else:
                    split = (
                        stratified_split(ids, labels, k, int(rng.integers(0, 2**31 - 1)),
                                         stratify=config.sampling != "unstratified")
                        if k < len(ids) else None
                    )
                base = {"repeat": repeat, "k": k, "rubric": rubric.key}
                if split is None or not split[1]:
                    for threshold in config.thresholds:
                        rows.append({**base, "threshold": threshold, "n_calibration": 0, "n_eval": 0,
                                     "n_calib_positive": 0, "n_calib_negative": 0,
                                     "stratified": False, "n_judges_retained": 0, "retained_judges": "",
                                     "has_sufficient_judges": False, "multi_judge_f1": math.nan,
                                     "multi_judge_f1_ties_wrong": math.nan,
                                     "tie_rate": math.nan, "no_judge_rate": math.nan, "calibration_ids": ""})
                    continue
                calib_ids, eval_ids, stratified = split
                for threshold in config.thresholds:
                    metrics = _evaluate(rubric, gold, predictions, config.judges, calib_ids, eval_ids, threshold)
                    rows.append({**base, "threshold": threshold, "n_calibration": len(calib_ids),
                                 "n_eval": len(eval_ids), "stratified": stratified,
                                 "calibration_ids": ",".join(sorted(calib_ids)), **metrics})
    return pd.DataFrame(rows, columns=GRID_COLUMNS)


def summarise(grid: pd.DataFrame) -> pd.DataFrame:
    """Roll the grid up to one row per ``(k, threshold)``.

    F1 is first averaged across rubrics within a repeat, then mean, SD and 95% CI
    are taken across repeats. The remaining columns are plain means over all rows.

    ``mean_f1`` NaN-skips rubrics that produced no verdict rows (``multi_judge_f1``
    is NaN), so it can rise at high thresholds purely because weak rubrics drop
    out of the average. ``mean_f1_penalised`` is the same computation but treats
    a rubric that had evaluation rows and no verdict (``n_eval > 0`` and
    ``multi_judge_f1`` NaN) as an F1 of 0.0 instead of dropping it; rows that are
    structurally empty (``n_eval == 0``, e.g. ``k`` too large for the rubric) stay
    NaN in both columns, since there is nothing to penalise.

    ``one_class_rate`` is the share of rows with a non-empty calibration sample
    (``n_calibration > 0``) whose calibration sample contains only one label
    class (``n_calib_positive == 0`` or ``n_calib_negative == 0``). The draw does
    not depend on the threshold, so the value repeats across the thresholds of a
    given ``k``.

    Args:
        grid: Output of :func:`run_study`.

    Returns:
        A frame indexed by ``(k, threshold)`` with columns ``mean_f1``, ``sd_f1``,
        ``ci95_f1``, ``mean_f1_penalised``, ``mean_f1_ties_wrong``,
        ``avg_judges_retained``, ``rubric_coverage``, ``tie_rate``,
        ``no_judge_rate``, ``one_class_rate``, ``n_repeats``.
    """
    per_repeat = grid.groupby(["k", "threshold", "repeat"])["multi_judge_f1"].mean()
    grouped = per_repeat.groupby(["k", "threshold"])
    f1 = grouped.agg(mean_f1="mean", sd_f1=lambda s: s.std(ddof=1), n_repeats="count")
    f1["ci95_f1"] = 1.96 * f1["sd_f1"] / np.sqrt(f1["n_repeats"])
    f1.loc[f1["n_repeats"] <= 1, "ci95_f1"] = math.nan

    penalised = grid.copy()
    no_verdict = penalised["n_eval"].gt(0) & penalised["multi_judge_f1"].isna()
    penalised.loc[no_verdict, "multi_judge_f1"] = 0.0
    per_repeat_penalised = penalised.groupby(["k", "threshold", "repeat"])["multi_judge_f1"].mean()
    f1["mean_f1_penalised"] = per_repeat_penalised.groupby(["k", "threshold"]).mean()

    per_repeat_ties_wrong = grid.groupby(["k", "threshold", "repeat"])["multi_judge_f1_ties_wrong"].mean()
    f1["mean_f1_ties_wrong"] = per_repeat_ties_wrong.groupby(["k", "threshold"]).mean()

    with_one_class = grid.copy()
    with_one_class["one_class"] = np.where(
        with_one_class["n_calibration"] > 0,
        (with_one_class["n_calib_positive"] == 0) | (with_one_class["n_calib_negative"] == 0),
        np.nan,
    )
    rest = with_one_class.groupby(["k", "threshold"]).agg(
        avg_judges_retained=("n_judges_retained", "mean"),
        rubric_coverage=("has_sufficient_judges", "mean"),
        tie_rate=("tie_rate", "mean"),
        no_judge_rate=("no_judge_rate", "mean"),
        one_class_rate=("one_class", "mean"),
    )
    return f1.join(rest)[[
        "mean_f1", "sd_f1", "ci95_f1", "mean_f1_penalised", "mean_f1_ties_wrong",
        "avg_judges_retained", "rubric_coverage", "tie_rate", "no_judge_rate", "one_class_rate", "n_repeats",
    ]]


def summarise_by_rubric(grid: pd.DataFrame) -> pd.DataFrame:
    """Roll the grid up to one row per ``(rubric, k, threshold)``.

    ``one_class_rate`` is the share of rows, among those with a non-empty
    calibration sample (``n_calibration > 0``), whose calibration sample
    contains no minority-label example (``n_calib_positive == 0`` or
    ``n_calib_negative == 0``). At small ``k`` a stratified draw can still land
    a one-class sample on a heavily skewed rubric; macro-F1 calibrated on such
    a sample behaves very differently from binary F1.

    Args:
        grid: Output of :func:`run_study`.

    Returns:
        A frame indexed by ``(rubric, k, threshold)`` with columns ``mean_f1``,
        ``sd_f1``, ``avg_judges_retained``, ``rubric_coverage``, ``tie_rate``,
        ``no_judge_rate``, ``one_class_rate``.
    """
    grid = grid.copy()
    has_calibration = grid["n_calibration"] > 0
    grid["one_class"] = np.where(
        has_calibration,
        (grid["n_calib_positive"] == 0) | (grid["n_calib_negative"] == 0),
        np.nan,
    )
    return grid.groupby(["rubric", "k", "threshold"]).agg(
        mean_f1=("multi_judge_f1", "mean"),
        sd_f1=("multi_judge_f1", lambda s: s.std(ddof=1)),
        avg_judges_retained=("n_judges_retained", "mean"),
        rubric_coverage=("has_sufficient_judges", "mean"),
        tie_rate=("tie_rate", "mean"),
        no_judge_rate=("no_judge_rate", "mean"),
        one_class_rate=("one_class", "mean"),
    )


def full_reliability(
    examples: list[Example],
    rubrics: list[Rubric],
    predictions: Predictions,
    judges: tuple[str, ...],
) -> pd.DataFrame:
    """Each judge's macro-F1 per rubric on every labelled example (context only).

    Args:
        examples: Examples with gold labels.
        rubrics: Rubrics to evaluate.
        predictions: Stage 1 cache.
        judges: Judge names to report on.

    Returns:
        A frame with columns ``rubric``, ``judge``, ``macro_f1``, ``n``.
    """
    rows = []
    for rubric in rubrics:
        ids, labels = _labelled_ids(examples, rubric)
        for judge in judges:
            preds = [_label(predictions, judge, rubric.key, i) for i in ids]
            rows.append({"rubric": rubric.key, "judge": judge,
                         "macro_f1": reliability(labels, preds, rubric.best_option),
                         "n": sum(p is not None for p in preds)})
    return pd.DataFrame(rows, columns=["rubric", "judge", "macro_f1", "n"])
