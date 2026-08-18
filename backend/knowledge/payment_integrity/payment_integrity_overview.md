---
title: Payment Integrity Overview
doc_id: payment_integrity.payment_integrity_overview
category: payment_integrity
tags: [payment_integrity, prepayment, postpayment, edits, recovery, controls]
source_type: curated_knowledge
version: 2.0
---

# Payment Integrity Overview

## What it means

Payment integrity is the discipline of ensuring healthcare claims are paid
**correctly** — the right amount, to the right provider, for the right
beneficiary, for a covered and appropriately documented service, once.

It is broader than fraud detection. Most payment integrity findings are errors,
not schemes: eligibility mismatches, coordination-of-benefits failures, pricing
and contract errors, coding mistakes, and duplicate submissions.

## The three control points

**1. Pre-payment** — controls applied before money moves. Cheapest to correct,
but must run fast and cannot examine long-run behavioural patterns.

**2. Post-payment** — audit and recovery after payment. Can use complete data
and behavioural history, but recovery is costly and often incomplete.

**3. Provider and network management** — enrolment screening, education,
corrective action, prepayment placement, network removal. Addresses the source
rather than individual claims.

## Where FWA detection sits

Fraud detection sits mainly at the post-payment and provider-management control
points, because scheme detection requires **accumulated behaviour over time**,
which is unavailable at the moment a single claim is adjudicated.

This is precisely why a risk engine scores providers and claim populations
rather than approving or denying individual claims in real time.

---

## Prepayment review and claim edits

Controls applied to a claim before payment is released, ranging from automated
rules to manual clinical review.

- **Format and completeness edits** — required fields, valid identifiers, valid
  code formats.
- **Eligibility and coverage edits** — was the beneficiary enrolled, is the
  service covered, is the provider enrolled and authorised.
- **Coding relationship edits** — code pairs that should not be billed together,
  bundling logic, modifier validity.
- **Frequency and unit limits** — maximum units per service per day, service
  frequency caps.
- **Duplicate detection** — matching on beneficiary, provider, date and code.
- **Manual medical review** — documentation requested and reviewed before
  payment, typically targeted at a specific provider or service line.

**Why edits matter analytically.** Edits define what a scheme must evade, which
makes edit behaviour valuable in two ways. First, **evasion is a signal**: claims
modified just enough to pass a known edit — a shifted date, an added modifier, a
split submission — are more probative than raw volume, because they imply
awareness of the control. Second, **prepayment placement is a remedy**: putting a
provider on prepayment review stops loss immediately while an investigation
proceeds, without requiring a fraud determination.

**What this looks like in data.** High denial rates followed by successful
resubmission with small changes; a jump in modifier use immediately after a
denial pattern; claims split across dates to avoid frequency limits; unit counts
sitting exactly at the allowable maximum.

**Legitimate explanations.** Genuine billing corrections after legitimate
denials; correct documented modifier use; billing staff learning payer rules and
improving accuracy; payer edit changes causing temporary spikes in denial and
resubmission.

**What an investigator should examine.** Denial and resubmission history, not
just paid claims — paid-only analysis hides evasion behaviour entirely; what
specifically changed between the denied and accepted versions; whether the change
is supported by documentation; whether prepayment review is the right immediate
control.

---

## Postpayment review and overpayment recovery

Review of claims after payment, to determine whether payment was correct and to
recover any overpayment.

Typical sequence: identify a target population → select claims for review
(census or statistical sample) → request and review documentation → determine
the error rate → calculate the overpayment → notify the provider → allow appeal
→ recover.

**Why this stage constrains everything upstream.** Postpayment review is where
FWA findings are actually quantified, because it is the only stage with access
to complete behavioural history, peer comparisons, and the documentation behind
the claim. It is also where the analytic work must be **defensible** — a provider
can appeal, and the finding must withstand challenge.

This is the practical reason a **risk score is not a finding**. The score selects
the population for review. The finding comes from documentation review.

**Legitimate explanations for apparent overpayment.** Documentation that exists
but was not supplied within the review window; coverage policy ambiguity or
changes during the period reviewed; payer pricing, contract loading or fee
schedule errors; unresolved coordination-of-benefits sequencing; coding
disagreements where the provider's position is defensible.

**What an investigator should examine.** Whether the review population is
correctly and narrowly defined; whether the error is systemic or isolated;
whether the provider had prior notice or education on the issue; whether the
pattern continued after notice — a key intent indicator; whether the correct
remedy is recovery, education, prepayment placement, or referral.

---

## What this means for interpreting a flag

An elevated risk score most often reflects an **error or utilization pattern**,
not a scheme. Explanations should reflect that base rate: the common causes are
billing system defects, coding practice, case-mix, and data quality — with fraud
as one possibility among several, not the default reading.

Practical sequence: establish whether the finding is an error, a practice
pattern, or a potential scheme (these have completely different remedies);
quantify financial exposure before escalating; consider whether education or a
prepayment control resolves it more effectively than an investigation; reserve
fraud referral for cases with evidence of intent, concealment, or persistence
after notice.

## Related

`fwa_fundamentals`, `detection_analytics_and_risk_scoring`,
`services_not_rendered`, `investigation_workflow`

> Most improper payments are mistakes. Recovery establishes that payment was
> incorrect; it does not establish that it was intentional.
