# RubricBench calibration study

Answers two questions raised in EMNLP demo feedback: how many human-labelled
examples does Kaleidoscope need to estimate judge reliability, and which
reliability threshold should gate judges out of the aggregated verdict?

Protocol (from the feedback): 3 judges × 14 rubrics on RubricBench; for each
calibration size k ∈ {10, 20, 30, 40, 50} draw k labelled examples, compute each
judge's macro-F1 on them, drop judges below threshold t ∈ {0.3, 0.4, 0.5, 0.6, 0.7},
majority-vote the survivors, and score the vote against the human labels on the
remaining examples. Repeat 200 times per k and report mean and SD; then score the gate itself against an out-of-sample truth.

## Prerequisites

- `backend/.env` with `PLATFORM_API_KEY`, `PLATFORM_API_BASE_URL` and `HF_TOKEN`
  (accept the RubricBench terms on HuggingFace first).
- Settings are constructed at import time, so every command — including
  `inspect` and `--help` — also needs `JWT_SECRET_KEY` and `ADMIN_API_KEY` set
  in `backend/.env`; the dev defaults from `backend/.env.example` are fine
  (`cp backend/.env.example backend/.env`).
- `cd backend && uv sync --extra test`

## Run

```bash
cd backend
uv run python -m experiments.rubricbench_calibration.run inspect          # check schema + column detection
uv run python -m experiments.rubricbench_calibration.run predict --limit 3 # smoke test one call per judge/rubric
uv run python -m experiments.rubricbench_calibration.run predict          # ~4,500 judge calls, resumable
uv run python -m experiments.rubricbench_calibration.run analyze          # ~6 min, no LLM
uv run python -m experiments.rubricbench_calibration.run analyze --sampling unstratified --sizes 5 10 20 30 40 50   # → outputs/unstratified/
uv run python -m experiments.rubricbench_calibration.run analyze --sampling shared                                    # → outputs/shared/
uv run python -m experiments.rubricbench_calibration.run analyze --policy annotator_1                                 # → outputs/policy_annotator_1/
uv run python -m experiments.rubricbench_calibration.run analyze --policy annotator_2                                 # → outputs/policy_annotator_2/
uv run python -m experiments.rubricbench_calibration.run analyze --policy annotator_1 --sampling shared               # → outputs/policy_annotator_1/shared/
```

`predict` skips cached rows and retries failures, so it is safe to re-run; it
reads only the full cache (`predictions.jsonl`), so on a fresh clone it starts
from scratch, while `analyze` falls back to the committed labels cache. Set
`LLM_MAX_CONCURRENT` in `.env` to throttle. If `inspect` mis-detects a column,
set `column_map` in `config.py` (see the docstring there).

Defaults: judges `govtech/gpt-5.6-luna`, `govtech/bedrock.claude-haiku-4-5`,
`govtech/gemini-3.5-flash-lite`; temperature 0 where the model allows it; models
matching Kaleidoscope's fixed-temperature list (currently any `gpt-5*` model, so
`gpt-5.6-luna`) run at 1.0, as they do in the product — the effective temperature
is recorded per prediction in `predictions.jsonl`; per-rubric stratified sampling;
annotator disagreements excluded. Override with `--repeats`, `--sampling shared`,
`--seed`, or by editing `StudyConfig`.

## Outputs (`outputs/`)

