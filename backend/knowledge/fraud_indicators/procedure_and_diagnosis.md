---
title: Procedure and Diagnosis Indicators
doc_id: fraud_indicators.procedure_and_diagnosis
category: fraud_indicators
tags: [procedure_frequency, diagnosis_patterns, code_combinations, coding_integrity]
source_type: curated_knowledge
version: 2.0
---

# Procedure and Diagnosis Indicators

Signals derived from *what* was billed rather than *how much*. These are often
more specific than volume indicators, because clinical coding carries meaning
that can be tested against the patient's documented condition.

---

## Unusual procedure frequency

**What it means.** A provider performs or bills a specific procedure far more
often than comparable providers, either in absolute terms or as a share of their
total service mix.

**Why it may be suspicious.** Concentration in a single procedure — particularly
a high-margin one — can indicate that billing is driven by reimbursement rather
than clinical need. Fabricated services also tend to concentrate, because a
scheme repeats what works.

**How it appears in claims data.** One procedure code representing a much larger
share of the provider's volume than for peers; the same procedure billed to a
high proportion of the beneficiary panel; procedure counts per beneficiary above
norms; near-identical service patterns across clinically dissimilar patients;
procedures appearing at fixed intervals regardless of patient condition.

**Possible legitimate explanations.** Focused or subspecialty practice built
around a specific procedure; referral patterns concentrating particular cases;
service lines where a single procedure is the core offering; guideline-driven
protocols requiring repeat procedures; equipment or capability that peers lack;
small volumes making share-based measures unstable.

**What an investigator should examine.** Whether the provider's stated specialty
and capabilities explain the concentration; whether the procedure is indicated by
the documented diagnoses; whether patients receiving it differ clinically from
those who do not; whether frequency per beneficiary is clinically plausible;
whether the concentration is in the highest-reimbursing available option;
documentation for a sample of the concentrated procedure.

---

## Unusual diagnosis patterns

**What it means.** The diagnoses reported by a provider differ markedly from
peers — in mix, in severity, in specificity, or in how consistently they appear.

**Why it may be suspicious.** Diagnosis codes justify payment. Adding,
inflating, or fabricating diagnoses can raise payment (through severity
weighting), establish medical necessity for services that would otherwise be
denied, or support a risk-adjusted payment arrangement.

**How it appears in claims data.** Severity or complication diagnoses reported far
more often than peers; the same diagnosis appearing on nearly every claim; a
sudden increase in diagnosis specificity or count per claim without a change in
population; diagnoses that rarely appear together clinically appearing routinely;
chronic conditions reported without any corresponding treatment or monitoring;
diagnosis mix inconsistent with the provider's specialty.

**Possible legitimate explanations.** Genuine documentation improvement capturing
conditions previously under-reported; a genuinely comorbid population; specialty
practice where certain diagnoses are expected on nearly every patient; coding
system or guideline changes altering reporting; risk-adjustment programs that
legitimately encourage complete chronic condition reporting; referral centre
receiving complex cases.

**What an investigator should examine.** Whether reported conditions are
supported by documented clinical evidence in the record; whether diagnoses are
accompanied by the treatment or monitoring you would expect them to generate;
whether a shift coincides with a system, vendor, or program change; whether
diagnosis reporting varies with the patient or is uniform; whether the added
diagnoses are specifically the ones that change payment.

---

## Unusual procedure and diagnosis combinations

**What it means.** Procedures billed with diagnoses that do not clinically
support them, or diagnosis-procedure pairings that appear at rates far above
peers.

**Why it may be suspicious.** This is one of the more specific signals available,
because the relationship between condition and treatment is clinically
constrained. A procedure billed without a supporting indication is either a
coding error or an attempt to establish necessity for a service that lacks one.

**How it appears in claims data.** Procedures billed against diagnoses that do
not indicate them; a single generic diagnosis used to justify a wide range of
procedures; diagnoses that appear only when a particular procedure is billed;
combinations that pass necessity edits but are clinically implausible;
sex-, age-, or site-inconsistent pairings.

**Possible legitimate explanations.** The supporting diagnosis is recorded on a
different claim or encounter in the episode; rule-out or diagnostic workup where
the final diagnosis is not yet established; incidental findings during a
procedure performed for another reason; coding sequence errors placing the
principal diagnosis incorrectly; legitimate off-label or atypical clinical
practice; data truncation where only a limited number of diagnosis fields are
retained.

**What an investigator should examine.** Whether the full episode of care — not
the single claim — contains a supporting indication; whether documentation
records the clinical reasoning; whether the same generic diagnosis is being
reused across unrelated services; whether implausible combinations concentrate in
particular codes or periods; whether the dataset truncates diagnosis fields,
which can create false signals.

## Related

`coding_misrepresentation`, `unnecessary_and_excessive_services`,
`coding_fundamentals`, `comparison_and_analysis_methods`

> Code-level signals are specific but fragile. Truncated diagnosis fields and
> episode fragmentation produce apparent mismatches that are pure data artefacts.
