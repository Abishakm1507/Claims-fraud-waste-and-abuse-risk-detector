---
title: Investigation Workflow
doc_id: investigation.investigation_workflow
category: investigation
tags: [provider_investigation, claim_investigation, prioritization, evidence, escalation]
source_type: curated_knowledge
version: 2.0
---

# Investigation Workflow

How a flagged case moves from a model output to a resolved decision.

---

## Provider-level investigation

Examines a provider's behaviour across their full claim population over time.
This is the level at which schemes are visible, because a scheme is a *pattern*,
and no single claim contains a pattern.

**Typical sequence.**

1. **Establish the basis for the flag** — which risk factors fired, what each
   measured, and against which peer group.
2. **Validate the data** — confirm provider attribution, specialty assignment,
   claim type separation, and completeness for the period. Data problems resolve
   a meaningful share of flags before any analysis.
3. **Profile the provider** — volume, payment, service mix, panel size, setting,
   and how each has moved over time.
4. **Benchmark against a defensible peer group** — and re-run if the initial
   group was wrong.
5. **Test benign explanations first** — practice type, case-mix, organisational
   structure, growth, system changes.
6. **Test adversarial explanations** — which specific scheme would produce this
   exact combination of signals, and what else would that scheme also produce?
7. **Sample and review documentation** — the point at which claims analysis stops
   and evidence begins.
8. **Quantify exposure** — the amount actually at risk, in paid dollars.
9. **Decide the remedy** — education, prepayment placement, recovery, or referral.

---

## Claim-level investigation

Examines individual claims in detail, normally as a sample drawn from a
provider-level concern rather than as a starting point.

**What claim review can establish.** Whether documentation supports the code
billed; whether the service was rendered by the practitioner billed; whether the
diagnosis supports the procedure; whether units match documented delivery;
whether the claim duplicates another.

**What claim review cannot establish.** Intent, pattern, or scale. A single
incorrect claim is an error. The same error repeated across a population, after
notice, is something else — and only provider-level work can show that.

---

## Investigation prioritization

Review capacity is always smaller than the flagged population, so prioritisation
is a permanent constraint rather than an occasional one.

**Practical factors.**

- **Financial exposure** — paid dollars actually at risk. Usually the dominant
  factor.
- **Strength and convergence of signal** — several independent factors pointing
  the same way is far stronger than one extreme value.
- **Persistence** — behaviour sustained across periods, especially after prior
  contact or education.
- **Ongoing loss** — whether the conduct is continuing and can be stopped now.
- **Remediability** — whether a cheap control (an edit, a prepayment placement,
  an education letter) resolves it without an investigation.
- **Beneficiary harm** — patterns implying unnecessary care or identity misuse
  carry weight beyond their dollar value.

A high risk score with low exposure and a plausible benign explanation is often
correctly deprioritised. **The score ranks; it does not decide.**

---

## Evidence-based investigation

**Standards that keep findings defensible.**

- Distinguish what the **data shows** from what the **model inferred** from what
  the **investigator concluded**. These are three different things and must not
  be blended in a case narrative.
- State the peer group and the period for every comparison. A deviation claim
  without its comparison basis is not a finding.
- Record benign explanations that were considered and how each was tested or
  ruled out. This is what survives an appeal.
- Prefer paid amounts over charged amounts for all exposure figures.
- Treat documentation as the evidence and claims as the lead.
- Note data limitations explicitly — truncated fields, missing periods,
  attribution ambiguity.

**Language discipline.** Case narratives use *flagged, elevated risk, potentially
suspicious, warrants further investigation, the model identified, the data shows,
this pattern may indicate*. They do not assert fraud unless verified information
confirms it.

---

## Deciding the remedy

Not every valid finding is an investigation.

- **Education** — isolated or systemic error with no indication of intent.
- **Prepayment review** — ongoing loss that must be stopped while work continues.
- **Overpayment recovery** — quantified incorrect payment.
- **Referral for investigation** — evidence of intent, concealment, or
  persistence after notice.

Matching the remedy to the finding matters more than escalating everything.

## Related

`comparison_and_analysis_methods`, `risk_factor_interpretation`,
`payment_integrity_overview`, `fwa_fundamentals`

> Analysis identifies where to look. Documentation establishes what happened.
> Only the second is evidence.
