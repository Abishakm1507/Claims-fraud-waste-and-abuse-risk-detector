---
title: Payment Systems and Program Integrity
doc_id: cms_concepts.payment_systems_and_program_integrity
category: cms_concepts
tags: [ms_drg, ipps, opps, apc, prospective_payment, program_integrity, incentives]
source_type: curated_knowledge
version: 2.0
---

# Payment Systems and Program Integrity

How payment is calculated, why that calculation creates the specific incentives
fraud schemes exploit, and who performs review.

---

## Prospective payment: the underlying idea

Rather than paying for each item consumed, prospective payment systems pay a
predetermined amount for a defined unit of care — a hospital stay, an outpatient
encounter — based on the patient's condition and the services delivered.

This design controls cost and rewards efficiency. It also **relocates the fraud
surface**: when payment depends on classification rather than on quantity, the
lever is *how the episode is coded*, not how many items are billed.

Understanding this explains why inpatient and outpatient risk factors look so
different.

---

## MS-DRG and inpatient payment

Inpatient hospital stays are grouped into diagnosis-related groups. Each group
carries a weight reflecting expected resource use, and payment derives from that
weight.

**What drives the group assignment.** The principal diagnosis, secondary
diagnoses (particularly those representing complications or comorbidities),
procedures performed, and discharge status.

**The incentive this creates.** Because secondary diagnoses can shift a stay into
a higher-weighted group, the financial return on adding or inflating severity
coding is direct and substantial. This is the specific mechanism behind inpatient
upcoding, and it is why secondary diagnosis reporting rates are a standard risk
factor.

**Related sensitivities.** Discharge status affects payment — transfers are often
paid differently from routine discharges. Short stays and the boundary between
inpatient and outpatient status carry payment consequences, which is why stays
clustering just past a threshold attract attention.

**What this means for analysis.** Inpatient deviation is usually about
**classification**: severity coding rates, group mix, discharge status coding.
Volume matters less than it does in outpatient settings.

---

## OPPS and APC outpatient payment

Hospital outpatient services are grouped into ambulatory payment classifications,
with services of similar clinical and cost characteristics paid at a common rate.
Some items are packaged into the primary service rather than paid separately.

**The incentive this creates.** Where services are packaged, the return comes
from **separating** them — reporting components individually so each is paid,
rather than accepting the packaged rate. This is the mechanism behind unbundling,
and it explains why edit-overriding modifier rates are the central outpatient
signal.

Volume also matters more here than in inpatient settings, because payment is
generally per encounter or per service rather than per episode.

**What this means for analysis.** Outpatient deviation is usually about
**composition and volume**: lines per encounter, modifier rates, service mix,
encounters per beneficiary.

---

## Why payment design determines risk factors

| Payment mechanism | Financial lever | Resulting scheme | Signature in data |
| --- | --- | --- | --- |
| Weighted episode payment | Classification of the episode | Severity/diagnosis inflation | Elevated secondary diagnosis and complication rates |
| Per-service payment | Code selection | Upcoding | Level mix skewed high; elevated paid per claim |
| Packaged/bundled payment | Separating components | Unbundling | High edit-override modifier rates; many lines per encounter |
| Quantity-based payment | Units and frequency | Overutilization | Units clustering at allowable maximums |
| Risk-adjusted capitation | Diagnosis completeness | Diagnosis inflation | Chronic conditions reported without corresponding treatment |

Reading a risk factor is much easier once you can identify which lever it
corresponds to — and which benign practice patterns also move that lever.

---

## The program integrity landscape

Program integrity work is distributed across several functions, which is why the
same provider may be reviewed by different entities for different purposes:

- **Claims processing contractors** apply edits and adjudicate claims, operating
  at the prepayment control point.
- **Audit and review functions** conduct postpayment medical review, identify
  improper payments, and pursue recovery.
- **Program integrity and investigative functions** develop cases involving
  suspected fraud and refer them onward.
- **Law enforcement and oversight bodies** conduct criminal and civil
  investigations and pursue enforcement action.

**The division of labour is deliberate and important.** Analytic and audit
functions establish that payment was incorrect. Only investigative and
enforcement functions establish intent. A detection platform sits at the earliest
stage of this chain — it identifies candidates for review, and its outputs are
inputs to a process, not conclusions from one.

## Related

`coding_misrepresentation`, `inpatient_and_outpatient_claims`,
`payment_integrity_overview`, `detection_analytics_and_risk_scoring`

> Every scheme is shaped by the payment system it exploits. Identify the lever a
> risk factor corresponds to, and both the suspicious and the benign explanations
> become much clearer.
