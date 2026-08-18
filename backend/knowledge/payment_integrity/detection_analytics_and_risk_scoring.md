---
title: Detection Analytics and Risk Scoring
doc_id: payment_integrity.detection_analytics_and_risk_scoring
category: payment_integrity
tags: [analytics, risk_score, models, false_positives, explainability, peer_groups]
source_type: curated_knowledge
version: 2.0
---

# Detection Analytics and Risk Scoring

## What it means

The use of statistical and machine learning methods over claims, provider and
beneficiary data to identify payments and behaviours that warrant review.

## Analytic approaches

- **Rule-based detection** — explicit conditions encoding known schemes and
  policy violations. Transparent and easy to defend; only finds what is already
  known.
- **Peer comparison and outlier detection** — measuring deviation from a
  comparable population. Finds unknown patterns; depends entirely on peer group
  quality.
- **Anomaly detection** — unsupervised identification of unusual records without
  labelled fraud examples. Useful where confirmed fraud labels are scarce.
- **Supervised models** — trained on historical confirmed outcomes. Powerful but
  limited by label availability, and biased toward previously detected schemes.
- **Network and link analysis** — relationships between providers, beneficiaries
  and entities, revealing coordinated behaviour that per-entity metrics miss.

## Why outputs must be interpreted carefully

1. **Labels are scarce and biased.** Confirmed fraud cases are rare, and the ones
   that exist are the ones that were previously caught. Models trained on them
   learn the shape of *detected* fraud, not fraud.
2. **Base rates are low.** Even a well-performing model produces a substantial
   share of false positives when the underlying event is rare.
3. **Deviation is not intent.** Every statistical method measures difference from
   expectation. No method measures intent.
4. **Peer group quality dominates.** Most false positives in peer-based scoring
   come from mis-specified comparison groups, not from model defects.
5. **Data quality propagates.** Attribution errors, missing records and specialty
   mis-assignment produce deviation that has nothing to do with behaviour.

## What a risk score actually represents

A risk score is a **relative prioritisation signal**. It expresses how strongly a
case's observed characteristics resemble patterns the model associates with
elevated risk, relative to the population.

It is **not**:

- a probability that fraud occurred
- a measure of dollar exposure
- a determination, finding, or accusation
- comparable across different model versions or scoring periods

Two providers with the same score can be flagged for entirely different reasons.
This is why **risk factors and feature contributions matter more than the score
value** when explaining a case: the score says *how strongly*, the factors say
*why*, and only the factors can be investigated.

## Risk levels

Risk levels (for example low / medium / high) are thresholds applied to the
score. Thresholds are operational choices balancing review capacity against
missed cases — they are not natural categories, and a case just above a threshold
is not materially different from one just below it.

## What an investigator should examine

1. Which specific factors drove the score, not just the score value.
2. Whether the peer group used for comparison is appropriate to the provider.
3. Whether the underlying data is complete and correctly attributed.
4. Whether the deviation is corroborated by independent evidence.
5. What the plausible benign explanations are, and how to test each one.
6. Whether the same provider was flagged in prior periods, and what happened.

## Related

`risk_factor_interpretation`, `peer_deviation_and_outliers`,
`comparison_and_analysis_methods`, `payment_integrity_overview`

> A model identifies statistical patterns. Investigators establish facts. The
> assistant explains the first and supports the second — it substitutes for
> neither, and never computes a score itself.
