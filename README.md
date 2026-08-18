# Healthcare Claims Fraud, Waste & Abuse — AI Investigation Assistant (UC01)

An investigator-facing assistant module for a larger Claims Fraud, Waste & Abuse
(FWA) Risk Detection platform.

This repository contains the **AI Investigation Assistant / RAG Bot module only**.
It is not a standalone general-purpose chatbot.

---

## What this module is for

**1. Domain knowledge questions** — "What is upcoding?", "Why can unusually high
reimbursement be suspicious?", "What is peer comparison?"
Answered from the curated knowledge base via semantic retrieval.

**2. Investigation / explanation questions** — "Why was provider PRV51001
flagged?", "What factors contributed to the risk?", "What should I examine next?"
Answered by retrieving **existing** risk-engine outputs, joining them with
**actual** dataset evidence, and explaining them using domain knowledge.

---

## Critical role separation

> **The assistant is an explanation layer, not a detection engine.**

| The assistant DOES | The assistant DOES NOT |
| --- | --- |
| Retrieve an existing risk score | Calculate a risk score |
| Retrieve existing risk factors | Invent risk factors |
| Query real datasets for exact numbers | Estimate numbers from text similarity |
| Explain what a flag means | Decide that a provider is fraudulent |
| Cite the evidence it used | Fabricate evidence, statistics, or cases |

> **ANOMALY != PROVEN FRAUD.**
> Permitted framing: *flagged, high risk, potentially suspicious, warrants
> further investigation, the model identified, the data shows, this pattern may
> indicate.* Prohibited framing: *this is fraud, this provider committed fraud* —
> unless explicit verified information states fraud was confirmed.

---

## Three information sources

| Source | Contents | Retrieval method |
| --- | --- | --- |
| **KNOWLEDGE** | Fraud concepts, indicators, claims terminology, payment integrity, investigation methodology, CMS concepts | Vector / semantic retrieval (FAISS) |
| **DATA** | 8 datasets, ~950k rows: Medicare provider analytics, CMS claims, OIG exclusions | Exact SQL over DuckDB |
| **MODEL** | Risk scores for 36,108 providers from the platform's Isolation Forest model — score, tier, component breakdown, peer-compared metrics | Direct lookup of existing engine output |

**Retrieval:** hybrid — dense (MiniLM + FAISS) fused with sparse (BM25) via
Reciprocal Rank Fusion. Used *only* for conceptual knowledge.
Counts, totals, averages, rankings, thresholds and comparisons must never be
answered by vector similarity.

---

## Target architecture

```
INVESTIGATOR -> CHAT UI -> QUESTION ROUTER
                              |
        +---------------------+---------------------+
        |                     |                     |
   KNOWLEDGE               DATA                   MODEL
   (FAISS RAG)      (structured query)     (existing risk engine)
        |                     |                     |
   fraud concepts        claims / providers    risk score / level
   indicators            actual values         risk factors
   investigation         comparisons           anomalies
        |                     |                     |
        +---------------------+---------------------+
                              |
                             LLM  (explanation layer only)
                              |
                     GROUNDED ANSWER + SOURCES
```

The LLM is never the source of truth for numeric or model-specific values.

---

## Question routing categories

| Category | Example | Resolved by |
| --- | --- | --- |
| `KNOWLEDGE` | "What is unbundling?" | Knowledge base |
| `DATA` | "How many claims did PRV51001 submit?" | Structured data layer |
| `MODEL` | "What is PRV51001's risk score?" | Risk engine outputs |
| `INVESTIGATION` | "Why was PRV51001 flagged?" | All three, combined |

---

## Build phases

| Phase | Scope | Status |
| --- | --- | --- |
| 1 | Project setup + knowledge base | **Complete** |
| 2 | Ingestion, chunking, embeddings | **Complete** |
| 3 | FAISS vector store + retrieval | **Complete** |
| 4 | LLM integration + grounded answers | **Complete** |
| 5 | FastAPI backend | **Complete** |
| 6 | React / Vite frontend | Not started |
| 7 | Question routing | **Complete** |
| 8 | Real dataset integration | **Complete** |
| 9 | Risk engine integration | **Complete** |
| 10 | Combined investigation workflow | **Complete** |
| 11 | Testing + final integration | In progress |

