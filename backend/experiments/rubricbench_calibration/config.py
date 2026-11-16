"""Configuration for the RubricBench calibration-size × threshold study."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

EXPERIMENT_DIR = Path(__file__).resolve().parent

SamplingMode = Literal["per_rubric", "shared", "unstratified"]
DisagreementPolicy = Literal["exclude", "annotator_1", "annotator_2"]


@dataclass(frozen=True)
class StudyConfig:
    """All knobs for the study. Defaults reproduce the EMNLP feedback protocol.

    Attributes:
        judges: Catalog-facing model names used as judges.
        calibration_sizes: Values of ``k`` (human-labelled examples) to test.
        thresholds: Reliability (macro-F1) cut-offs to test.
        repeats: Number of random calibration samples per ``k``.
        seed: Base random seed; repeat ``r`` uses ``seed + r``.
        sampling: ``per_rubric`` draws a stratified sample per rubric;
            ``shared`` draws one sample of example ids used by all rubrics;
            ``unstratified`` draws a plain random sample per rubric (no class
            balancing), the regime a real annotator produces.
        disagreement_policy: How to resolve the two annotators into one gold label.
        dataset_id: HuggingFace dataset id.
        dataset_split: Split name, or ``None`` to use the first available split.
        column_map: Optional overrides for column detection. Keys: ``id``,
            ``question``, ``answer``, ``context``, and ``labels.<rubric_key>``
            (a column name or list of column names, one per annotator).
        temperature: Sampling temperature for judge calls.
        output_dir: Where reports are written; the prediction cache is always
            ``EXPERIMENT_DIR / 'outputs' / 'predictions.jsonl'``.
        coverage_floor: Minimum rubric coverage for a threshold to be eligible in
            the automatic per-``k`` recommendation line.
        headline_exclude: Rubric keys reported only in the appendix because the
            product judge prompt cannot see the knowledge base they need.
        truth_cutoff: Full-/held-out-data κ at or above which a judge counts as
            truly aligned in the gate diagnostics.
    """

    judges: tuple[str, ...] = (
        "govtech/gpt-5.6-luna",
        "govtech/bedrock.claude-haiku-4-5",
        "govtech/gemini-3.5-flash-lite",
    )
    calibration_sizes: tuple[int, ...] = (10, 20, 30, 40, 50)
    thresholds: tuple[float, ...] = (0.3, 0.4, 0.5, 0.6, 0.7)
    repeats: int = 200
    seed: int = 42
    sampling: SamplingMode = "per_rubric"
    disagreement_policy: DisagreementPolicy = "exclude"
    dataset_id: str = "govtech/RubricBench"
    dataset_split: str | None = None
    column_map: dict[str, str | list[str]] = field(default_factory=dict)
    temperature: float = 0.0
    output_dir: Path = EXPERIMENT_DIR / "outputs"
    coverage_floor: float = 0.9
    headline_exclude: tuple[str, ...] = ("faithfulness", "context_recall")
    truth_cutoff: float = 0.2

    @property
    def predictions_path(self) -> Path:
        """Path of the Stage 1 prediction cache (shared by every sampling mode)."""
        return EXPERIMENT_DIR / "outputs" / "predictions.jsonl"

    @property
    def labels_path(self) -> Path:
        """Path of the committed, labels-only Stage 1 cache (shared by every sampling mode).

        Unlike :attr:`predictions_path`, this file holds only judge labels (no
        explanations), so it can be committed even though RubricBench is a
        gated dataset; see ``predict.write_label_cache``.
        """
        return EXPERIMENT_DIR / "outputs" / "predictions_labels.jsonl"
