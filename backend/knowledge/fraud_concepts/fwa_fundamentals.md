---
title: Fraud, Waste and Abuse Fundamentals
doc_id: fraud_concepts.fwa_fundamentals
category: fraud_concepts
tags: [fwa, fraud, waste, abuse, intent, definitions]
source_type: curated_knowledge
version: 2.0
---

# Fraud, Waste and Abuse Fundamentals

## Fraud vs waste vs abuse

These three terms are distinguished by **intent** and **severity**, not by how
the claim looks in the data.

- **Fraud** — knowingly and willfully submitting false or misleading information
  to obtain a payment the party is not entitled to. Requires intent to deceive.
- **Waste** — overuse of services or inefficient practices that consume
  resources without producing benefit. Generally not deliberate deception.
- **Abuse** — practices inconsistent with sound fiscal, business or medical
  practice resulting in unnecessary cost. Sits between waste and fraud; intent
  is unclear or unproven.

## Why the distinction governs everything the system does

The same data pattern can be produced by all three — and by entirely legitimate
practice. High billing volume might reflect a scheme, a wasteful care pattern,
an abusive billing habit, or an appropriate high-volume practice.

**Intent is not observable in claims data.** Analytics can measure how far
behaviour deviates from expectation and how much money is exposed. It cannot
measure why. This is the structural reason a detection system can never classify
a case as fraud on statistical grounds alone.

## What detection actually produces

A risk model ranks claims and providers by deviation, volume, concentration and
pattern irregularity. That ranking **prioritises human review**. It does not
adjudicate, and a high score is not a finding.

## Language discipline

Correct framing when describing a flagged case:
*flagged, high risk, potentially suspicious, warrants further investigation, the
model identified, the data shows, this pattern may indicate.*

Incorrect framing unless verified information confirms fraud:
*this is fraud, this provider committed fraud, this claim is fraudulent.*

## How an investigator should approach an FWA flag

1. Establish what the model actually measured.
2. Verify the underlying data is correct, complete and correctly attributed.
3. Test benign explanations before adversarial ones.
4. Seek corroborating evidence outside the claims data — records, documentation,
   beneficiary statements.
5. Distinguish error from deliberate conduct. Repetition, concealment,
   one-directional benefit, and persistence after notice are far more probative
   than volume alone.

## Related

`payment_integrity_overview`, `fraud_actors`,
`detection_analytics_and_risk_scoring`, `investigation_workflow`

> An anomaly, a high risk score, or an outlier ranking does not prove fraud.