Phases 8 and 9 are blocked until the datasets and risk engine exist. Their
service interfaces are built and report "not connected" rather than returning
placeholder values. See `WALKTHROUGH.md` for a file-by-file explanation.

---

## Knowledge base — 20 documents across 7 categories

```
backend/knowledge/
├── fraud_concepts/     (5)  What the schemes are
├── payment_integrity/  (2)  Where detection sits in the payment lifecycle
├── fraud_indicators/   (4)  What the signals look like in data
├── healthcare_claims/  (3)  Core claims vocabulary
├── investigation/      (3)  How to work a case
├── provider_behavior/  (1)  How to reason about a provider's pattern
└── cms_concepts/       (2)  Medicare / CMS background
```

See `backend/knowledge/INDEX.md` for the full document map.

All 20 documents are written. `python scripts/verify_structure.py` confirms the
folder layout, the document set, and that every document has valid front matter.

### Document format

Every document carries YAML front matter:

```yaml
---
title: Coding Misrepresentation — Upcoding, Downcoding, Unbundling
doc_id: fraud_concepts.coding_misrepresentation
category: fraud_concepts
tags: [upcoding, downcoding, unbundling, coding_integrity]
source_type: curated_knowledge
version: 2.0
---
```

These fields map directly onto the retrieval metadata required in later phases:
`source` (file path), `category`, `document` (`doc_id`), plus `chunk_id` and
`similarity_score` generated at index time.

**Every fraud indicator section follows a fixed five-part structure:**

1. What it means
2. Why it may be suspicious
3. How it appears in claims data
4. Possible legitimate explanations
5. What an investigator should examine

Part 4 is mandatory — it is the structural guarantee that the assistant surfaces
benign explanations alongside suspicious ones.

### Content policy

The knowledge base contains **general domain education only**: no real provider
statistics, no real claims, no real risk scores, no named fraud cases, and no
synthetic placeholder data that could be mistaken for real evidence.
Case-specific facts enter the system exclusively at runtime, from the DATA and
MODEL sources.

Illustrative code references appear only as generic teaching examples of public
code-set structure, never as claims of observed activity.

---

## Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Data is found automatically when this module sits in the project repo. Verify:

```bash
python -c "from backend.data import warehouse as wh; print(wh.source())"
```

Build the knowledge index (first run downloads the ~80 MB embedding model):

```bash
python scripts/build_index.py
```

Test retrieval:

```bash
python scripts/search.py "what is upcoding"
python scripts/search.py "why can duplicate billing be suspicious"
python scripts/search.py            # interactive mode
```

Add your OpenAI key to `.env`:

```
LLM_API_KEY=sk-your-key-here
```

Ask a question through the full pipeline:

```bash
python scripts/ask.py "what is upcoding"
python scripts/ask.py "why was PRV51001 flagged"
```

Run the API:

```bash
uvicorn backend.main:app --reload --port 8732
```

Then open http://localhost:8732/docs to try `POST /api/chat` in the browser.

Verify the project:

```bash
python scripts/verify_structure.py     # expect 20/20 documents
```

---

## Future dataset integration (Phase 8 — do not pre-build)

When real datasets arrive: inspect every file → catalogue columns and dtypes →
quantify missing values and duplicates → identify primary/foreign-key-like
relationships → map how datasets join → determine which questions each dataset
can answer → build the structured layer → implement exact filtering, counting,
aggregation, ranking, comparison → wire into the router → test numeric questions
against ground truth.

**No schema is assumed in advance, and no engine is chosen in advance.**
`backend/data/` stays empty until the datasets exist.

## Future risk engine integration (Phase 9 — do not pre-build)

`backend/model/` stays empty until the engine exists. The assistant will read
provider/claim identifiers, risk score, risk level, risk factors, detected
anomalies, model prediction, feature contributions and detection reason. It will
never compute any of them. When a value is unavailable, the assistant says so
rather than estimating.

---

## Planned API contract (Phase 5 — reference only)

`POST /api/chat` will eventually return:

```
answer, question_type, sources, data_evidence,
model_information, risk_score, risk_factors
```

Fields backed by sources that are not yet connected return `null` — never a
placeholder value.

---

## Disclaimer

This system supports human investigators. It does not make adjudication,
payment, referral, or enforcement decisions. Outputs are investigative leads
requiring human review and verification.
