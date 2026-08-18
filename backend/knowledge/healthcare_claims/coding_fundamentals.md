---
title: Coding Fundamentals
doc_id: healthcare_claims.coding_fundamentals
category: healthcare_claims
tags: [diagnosis_code, procedure_code, modifiers, units, principal_diagnosis]
source_type: curated_knowledge
version: 2.0
---

# Coding Fundamentals

Codes are how a claim describes clinical reality, and they determine payment.
Understanding what each code type asserts is prerequisite to interpreting any
coding-based risk factor.

---

## Diagnosis codes

Standardised codes describing the patient's condition — what is wrong, and why
care was needed.

**Structure.** Modern diagnosis code sets are hierarchical and highly specific,
capturing not just the condition but often its location, severity, stage,
laterality and episode of care. Codes generally begin with a letter followed by
digits (for example `I10` for essential hypertension), with additional characters
adding specificity.

**Principal versus secondary.** The **principal diagnosis** is the condition
chiefly responsible for the encounter or admission. **Secondary diagnoses**
capture comorbidities and complications. On inpatient claims, secondary
diagnoses can substantially change payment by shifting the stay into a
higher-weighted group — which is why secondary diagnosis reporting patterns are a
standard analytic target.

**What diagnosis codes do in the payment system.** They establish medical
necessity for procedures, drive severity weighting on inpatient stays, and
support risk-adjusted payment arrangements.

**Data caveat that matters constantly.** Many datasets retain only a limited
number of diagnosis fields per claim. Truncation creates apparent
procedure-diagnosis mismatches that are pure artefacts. Confirm field capacity
before treating a missing indication as a finding.

---

## Procedure and service codes

Standardised codes describing what was actually done — the service, procedure,
item or supply being billed.

**Common code families.** Procedure and service coding uses several coexisting
systems: codes for physician and outpatient services (for example `99213` for an
office visit); codes for supplies, drugs and equipment; and separate procedure
coding used for inpatient hospital procedures. Which set applies depends on the
setting and the payment system.

**What procedure codes do in the payment system.** They are the primary
determinant of payment amount in outpatient and professional billing. Selecting a
different code changes the payment, which is exactly the mechanism upcoding and
unbundling exploit.

---

## Modifiers

Two-character suffixes appended to a procedure code that qualify it without
changing its identity — indicating, for example, that a service was bilateral,
repeated, performed by a different practitioner, distinct from another service on
the same day, or reduced in scope.

**Why modifiers carry disproportionate analytic weight.** Modifiers can
**override automated payment edits**. A bundling edit that would otherwise deny a
code pair can be bypassed by a modifier asserting the services were distinct.
This makes modifier usage the central signal for unbundling and duplicate
detection.

The signal is never modifier *use* — modifiers are routine, necessary and
correct in most cases. The signal is a rate of edit-overriding modifier use far
above peers, combined with documentation that does not support the assertion the
modifier makes.

---

## Units of service

The quantity billed on a claim line — minutes, sessions, doses, items.

Units are a frequent target because they multiply payment directly without
requiring any change to the codes. The characteristic pattern is units clustering
at the allowable maximum rather than distributing naturally across patients.

Unit definitions vary by code and are a common source of honest error: a code
billed in 15-minute increments and one billed per session look identical in the
data but mean very different things.

---

## How coding drives payment, and therefore drives risk factors

Three mechanisms account for most coding-based risk factors:

1. **Code selection** — a higher-level or more complex code pays more (upcoding).
2. **Code composition** — billing components separately pays more than the bundle
   (unbundling).
3. **Diagnosis weighting** — severity and complication codes raise inpatient
   payment and justify necessity (diagnosis inflation).

Each mechanism produces a distinct data signature, which is why risk factors are
usually specific about *which* coding dimension deviated.

## Related

`coding_misrepresentation`, `procedure_and_diagnosis`, `claims_fundamentals`,
`payment_systems_and_program_integrity`

> Code references here are generic teaching examples of public code-set
> structure. They are not observations about any provider or claim.