| File | Contents | Committed |
|---|---|---|
| `predictions.jsonl` | Stage 1 cache: one judge verdict per line with explanation, token counts and cost | no (RubricBench is gated; explanations quote the answers) |
| `predictions_labels.jsonl` | The same verdicts stripped to judge, rubric, example id, chosen option, temperature and model; `analyze` falls back to it when the full cache is absent, so the study reruns without the platform | yes |
| `results_grid.csv` | One row per (repeat, k, threshold, rubric) | no (20 MB) |
| `summary.md` / `summary.csv` | Gate operating characteristics, null-judge pass rates (pooled and per rubric), recommended threshold per k, reliability-estimate noise, live vs dead split, baselines, the per-rubric constant-majority null, then the feedback's k × threshold table with its prescribed rule and the appendix for excluded rubrics | yes |
| `gate_operating_characteristics.csv`, `synthetic_gate_pass_rates.csv`, `synthetic_gate_pass_rates_by_rubric.csv`, `baselines.csv` | The headline tables as CSV | yes |
| `by_rubric.md` | The k × threshold table per rubric, all 14 rubrics, with the one-class-calibration-sample rate | yes |
| `judge_reliability_full.csv` | Each judge's macro-F1 per rubric on all labelled data | yes |
| `unstratified/`, `shared/`, `policy_annotator_1/`, `policy_annotator_2/`, `policy_annotator_1/shared/` | The same set for the other sampling modes and disagreement policies (the prediction cache is shared; every run uses 200 repeats) | tables yes, grids no |

## How the metrics mirror the product

- Reliability = macro-F1 with positive class = the rubric's best option, missing
  predictions dropped (`MetricsService.calculate_judge_alignment`).
- Aggregation = majority vote; even splits are ties, no retained judge is
  "no aligned judge", a retained judge with a missing prediction is "pending"
  (`_resolve_row_aggregate`). Ties and pending/no-judge rows are excluded from
  the multi-judge F1 and reported as rates.
- Rubric coverage = share of (rubric, repeat) cells with ≥ 1 judge retained.
- Mean F1 skips rubrics with no verdict rows, so it is conditional on coverage;
  the penalised column counts such rubrics as 0 and should move together with
  coverage.

## Assumptions

- RubricBench column names are detected heuristically; always run `inspect` first.
- Two annotators per example. In the HuggingFace release each rubric column holds one
  cell per example shaped like `{'annotator1': {'label': ..., 'comments': ...}, 'annotator2': {...}}`;
  the loader expands that into one label per annotator. Default policy drops an example for
  a rubric when the two disagree (on the 108-example release that leaves 76 to 107 usable
  labels per rubric, matching the card's agreement rates); `disagreement_policy` can trust
  one annotator instead. If the dataset ships an adjudicated label column, it is used as-is.
- Per-rubric sampling means each rubric draws its own k examples. Use
  `--sampling shared` to draw one set of ids for all rubrics, which matches how a
  Kaleidoscope user annotates in practice.
- `summary.md` prints two selection rules. The recommended one picks, per k, the
  threshold whose gate has the highest balanced accuracy at separating judges
  that are aligned out of sample (κ ≥ 0.2 on the held-out ids) from those that
  are not. The feedback's prescribed rule (highest mean F1 among thresholds with
  coverage ≥ 0.9) is printed underneath with a caveat: it treats abstention as
  failure and so prefers thresholds that emit verdicts on rubrics where no judge
  has signal. The final recommendation is a human judgement; see Results.
- `faithfulness` and `context_recall` are excluded from the headline tables
  (`headline_exclude`) because of the no-KB issue above; they appear in the
  appendix and in `by_rubric.md`.
- `shared` sampling can only draw from examples that carry a gold label on every
  rubric. Under the default `exclude` policy that leaves too few examples for
  k ≥ 20, so the default shared run reports k = 10 only; the
  `--policy annotator_1` shared run uses all 108 examples and covers every k.
- At k=10 a calibration sample can contain no examples of the minority label on
  heavily skewed rubrics; `by_rubric.md` reports the one-class rate so such cells
  can be discounted.
- The product's `default_rubric_judge.md` has no knowledge-base slot, so Stage 1
  judges faithfulness and context recall without the KB, exactly as the product
  does. Low F1 on `faithfulness`/`context_recall` should be read with that in
  mind; a `--with-context` variant that supplies the KB is a possible follow-up.

## Results

Run 2026-09-21 on the cached predictions (3 judges × 14 rubrics × 108 examples,
200 repeats per k). Headline numbers are over the 12 rubrics with a usable judge
prompt; numbers in brackets are from the `unstratified` run, which draws
calibration samples the way an annotator produces them.

