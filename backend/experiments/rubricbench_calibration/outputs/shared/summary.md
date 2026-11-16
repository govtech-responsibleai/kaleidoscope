# RubricBench calibration study — summary

_Headline tables cover 12 rubrics. Excluded from headline: faithfulness, context_recall (the product judge prompt has no knowledge-base slot, so these judges never saw the source they are asked about; see appendix). Rubrics with no judge at κ ≥ 0.2: coherence, instruction_following, sensibleness, structure._

## Gate operating characteristics

Truth = judge's Cohen's κ ≥ 0.2 on the held-out evaluation ids of the same draw (out of sample).

| k | threshold | TPR (aligned admitted) | FPR (misaligned admitted) | Balanced accuracy | n aligned | n misaligned |
|---|---|---|---|---|---|---|
| 10 | 0.3 | 1.00 | 1.00 | 0.50 | 3710 | 3490 |
| 10 | 0.4 | 0.99 | 0.95 | 0.52 | 3710 | 3490 |
| 10 | 0.5 | 0.75 | 0.30 | 0.73 | 3710 | 3490 |
| 10 | 0.6 | 0.74 | 0.30 | 0.72 | 3710 | 3490 |
| 10 | 0.7 | 0.61 | 0.30 | 0.66 | 3710 | 3490 |

Sensitivity: truth = held-out macro-F1 ≥ 0.5 on the same draw (same statistic as the gate; optimistic).

| k | threshold | TPR (aligned admitted) | FPR (misaligned admitted) | Balanced accuracy | n aligned | n misaligned |
|---|---|---|---|---|---|---|
| 10 | 0.3 | 1.00 | 1.00 | 0.50 | 4749 | 2451 |
| 10 | 0.4 | 0.98 | 0.97 | 0.51 | 4749 | 2451 |
| 10 | 0.5 | 0.66 | 0.30 | 0.68 | 4749 | 2451 |
| 10 | 0.6 | 0.65 | 0.30 | 0.68 | 4749 | 2451 |
| 10 | 0.7 | 0.55 | 0.30 | 0.63 | 4749 | 2451 |

## Null judges through the gate

Pass rate = share of calibration draws on which a judge with no signal reaches the threshold. random = uniform over the rubric's options; constant = always the calibration draw's majority label. A threshold with power must send both to ~0.

| k | threshold | random judge pass rate | constant-majority judge pass rate | random mean F1 | constant mean F1 | draws |
|---|---|---|---|---|---|---|
| 10 | 0.3 | 0.71 | 1.00 | 0.399 | 0.583 | 2400 |
| 10 | 0.4 | 0.43 | 0.96 | 0.399 | 0.583 | 2400 |
| 10 | 0.5 | 0.23 | 0.24 | 0.399 | 0.583 | 2400 |
| 10 | 0.6 | 0.11 | 0.24 | 0.399 | 0.583 | 2400 |
| 10 | 0.7 | 0.02 | 0.24 | 0.399 | 0.583 | 2400 |

Per rubric, random judge only, smallest and largest k:

| rubric | share of best option | pass rate t=0.5 @ k=min | pass rate t=0.5 @ k=max | pass rate t=0.6 @ k=min | pass rate t=0.6 @ k=max |
|---|---|---|---|---|---|
| empathy | 0.32 | 0.36 | 0.36 | 0.17 | 0.17 |
| verbosity | 0.33 | 0.36 | 0.36 | 0.21 | 0.21 |
| factual_correctness | 0.60 | 0.36 | 0.36 | 0.17 | 0.17 |
| structure | 0.66 | 0.17 | 0.17 | 0.08 | 0.08 |
| clarity | 0.68 | 0.29 | 0.29 | 0.16 | 0.16 |
| instruction_following | 0.78 | 0.20 | 0.20 | 0.09 | 0.09 |
| professionalism | 0.78 | 0.20 | 0.20 | 0.12 | 0.12 |
| specificity | 0.80 | 0.33 | 0.33 | 0.12 | 0.12 |
| bias | 0.87 | 0.01 | 0.01 | 0.01 | 0.01 |
| fluency | 0.89 | 0.24 | 0.24 | 0.14 | 0.14 |
| sensibleness | 0.90 | 0.23 | 0.23 | 0.12 | 0.12 |
| coherence | 0.93 | 0.00 | 0.00 | 0.00 | 0.00 |

## Recommended threshold per calibration size (argmax gate balanced accuracy, κ truth)

- k=10: recommended threshold 0.5 (gate balanced accuracy 0.73, TPR 0.75, FPR 0.30)

## Reliability-estimate noise

| k | SD of a judge's calibration macro-F1 across repeats | Mean bias vs full-data F1 | judge×rubric pairs |
|---|---|---|---|
| 10 | 0.105 | 0.075 | 36 |

## Live vs dead rubrics

Live = at least one judge with full-data κ ≥ 0.2. Abstain rate = share of rubric×repeat cells with no judge retained.

