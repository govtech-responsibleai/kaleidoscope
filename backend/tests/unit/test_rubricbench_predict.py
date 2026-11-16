import json
from unittest.mock import AsyncMock

import pytest

from experiments.rubricbench_calibration.config import StudyConfig
from experiments.rubricbench_calibration.dataset import Example
from experiments.rubricbench_calibration.predict import (
    LABEL_FIELDS,
    PredictionRecord,
    build_prompt,
    effective_temperature,
    load_predictions,
    run_predictions,
    write_label_cache,
)
from experiments.rubricbench_calibration.rubrics import Rubric, RubricOption
from src.common.models import RubricJudgmentResult

FACT = Rubric(
    key="factual_correctness", name="Factual Correctness", criteria="Is it correct?",
    options=(RubricOption("correct", "yes"), RubricOption("incorrect", "no")),
    best_option="correct",
)
EXAMPLES = [
    Example("e1", "Q1", "A1", {"factual_correctness": "correct"}),
    Example("e2", "Q2", "A2", {"factual_correctness": "incorrect"}),
]


class _FakeClient:
    def __init__(self, answers):
        self.answers = answers
        self.generate_structured_async = AsyncMock(side_effect=self._respond)

    async def _respond(self, prompt, response_model, temperature, **kwargs):
        value = self.answers.pop(0)
        if isinstance(value, Exception):
            raise value
        return RubricJudgmentResult(chosen_option=value, explanation="because"), {
            "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15, "cost": 0.001, "model": "wire-model",
        }


def test_build_prompt_includes_rubric_options_and_english_directive():
    prompt = build_prompt(FACT, EXAMPLES[0])
    assert "Factual Correctness" in prompt
    assert "**correct**: yes" in prompt
    assert "Q1" in prompt and "A1" in prompt
    assert "## Output Language" in prompt


@pytest.mark.asyncio
async def test_run_predictions_writes_jsonl_and_canonicalises(tmp_path):
    path = tmp_path / "predictions.jsonl"
    client = _FakeClient(["  Correct ", "nonsense"])
    config = StudyConfig(judges=("govtech/j1",), output_dir=tmp_path)

    results = await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: client)

    assert results[("govtech/j1", "factual_correctness", "e1")].chosen_option == "correct"
    unmatched = results[("govtech/j1", "factual_correctness", "e2")]
    assert unmatched.chosen_option is None
    assert unmatched.raw_option == "nonsense"
    lines = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(lines) == 2
    assert lines[0]["prompt_tokens"] == 10


@pytest.mark.asyncio
async def test_run_predictions_skips_cached_and_retries_failures(tmp_path):
    path = tmp_path / "predictions.jsonl"
    config = StudyConfig(judges=("govtech/j1",), output_dir=tmp_path)

    first = _FakeClient(["correct", RuntimeError("boom")])
    results = await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: first)
    failed = results[("govtech/j1", "factual_correctness", "e2")]
    assert failed.chosen_option is None and "boom" in failed.error

    second = _FakeClient(["incorrect"])
    results = await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: second)
    assert second.generate_structured_async.await_count == 1
    assert results[("govtech/j1", "factual_correctness", "e2")].chosen_option == "incorrect"
    assert results[("govtech/j1", "factual_correctness", "e1")].chosen_option == "correct"


@pytest.mark.asyncio
async def test_effective_temperature_records_fixed_temperature_models(tmp_path):
    assert effective_temperature("govtech/gpt-5.6-luna", 0.0) == 1.0
    assert effective_temperature("govtech/bedrock.claude-haiku-4-5", 0.0) == 0.0

    path = tmp_path / "predictions.jsonl"
    client = _FakeClient(["correct"])
    config = StudyConfig(judges=("govtech/gpt-5.6-luna",), output_dir=tmp_path)

    results = await run_predictions(config, [FACT], [EXAMPLES[0]], path, client_factory=lambda judge: client)

    assert results[("govtech/gpt-5.6-luna", "factual_correctness", "e1")].temperature == 1.0


def test_load_predictions_keeps_latest_record_per_key(tmp_path):
    path = tmp_path / "p.jsonl"
    old = PredictionRecord("j", "r", "e", None, None, None, 0, 0, 0.0, None, "err")
    new = PredictionRecord("j", "r", "e", "correct", "correct", "ok", 1, 1, 0.0, "m", None)
    path.write_text(json.dumps(old.to_json()) + "\n" + json.dumps(new.to_json()) + "\n")
    assert load_predictions(path)[("j", "r", "e")].chosen_option == "correct"