**Recommendation: keep the gate at macro-F1 ≥ 0.5, refuse to gate below 20
labelled responses per rubric, and recommend 30 or more.**

- *Threshold.* Scored as a classifier of judges against an out-of-sample
  truth (κ ≥ 0.2 on the held-out ids), the gate at t ≤ 0.4 is not a gate: it
  admits 81–100% of misaligned judges at every k (balanced accuracy 0.50–0.59).
  At t = 0.5 it admits 74–95% of aligned judges and 19–39% of misaligned ones
  (balanced accuracy 0.77–0.81 for k ≥ 20). The false-admit rate at 0.5
  **rises** with calibration size: 0.19, 0.30, 0.28, 0.33, 0.39 at k = 10…50
  against the κ truth, and 0.19, 0.24, 0.23, 0.26, 0.32 against the
  held-out-F1 truth. At t = 0.6 it is flat or falls: 0.19, 0.20, 0.15, 0.17,
  0.18 and 0.18, 0.11, 0.07, 0.07, 0.09. The cause is visible in
  `judge_reliability_full.csv`: three judge × rubric pairs sit at full-data
  F1 0.50–0.52 with no out-of-sample signal (gpt-5.6-luna on coherence,
  0.519; claude-haiku-4-5 and gemini-3.5-flash-lite on structure, 0.508 and
  0.501). On coherence (93% one class) the constant-majority null is 0.48, so
  0.5 clears it by 0.02; on structure (66% one class, null 0.40) the judges
  are simply near chance. More data admits those judges more consistently,
  while 0.6 keeps a margin above them. Balanced accuracy is close (0.5:
  0.77–0.81; 0.6: 0.75–0.80) because 0.6 also rejects more aligned judges
  (TPR 0.70–0.77 against 0.74–0.95). The shipped default stays 0.5; teams
  evaluating rubrics with more than about 85% of responses in one class, or
  whose judges sit within 0.05 of the gate, should set
  `RELIABILITY_THRESHOLD=0.6`, and the paper should state the trend rather
  than call the two thresholds tied.
- *Judges with no signal.* Measured directly on the same calibration draws
  (`synthetic_gate_pass_rates.csv`, pooled over the 12 headline rubrics): a
  uniform-random judge passes t = 0.5 on 32%, 29%, 27%, 27%, 25% of draws at
  k = 10…50 and t = 0.6 on 17%, 9%, 6%, 4%, 2%; a constant-majority judge
  never passes 0.5 or above (its macro-F1 is at most 0.48 on these rubrics)
  but passes 0.4 on 75–92% of draws. The pooled figure hides the split the
  reviewers pointed at (`synthetic_gate_pass_rates_by_rubric.csv`): on the
  near-balanced rubrics the random judge's expected macro-F1 approaches 0.5
  from below, so at k = 50 it still clears the 0.5 gate on 36–47% of draws on
  the five rubrics whose best-option share is between 0.32 and 0.68 (47% on
  factual_correctness), roughly flat or rising from k = 10 (four of the five
  rise; clarity dips from 0.40 to 0.38); on the four rubrics with 87% or
  more in one class it falls to 1–13% at k = 50. At t = 0.6 the random
  judge passes at most 6% of draws at k = 50 on any rubric. The reviewers'
  claim therefore holds on balanced rubrics: at 0.5 the gate cannot exclude a
  random judge no matter how many labels are collected, and only 0.6 has that
  power on every rubric.
- *Minimum calibration size.* The SD of a judge's calibration macro-F1 across
  draws is 0.127 (0.178) at k = 10, 0.085 (0.112) at k = 20, 0.064 (0.076) at
  k = 30, 0.041 (0.044) at k = 50; bias is ≤ 0.014 for k ≥ 10 (0.046 at
  k = 5 unstratified). Under
  unstratified draws 33% of k = 5 samples and 13% of k = 10 samples contain a
  single label class, on which a constant judge scores macro-F1 1.0. Gate
  balanced accuracy at t = 0.5 is 0.60 (k = 5), 0.70 (k = 10), 0.76 (k = 20),
  0.77–0.79 (k ≥ 30). Twenty is where the estimate's SD drops below the
  distance between a 0.6 judge and the 0.5 cut and the one-class rate falls
  below 5%; thirty buys the last clear improvement.
