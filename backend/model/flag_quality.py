"""
Flag quality assessment.

THE QUESTION THIS ANSWERS
"Is this flag worth acting on?" - which is different from "how high is the
score?" and is the question an investigator actually faces when triaging a
queue.

WHY NOTHING ELSE IN THE PIPELINE CAN ANSWER IT
The agents score one case in isolation. They correctly report peer sample size,
skipped agents and stated limitations, but they do not judge what those mean for
the reliability of their own output - and the contract forbids this module from
recomputing their score.

Assessing reliability is not recomputing. This module reads only what the
handoff already states, applies the standards in the knowledge base, and reports
how much weight the evidence can bear.

THE STANDARDS APPLIED, ALL FROM THE KNOWLEDGE BASE
- A peer group that is too small cannot define a distribution, and a wrong or
  unstable peer group is the leading cause of false positives.
- Convergence across several independent findings is far stronger evidence than
  one extreme metric.
- Missing data is not low risk. A skipped agent means a dimension was never
  checked, not that it was checked and found clean.
- Deviation magnitude and rarity answer different questions, so both matter.

WHAT THIS NEVER DOES
It never changes the score, never overrides the risk category, and never clears
a provider. It reports how much confidence the stated evidence supports, so an
investigator can prioritise - and so a thin flag is not pursued as though it
were a strong one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Below this, a peer cohort cannot define a stable distribution. Matches the
# MIN_PEER_COHORT the assistant's own peer comparison uses.
MIN_RELIABLE_PEER_SAMPLE = 20
SMALL_PEER_SAMPLE = 50


@dataclass
class QualityAssessment:
    """How much weight the evidence behind a flag can bear."""

    confidence: str = "unknown"          # strong | moderate | limited | unknown
    summary: str = ""
    strengthens: list[str] = field(default_factory=list)
    weakens: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    recommended_posture: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_confidence": self.confidence,
            "summary": self.summary,
            "strengthens_the_flag": self.strengthens,
            "weakens_the_flag": self.weakens,
            "not_checked": self.gaps,
            "recommended_posture": self.recommended_posture,
        }

    def as_prompt_block(self) -> str:
        lines = [f"Evidence confidence: {self.confidence.upper()}", self.summary]
        if self.strengthens:
            lines.append("\nWhat strengthens the flag:")
            lines += [f"- {x}" for x in self.strengthens]
        if self.weakens:
            lines.append("\nWhat weakens it, or argues it may be an artefact:")
            lines += [f"- {x}" for x in self.weakens]
        if self.gaps:
            lines.append("\nNot checked (absence of a finding here is not a "
                         "clean result):")
            lines += [f"- {x}" for x in self.gaps]
        if self.recommended_posture:
            lines.append(f"\nSuggested posture: {self.recommended_posture}")
        return "\n".join(lines)


def _pct(v) -> float | None:
    if v is None:
        return None
    return v * 100 if v <= 1 else v


def assess_handoff(case) -> QualityAssessment:
    """Assess a parsed multi-agent HandoffCase."""
    q = QualityAssessment()
    if not getattr(case, "available", False):
        q.summary = "No case supplied, so evidence quality cannot be assessed."
        return q

    strong = weak = 0

    # --- convergence: independent findings agreeing is the strongest signal ---
    agents = {f.agent for f in case.findings if f.agent}
    n_find = len(case.findings)
    if len(agents) >= 2:
        q.strengthens.append(
            f"{n_find} findings across {len(agents)} independent agents "
            f"({', '.join(sorted(agents))}). Convergence across separate "
            f"methods is stronger than any single extreme metric.")
        strong += 2
    elif n_find == 1:
        q.weakens.append(
            "Only one finding, from a single agent. A lone signal is weak "
            "evidence and is the pattern most often explained by case-mix or "
            "an imperfect comparison.")
        weak += 1

    # --- peer sample sizes: the leading source of false positives ---
    for f in case.findings:
        for e in f.evidence:
            n = e.get("peer_sample_size")
            grp = e.get("peer_group") or "peer group"
            if n is None:
                continue
            if n < MIN_RELIABLE_PEER_SAMPLE:
                q.weakens.append(
                    f"'{f.title or f.finding_id}' compares against {grp} with "
                    f"only {n} providers. A cohort this small cannot define a "
                    f"stable distribution, so the percentile may be an artefact "
                    f"of the comparison rather than a behavioural signal.")
                weak += 2
            elif n < SMALL_PEER_SAMPLE:
                q.weakens.append(
                    f"'{f.title or f.finding_id}' uses a small cohort "
                    f"({n} providers in {grp}); percentiles are unstable at "
                    f"this size.")
                weak += 1
            else:
                q.strengthens.append(
                    f"'{f.title or f.finding_id}' compares against {n} "
                    f"providers in {grp}, large enough for a stable "
                    f"distribution.")
                strong += 1

            # --- magnitude and rarity answer different questions ---
            pct, dev = _pct(e.get("percentile")), e.get("deviation_ratio")
            if pct is not None and pct >= 99 and dev and dev >= 3:
                q.strengthens.append(
                    f"{e.get('metric')} is both extreme in rank "
                    f"({pct:.0f}th percentile) and in magnitude ({dev:.1f}x the "
                    f"peer median). Rarity and size together are harder to "
                    f"explain by case-mix alone.")
                strong += 2
            elif pct is not None and pct >= 90 and dev and dev < 1.5:
                q.weakens.append(
                    f"{e.get('metric')} ranks high ({pct:.0f}th percentile) but "
                    f"is only {dev:.2f}x the peer median. A high rank with a "
                    f"small margin means the peer distribution is tight, not "
                    f"that the provider is far from normal.")
                weak += 1

    # --- coverage gaps: missing data is not a clean result ---
    for agent in case.agents_skipped:
        q.gaps.append(f"The {agent} agent did not run, so that dimension was "
                      f"never examined.")
    for k, v in (case.data_availability or {}).items():
        if str(v).upper() not in ("AVAILABLE", "TRUE"):
            q.gaps.append(f"{k} data was unavailable ({v}).")
    if case.synthesis_complete is False:
        q.gaps.append("The risk synthesis is incomplete - not every scoring "
                      "component was available.")
        weak += 1
    for lim in case.limitations:
        q.gaps.append(lim)

    # --- low-confidence findings ---
    low = [f for f in case.findings
           if f.confidence is not None and f.confidence < 0.5]
    if low:
        q.weakens.append(
            f"{len(low)} finding(s) carry a confidence below 0.5, as reported "
            f"by the agents themselves.")
        weak += 1

    # --- verdict ---
    if strong >= 3 and weak == 0:
        q.confidence = "strong"
        q.recommended_posture = (
            "The evidence supports proceeding with a documentation review.")
    elif strong > weak:
        q.confidence = "moderate"
        q.recommended_posture = (
            "Reasonable basis to review, but verify the peer group and test "
            "benign explanations before escalating.")
    elif weak > 0:
        q.confidence = "limited"
        q.recommended_posture = (
            "Treat as a low-priority lead. Confirm the comparison basis before "
            "spending investigative effort - this profile is consistent with a "
            "peer-group or data artefact.")
    else:
        q.confidence = "unknown"
        q.recommended_posture = (
            "Insufficient information about the evidence basis to judge "
            "reliability.")

    gaps = len(q.gaps)
    q.summary = (
        f"{n_find} finding(s) from {len(agents) or 0} agent(s); "
        f"{len(q.strengthens)} factor(s) strengthen the flag, "
        f"{len(q.weakens)} weaken it"
        + (f", and {gaps} dimension(s) were not checked." if gaps else ".")
    )
    return q


def assess_provider_risk(model_info) -> QualityAssessment:
    """
    Assess a provider risk-model result (the non-agent path).

    Same standards, applied to what the provider risk model reports: how many
    metrics deviate, how far, and whether the peer group is stable.
    """
    q = QualityAssessment()
    if not getattr(model_info, "available", False):
        q.summary = "No model output supplied, so evidence quality cannot be "\
                    "assessed."
        return q

    factors = model_info.risk_factors or []
    strong = weak = 0

    if len(factors) >= 3:
        q.strengthens.append(
            f"{len(factors)} separate metrics deviate from peers. Deviation on "
            f"several independent dimensions is far stronger than one extreme "
            f"value.")
        strong += 2
    elif len(factors) == 1:
        q.weakens.append(
            "Only one metric deviates. A single deviating metric is commonly "
            "produced by case-mix or subspecialty focus rather than by "
            "behaviour.")
        weak += 1
    elif not factors:
        q.weakens.append(
            "No individual metric reaches the deviation threshold, so the score "
            "rests on the composite anomaly signal rather than on any specific "
            "measurable difference.")
        weak += 1

    for f in factors:
        c = f.contribution or 0
        if c >= 0.9:
            q.strengthens.append(
                f"{f.name}: {f.description}. This is an extreme position within "
                f"the peer distribution.")
            strong += 1

    if getattr(model_info, "peer_group", None):
        q.strengthens.append(
            f"Comparison is against a defined peer group ({model_info.peer_group}), "
            f"not the population at large.")
        strong += 1
    else:
        q.gaps.append("The peer group used for comparison is not stated, so the "
                      "basis of the deviation cannot be verified.")

    q.gaps.append(
        "This model was trained without any fraud ground-truth label. It "
        "identifies statistical anomalies, so a high score means unusual, not "
        "improper.")

    if strong >= 3 and weak == 0:
        q.confidence = "strong"
        q.recommended_posture = (
            "The evidence supports proceeding with a documentation review of "
            "the highest-value claims.")
    elif strong > weak:
        q.confidence = "moderate"
        q.recommended_posture = (
            "Reasonable basis to review. Verify the peer group reflects the "
            "provider's actual practice before escalating.")
    else:
        q.confidence = "limited"
        q.recommended_posture = (
            "Treat as a low-priority lead and confirm the comparison basis "
            "first.")

    q.summary = (
        f"{len(factors)} deviating metric(s); {len(q.strengthens)} factor(s) "
        f"strengthen the flag, {len(q.weakens)} weaken it.")
    return q