| k | threshold | class | mean F1 (ties dropped) | mean F1 (ties wrong) | abstain rate | rubrics |
|---|---|---|---|---|---|---|
| 10 | 0.3 | dead | 0.475 | 0.475 | 0.000 | 4 |
| 10 | 0.3 | live | 0.698 | 0.698 | 0.000 | 8 |
| 10 | 0.4 | dead | 0.475 | 0.475 | 0.000 | 4 |
| 10 | 0.4 | live | 0.704 | 0.695 | 0.000 | 8 |
| 10 | 0.5 | dead | 0.471 | 0.471 | 0.615 | 4 |
| 10 | 0.5 | live | 0.761 | 0.685 | 0.018 | 8 |
| 10 | 0.6 | dead | 0.471 | 0.471 | 0.615 | 4 |
| 10 | 0.6 | live | 0.757 | 0.692 | 0.018 | 8 |
| 10 | 0.7 | dead | 0.471 | 0.471 | 0.615 | 4 |
| 10 | 0.7 | live | 0.746 | 0.701 | 0.116 | 8 |

## Baselines

Same calibration draws. `ungated` = all judges vote; `single_best` = highest calibration-F1 judge alone; `constant_majority` = always the calibration majority label; `random` = uniform over options.

| k | baseline | mean F1 | SD |
|---|---|---|---|
| 10 | constant_majority | 0.413 | 0.001 |
| 10 | random | 0.453 | 0.015 |
| 10 | single_best | 0.629 | 0.007 |
| 10 | ungated | 0.624 | 0.002 |

## Constant-majority baseline per rubric

| rubric | n | share of best option | constant-majority macro-F1 |
|---|---|---|---|
| factual_correctness | 89 | 0.60 | 0.373 |
| faithfulness | 96 | 0.30 | 0.411 |
| sensibleness | 105 | 0.90 | 0.472 |
| specificity | 76 | 0.80 | 0.445 |
| context_recall | 99 | 0.43 | 0.361 |
| instruction_following | 89 | 0.78 | 0.437 |
| bias | 107 | 0.87 | 0.465 |
| coherence | 102 | 0.93 | 0.482 |
| fluency | 93 | 0.89 | 0.472 |
| empathy | 90 | 0.32 | 0.404 |
| clarity | 87 | 0.68 | 0.404 |
| professionalism | 104 | 0.78 | 0.438 |
| structure | 91 | 0.66 | 0.397 |
| verbosity | 89 | 0.33 | 0.403 |

## Prescribed table (k × threshold, headline rubrics)

| Calibration size | Reliability threshold | Mean multi-judge macro-F1 (ties dropped) | SD over repeats | Mean F1 (ties wrong) | Mean F1 (no-verdict rubrics = 0) | Avg. judges retained | Rubric coverage | Tie rate | No-judge rate | Repeats | One-class sample rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 0.3 | 0.624 | 0.002 | 0.624 | 0.624 | 3.00 | 1.00 | 0.000 | 0.000 | 200 | 0.241 |
| 10 | 0.4 | 0.628 | 0.007 | 0.622 | 0.628 | 2.92 | 1.00 | 0.007 | 0.000 | 200 | 0.241 |
| 10 | 0.5 | 0.714 | 0.022 | 0.650 | 0.559 | 1.60 | 0.78 | 0.056 | 0.217 | 200 | 0.241 |
| 10 | 0.6 | 0.711 | 0.019 | 0.656 | 0.556 | 1.58 | 0.78 | 0.049 | 0.217 | 200 | 0.241 |
| 10 | 0.7 | 0.698 | 0.021 | 0.661 | 0.500 | 1.39 | 0.72 | 0.032 | 0.282 | 200 | 0.241 |
| 20 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |

### prescribed criterion (highest mean F1 with coverage ≥ 0.90; treats abstention as failure)

- k=10: best threshold 0.4 (mean F1 0.628 ± 0.007, coverage 1.00)
- k=20: no threshold reaches coverage ≥ 0.90
- k=30: no threshold reaches coverage ≥ 0.90
- k=40: no threshold reaches coverage ≥ 0.90
- k=50: no threshold reaches coverage ≥ 0.90

## Appendix: rubrics excluded from headline

| Calibration size | Reliability threshold | Mean multi-judge macro-F1 (ties dropped) | SD over repeats | Mean F1 (ties wrong) | Mean F1 (no-verdict rubrics = 0) | Avg. judges retained | Rubric coverage | Tie rate | No-judge rate | Repeats | One-class sample rate |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 10 | 0.3 | 0.399 | 0.004 | 0.399 | 0.399 | 3.00 | 1.00 | 0.000 | 0.000 | 200 | 0.000 |
| 10 | 0.4 | 0.399 | 0.004 | 0.399 | 0.399 | 3.00 | 1.00 | 0.000 | 0.000 | 200 | 0.000 |
| 10 | 0.5 | 0.608 | 0.104 | 0.423 | 0.280 | 0.74 | 0.46 | 0.126 | 0.540 | 184 | 0.000 |
| 10 | 0.6 | 0.482 | 0.079 | 0.434 | 0.199 | 0.48 | 0.41 | 0.030 | 0.588 | 165 | 0.000 |
| 10 | 0.7 | 0.441 | 0.002 | 0.441 | 0.073 | 0.17 | 0.17 | 0.000 | 0.835 | 66 | 0.000 |
| 20 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 20 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 30 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 40 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.3 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.4 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.5 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.6 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |
| 50 | 0.7 | n/a | n/a | n/a | n/a | 0.00 | 0.00 | n/a | n/a | 0 | n/a |

_Coverage is the share of (rubric, repeat) cells with at least one judge retained. Mean F1 (ties dropped) skips tied, pending and no-judge rows, so it is conditional on coverage; 'ties wrong' scores a tied verdict as the wrong label; the penalised column counts a rubric with no verdict as 0. SD is the spread over repeated calibration draws a single user would experience._