- *What the gate is for.* On the 8 rubrics where at least one judge has
  signal (κ ≥ 0.2), gating changes little: ungated majority vote scores 0.70
  and the t = 0.5 gate 0.72 with ties dropped, 0.67 with ties scored as
  errors (removing one judge from three leaves two, and two judges tie on
  10–30% of rows on the rubrics where they disagree). On the 4 rubrics where
  no judge has signal (sensibleness, coherence, instruction_following,
  structure — all three judges are near-constant predictors), the ungated
  vote emits a chance-level verdict (F1 ≈ 0.48) 100% of the time; the gate
  withholds it 58–79% of the time at t = 0.5 and 80–97% at t = 0.6, rising
  with k. The gate is an abstention mechanism, not an accuracy booster, and
  the honest claim is that it withholds automated scores where no judge is
  aligned.
- *Baselines.* Ungated vote 0.626; single best judge selected on the
  calibration draw 0.630–0.645; uniform-random judge 0.45; constant-majority
  judge 0.43 (all k, headline rubrics, ties dropped).
- *Sensitivity to the gold-label policy and to shared draws.* The default
  drops an example for a rubric when the two annotators disagree (76–107
  labels per rubric), which removes the hardest cases. Rerunning the analysis
  on annotator 1's labels alone (`--policy annotator_1`, 108 labels per
  rubric) or annotator 2's alone (`--policy annotator_2`), both at 200
  repeats, lowers every F1 level (ungated vote 0.605 and 0.581 against 0.626
  at k = 50) and, under annotator 2, leaves six of the twelve rubrics with no
  judge at κ ≥ 0.2, but the threshold picture is unchanged: at t = 0.5 the
  false-admit rate runs 0.21 → 0.41 (annotator 1) and 0.27–0.34 (annotator 2)
  across k = 10…50, at t = 0.6 it runs 0.18 → 0.16 and 0.26 → 0.14, and the
  two thresholds' balanced accuracies stay within 0.025 of each other
  (0.69–0.80, the 0.69 being both thresholds at k = 10 under annotator 2).
  The calibration-F1 noise barely moves (SD 0.127–0.128 at k = 10 and
  0.041–0.045 at k = 50 across the three per-rubric runs), so the 20- and
  30-label recommendations do not depend on the policy. Drawing one shared
  calibration set for all rubrics, the way a Kaleidoscope user annotates, on
  annotator 1's labels (`--policy annotator_1 --sampling shared`, every k)
  gives the same shape again: false-admit 0.30 → 0.42 at 0.5 and 0.26 → 0.17
  at 0.6, balanced accuracy 0.70–0.78 against 0.68–0.79; its calibration
  noise is higher (SD 0.175 at k = 10, 0.047 at k = 50) because a shared draw
  is stratified on one rubric's labels only. The recommendation holds under
  all three (tables under `outputs/policy_annotator_1/`,
  `outputs/policy_annotator_2/`, `outputs/policy_annotator_1/shared/`).
- *Prescribed rule.* "Highest mean F1 with coverage ≥ 0.9" selects t = 0.4 at
  every k. That is an artifact of the rule: it forbids abstention and averages
  only over rubrics that emitted a verdict, so it picks the threshold whose
  gate has ~0.5 balanced accuracy.

Headline k × threshold table (12 rubrics, per-rubric stratified draws, 200
repeats; ties dropped from F1):

