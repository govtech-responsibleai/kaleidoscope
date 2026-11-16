"""Load RubricBench and normalise it into per-example gold labels.

Column names in the HuggingFace release are not documented, so detection is
heuristic (rubric key in the column name, then label vocabulary) with explicit
overrides via ``StudyConfig.column_map``. Run ``run.py inspect`` to see what
was detected before spending money on predictions.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterable

from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.rubrics import Rubric

if TYPE_CHECKING:
    from datasets import Dataset

logger = logging.getLogger(__name__)

QUESTION_CANDIDATES = ("question", "query", "prompt", "user_query", "user_input", "input")
ANSWER_CANDIDATES = ("answer", "response", "chatbot_response", "bot_response", "output", "completion")
CONTEXT_CANDIDATES = ("context", "knowledge_base", "retrieved_context", "all_citations", "citations", "kb", "sources")
ID_CANDIDATES = ("id", "example_id", "sample_id", "qa_id", "idx", "index")


@dataclass(frozen=True)
class Example:
    """One RubricBench question-answer pair with resolved gold labels.

    Attributes:
        example_id: Stable string id.
        question: User question.
        answer: Chatbot answer being judged.
        gold: Rubric key to gold label; ``None`` when no usable label exists.
        context: Optional knowledge-base text when the dataset provides it.
    """

    example_id: str
    question: str
    answer: str
    gold: dict[str, str | None]
    context: str | None = None


@dataclass(frozen=True)
class ColumnMap:
    """Resolved column names for one dataset layout."""

    id: str | None
    question: str
    answer: str
    context: str | None
    labels: dict[str, list[str]] = field(default_factory=dict)


def _slug(name: str) -> str:
    """Lower-case a name and collapse non-alphanumeric runs into single underscores.

    Args:
        name: Raw column or rubric name.

    Returns:
        The slugified name.
    """
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def _tokens(name: str) -> list[str]:
    """Split a slugged name into its underscore-separated tokens.

    Args:
        name: Raw column or rubric name.

    Returns:
        The non-empty tokens of ``_slug(name)``.
    """
    return [token for token in _slug(name).split("_") if token]


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    """Check whether ``needle`` occurs as a contiguous sub-sequence of ``haystack``.

    Args:
        haystack: Tokens to search within.
        needle: Tokens to search for, in order.

    Returns:
        ``True`` if ``needle`` is a non-empty contiguous sub-sequence of ``haystack``.
    """
    if not needle:
        return False
    span = len(needle)
    return any(haystack[i : i + span] == needle for i in range(len(haystack) - span + 1))


def _first_match(column_names: list[str], candidates: tuple[str, ...]) -> str | None:
    """Find the dataset column whose slug matches the first present candidate slug.

    Args:
        column_names: Dataset column names.
        candidates: Candidate slugs to look for, in priority order.

    Returns:
        The matching original column name, or ``None`` if no candidate matched.
    """
    slugs = {_slug(name): name for name in column_names}
    for candidate in candidates:
        if candidate in slugs:
            return slugs[candidate]
    return None


def _columns_by_key(column_names: list[str], rubric: Rubric, taken: set[str]) -> list[str]:
    """Find unclaimed columns whose tokens contain the rubric's key or name as a sub-sequence.

    Args:
        column_names: Dataset column names.
        rubric: Rubric to match column tokens against.
        taken: Columns already claimed by a reserved field or an earlier rubric.

    Returns:
        Matching column names, sorted.
    """
    key_tokens = _tokens(rubric.key)
    name_tokens = _tokens(rubric.name)
    matches = [
        name for name in column_names
        if name not in taken
        and (_contains_tokens(_tokens(name), key_tokens) or _contains_tokens(_tokens(name), name_tokens))
    ]
    return sorted(matches)


def _columns_by_vocab(column_names: list[str], sample_rows: list[dict], rubric: Rubric, taken: set[str]) -> list[str]:
    """Find unclaimed columns whose sampled values all fall within the rubric's option vocabulary.

    Args:
        column_names: Dataset column names.
        sample_rows: Sample rows used to inspect column values.
        rubric: Rubric whose option vocabulary to match against.
        taken: Columns already claimed by a reserved field or an earlier rubric.

    Returns:
        Matching column names, sorted.
    """
    if not sample_rows:
        return []
    vocab = {v.lower() for v in rubric.option_values}
    matches: list[str] = []
    for name in column_names:
        if name in taken:
            continue
        values = {
            str(label).strip().lower()
            for row in sample_rows
            for label in expand_annotations(row.get(name))
            if label not in (None, "")
        }
        if values and values <= vocab:
            matches.append(name)
    return sorted(matches)


def detect_columns(
    column_names: list[str],
    sample_rows: list[dict],
    rubrics: list[Rubric],
    overrides: dict[str, Any],
) -> ColumnMap:
    """Work out which columns hold the question, answer, and per-rubric labels.

    Args:
        column_names: Dataset column names.
        sample_rows: A few rows used for vocabulary-based detection.
        rubrics: Rubrics whose label columns must be found.
        overrides: ``StudyConfig.column_map`` entries; keys ``id``, ``question``,
            ``answer``, ``context`` and ``labels.<rubric_key>``.

    Returns:
        The resolved column map.

    Raises:
        ValueError: If the question, answer, or any rubric's labels cannot be found.
    """
    question = overrides.get("question") or _first_match(column_names, QUESTION_CANDIDATES)
    answer = overrides.get("answer") or _first_match(column_names, ANSWER_CANDIDATES)
    if not question or not answer:
        raise ValueError(
            f"Could not detect question/answer columns from {column_names}. "
            "Set column_map['question'] and column_map['answer']."
        )
    context = overrides.get("context") or _first_match(column_names, CONTEXT_CANDIDATES)
    id_column = overrides.get("id") or _first_match(column_names, ID_CANDIDATES)

    reserved = {question, answer, context, id_column} - {None}
    labels: dict[str, list[str]] = {}
    taken: set[str] = set(reserved)
    for rubric in rubrics:
        override = overrides.get(f"labels.{rubric.key}")
        if override:
            columns = [override] if isinstance(override, str) else list(override)
        else:
            columns = _columns_by_key(column_names, rubric, taken)
            if not columns:
                columns = _columns_by_vocab(column_names, sample_rows, rubric, taken)
        if not columns:
            raise ValueError(
                f"No label column found for rubric '{rubric.key}'. "
                f"Set column_map['labels.{rubric.key}']."
            )
        labels[rubric.key] = columns
        taken.update(columns)
    return ColumnMap(id=id_column, question=question, answer=answer, context=context, labels=labels)


def expand_annotations(raw: Any) -> list[Any]:
    """Expand one label cell into one raw label per annotator.

    RubricBench stores both annotators in a single cell as a dict literal such as
    ``{'annotator1': {'label': 'correct', 'comments': None}, 'annotator2': {...}}``
    (a Python ``repr`` string in the HuggingFace release; JSON is accepted too).
    Annotators are ordered by key name. Anything that is not such a dict is
    returned unchanged as a one-element list.

    Args:
        raw: The cell value.

    Returns:
        Raw labels, one per annotator (``None`` where an annotator has none).
    """
    parsed: Any = raw
    if isinstance(raw, str) and raw.strip().startswith("{"):
        text = raw.strip()
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            try:
                parsed = json.loads(text)
            except ValueError:
                parsed = raw
    if isinstance(parsed, dict) and parsed and all(isinstance(key, str) for key in parsed):
        labels: list[Any] = []
        for key in sorted(parsed):
            entry = parsed[key]
            labels.append(entry.get("label") if isinstance(entry, dict) else entry)
        return labels
    return [raw]


def resolve_gold(rubric: Rubric, raw_values: list[Any], policy: str) -> str | None:
    """Collapse one or more annotator labels into a single gold label.

    Args:
        rubric: Rubric whose vocabulary the labels must match.
        raw_values: One value per label column, in column order.
        policy: ``exclude`` (all non-missing labels must agree), ``annotator_1``
            or ``annotator_2`` (take that column only).

    Returns:
        A canonical option or ``None`` when the example should be skipped.

    Raises:
        ValueError: If ``policy`` is not one of ``exclude``, ``annotator_1``,
            ``annotator_2``.
    """
    if policy not in ("exclude", "annotator_1", "annotator_2"):
        raise ValueError(f"Unknown disagreement policy '{policy}'")
    canonical = [rubric.canonicalize(v if v is None else str(v)) for v in raw_values]
    if policy == "annotator_1":
        return canonical[0] if canonical else None
    if policy == "annotator_2":
        return canonical[1] if len(canonical) > 1 else None
    present = [v for v in canonical if v is not None]
    if not present:
        return None
    return present[0] if len(set(present)) == 1 else None


def normalise_rows(
    rows: Iterable[dict],
    rubrics: list[Rubric],
    columns: ColumnMap,
    policy: str,
) -> list[Example]:
    """Turn raw dataset rows into :class:`Example` objects.

    Args:
        rows: Dataset rows as dicts.
        rubrics: Rubrics to resolve labels for.
        columns: Column map from :func:`detect_columns`.
        policy: Disagreement policy passed to :func:`resolve_gold`.

    Returns:
        Examples in row order; ids fall back to the row index.
    """
    examples: list[Example] = []
    for index, row in enumerate(rows):
        example_id = str(row[columns.id]) if columns.id else str(index)
        gold = {
            rubric.key: resolve_gold(
                rubric,
                [label for c in columns.labels[rubric.key] for label in expand_annotations(row.get(c))],
                policy,
            )
            for rubric in rubrics
        }
        examples.append(
            Example(
                example_id=example_id,
                question=str(row[columns.question]),
                answer=str(row[columns.answer]),
                gold=gold,
                context=str(row[columns.context]) if columns.context and row.get(columns.context) else None,
            )
        )
    return examples


def _load_raw(config: StudyConfig) -> "Dataset":
    """Download the configured HuggingFace dataset and return its rows split.

    Args:
        config: Study configuration naming the dataset id and split.

    Returns:
        The loaded dataset split.
    """
    from datasets import load_dataset

    dataset = load_dataset(config.dataset_id, split=config.dataset_split) if config.dataset_split \
        else load_dataset(config.dataset_id)
    if not hasattr(dataset, "column_names") or isinstance(dataset.column_names, dict):
        split = next(iter(dataset))
        logger.info("Using split '%s' from %s", split, config.dataset_id)
        dataset = dataset[split]
    return dataset


def load_rubricbench(config: StudyConfig, rubrics: list[Rubric]) -> list[Example]:
    """Download RubricBench (needs ``HF_TOKEN`` for the gated repo) and normalise it."""
    dataset = _load_raw(config)
    rows = [dict(row) for row in dataset]
    columns = detect_columns(list(dataset.column_names), rows[:25], rubrics, config.column_map)
    examples = normalise_rows(rows, rubrics, columns, config.disagreement_policy)
    usable = {r.key: sum(e.gold[r.key] is not None for e in examples) for r in rubrics}
    logger.info("Loaded %d examples; usable gold labels per rubric: %s", len(examples), usable)
    return examples


def describe_dataset(config: StudyConfig, rubrics: list[Rubric]) -> str:
    """Human-readable schema summary for ``run.py inspect``."""
    dataset = _load_raw(config)
    rows = [dict(row) for row in dataset]
    lines = [f"dataset: {config.dataset_id}", f"rows: {len(rows)}", "columns:"]
    lines.extend(f"  - {name}" for name in dataset.column_names)
    lines.append("first row:")
    lines.extend(f"  {k}: {str(v)[:120]!r}" for k, v in rows[0].items())
    try:
        columns = detect_columns(list(dataset.column_names), rows[:25], rubrics, config.column_map)
        lines.append("detected columns:")
        lines.append(f"  id={columns.id} question={columns.question} answer={columns.answer} context={columns.context}")
        lines.extend(f"  labels.{key}: {cols}" for key, cols in columns.labels.items())
    except ValueError as exc:
        lines.append(f"column detection failed: {exc}")
    return "\n".join(lines)
