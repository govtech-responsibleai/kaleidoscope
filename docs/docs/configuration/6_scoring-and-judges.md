---
sidebar_position: 6
title: Scoring and Validation
---

# Scoring and Validation

Once you have an evaluation set, scoring and validation happen on the same page: judges score your target's responses automatically, you annotate a sample with human labels, and Kaleidoscope calculates how reliable each judge is.

## Baseline Judges

When you create or update a rubric, Kaleidoscope automatically generates up to three **baseline judges** using different models from your [configured providers](./1_providers.md). The first is marked as the primary baseline.

Baseline judges cannot be edited (they stay in sync with the rubric definition). To experiment with different models or prompting strategies, see [Custom Judges](#custom-judges) below.

:::note
The primary baseline judge is what you see used by default in the annotations interface and the evaluation set page.
:::

## Running a Scoring Job

A scoring job processes your evaluation set through three stages:

### Stage 1: Generate Responses

Kaleidoscope sends each approved input to your target and stores the response along with metadata (model used, tokens, RAG citations if available).

### Stage 2: Extract Claims (claim-based rubrics only)

For rubrics using claim-based scoring, each response is decomposed into atomic factual claims. Claims are checked for "checkworthiness" - trivial or subjective statements are skipped. This stage is skipped entirely if no rubrics use claim-based scoring.

### Stage 3: Score

Judges evaluate each response (or claim) and produce a verdict. For response-level rubrics, each judge picks one option. For claim-based rubrics, each checkworthy claim is scored independently and results are aggregated.

:::note
Judge reasoning is always written in English, regardless of the language the input was generated in. This keeps scores readable across multilingual evaluation sets.
:::

### Job Status

| Stage | Description |
|-------|-------------|
| Starting | Job initialised |
| Generating responses | Calling your target |
| Processing responses | Extracting claims |
| Scoring responses | Judges evaluating |
| Completed | All scores available |

Questions are batched and queued: they run through the pipeline with bounded concurrency rather than all at once. A failed question shows its own error and does not block the others — the evaluate button then offers to re-run just the failed ones.

### Failures on large runs

On large runs (e.g. 30+ questions) some questions may fail with a provider error such as `ServiceUnavailableError` / HTTP 502 / 503 (`"This model is currently experiencing high demand"` / `UNAVAILABLE`). This is a **transient overload** of the underlying model — either your target application's model (surfaced as a `502` from the target) or a judge model — not a hard quota limit.

Kaleidoscope retries these automatically with exponential backoff plus jitter (jitter spreads simultaneous retries so they don't all hit the overloaded model in the same instant). A question only fails after its retries are exhausted, and failures never block the other questions.

If failures persist on large runs, reduce the sustained request rate:

- **Target-side overload** (error traced to answer generation / a `502` from your target): lower `BATCH_MAX_CONCURRENT_JOBS` — this is how many questions call your target in parallel.
- **Judge-side overload** (error during scoring): lower `LLM_MAX_CONCURRENT` and/or `BATCH_MAX_CONCURRENT_CLAIMS`.

See [Environment Variables → LLM Concurrency & Throttling](./2_environment-variables.md#llm-concurrency--throttling). Re-running just the failed questions after the first pass usually succeeds, since the transient spike has passed and the queue is no longer saturated.

### Cost Tracking

Every scoring job tracks token usage (prompt + completion) and estimated cost. View totals on the scoring page to monitor spend across different models and rubrics.

## Annotations

Automated judges are useful, but you need to know how much to trust them. Human annotation creates the **ground truth** that validates judge reliability.

### Selecting Responses

By default, 20% of your evaluation set is selected for annotation, but a representative sample is enough. We recommend starting with 50 generated inputs and annotating 10-20 of them.

Selected responses are flagged across all rubrics, so you annotate the same responses for every rubric to get comparable alignment metrics.

![Annotations UI](/img/screenshots/annotations.png)

The annotation interface shows the judge's recommendation alongside your annotation buttons. For each response and rubric, you choose the label you believe is correct. The judge's pre-filled recommendation speeds up the process - you only need to confirm or override it.

### LLM-assisted claim review

For claim-based rubrics like Accuracy, the UI shows individual claims extracted from the response, color-coded by whether they are supported by the knowledge base. This helps you quickly identify which specific claims are accurate or hallucinated.

![Highlighter](/img/screenshots/highlighter.png)

## Judge Reliability

Once you've annotated responses, Kaleidoscope compares each judge's labels against your annotations using **macro F1**. Three numbers govern the gate, all set by environment variables (see [Environment Variables](2_environment-variables.md#judge-reliability-gate)):

| Setting | Default | Meaning |
|---|---|---|
| `RELIABILITY_THRESHOLD` | 0.5 | Macro-F1 a judge must reach to join the aggregated verdict |
| `MIN_CALIBRATION_SAMPLES` | 20 | Below this many annotated responses for a rubric, no judge is gated in or out and the aggregate is withheld |
| `RECOMMENDED_CALIBRATION_SAMPLES` | 30 | The annotation target the UI nudges you towards |

Each judge shows one of four states:

| State | Meaning |
|---|---|
| **Aligned** | F1 ≥ threshold on ≥ the minimum number of labels — its votes count |
| **Unreliable** | Compared on enough labels and fell below the threshold — excluded |
| **Not calibrated (n of 20)** | Fewer labels than the minimum — reliability is shown for information only |
| **Not calibrated (0 of 20)** | No annotations for this rubric yet, or the judge has not scored the annotated responses yet |

### How many responses should I annotate?

The defaults come from a resampling study on the public RubricBench calibration set (three judges, fourteen rubrics, 200 random calibration draws per size). With 10 labels a judge's reliability estimate has a standard deviation of about ±0.13, so a true 0.6 judge fails the 0.5 gate roughly one time in five. At 20 labels the SD is ±0.09, at 30 it is ±0.06, and at 50 ±0.04. Twenty is the floor at which the gate stops being noise; thirty or more is recommended. The 0.5 threshold sits only 0.02 above the score a judge gets by always predicting the majority label on the most skewed rubrics, so on rubrics where more than about 85% of responses share one label, a judge with no real signal can clear it once enough labels accumulate. Raise `RELIABILITY_THRESHOLD` to 0.6 for such rubrics, and for any rubric on which no judge clears 0.5 by a comfortable margin (a judge at 0.50–0.55 is within noise of a judge with no signal); the study found 0.6 keeps the false-admit rate flat as annotations grow, at the cost of excluding some judges that would have aligned. On a rubric where no judge reaches the threshold, Kaleidoscope withholds the automated score rather than reporting one — that is the intended behaviour, and it means the rubric needs human review.

Calibration ground truth is the annotation you save in the evaluation set. Editing an aggregated label on the scoring page changes the reported verdict but never the calibration.

:::note
Judge scoring now runs at temperature 0 for models that allow it; reliability scores computed before this change were produced at temperature 1.0 and may differ slightly.
:::

## Multiple Judges

In the scoring page, you can run more than one judge per rubric. This lets you compare how different models perform on the same evaluation criteria.

![Judge list](/img/screenshots/judge_list.png)

Each judge's reliability score is shown individually, calibrated against the human annotations you collected in the evaluation set page.

### Aggregated Verdicts

For each response and rubric, Kaleidoscope aggregates scores from all aligned judges using **majority vote**:

| State | Meaning |
|-------|---------|
| **Majority** | Aligned judges agree on one option |
| **Majority tied** | Aligned judges split evenly - no clear winner |
| **Not calibrated** | Fewer than the minimum number of annotated responses, or the judges have not yet scored enough of the annotated responses — score withheld |
| **No aligned judge** | Enough annotations, but no judge meets the reliability threshold — score withheld, human review required |
| **Override** | A human manually edited the aggregated label |
| **Pending** | Scoring not yet complete for all aligned judges |

A withheld score is shown as a gap on the report trend chart, never as 0%.

Users can manually override any aggregated verdict if you disagree with the majority.

### Upgrading from an earlier version

Earlier versions gated judges with no minimum number of annotations. After upgrading, any rubric with fewer than `MIN_CALIBRATION_SAMPLES` (default 20) annotated responses shows its automated score as withheld until it reaches the floor. Reliability values recorded before the upgrade were computed at temperature 1.0 and are recomputed on the next scoring run.

### Custom Judges

Users can add custom judges to the judge list above. Available judge models depend on which [LLM providers](./1_providers.md) are configured.

To create one, click **Create Judge** on the scoring page, choose a rubric, model, and name, and optionally customise the prompt template.