| k | t | mean F1 | SD | F1 (ties wrong) | judges retained | coverage | tie rate | no-judge rate |
|---|---|---|---|---|---|---|---|---|
| 10 | 0.3 | 0.626 | 0.005 | 0.625 | 2.99 | 1.00 | 0.001 | 0.000 |
| 10 | 0.4 | 0.635 | 0.011 | 0.610 | 2.79 | 1.00 | 0.031 | 0.003 |
| 10 | 0.5 | 0.711 | 0.031 | 0.654 | 1.43 | 0.66 | 0.047 | 0.340 |
| 10 | 0.6 | 0.708 | 0.033 | 0.655 | 1.35 | 0.64 | 0.043 | 0.359 |
| 10 | 0.7 | 0.747 | 0.042 | 0.699 | 0.81 | 0.44 | 0.024 | 0.558 |
| 20 | 0.3 | 0.627 | 0.008 | 0.627 | 3.00 | 1.00 | 0.000 | 0.000 |
| 20 | 0.4 | 0.639 | 0.014 | 0.615 | 2.71 | 0.97 | 0.033 | 0.026 |
| 20 | 0.5 | 0.696 | 0.030 | 0.640 | 1.77 | 0.75 | 0.053 | 0.247 |
| 20 | 0.6 | 0.713 | 0.033 | 0.662 | 1.46 | 0.68 | 0.041 | 0.320 |
| 20 | 0.7 | 0.753 | 0.035 | 0.710 | 0.86 | 0.48 | 0.023 | 0.522 |
| 30 | 0.3 | 0.626 | 0.010 | 0.626 | 3.00 | 1.00 | 0.000 | 0.000 |
| 30 | 0.4 | 0.630 | 0.013 | 0.619 | 2.91 | 0.99 | 0.014 | 0.005 |
| 30 | 0.5 | 0.695 | 0.030 | 0.645 | 1.80 | 0.76 | 0.047 | 0.243 |
| 30 | 0.6 | 0.735 | 0.035 | 0.672 | 1.37 | 0.65 | 0.045 | 0.350 |
| 30 | 0.7 | 0.755 | 0.036 | 0.712 | 0.87 | 0.49 | 0.023 | 0.513 |
| 40 | 0.3 | 0.626 | 0.012 | 0.626 | 3.00 | 1.00 | 0.000 | 0.000 |
| 40 | 0.4 | 0.628 | 0.013 | 0.621 | 2.91 | 0.99 | 0.009 | 0.005 |
| 40 | 0.5 | 0.686 | 0.030 | 0.633 | 1.91 | 0.80 | 0.053 | 0.203 |
| 40 | 0.6 | 0.734 | 0.029 | 0.673 | 1.42 | 0.65 | 0.045 | 0.349 |
| 40 | 0.7 | 0.759 | 0.031 | 0.719 | 0.85 | 0.49 | 0.022 | 0.508 |
| 50 | 0.3 | 0.626 | 0.017 | 0.626 | 3.00 | 1.00 | 0.000 | 0.000 |
| 50 | 0.4 | 0.626 | 0.017 | 0.622 | 2.93 | 1.00 | 0.006 | 0.004 |
| 50 | 0.5 | 0.678 | 0.032 | 0.635 | 2.01 | 0.81 | 0.045 | 0.194 |
| 50 | 0.6 | 0.736 | 0.036 | 0.669 | 1.43 | 0.65 | 0.050 | 0.355 |
| 50 | 0.7 | 0.768 | 0.029 | 0.728 | 0.84 | 0.48 | 0.023 | 0.515 |

Limitations: RubricBench is the team's own dataset with heavy label skew
(7/14 rubrics ≥ 78% one class); three judges, two of them near-constant on
several rubrics; gpt-5.6-luna ran at temperature 1.0 with one sample per
item, so its per-item labels carry unmeasured run-to-run variance; the
out-of-sample truth is itself estimated on 50–90 held-out items and caps the
measurable gate accuracy near 0.8; faithfulness and context_recall were judged
without the knowledge base and are excluded from the headline. The pilot
reported in the paper collected about 40 annotations across four use cases,
which is below the 20-per-rubric floor this study recommends, so the pilot's
automated scores would be withheld under the shipped defaults.
