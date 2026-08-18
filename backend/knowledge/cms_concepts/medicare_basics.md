---
title: Medicare Basics
doc_id: cms_concepts.medicare_basics
category: cms_concepts
tags: [medicare, coverage, parts, npi, identifiers, claim_lifecycle, adjudication]
source_type: curated_knowledge
version: 2.0
---

# Medicare Basics

Background an investigator needs to interpret claims data correctly. General
educational content about program structure.

---

## What Medicare is

A United States federal health insurance program administered by the Centers for
Medicare & Medicaid Services (CMS), covering primarily people aged 65 and older,
along with certain younger people with disabilities and people with end-stage
renal disease.

Its scale is why it matters analytically: a very large beneficiary population and
claim volume, which makes systematic analysis both necessary and feasible, and
makes even small per-claim errors financially significant in aggregate.

---

## Coverage parts

Medicare is organised into parts, each covering different services and generating
different claim data:

- **Part A — hospital insurance.** Inpatient hospital stays, skilled nursing
  facility care, hospice, some home health. Produces institutional claims
  covering an entire stay.
- **Part B — medical insurance.** Physician services, outpatient care,
  diagnostics, durable medical equipment, preventive services. Produces
  professional and outpatient claims, generally per service.
- **Part C — Medicare Advantage.** Coverage delivered through private plans that
  receive risk-adjusted payments. Data availability and structure differ from
  fee-for-service, and the payment mechanism creates different incentives —
  notably around diagnosis reporting completeness.
- **Part D — prescription drug coverage.** Delivered through private plans.
  Produces pharmacy claim data.

**Why the distinction matters for analysis.** Different parts produce different
claim types with different structures, code sets, and pricing. Pooling them
produces meaningless comparisons, and the fraud surface differs across them.

---

## Provider identifiers

**NPI (National Provider Identifier)** — a unique ten-digit identifier assigned to
healthcare providers in the United States, used on claims to identify billing,
rendering, referring and other provider roles.

**Key analytic caution.** An NPI may belong to an **individual practitioner** or
to an **organisation**. Organisational NPIs can cover many practitioners. Treating
the two as equivalent in a volume or capacity analysis produces some of the most
severe false positives in provider analytics — an organisation will always look
extraordinary next to individuals.

A single claim carries several provider roles, and attributing behaviour to the
wrong role misdirects an investigation. Confirm which role a dataset field
represents before building provider-level metrics.

---

## Beneficiary identifiers

Beneficiaries are identified by program identifiers that link claims to a person
and to their enrolment and coverage periods.

**Analytic cautions.** Identifiers can change over time, which fragments a
beneficiary's history unless properly linked. Identity resolution errors either
merge distinct people or split one person into several, and both distort every
per-beneficiary metric and every network analysis. Beneficiary identifiers are
also a target for misuse, which is why beneficiaries appearing in suspicious
patterns are frequently victims rather than participants.

---

## The claim lifecycle

1. **Service delivered** and documented in the medical record.
2. **Claim prepared** — coded by the provider or a billing agent.
3. **Submitted** — often through a clearinghouse, in a standard electronic format.
4. **Edits applied** — format, eligibility, coverage, coding relationship,
   frequency and duplicate checks.
5. **Adjudicated** — the claim is priced under the applicable payment system and
   approved, reduced, or denied.
6. **Paid**, with cost-sharing and coordination of benefits applied.
7. **Remittance** issued to the provider explaining the outcome.
8. **Adjustments** — corrections, replacements, voids, appeals, and recoveries,
   which can occur long after original payment.

**Two consequences that shape every analysis.**

First, **claims data is not static**. Adjustments, replacements and recoveries
change the record after the fact. An analysis run at one point may not reproduce
later, and adjustment records misread as originals inflate duplicate counts.

Second, **denied claims are data too**. Analyses restricted to paid claims cannot
see denial-and-resubmission behaviour, which is where edit evasion is visible.

## Related

`claims_fundamentals`, `payment_systems_and_program_integrity`,
`payment_integrity_overview`, `provider_patterns_and_peer_groups`

> Confirm whether a provider identifier represents a person or an organisation
> before computing anything per-provider. This one check prevents a large share
> of false positives.
