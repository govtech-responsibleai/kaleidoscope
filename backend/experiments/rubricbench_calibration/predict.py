"""Stage 1: collect judge predictions for every judge × rubric × example.

Predictions are appended to a JSONL cache as they arrive. Re-running skips
successful cached rows and retries failed ones, so a long run can be resumed.
Human labels are never read here.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.rubrics import Rubric
from src.common.config import MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE
from src.common.llm import CostTracker, LLMClient
from src.common.llm.provider_service import resolve_model_runtime_config_from_env
from src.common.models import RubricJudgmentResult
from src.common.prompts import render_template
from src.scoring.services.judge_scoring import ENGLISH_OUTPUT_DIRECTIVE

logger = logging.getLogger(__name__)

PredictionKey = tuple[str, str, str]
ClientFactory = Callable[[str], LLMClient]

LABEL_FIELDS = ("judge", "rubric", "example_id", "chosen_option", "temperature", "model")


@dataclass
class PredictionRecord:
    """One judge verdict on one example for one rubric.

    The trailing fields default so a stripped labels-only row (see
    :func:`write_label_cache`) can still be loaded: only :data:`LABEL_FIELDS`
    are guaranteed to be populated on a record read from the labels cache.
    """

    judge: str
    rubric: str
    example_id: str
    chosen_option: str | None
    raw_option: str | None = None
    explanation: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    model: str | None = None
    error: str | None = None
    temperature: float | None = None

    @property
    def key(self) -> PredictionKey:
        """Identity of this prediction in the cache."""
        return (self.judge, self.rubric, self.example_id)

    def to_json(self) -> dict:
        """Serialisable dict."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "PredictionRecord":
        """Inverse of :meth:`to_json`."""
        return cls(**data)


def build_prompt(rubric: Rubric, example: Example) -> str:
    """Render the product's rubric judge prompt for one example."""
    prompt = render_template(
        "default_rubric_judge.md",
        question_text=example.question,
        answer_text=example.answer,
        rubric_name=rubric.name,
        rubric_criteria=rubric.criteria,
        rubric_options=rubric.options_as_dicts(),
    )
    return prompt + ENGLISH_OUTPUT_DIRECTIVE


def load_predictions(path: Path, fallback: Path | None = None) -> dict[PredictionKey, PredictionRecord]:
    """Read the JSONL cache; later rows for the same key win.

    RubricBench is a gated dataset, so the full cache at ``path`` (which holds
    judge explanations) is not committed. ``analyze`` passes the committed
    labels-only cache written by :func:`write_label_cache` as ``fallback`` so
    it can rerun without the platform. ``predict`` passes no fallback: on a
    fresh clone it must start from scratch rather than treat the labels cache
    as already-scored rows.

    Args:
        path: Path of the full prediction cache.
        fallback: Optional labels-only cache read when ``path`` is missing.

    Returns:
        Records keyed by ``(judge, rubric, example_id)``; empty when neither
        file exists.
    """
    if not path.exists():
        if fallback is not None and fallback.exists():
            path = fallback
        else:
            return {}
    records: dict[PredictionKey, PredictionRecord] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                record = PredictionRecord.from_json(json.loads(line))
                records[record.key] = record
    return records


