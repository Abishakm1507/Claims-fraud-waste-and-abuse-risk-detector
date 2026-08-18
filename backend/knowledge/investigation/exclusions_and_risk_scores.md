---
title: Exclusions and Risk Score Interpretation
doc_id: investigation.exclusions_and_risk_scores
category: investigation
tags: [leie, exclusion, 1128, risk_score, risk_tier, isolation_forest, anomaly_score, hhi]
source_type: curated_knowledge
version: 1.0
---

# Exclusions and Risk Score Interpretation

Reference for the specific signals this platform's detection model reports.

---

## OIG exclusion (LEIE)

**What it means.** The List of Excluded Individuals and Entities (LEIE) is
maintained by the HHS Office of Inspector General. A person or organisation on
it is barred from participating in federal healthcare programs. No federal
payment may be made for items or services they furnish, order or prescribe.

**Exclusion authorities** appear as statute codes:

- **1128(a)** — mandatory exclusions. `1128A1` program-related conviction,
  `1128A2` patient abuse or neglect, `1128A3` felony healthcare fraud,
  `1128A4` felony controlled-substance conviction.
- **1128(b)** — permissive exclusions, applied at OIG discretion. `1128B4` is
  the most common: license revocation, suspension or surrender.

**Why an exclusion match matters.** Unlike a statistical anomaly, an exclusion
is a documented enforcement action. Payment to an excluded party is an improper
payment regardless of whether the service was appropriate.

**Why it still is not proof of fraud in a given claim.** Many exclusions are
licensure actions rather than fraud convictions. `1128B4` is a license issue,
not a finding of billing misconduct. The exclusion establishes ineligibility for
payment; it does not establish that a particular claim was fraudulent.

**Matching caveat that matters.** A large share of LEIE records carry no NPI,
because many excluded individuals are aides and support staff who never had one.
Matching on name and state alone produces frequent false positives — a common
name in a populous state will collide. Only an exact identifier match should be
treated as confirmed; a name match is a lead requiring verification against
date of birth, address, licence number and specialty.

**What an investigator should examine.** Whether the match is on an exact
identifier or a name; whether the exclusion period overlaps the dates of
service; the exclusion authority, since mandatory and permissive exclusions
carry different weight; whether reinstatement has occurred; whether the excluded
party's services were billed under another provider's identifier.

---

## Reading a unified risk score

**What the score is.** A 0-100 prioritisation value blended from several
components, each percentile-ranked within the scored population before
weighting. It expresses how unusual a provider looks relative to that
population.

**What it is not.** Not a probability that fraud occurred, not an estimate of
financial exposure, not comparable across model versions or scoring runs, and
not a determination of any kind.

**Tiers** (Low / Moderate / High / Critical) are thresholds applied to the
score. They are operational choices balancing review capacity against missed
cases, not natural categories. A provider just above a boundary is not
materially different from one just below it.

**Why components matter more than the total.** Two providers can share a score
and have nothing in common. One may be flagged for extreme service concentration
and another for price deviation. The components say *why*, and only the
components can be investigated.

---

## Component signals

**Statistical anomaly score (Isolation Forest).** An unsupervised measure of how
easily a provider is separated from the rest of the population across many
features at once. It captures unusual *combinations* that no single metric
reveals. Because it is unsupervised, it is trained without any fraud label — it
learns what is unusual, not what is fraudulent. A high anomaly score means the
provider's overall profile is atypical, and nothing more.

**Peer deviation score.** How far the provider sits from same-specialty peers
across standardised metrics, usually expressed as z-scores or percentiles. Its
quality depends entirely on peer group construction: a subspecialist benchmarked
against generalists will deviate for reasons that have nothing to do with
behaviour.

**Service pattern concentration (HHI).** The Herfindahl-Hirschman Index measures
how concentrated a provider's billing is across procedure codes. It is the sum
of squared shares: near 0 means work spread evenly across many codes, near 1
means nearly all revenue from a single code.

High concentration can indicate billing driven by one profitable service. It is
also entirely normal for focused practices — a dialysis centre, an imaging
facility, or a single-procedure surgical practice will show high HHI by design.
Concentration is only meaningful against the concentration of true peers.

**Geographic price deviation.** Compares the provider's average payment or
charge for each procedure against state and national benchmarks for the same
procedure. Because it compares like with like at code level, it is less
sensitive to service-mix differences than aggregate metrics. Elevated deviation
means the provider is paid more than others for the same work, which can reflect
site of service, patient complexity, or payment locality adjustments.

---

## Deviation ratios and percentiles

A **deviation ratio** expresses a provider's value as a multiple of the peer
median: 5.3x means five times the typical peer. A **percentile** expresses
position within the peer distribution: 99th means only 1% of peers are higher.

The two answer different questions. A ratio quantifies magnitude; a percentile
quantifies rarity. A modest ratio can still be an extreme percentile in a tight
distribution, and a large ratio can be unremarkable in a highly skewed one.
Report both where available.

---

## What an investigator should do with a high score

1. Read the components, not the total — they determine the investigation.
2. Verify the peer group is appropriate to the provider's actual practice.
3. Check whether deviation appears on several independent dimensions.
   Convergence is far stronger evidence than one extreme metric.
4. Establish financial exposure in paid dollars, which determines priority.
5. Test benign explanations — case-mix, subspecialty focus, site of service,
   legitimate growth, data quality — before adversarial ones.
6. Move to documentation review, which is where evidence begins.

> A model trained without fraud labels identifies statistical anomalies. It
> cannot identify fraud, and its output is a starting point for investigation
> rather than a conclusion.
