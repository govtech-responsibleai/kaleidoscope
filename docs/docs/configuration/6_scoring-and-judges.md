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

### Job Status

| Stage | Description |
|-------|-------------|
| Starting | Job initialised |
| Generating responses | Calling your target |
| Processing responses | Extracting claims |
| Scoring responses | Judges evaluating |
| Completed | All scores available |

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

Once you've annotated enough responses, Kaleidoscope compares judge scores against your annotations using **macro F1** as the primary reliability metric. 

A judge with **F1 >= 0.5** is considered "aligned" and trusted for aggregation. Judges below this threshold are flagged as unreliable and their scores are excluded from the aggregated verdict.

:::info For developers
The reliability threshold is configurable [here](https://github.com/govtech-responsibleai/kaleidoscope/blob/main/backend/src/scoring/services/metrics_service.py) with `RELIABILITY_THRESHOLD`.
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
| **No aligned judge** | No judges meet the reliability threshold |
| **Override** | A human manually edited the aggregated label |
| **Pending** | Scoring not yet complete for all aligned judges |

Users can manually override any aggregated verdict if you disagree with the majority.

### Custom Judges

Users can add custom judges to the judge list above. Available judge models depend on which [LLM providers](./1_providers.md) are configured.

To create one, click **Create Judge** on the scoring page, choose a rubric, model, and name, and optionally customise the prompt template.

