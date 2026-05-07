---
sidebar_position: 4
title: Defining Rubrics
---

# Defining Rubrics

**Rubrics** are the criteria your evaluation scores against. 

## Anatomy of a Rubric

Every rubric has:

| Field | Description |
|-------|-------------|
| **Name** | Short label (e.g. "Accuracy", "Tone") |
| **Criteria** | Natural-language description of what you're evaluating |
| **Options** | Two or more possible labels (e.g. "Accurate" / "Inaccurate") with descriptions |
| **Best option** | The label that represents a passing score. (E.g. between "Good"/"Bad", if best option is "Good", then a score of 90% means 90% of items are "Good") |
| **Scoring mode** | Whether to evaluate the full response or individual claims |

### Scoring Modes

| Mode | How it works | Best for |
|------|-------------|----------|
| **Response-level** | Judge evaluates the entire answer and picks one option | Tone, helpfulness, style |
| **Claim-based** | Answer is split into atomic claims; each claim is scored independently | Factual accuracy, hallucination |

Claim-based scoring gives finer-grained results but costs more tokens (one judge call per claim).

:::note
Currently, scoring mode is not configurable in the UI. The built-in Accuracy rubric uses claim-based scoring. All other rubrics (preset and custom) use response-level scoring by default.
:::

## Rubric Types

Kaleidoscope organises rubrics into three groups:

### Fixed Rubrics

Always present on every target. Fixed rubrics cannot be deleted or edited on the frontend.

| Rubric | Criteria | Scoring Mode |
|--------|----------|--------------|
| **Accuracy** | Are the claims in the response supported by the provided context, or do they contain hallucinations? | Claim-based |

### Preset Rubrics

Built-in templates you can optionally add to a target. These presets come with specifically designed judge prompts which we tuned through several rounds of aligning the judge's scores against human labels across different use cases.

| Rubric | Criteria | Scoring Mode |
|--------|----------|--------------|
| **Empathy** | Does the response demonstrate empathy and emotional awareness appropriate to the user's situation? | Response-level |
| **Verbosity** | Is the response appropriately concise, or does it include unnecessary repetition, filler, or excessive detail? | Response-level |

### Custom Rubrics

Rubrics you define in natural language. The criteria you define is fed into the LLM judges.

![Rubrics](/img/screenshots/rubrics_custom.png)

When you add or update a rubric, Kaleidoscope automatically creates baseline judges for it using your configured providers. See [Scoring and Judges](./6_scoring-and-judges.md) for details.