def write_label_cache(predictions: dict[PredictionKey, PredictionRecord], path: Path) -> int:
    """Write a stripped, committable cache of judge labels only.

    RubricBench is a gated dataset, so the full prediction cache (which holds
    judge explanations quoting the dataset's questions and answers) cannot be
    committed. This writes only :data:`LABEL_FIELDS` per record, which lets
    ``analyze`` rerun from a committed cache without redistributing the
    dataset's content.

    Args:
        predictions: Stage 1 prediction cache.
        path: Output path; the parent directory is created if missing.

    Returns:
        The number of rows written.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [r for r in predictions.values() if r.error is None]
    rows.sort(key=lambda r: r.key)
    with path.open("w", encoding="utf-8") as handle:
        for record in rows:
            data = record.to_json()
            handle.write(json.dumps({field: data[field] for field in LABEL_FIELDS}) + "\n")
    return len(rows)


def default_client_factory(judge: str) -> LLMClient:
    """Build a client for a catalog model using shared env credentials."""
    return LLMClient.from_runtime_config(resolve_model_runtime_config_from_env(judge))


def effective_temperature(model: str, requested: float) -> float:
    """Resolve the temperature ``LLMClient`` will actually use for ``model``.

    Mirrors ``LLMClient``'s fixed-temperature override: models matching a
    keyword in ``MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE`` are always run at
    temperature 1.0 in the product, regardless of what was requested.

    Args:
        model: Catalog-facing model name (e.g. ``govtech/gpt-5.6-luna``).
        requested: Temperature the caller asked for.

    Returns:
        ``1.0`` if any fixed-temperature keyword is a substring of ``model``,
        else ``requested``.
    """
    if any(keyword in model for keyword in MODEL_KEYWORDS_WITH_FIXED_TEMPERATURE):
        return 1.0
    return requested


async def _predict_one(
    client: LLMClient,
    judge: str,
    rubric: Rubric,
    example: Example,
    temperature: float,
) -> PredictionRecord:
    """Get one judge's verdict on one example for one rubric.

    Failures are caught and recorded on the returned record rather than
    raised, so a batch run can keep going and a rerun can retry just the
    failed rows.

    Args:
        client: LLM client for this judge.
        judge: Catalog-facing model name, stored on the record for the cache key.
        rubric: Rubric to score the example against.
        example: Example being judged; its gold label is not read.
        temperature: Sampling temperature for the judge call.

    Returns:
        A ``PredictionRecord``. On success ``error`` is ``None``; on failure
        ``error`` is set to a non-empty message describing the exception. In
        both cases ``temperature`` records what ``LLMClient`` actually used
        (see :func:`effective_temperature`), not necessarily ``temperature``
        as passed in.
    """
    actual_temperature = effective_temperature(judge, temperature)
    try:
        result, metadata = await client.generate_structured_async(
            prompt=build_prompt(rubric, example),
            response_model=RubricJudgmentResult,
            temperature=temperature,
            metadata={"generation_name": "rubricbench-judge", "tags": ["experiment", "rubricbench"]},
        )
    except Exception as exc:  # noqa: BLE001 - any failure is recorded, not raised
        logger.warning("Judge %s failed on %s/%s: %s", judge, rubric.key, example.example_id, exc)
        error = str(exc) or type(exc).__name__
        return PredictionRecord(
            judge, rubric.key, example.example_id, None, None, None, 0, 0, 0.0, None, error,
            temperature=actual_temperature,
        )
    return PredictionRecord(
        judge=judge,
        rubric=rubric.key,
        example_id=example.example_id,
        chosen_option=rubric.canonicalize(result.chosen_option),
        raw_option=result.chosen_option,
        explanation=result.explanation,
        prompt_tokens=int(metadata.get("prompt_tokens", 0)),
        completion_tokens=int(metadata.get("completion_tokens", 0)),
        cost=float(metadata.get("cost", 0.0)),
        model=metadata.get("model"),
        error=None,
        temperature=actual_temperature,
    )


async def run_predictions(
    config: StudyConfig,
    rubrics: list[Rubric],
    examples: list[Example],
    path: Path,
    client_factory: ClientFactory | None = None,
    judges: tuple[str, ...] | None = None,
) -> dict[PredictionKey, PredictionRecord]:
    """Fill the prediction cache for every judge × rubric × example.

    Args:
        config: Study configuration (temperature, judges).
        rubrics: Rubrics to score.
        examples: Examples to score; gold labels are ignored.
        path: JSONL cache path.
        client_factory: Builds an ``LLMClient`` per judge; defaults to env credentials.
        judges: Subset of ``config.judges`` to run; defaults to all.

    Returns:
        All cached predictions after this run, keyed by (judge, rubric, example_id).
    """
    factory = client_factory or default_client_factory
    cached = load_predictions(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    pending: list[tuple[str, Rubric, Example]] = [
        (judge, rubric, example)
        for judge in (judges or config.judges)
        for rubric in rubrics
        for example in examples
        if (existing := cached.get((judge, rubric.key, example.example_id))) is None or existing.error is not None
    ]
    logger.info("%d predictions cached, %d to run", len(cached), len(pending))
    if not pending:
        return cached

    clients = {judge: factory(judge) for judge in {item[0] for item in pending}}
    trackers = {judge: CostTracker() for judge in clients}
    tasks = [
        asyncio.create_task(_predict_one(clients[judge], judge, rubric, example, config.temperature))
        for judge, rubric, example in pending
    ]
    with path.open("a", encoding="utf-8") as handle:
        for future in asyncio.as_completed(tasks):
            record = await future
            cached[record.key] = record
            handle.write(json.dumps(record.to_json()) + "\n")
            handle.flush()
            if record.error is None:
                trackers[record.judge].add_call(record.to_json())
    for judge, tracker in trackers.items():
        tracker.log_summary(prefix=judge)
    failures = sum(1 for r in cached.values() if r.error)
    if failures:
        logger.warning("%d predictions failed; rerun `predict` to retry them", failures)
    return cached
