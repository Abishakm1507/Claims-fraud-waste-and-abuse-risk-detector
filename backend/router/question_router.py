"""
PHASE 7 - Question router.

Decides which information source(s) a question needs:

    KNOWLEDGE      conceptual  -> FAISS semantic retrieval
    DATA           numeric     -> structured query over real datasets
    MODEL          model output-> existing risk engine
    INVESTIGATION  explanation -> all three, combined

WHY THIS EXISTS:
The three sources answer different kinds of question, and using the wrong one
produces confidently wrong answers. Semantic similarity cannot count claims; a
SQL query cannot explain what upcoding means. Routing is what keeps numeric
questions away from the vector store.

WHY RULES AND NOT AN LLM CLASSIFIER:
Routing must be deterministic, instant, free, and auditable - you can point at
the exact pattern that fired. An LLM classifier would add latency and cost to
every request and could silently misroute a numeric question into semantic
search, which is the specific failure this design exists to prevent.

EXTENDING THIS:
Add patterns to the lists below. Each is a (regex, weight) pair. Nothing else
needs to change - the router is intentionally the only place routing logic
lives.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class QuestionType(str, Enum):
    KNOWLEDGE = "KNOWLEDGE"
    DATA = "DATA"
    MODEL = "MODEL"
    INVESTIGATION = "INVESTIGATION"


# ---------------------------------------------------------------------------
# Entity patterns
#
# Identifier formats are a guess until the real datasets arrive. When they do,
# update these patterns to match the actual ID columns - that is the only
# change the router needs for Phase 8.
# ---------------------------------------------------------------------------

# Formats confirmed against the real datasets:
#   NPI          10 digits beginning 1 or 2      e.g. 1003053851
#   CLM_ID       negative 12-15 digit integer    e.g. -10000930037832
#   provider CCN 6 alphanumeric chars            e.g. 01S023, 011500
# The CCN pattern is deliberately keyword-gated: six alphanumeric characters is
# too common a shape to match safely on its own.
ENTITY_PATTERNS: list[tuple[str, str]] = [
    # Real NPIs begin 1 or 2. The CMS synthetic claims use placeholder NPIs
    # beginning 999999, and an investigator may well paste one - so those are
    # recognised too, and the lookup then reports honestly that the identifier
    # is not in the scored population.
    ("provider", r"\b(?:[12]\d{9}|9{6}\d{4})\b"),
    ("provider", r"\b(?:PRV|PROV|NPI)[-_ ]?\d{3,12}\b"),
    ("claim", r"-\d{12,15}\b"),
    ("claim", r"\b(?:CLM|CLAIM)[-_ ]?\d{3,12}\b"),
    ("facility", r"(?:ccn|facility|provider number)\s*:?\s*([0-9A-Z]{6})\b"),
]

# ---------------------------------------------------------------------------
# Signal patterns, as (regex, weight).
# Higher weight = stronger evidence for that route.
# ---------------------------------------------------------------------------

INVESTIGATION_PATTERNS: list[tuple[str, float]] = [
    (r"\bwhy\s+(?:was|is|were|are|did)\b.*\b(?:flag|flagged|high[- ]?risk|risky|suspicious|selected)\b", 3.0),
    (r"\bwhy\s+(?:was|is|were|are)\b.*\b(?:detected|identified|scored)\b", 2.5),
    (r"\bwhat\s+(?:should|do)\s+i\s+(?:investigate|examine|review|look at|check)\b", 3.0),
    (r"\bwhat\s+(?:evidence|factors?)\s+(?:supports?|contributed|led)\b", 2.5),
    (r"\bexplain\b.*\b(?:flag|flagged|risk|detection|why)\b", 2.0),
    (r"\b(?:justify|reason for)\b.*\b(?:flag|risk|score)\b", 2.0),
    (r"\bwhat\s+(?:happened|is going on)\s+with\b", 1.5),
    (r"\bnext steps?\b", 1.5),
    (r"\bshould i (?:escalate|refer|pursue|open)\b", 2.0),
]

MODEL_PATTERNS: list[tuple[str, float]] = [
    (r"\brisk\s+score\b", 3.0),
    (r"\brisk\s+level\b", 3.0),
    (r"\brisk\s+factors?\b", 2.5),
    (r"\b(?:detected\s+)?anomal(?:y|ies)\b", 2.5),
    (r"\bmodel\s+(?:output|prediction|said|says|score|result)\b", 3.0),
    (r"\bfeature\s+contributions?\b", 3.0),
    (r"\bdetection\s+reason\b", 3.0),
    (r"\bwhat\s+did\s+the\s+model\b", 3.0),
    (r"\bconfidence\s+score\b", 2.0),
    (r"\bis\s+\S+\s+(?:high|medium|low)\s+risk\b", 2.0),
]

DATA_PATTERNS: list[tuple[str, float]] = [
    (r"\bhow\s+(?:many|much)\b", 3.0),
    (r"\btotal\s+(?:number|amount|reimbursement|payment|claims?|cost)\b", 3.0),
    (r"\b(?:average|mean|median)\b", 2.5),
    (r"\bcount\s+of\b", 2.5),
    (r"\bwhich\s+providers?\b.*\b(?:highest|lowest|most|least|top|exceed|above|below|more than)\b", 3.0),
    (r"\b(?:top|bottom)\s+\d+\b", 3.0),
    (r"\b(?:highest|lowest|largest|smallest)\b", 2.0),
    (r"\bexceed(?:s|ing)?\b", 2.0),
    (r"\b(?:more|less|greater|fewer)\s+than\b", 2.0),
    (r"\b(?:above|below|over|under)\s+\$?\d", 2.5),
    (r"\$\s?\d[\d,]*", 2.0),
    (r"\bcompare[ds]?\s+(?:with|to|against)\b", 2.0),
    (r"\bcomparison\s+(?:with|to|against)\b", 2.0),
    (r"\brank(?:ed|ing)?\b", 2.0),
    (r"\blist\s+(?:all|the)\b", 1.5),
    (r"\bpercentage|percent\b", 2.0),
    (r"\bbreakdown\s+of\b", 2.0),
    (r"\bsum\s+of\b", 2.5),
    # Peer comparison is a DATA operation: it is computed from the datasets,
    # not retrieved from the knowledge base. These fire only alongside an
    # entity in practice, because the entity boost is what lifts them.
    (r"\bcompare[ds]?\b|\bcomparison\b", 2.5),
    (r"\bpeers?\b|\bsimilar\s+providers?\b", 2.5),
    (r"\boutlier\b", 2.0),
    (r"\bunusually\s+(?:high|low|large|small)\b", 2.5),
    (r"\bdeviat(?:e|es|ion|ing)\b", 2.5),
    (r"\bbenchmark\b", 2.0),
    (r"\bmost\s+different\b|\bdiffer\s+most\b", 2.5),
    (r"\bhow\s+does\b.*\bcompare\b", 3.0),
    (r"\bpercentile\b", 2.5),
    # Claim lookups
    (r"\bclaim\s+-?\d{4,}", 3.0),
    (r"\b(?:show|look\s*up|find|get|details?\s+(?:of|for))\b.*\bclaim\b", 2.5),
    (r"\bwhat\s+(?:was|is)\b.*\b(?:paid|payment|charge)\b", 2.0),
    # Profile phrasing. These reach DATA only alongside an identifier, because
    # the entity boost is what lifts them above the definitional route.
    (r"\btell\s+me\s+about\b", 2.0),
    (r"\bdetails?\s+(?:of|about|for|on)\b", 2.0),
    (r"\bprofile\b|\bbackground\b|\boverview\s+of\b", 2.0),
    (r"\bwho\s+is\b", 1.5),
    (r"\bwhat\s+do\s+you\s+know\s+about\b", 2.5),
    (r"\binformation\s+(?:about|on)\b", 2.0),
    (r"\beverything\s+about\b", 2.5),
]

KNOWLEDGE_PATTERNS: list[tuple[str, float]] = [
    (r"\bwhat\s+(?:is|are|does)\s+(?:a|an|the)?\s*\w+", 2.0),
    (r"\bwhat\s+does\b.*\bmean\b", 3.0),
    (r"\bdefine\b|\bdefinition\s+of\b", 3.0),
    (r"\bexplain\s+(?:the\s+)?(?:concept|term|idea|meaning)\b", 2.5),
    (r"\bwhy\s+(?:can|could|might|would|is|are)\b.*\b(?:suspicious|a concern|problematic|risky)\b", 3.0),
    (r"\bhow\s+(?:can|could|do|does)\b.*\b(?:appear|show up|manifest|indicate)\b", 2.0),
    (r"\btypes?\s+of\b", 1.5),
    (r"\bdifference\s+between\b", 2.0),
    (r"\bwhat\s+(?:should|do)\s+(?:an?\s+)?investigators?\s+(?:look for|know|understand)\b", 2.5),
    (r"\bcommon\s+(?:indicators?|signs?|patterns?|schemes?)\b", 2.5),
    (r"\blegitimate\s+(?:explanations?|reasons?)\b", 2.0),
    (r"\bwhat\s+is\s+meant\s+by\b", 3.0),
]


# Openers that signal a request for a definition rather than a data operation.
DEFINITIONAL_RE = re.compile(
    r"^\s*(?:what\s+(?:is|are|does|do)\b(?!.*\b(?:total|many|much)\b)"
    r"|what'?s\s+(?:a|an|the)?\s*\w+\s*\??$"
    r"|define\b|definition\s+of\b|explain\s+(?:the\s+)?(?:concept|term|meaning)\b"
    r"|meaning\s+of\b|tell\s+me\s+about\s+(?:the\s+)?(?:concept|term)\b)",
    re.IGNORECASE,
)


# General methodology phrasing. Applied only when no identifier is present:
# with an identifier the same words describe a real case and belong to DATA or
# INVESTIGATION.
METHODOLOGY_RE = re.compile(
    r"\bwhat\s+should\s+(?:an?\s+)?(?:i|we|investigators?|one)\b"
    r"|\bwhat\s+(?:do|does)\s+(?:an?\s+)?investigators?\b"
    r"|\bhow\s+(?:do|should|does)\s+(?:i|we|an?\s+investigator)\b"
    r"|\bwhat\s+are\s+(?:the\s+)?(?:steps|best practices|things)\b",
    re.IGNORECASE,
)


@dataclass
class RoutingDecision:
    """Where a question should go, and why."""

    question_type: QuestionType
    confidence: float
    entities: dict[str, list[str]] = field(default_factory=dict)
    matched_signals: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)

    @property
    def needs_knowledge(self) -> bool:
        return self.question_type in (
            QuestionType.KNOWLEDGE, QuestionType.INVESTIGATION
        )

    @property
    def needs_data(self) -> bool:
        return self.question_type in (
            QuestionType.DATA, QuestionType.INVESTIGATION
        )

    @property
    def needs_model(self) -> bool:
        return self.question_type in (
            QuestionType.MODEL, QuestionType.INVESTIGATION
        )

    def to_dict(self) -> dict:
        return {
            "question_type": self.question_type.value,
            "confidence": round(self.confidence, 3),
            "entities": self.entities,
            "matched_signals": self.matched_signals,
            "scores": {k: round(v, 2) for k, v in self.scores.items()},
        }


class QuestionRouter:
    """Rule-based classifier over the four question types."""

    def __init__(self) -> None:
        self._compiled = {
            QuestionType.INVESTIGATION: self._compile(INVESTIGATION_PATTERNS),
            QuestionType.MODEL: self._compile(MODEL_PATTERNS),
            QuestionType.DATA: self._compile(DATA_PATTERNS),
            QuestionType.KNOWLEDGE: self._compile(KNOWLEDGE_PATTERNS),
        }
        self._entity_res = [
            (name, re.compile(pat, re.IGNORECASE)) for name, pat in ENTITY_PATTERNS
        ]

    @staticmethod
    def _compile(patterns: list[tuple[str, float]]):
        return [(re.compile(p, re.IGNORECASE), w) for p, w in patterns]

    @staticmethod
    def _normalise(kind: str, raw: str) -> str:
        """
        Strip prefixes so the value is the bare identifier the data layer
        expects: "NPI 1003053851" -> "1003053851".
        """
        v = raw.strip().upper()
        v = re.sub(r"^(?:NPI|PRV|PROV|CLM|CLAIM|BENE|BEN|MBI)[-_ ]?", "", v)
        if kind == "claim":
            m = re.search(r"-?\d+", v)
            return m.group(0) if m else v
        if kind == "provider":
            digits = re.sub(r"\D", "", v)
            return digits or v
        return v

    def extract_entities(self, question: str) -> dict[str, list[str]]:
        """Pull provider / claim / facility identifiers out of the question."""
        found: dict[str, list[str]] = {}
        for name, regex in self._entity_res:
            for m in regex.finditer(question):
                # Use the capture group when the pattern defines one.
                raw = m.group(1) if m.groups() else m.group(0)
                val = self._normalise(name, raw)
                if not val:
                    continue
                found.setdefault(name, [])
                if val not in found[name]:
                    found[name].append(val)
        # A negative claim id also matches the provider digit pattern; the
        # claim reading wins, so drop the spurious provider hit.
        if "claim" in found and "provider" in found:
            claim_digits = {c.lstrip("-") for c in found["claim"]}
            found["provider"] = [p for p in found["provider"]
                                 if p not in claim_digits
                                 and not any(p in c for c in claim_digits)]
            if not found["provider"]:
                found.pop("provider")
        return found

    def route(self, question: str) -> RoutingDecision:
        if not question or not question.strip():
            return RoutingDecision(
                question_type=QuestionType.KNOWLEDGE, confidence=0.0
            )

        text = question.strip()
        entities = self.extract_entities(text)
        has_entity = bool(entities)

        scores: dict[QuestionType, float] = {}
        signals: dict[QuestionType, list[str]] = {}

        for qtype, patterns in self._compiled.items():
            total = 0.0
            hits: list[str] = []
            for regex, weight in patterns:
                if regex.search(text):
                    total += weight
                    hits.append(regex.pattern)
            scores[qtype] = total
            signals[qtype] = hits

        # A definitional opener with no identifier is a concept question, even
        # when it contains a word that is also a data operation ("what is peer
        # comparison?" is KNOWLEDGE; "compare 1003053851 with peers" is DATA).
        if not has_entity and DEFINITIONAL_RE.match(text):
            scores[QuestionType.KNOWLEDGE] = scores[QuestionType.KNOWLEDGE] * 2.5 + 2.0
            scores[QuestionType.DATA] *= 0.35

        # Methodology questions - "what should I look for when a provider is an
        # outlier?" - are about how to investigate, not about a case. Without an
        # identifier there is no case to query, so they belong to KNOWLEDGE even
        # though they contain data vocabulary like "outlier" or "compare".
        if not has_entity and METHODOLOGY_RE.search(text):
            # Added rather than multiplied: these questions often match no
            # KNOWLEDGE pattern at all ("what should I look for..." is not
            # definitional phrasing), and multiplying zero leaves zero.
            scores[QuestionType.KNOWLEDGE] += 4.0
            scores[QuestionType.DATA] *= 0.25
            scores[QuestionType.INVESTIGATION] *= 0.4

        # A concrete identifier means the question is about a specific case,
        # which strengthens the case-specific routes and weakens the general one.
        if has_entity:
            scores[QuestionType.INVESTIGATION] *= 1.5
            scores[QuestionType.MODEL] *= 1.3
            scores[QuestionType.DATA] *= 1.3
            scores[QuestionType.KNOWLEDGE] *= 0.6

        # "Why was X flagged" reads as both INVESTIGATION and KNOWLEDGE.
        # Investigation wins when it has any signal at all, because it is the
        # superset route - it retrieves knowledge as well.
        if scores[QuestionType.INVESTIGATION] > 0:
            scores[QuestionType.INVESTIGATION] += 0.5

        best = max(scores, key=lambda k: scores[k])

        # Nothing matched: default to KNOWLEDGE. Answering a conceptual question
        # from the curated corpus is the safe failure mode; guessing at a number
        # is not.
        if scores[best] == 0.0:
            return RoutingDecision(
                question_type=QuestionType.KNOWLEDGE,
                confidence=0.3,
                entities=entities,
                matched_signals=[],
                scores={k.value: v for k, v in scores.items()},
            )

        total = sum(scores.values()) or 1.0
        confidence = scores[best] / total

        return RoutingDecision(
            question_type=best,
            confidence=confidence,
            entities=entities,
            matched_signals=signals[best],
            scores={k.value: v for k, v in scores.items()},
        )


_router: QuestionRouter | None = None


def get_router() -> QuestionRouter:
    global _router
    if _router is None:
        _router = QuestionRouter()
    return _router


def route_question(question: str) -> RoutingDecision:
    return get_router().route(question)
