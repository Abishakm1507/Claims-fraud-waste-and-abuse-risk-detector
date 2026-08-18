---
title: Comparison and Analysis Methods
doc_id: investigation.comparison_and_analysis_methods
category: investigation
tags: [peer_comparison, outlier_analysis, reimbursement_analysis, utilization_analysis, trend_analysis]
source_type: curated_knowledge
version: 2.0
---

# Comparison and Analysis Methods

The analytic techniques an investigator applies once a case is opened.

---

## Peer comparison

Measuring a provider against a group of comparable providers on the same metric,
same period, same definitions.

**Constructing a defensible peer group.** Match on specialty (at the right level
of granularity — subspecialty matters), care setting, geography, panel size, and
case-mix where possible. Exclude providers whose billing identifier represents a
fundamentally different kind of entity.

**Why this dominates result quality.** A wrong peer group manufactures deviation
out of nothing. A subspecialist benchmarked against generalists will appear to
upcode; an organisation benchmarked against individuals will appear to
over-bill. Checking the peer group is the highest-yield first step in reviewing
any deviation-based flag.

**Reporting requirement.** Always state the peer group definition, its size, and
the period. A percentile without its comparison basis is not interpretable.

---

## Outlier analysis

Identifying values far outside the expected range.

**Method notes.** Percentile-based measures are more robust than
standard-deviation measures on claims data, which is heavily skewed and rarely
normally distributed. Small denominators produce unstable ratios — a provider
with few beneficiaries can top a per-beneficiary ranking on a handful of claims.

**Mandatory first step.** Verify the data. The most extreme values in claims
datasets are disproportionately errors: duplicated records, unit misreporting,
decimal and scaling errors, or an identifier aggregating many practitioners.

**Interpretation limit.** Every distribution has a top percentile by
construction. Occupying it is a position, not a finding.

---

## Reimbursement analysis

Examining payment patterns.

**What to compute.** Total paid; paid per claim; paid per beneficiary; paid per
practitioner; concentration of payment across codes and beneficiaries; the split
between charged, allowed and paid.

**Interpretation guidance.** Distinguish payment driven by **volume** from
payment driven by **mix**. Rising totals with a flat per-claim average indicate
growth; a rising per-claim average with flat volume indicates a change in what is
being billed — the second is the more specific signal. Always use paid amounts.
Always separate claim types.

---

## Utilization analysis

Examining service quantities relative to population.

**What to compute.** Services per beneficiary; visits or admissions per
beneficiary; units per service; episode length; the distribution of each, not
just the mean.

**Interpretation guidance.** Normalise everything — raw counts confound size with
behaviour. Examine distributions: clustering at policy or payment limits is a
much stronger signal than an elevated average, because clinical need does not
produce clustering at administrative boundaries. Case-mix must be considered
before concluding that utilization is excessive.

---

## Procedure analysis

Examining what was billed and in what combination.

**What to compute.** Service mix as a share of the provider's volume; level mix
within a code family; modifier usage rates; frequency of specific code pairs on
the same encounter; procedure-to-diagnosis consistency; lines per encounter.

**Interpretation guidance.** Share-based measures are more informative than
counts because they are size-independent. Low variance is itself a signal —
clinically driven coding varies with the patient, templated coding does not.
Edit-overriding modifier rates are the specific measure for unbundling.

---

## Trend analysis

Examining how a provider's profile moves over time.

**What to compute.** Period-over-period volume, payment, per-claim value and
service mix; the date and size of any step change; whether the provider's
percentile position within the peer group is stable or moving.

**Interpretation guidance.** Change is often more diagnostic than level, because
a change has a cause with a date attached. Always test whether peers moved at the
same time — a simultaneous shift across the peer group indicates an external
cause (policy change, fee schedule update, coding guideline revision) and
usually clears the provider. Distinguish a sustained new level from a transient
spike.

---

## Cross-cutting rules

1. **Normalise before comparing.** Per-beneficiary and per-practitioner, not raw
   totals.
2. **Separate claim types.** Inpatient and outpatient are never pooled.
3. **Use paid amounts.** Charged amounts overstate everything.
4. **Prefer distributions to averages.** Means hide the shape that carries the
   signal.
5. **State the basis.** Peer group, period, and metric definition accompany every
   comparison.
6. **Check convergence.** One extreme metric is weak; several independent metrics
   agreeing is strong.

## Related

`peer_deviation_and_outliers`, `investigation_workflow`,
`provider_patterns_and_peer_groups`, `detection_analytics_and_risk_scoring`

> Most apparent deviation dissolves under a corrected peer group and normalised
> metrics. Do that work before interpreting anything.