@pytest.mark.asyncio
async def test_failure_with_empty_message_is_recorded_and_retried(tmp_path):
    path = tmp_path / "predictions.jsonl"
    config = StudyConfig(judges=("govtech/j1",), output_dir=tmp_path)

    first = _FakeClient([RuntimeError(), "correct"])
    results = await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: first)
    failed = results[("govtech/j1", "factual_correctness", "e1")]
    assert failed.chosen_option is None
    assert failed.error == "RuntimeError"

    second = _FakeClient(["incorrect"])
    results = await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: second)
    assert second.generate_structured_async.await_count == 1
    assert results[("govtech/j1", "factual_correctness", "e1")].chosen_option == "incorrect"


def test_write_label_cache_then_load_predictions_matches_full_cache(tmp_path):
    ok1 = PredictionRecord("j1", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    ok2 = PredictionRecord("j2", "r", "e2", "incorrect", "incorrect", "because", 1, 1, 0.01, "m", None)
    failed = PredictionRecord("j1", "r", "e2", None, None, None, 0, 0, 0.0, None, "boom")
    predictions = {ok1.key: ok1, ok2.key: ok2, failed.key: failed}
    labels_path = tmp_path / "nested" / "predictions_labels.jsonl"

    n = write_label_cache(predictions, labels_path)

    assert n == 2
    loaded = load_predictions(labels_path)
    expected = {k: v.chosen_option for k, v in predictions.items() if v.error is None}
    assert set(loaded) == set(expected)
    assert {k: r.chosen_option for k, r in loaded.items()} == expected


def test_write_label_cache_writes_only_label_fields_sorted_by_key(tmp_path):
    b = PredictionRecord("j2", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    a = PredictionRecord("j1", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    labels_path = tmp_path / "predictions_labels.jsonl"

    write_label_cache({b.key: b, a.key: a}, labels_path)

    lines = [json.loads(line) for line in labels_path.read_text().splitlines()]
    assert [line["judge"] for line in lines] == ["j1", "j2"]
    assert all(set(line) == set(LABEL_FIELDS) for line in lines)


def test_load_predictions_uses_explicit_fallback_when_full_cache_is_missing(tmp_path):
    full_path = tmp_path / "predictions.jsonl"
    labels_path = tmp_path / "predictions_labels.jsonl"
    ok = PredictionRecord("j", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    write_label_cache({ok.key: ok}, labels_path)
    assert not full_path.exists()

    loaded = load_predictions(full_path, fallback=labels_path)

    assert loaded[ok.key].chosen_option == "correct"


def test_load_predictions_without_fallback_ignores_sibling_labels_file(tmp_path):
    """`predict` must start from scratch on a fresh clone, not resume from the labels cache."""
    full_path = tmp_path / "predictions.jsonl"
    ok = PredictionRecord("j", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    write_label_cache({ok.key: ok}, full_path.with_name("predictions_labels.jsonl"))
    assert not full_path.exists()

    assert load_predictions(full_path) == {}


@pytest.mark.asyncio
async def test_run_predictions_does_not_resume_from_labels_cache(tmp_path):
    path = tmp_path / "predictions.jsonl"
    cached = PredictionRecord("govtech/j1", "factual_correctness", "e1", "correct", "correct", "x", 1, 1, 0.0, "m", None)
    write_label_cache({cached.key: cached}, path.with_name("predictions_labels.jsonl"))
    config = StudyConfig(judges=("govtech/j1",), temperature=0.0)
    client = _FakeClient(["correct"] * len(EXAMPLES))

    await run_predictions(config, [FACT], EXAMPLES, path, client_factory=lambda judge: client)

    assert client.generate_structured_async.await_count == len(EXAMPLES)
    assert path.exists()


def test_load_predictions_prefers_full_cache_when_both_exist(tmp_path):
    full_path = tmp_path / "predictions.jsonl"
    full_record = PredictionRecord("j", "r", "e1", "correct", "correct", "because", 1, 1, 0.01, "m", None)
    full_path.write_text(json.dumps(full_record.to_json()) + "\n")
    stale_label = PredictionRecord("j", "r", "e1", "incorrect", None, None, 0, 0, 0.0, None, None)
    write_label_cache({stale_label.key: stale_label}, full_path.with_name("predictions_labels.jsonl"))

    loaded = load_predictions(full_path)

    assert loaded[full_record.key].chosen_option == "correct"


def test_from_json_accepts_only_label_fields():
    data = {"judge": "j", "rubric": "r", "example_id": "e1", "chosen_option": "correct",
            "temperature": 0.0, "model": "m"}
    assert set(data) == set(LABEL_FIELDS)

    record = PredictionRecord.from_json(data)

    assert record.chosen_option == "correct"
    assert record.error is None
    assert record.explanation is None
    assert record.raw_option is None
    assert record.prompt_tokens == 0
    assert record.completion_tokens == 0
    assert record.cost == 0.0
