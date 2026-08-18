---
title: Services Not Rendered and Duplicate Billing
doc_id: fraud_concepts.services_not_rendered
category: fraud_concepts
tags: [phantom_billing, services_not_provided, duplicate_billing, repeated_billing]
source_type: curated_knowledge
version: 2.0
---

# Services Not Rendered and Duplicate Billing

Schemes where the claim asserts activity that did not occur as billed, or seeks
payment more than once for the same activity.

---

## Phantom billing

**What it means.** Claims for services, supplies, visits or procedures that never
took place at all. Variants: visits with beneficiaries never seen; equipment or
supplies never delivered; tests never performed or interpreted; services
attributed to beneficiaries whose identifiers were obtained improperly; services
billed under a provider identifier without that provider's knowledge.

**Why it may be suspicious.** With no real clinical activity constraining the
pattern, phantom billing frequently produces volumes and combinations exceeding
what a real practice could physically deliver.

**How it appears in claims data.**

- Service volume implying implausible working hours or throughput.
- Beneficiaries billed by geographically distant providers with no plausible
  care relationship.
- Services billed on dates when the beneficiary was demonstrably elsewhere —
  for example outpatient visits overlapping an inpatient stay.
- Beneficiaries with no other claims history suddenly generating dense activity
  from one provider.
- Repetitive, templated claim lines with little clinical variation.
- Billing continuing after a beneficiary's death or a provider's departure.

**Possible legitimate explanations.**

- Data entry or identifier errors placing claims under the wrong provider or
  beneficiary.
- Legitimate telehealth or remote interpretation explaining geographic distance.
- Locum tenens, group billing, or supervising-physician arrangements where the
  billing identifier is not the performing individual.
- Backdated or delayed submissions distorting date-based analysis.
- Mobile, home-visit, or facility-round practices with atypical patterns.

**What an investigator should examine.** Whether the beneficiary can confirm the
encounter; whether records exist that predate claim submission; timeline
conflicts and impossible service-hour totals; whether beneficiary identifiers
appear across unrelated providers, suggesting identifier compromise; whether the
billing identifier matches who actually rendered care.

---

## Billing for services not provided (partial cases)

**What it means.** Broader than phantom billing, covering partial falsity that is
harder to detect: a service started but not completed yet billed as complete; a
bundled component never performed; care rendered by unqualified personnel but
billed as if by a qualified practitioner; time-based services billed for more
time than delivered; supervision or interpretation billed without the
supervising practitioner's involvement; group services billed as individual
sessions.

**Why it may be suspicious.** The claim asserts facts about what happened. When
the assertion is false the payment is unearned, even though *some* care occurred.
These cases are usually invisible at the level of an individual claim.

**How it appears in claims data.** Time-based totals implying more service hours
than available; supervising-practitioner volumes exceeding plausible personal
involvement; high per-beneficiary density with little clinical variation;
consistent billing of maximum allowable units; services billed with none of the
downstream activity you would expect to follow them.

**Possible legitimate explanations.** Valid incident-to, supervision or
team-based billing arrangements; group practice conventions where the billing
identifier is the entity; documentation held in systems not yet reviewed;
unit-of-service misunderstandings; legitimately intensive treatment programs.

**What an investigator should examine.** Contemporaneous documentation for
sampled services; staffing, licensure and scheduling records against billed
times; total billed service hours per practitioner per day; beneficiary
confirmation; whether unit counts match documented delivery.

---

## Duplicate and repeated billing

**What it means.** Submitting more than one claim for the same service,
beneficiary and date of service. Includes exact resubmission of a paid claim;
the same service billed by two entities without a valid split arrangement; the
same service billed to two payers without coordination of benefits; and
near-duplicates where a code, modifier or date is altered slightly to evade
automated duplicate edits.

**Why it may be suspicious.** Payers deploy automated duplicate edits, so
duplicates that *survive* those edits suggest either a systemic billing defect or
deliberate evasion. Small variations engineered to defeat a known edit are
particularly probative — they indicate awareness of the control.

**How it appears in claims data.**

- Multiple lines sharing beneficiary, provider, date and procedure code.
- Same service, same date, different providers within one organisation.
- High volumes of adjustment, replacement or void-and-rebill transactions.
- Claims differing only by a modifier, a one-day date shift, or a trivially
  different code.

**Possible legitimate explanations.**

- Corrected or replacement claims legitimately superseding an original.
- Services genuinely performed more than once on the same day (repeat imaging,
  repeat labs, bilateral procedures), usually signalled by modifiers.
- Split billing between professional and technical components.
- Coordination-of-benefits sequencing across primary and secondary payers.
- Clearinghouse or EDI transmission errors causing accidental resubmission.

**What an investigator should examine.**

1. Whether duplicates were paid or denied — only paid duplicates create exposure
   and a recovery obligation.
2. Whether modifiers correctly and truthfully justify repeat services.
3. Whether the pattern concentrates in a period, a code, or a billing system,
   which suggests a technical defect rather than intent.
4. Whether variations look engineered to evade a specific edit.
5. Coordination-of-benefits records, to rule out multi-payer duplication.

## Related

`duplication_and_repetition`, `payment_integrity_overview`,
`provider_patterns_and_peer_groups`, `fraud_actors`

> Claims data can show that billed services are implausible. It cannot by itself
> show that they did not occur. Most duplicate patterns are system defects.
