---
title: Provider Patterns and Peer Groups
doc_id: provider_behavior.provider_patterns_and_peer_groups
category: provider_behavior
tags: [billing_patterns, peer_groups, specialty_norms, capacity, referral_patterns]
source_type: curated_knowledge
version: 2.0
---

# Provider Patterns and Peer Groups

How to characterise a provider's behaviour, and how to build the comparison that
makes that characterisation meaningful.

---

## What a provider billing pattern is

The stable profile of how a provider bills, described across several dimensions
at once:

- **Volume** — claims, services, encounters, normalised by panel and
  practitioner count.
- **Service mix** — which codes make up their work, and in what proportions.
- **Intensity** — level mix within code families, units per service, lines per
  encounter.
- **Payment profile** — paid per claim, per beneficiary, concentration of revenue.
- **Panel characteristics** — size, demographics, comorbidity, turnover.
- **Temporal shape** — stability, growth, seasonality, step changes.

A pattern is only interpretable as a **whole**. Single metrics are weak evidence;
patterns that deviate across several independent dimensions simultaneously are
what carry weight, because benign causes usually explain one dimension rather
than several at once.

---

## Peer group construction

A peer group is a constructed analytic object, not a fact in the data. Its
definition determines what counts as deviation, and therefore determines what
gets flagged.

**Dimensions that usually need to match.**

- **Specialty**, at the right granularity. Subspecialty differences are often
  larger than the difference between a flagged provider and their nominal peers.
- **Care setting** — office, hospital outpatient, inpatient facility, ambulatory
  surgical, home, telehealth.
- **Entity type** — individual practitioner versus group versus institution. This
  is the single most common mismatch and produces the most dramatic false
  positives.
- **Geography** — practice patterns, payment rates and population health vary
  regionally.
- **Panel size** — small denominators destabilise every ratio metric.
- **Case-mix** — the strongest adjustment available, and the most often missing.

**Failure modes to check for.**

- Group too broad — real differences in practice type read as deviation.
- Group too narrow — unstable statistics, and a scheme shared across the group
  becomes the norm and disappears.
- Stale specialty data — providers benchmarked against a field they no longer
  practise.
- Mixed entity types — organisations and individuals in one distribution.
- No case-mix adjustment where acuity varies widely.

**Because peer group error is the leading cause of false positives, verifying the
peer group is the highest-yield first step when reviewing any deviation flag.**

---

## Specialty billing norms

Different specialties have fundamentally different, entirely legitimate billing
shapes:

- Some are **high-volume, low-value** — many brief encounters.
- Some are **low-volume, high-value** — few, expensive interventions.
- Some are **procedure-concentrated** — most revenue from a narrow code set.
- Some are **diagnostic-heavy** — high ancillary-to-encounter ratios.
- Some are **episode-based** — clusters of activity around discrete events.

A provider whose shape does not match their recorded specialty is worth
examining — but the first hypothesis should be that **the specialty coding is
wrong**, not that the behaviour is. Specialty data is frequently self-reported,
outdated, or too coarse to capture actual practice.

---

## Provider volume and capacity

Capacity analysis tests whether billed activity is **physically possible**,
independent of any comparison group. It is one of the few analyses that does not
depend on peer construction.

**What to check.** Total billed service time per day against available hours;
encounters per day against realistic throughput; simultaneous services at
different locations; activity on days the practice was closed; volume relative to
the number of practitioners actually enrolled under the identifier; whether
facility capacity supports the billed inpatient volume.

**Legitimate explanations to rule out first.** A billing identifier covering many
practitioners; group and incident-to billing arrangements; locum coverage;
supervision arrangements; telehealth removing geographic constraints; backdated
submissions distorting date-based totals; time-unit definitions being
misinterpreted by the analyst.

**Why it is valuable.** Where capacity is genuinely exceeded after these are
ruled out, the finding is difficult to explain benignly — far more so than an
elevated percentile.

---

## Beneficiary sharing and referral patterns

Relational structure that per-provider metrics cannot see.

**What to look at.** Overlap between provider panels; beneficiary clusters
appearing across a small set of otherwise unconnected providers; directionality
and concentration of referral flows; the geographic spread of a provider's panel;
whether beneficiaries have plausible care relationships with everyone billing for
them.

**Why it matters.** Coordinated schemes distribute activity so that no single
provider looks extreme. Network structure can reveal what per-entity metrics
deliberately hide.

**Legitimate explanations.** Integrated delivery systems, group practices and
formal referral networks share patients by design; facility-based practice means
many practitioners see the same inpatients; specialty care requires travel;
telehealth removes geography entirely; rural areas concentrate care in few
providers; identity resolution errors merge or split beneficiary records and
manufacture false overlap.

**What an investigator should examine.** Whether an organisational or referral
relationship explains the overlap; whether the same entity cluster recurs across
multiple independently flagged cases; whether beneficiaries recognise all
providers billing for them; whether beneficiary identity data quality could
produce the structure artificially.

## Related

`claims_fundamentals`, `peer_deviation_and_outliers`,
`comparison_and_analysis_methods`, `fraud_actors`

> Before concluding that a provider is unusual, confirm you have compared them to
> the right providers, and that their billing identifier means what you assume.
