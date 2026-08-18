---
title: Inpatient and Outpatient Claims
doc_id: healthcare_claims.inpatient_and_outpatient_claims
category: healthcare_claims
tags: [inpatient, outpatient, admission, discharge, length_of_stay, setting]
source_type: curated_knowledge
version: 2.0
---

# Inpatient and Outpatient Claims

The two claim types are structurally different, priced by different systems, and
must never be pooled into a single benchmark.

---

## Inpatient claim

A claim for care delivered to a patient who has been formally admitted to a
facility and occupies a bed across at least one overnight period.

**Distinguishing features.** Covers a whole stay rather than a single service;
spans an admission date and a discharge date; carries a principal diagnosis plus
secondary diagnoses that affect payment weighting; typically paid as a bundled
amount for the stay rather than per service; includes discharge status
indicating where the patient went next.

**Why it matters for fraud work.** Inpatient care is the highest-cost setting,
and payment is driven by the diagnosis and severity coding rather than by the
count of services delivered. That shifts the fraud surface: the lever is
**coding of the stay**, not volume of line items.

---

## Outpatient claim

A claim for care delivered without formal admission — office visits, clinic
encounters, emergency visits without admission, ambulatory procedures, diagnostic
testing, therapy.

**Distinguishing features.** Usually a single date of service; priced per service
or per group of services; multiple lines each carrying its own code, modifiers
and units; encounters can repeat frequently.

**Why it matters for fraud work.** High volume and lower per-encounter scrutiny
make outpatient the setting where fabricated encounters, repeat services and
fragmentation are most common. The fraud surface here is **volume and line
composition**.

---

## Admission and discharge

**Admission** is the formal decision to place a patient in inpatient status —
itself a clinical judgement subject to review, since the same patient can
sometimes be managed in either setting.

**Discharge** ends the stay and records a status indicating the destination:
home, another facility, transfer, against medical advice, or death.

**Length of stay** is derived from the two dates. It is a core utilization
measure and a routine risk factor.

**Why these fields carry weight.** Admission decisions determine which payment
system applies, and discharge status can change payment — transfers are often
paid differently from routine discharges. Both are therefore points where coding
choices have financial consequences, and both are testable against
documentation.

**Legitimate variation to expect.** Facility role and case-mix drive admission
rates and stay lengths far more than behaviour does. Tertiary centres, trauma
services and facilities serving older or more comorbid populations will show
longer stays and higher admission rates for entirely clinical reasons. Regional
practice patterns and the availability of post-acute options also vary widely.

**What an investigator should examine.** Whether stay length is proportionate to
the documented condition; whether admissions meet documented clinical criteria
for inpatient status; whether short stays cluster just above a threshold that
changes payment; whether readmission patterns suggest premature discharge
followed by rebilling; whether discharge status coding matches what actually
happened.

---

## Why the two must be analysed separately

Inpatient and outpatient claims differ in unit of analysis (a stay versus a
service), pricing mechanism, code sets, and typical value by an order of
magnitude. Pooling them produces meaningless averages, and a provider's apparent
deviation can be entirely an artefact of their inpatient-outpatient mix.

Any peer comparison, per-claim average, or utilization rate must be computed
within a single claim type.

## Related

`claims_fundamentals`, `volume_and_reimbursement`,
`payment_systems_and_program_integrity`, `comparison_and_analysis_methods`

> A high average payment per claim usually means the provider has more inpatient
> activity than their peers, not that they are coding differently. Separate the
> claim types before drawing any conclusion.
