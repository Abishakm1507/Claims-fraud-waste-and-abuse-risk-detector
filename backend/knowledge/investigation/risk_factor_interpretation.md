---
title: Risk Factor Interpretation
doc_id: investigation.risk_factor_interpretation
category: investigation
tags: [risk_score, risk_factors, feature_contributions, explanation, language_discipline]
source_type: curated_knowledge
version: 2.0
---

# Risk Factor Interpretation

How to read the output of a fraud/risk engine and turn it into investigative
action. This is the reference for explaining *why something was flagged*.

---

## The three layers of model output

**Risk score** — a relative prioritisation value. It says *how strongly* the case
resembles patterns associated with elevated risk, relative to the population. It
does not say what is wrong, and it cannot be investigated directly.

**Risk level** — a threshold applied to the score (low / medium / high).
Thresholds are operational choices balancing review capacity against missed
cases. A case just above a threshold is not materially different from one just
below.

**Risk factors and feature contributions** — the specific measured behaviours
that drove the score. **This is the only layer that can actually be
investigated.** Two providers with identical scores may share nothing in common;
their factors are what differ, and the factors determine what to do next.

Practical consequence: an explanation built around the score is not useful. An
explanation built around the factors is.

---

## Reading a risk factor

For each factor, establish four things before acting on it:

1. **What was measured** — the precise metric, not the label. "High
   reimbursement" could mean total paid, paid per claim, or paid per beneficiary,
   and these lead to completely different investigations.
2. **What it was compared against** — which peer group, which period. Most false
   positives originate here.
3. **How large the deviation is** — position in the distribution, not just the
   fact of being flagged.
4. **What benign explanations exist** — every factor has them, and they are
   tested first.

---

## Translating factors into next steps

| Factor type | What it points at | First investigative step |
| --- | --- | --- |
| High claim volume | Fabricated or unnecessary encounters, or a large entity | Confirm whether the identifier is one practitioner or many; normalise per beneficiary |
| High total reimbursement | Financial exposure | Normalise by panel and practitioner size; check for pass-through costs |
| High reimbursement per claim | Coding level, service mix | Compare level mix to peers; sample documentation on highest-value claims |
| Unusual procedure frequency | Concentration in a profitable service | Check whether specialty and capability explain it; test indication against diagnoses |
| Unusual diagnosis patterns | Severity or necessity coding | Check whether conditions are supported by treatment and monitoring |
| Duplicate or repeated billing | Billing system defect or edit evasion | Confirm adjustment/replacement handling; check paid vs denied |
| Peer deviation | Comparison validity, or genuine difference | **Verify the peer group before anything else** |
| Sudden change | An event with a date | Identify what changed then; check whether peers moved too |
| Unusual relationships | Coordinated activity or identity misuse | Check organisational and referral relationships; test data quality |

---

## Combining knowledge, data and model output

A complete explanation of a flag draws on three distinct sources, and the
distinction between them must remain visible in the explanation:

- **Model output** — what was detected, at what score, driven by which factors.
  Retrieved, never calculated.
- **Actual data** — the real values behind those factors, and how they compare to
  peers. Retrieved by structured query, never estimated.
- **Domain knowledge** — what those patterns can mean, what can produce them
  benignly, and what to examine next.

Blending these into undifferentiated prose is the main failure mode. A reader
must be able to tell which statements are measured facts and which are general
domain interpretation.

---

## When information is unavailable

If the data layer or the model output is not available for a case, the correct
response is to say so and answer only what the available sources support.

Never estimate a risk score. Never infer a count, total or comparison from
general knowledge. Never present a plausible-sounding number without a source.
An incomplete answer that is clearly marked incomplete is far more useful than a
complete-sounding answer with fabricated components.

---

## Language discipline

**Use:** flagged; elevated risk; high risk; potentially suspicious; warrants
further investigation; the model identified; the data shows; this pattern may
indicate; these findings are consistent with.

**Do not use** unless verified information confirms fraud: this is fraud; the
provider committed fraud; this claim is fraudulent; proven; guilty.

**Always include** the benign possibilities alongside the suspicious reading, and
the next investigative step. An explanation that gives only the adversarial
interpretation is incomplete regardless of how high the score is.

---

## Structure of a good explanation

1. What the model flagged and at what risk level.
2. Which factors contributed.
3. What the actual data shows for those factors, with the comparison basis.
4. What those patterns can mean in fraud terms.
5. What can also produce them legitimately.
6. What the investigator should examine next.
7. An explicit statement that this does not establish fraud.

## Related

`detection_analytics_and_risk_scoring`, `investigation_workflow`,
`comparison_and_analysis_methods`, `fwa_fundamentals`

> The score prioritises. The factors explain. The data evidences. The
> investigator concludes. These roles do not transfer.
