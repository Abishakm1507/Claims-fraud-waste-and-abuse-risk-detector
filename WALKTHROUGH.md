# Code Walkthrough

What each file does, why it is built that way, and the questions you are most
likely to be asked about it.

---

## Pipeline in one line

```
knowledge/*.md → ingestion → chunking → embeddings → FAISS → retriever → (LLM, Phase 4)
```

---

## `backend/config.py`

Reads `.env` and exposes every path, model name and tuning value as a constant.
Nothing else in the codebase hard-codes a path or a model name.

**Why:** changing the embedding model, chunk size or retrieval threshold is a
one-line edit in `.env`, with no code change and no redeploy.

---

## `backend/rag/ingestion.py` — Phase 2

Walks `backend/knowledge/`, reads every `.md`, and splits each file into
**front matter** (metadata) and **body** (content).

Key decisions:

- **`INDEX.md` is excluded.** It is a table of contents. If indexed, a query
  could match the contents list and return it as an answer.
- **Missing front matter degrades, it does not crash.** Category falls back to
  the folder name, `doc_id` to `category.filename`. One malformed document
  cannot break the build.
- **Duplicate `doc_id`s are rejected.** Two documents with the same id would
  make citations ambiguous.

Run alone: `python -m backend.rag.ingestion`

---

## `backend/rag/chunking.py` — Phase 2

Splits documents into retrievable pieces. **This is the most important design
decision in the retrieval layer.**

**Why heading-aware rather than fixed-size:** the knowledge base is written so
each `##` section is one self-contained concept, containing the five parts
(what it means / why suspicious / how it appears in data / *possible legitimate
explanations* / what to examine). A blind character-count split would routinely
separate a concept from its legitimate explanations — precisely the content that
stops the bot presenting only the incriminating reading. So sections are split
on `##` first, and only sub-split when a section exceeds the budget. Sub-splits
break on paragraph boundaries, never mid-sentence.

**Context prefix:** every chunk is embedded as `"Document title > Section"` plus
the text. Without it, a chunk beginning `"- Data entry errors..."` has no topic
attached and embeds poorly. `raw_text` (without the prefix) is what gets shown
to the user.

**`Related` sections are skipped.** They are cross-reference lists for human
readers, not knowledge.

**Result:** 20 documents → 204 chunks, average ~516 characters, none over budget.

Run alone: `python -m backend.rag.chunking`

---

## `backend/rag/embeddings.py` — Phase 2

Wraps `all-MiniLM-L6-v2` and converts text to 384-dimension vectors.

**Why this model:** ~80 MB, runs fast on CPU with no GPU, and is strong on
short-passage semantic search — which is exactly this task. Small dimension
keeps the index tiny.

**Why vectors are normalised:** with L2-normalised vectors, an inner-product
search equals cosine similarity, so scores land in a predictable 0–1 range that
a threshold can be set against.

**Lazy loading:** the model loads on first use, not on import, so importing this
module stays cheap.

---

## `backend/rag/vector_store.py` — Phase 3

FAISS index plus parallel chunk metadata, with save/load.

**Why `IndexFlatIP`:** "Flat" means exhaustive search — exact results, no
approximation, no tuning. At a few hundred chunks it is instant. "IP" means
inner product, which on normalised vectors is cosine similarity.
*If asked "why not an approximate index like IVF or HNSW?"* — those trade
accuracy for speed at scales this corpus is nowhere near. This class is the one
place to revisit if the corpus grows to hundreds of thousands of chunks; the
interface would not change.

**Why FAISS and not a database:** the query is "find text with similar meaning",
which is a vector-distance operation. SQL indexes cannot do that. Conversely,
FAISS is the wrong tool for "how many claims did this provider submit" — that is
an exact lookup, which is why Phase 8 uses a structured engine instead.

**Two files persist:** `knowledge_index.faiss` (vectors) and
`knowledge_index_metadata.json` (chunk metadata). Position `i` in the index
corresponds to entry `i` in the metadata list. `load()` verifies the two lengths
match and refuses to load a corrupt store.

---

## `backend/rag/retriever.py` — Phase 3

The single entry point for knowledge search. Embeds the query, searches,
filters, returns results with metadata and similarity score.

**Why a minimum score:** vector search always returns its top-k, even for a
question the corpus cannot answer — the nearest neighbours are just the
least-bad ones. The score floor is what lets the pipeline say *"I have no
knowledge on this"* instead of answering from irrelevant chunks. **This is the
main structural defence against fabricated answers in Phase 4.**

**Why a per-document cap:** adjacent chunks from one document are often all
similar to a query, which would fill the LLM's context with near-duplicates from
a single source. Capping at 2 per document keeps retrieved context diverse.

**Why over-fetch:** filtering by score, category and the per-document cap
discards results, so it fetches `top_k × 4` before filtering.

`as_source()` produces the compact citation form the API returns — `chunk_id`,
`document`, `section`, `category`, `source`, `similarity_score` — which is
exactly the metadata the spec requires.

---

## `scripts/build_index.py`

Runs the whole pipeline and writes the index. Re-run after any knowledge edit.

```bash
python scripts/build_index.py
```

## `scripts/search.py`

Terminal search, to judge retrieval quality before any LLM is involved.

```bash
python scripts/search.py "what is upcoding"
python scripts/search.py          # interactive
```

What it prints is exactly what the LLM will receive as grounding in Phase 4.

## `scripts/verify_structure.py`

Checks folders, the 20-document set, and front matter validity.

---

## Questions you may be asked

**Why RAG instead of fine-tuning?**
Knowledge changes and must be auditable. RAG lets a document be edited and
re-indexed in seconds, and every answer cites the chunk it came from. A
fine-tuned model cannot show its source, and updating it means retraining.

**Why not send the whole knowledge base to the LLM?**
Context limits, cost, and accuracy — retrieval quality drops as irrelevant
context grows. Retrieval sends only the few hundred words that matter.

**How does the bot avoid making things up?**
Three layers. Retrieval returns nothing below the similarity floor. The prompt
(Phase 4) instructs the model to answer only from retrieved chunks and to say
when it lacks information. Numbers never come from the LLM at all — the router
sends them to the data and model services.

**Why does the router exist?**
Because the three sources answer different question types, and using the wrong
one produces confidently wrong answers. Semantic similarity cannot count claims;
a SQL query cannot explain what upcoding means.

**What stops the bot calling something fraud?**
It has no detection capability by design — it retrieves an existing score rather
than computing one. The knowledge base states `ANOMALY ≠ PROVEN FRAUD`
throughout, every indicator carries a "possible legitimate explanations" section
that retrieval surfaces alongside the suspicious reading, and the Phase 4 prompt
enforces the permitted vocabulary.

---

# Batch B — Phases 7, 4, 5

## `backend/router/question_router.py` — Phase 7

Classifies each question as `KNOWLEDGE`, `DATA`, `MODEL` or `INVESTIGATION`, and
extracts entity IDs (`PRV51001` and similar).

**Why routing exists at all:** the three sources answer different kinds of
question, and using the wrong one produces confidently wrong answers. Semantic
similarity cannot count claims; a SQL query cannot explain what upcoding means.
Routing is what keeps numeric questions away from the vector store.

**Why rules and not an LLM classifier:** routing must be deterministic, instant,
free and auditable — you can point at the exact regex that fired. An LLM
classifier adds latency and cost to every request and could silently misroute a
numeric question into semantic search, which is the specific failure this design
exists to prevent.

**How it scores:** each route has a list of `(regex, weight)` pairs. Weights sum
per route, and the highest wins. Finding a concrete entity ID multiplies the
case-specific routes up and the general knowledge route down, because an ID means
the question is about a specific case. `INVESTIGATION` gets a small bonus when it
matches at all, because it is the superset route — it retrieves knowledge too.

**Default is `KNOWLEDGE`.** If nothing matches, answering from the curated corpus
is the safe failure mode. Guessing at a number is not.

**Extending it:** add patterns to the lists at the top of the file. Nothing else
changes — routing logic lives in exactly one place.

Tested against all 28 routing examples in the spec: 28/28 correct.

---

## `backend/data/structured_data_service.py` — Phase 8 integration point

**Not implemented, deliberately.** It defines the interface and reports
`available: False`. It contains no sample providers and no placeholder totals — a
fake number here would flow through the API and appear to an investigator as
real.

The file header carries the Phase 8 checklist: inspect files, quantify missing
values and duplicates, identify key relationships, decide which questions each
dataset answers, choose the engine, implement, test against ground truth.

## `backend/model/risk_engine_service.py` — Phase 9 integration point

Same approach. **The rule this file enforces: the chatbot retrieves risk scores,
it never calculates them.** There is no scoring logic here and none should be
added — if the assistant could compute a score it would become a second,
unvalidated detection engine, and an investigator could not tell which number
came from where.

`ModelInformation` already carries every field the engine may expose: risk score,
risk level, risk factors with feature contributions, detected anomalies, model
prediction, detection reason, model version.

---

## `backend/llm/prompts.py` — Phase 4

The system prompt, kept separate from service code so the behavioural rules are
reviewable in one place.

Six absolute rules: ground every answer in provided context; never fabricate;
never calculate a risk score; anomaly is not proven fraud (with the permitted and
forbidden vocabulary listed explicitly); keep model / data / knowledge
distinguishable; always include legitimate explanations.

There are four per-route instructions. The `INVESTIGATION` one specifies the
seven-part answer structure and says that when model output or data is
unavailable, the answer must say so **at the point where it would have appeared**
— not quietly skip it, and not fill the gap with a hypothetical.

`build_user_prompt()` assembles the prompt. Note that when a source is missing it
inserts an explicit `NOT AVAILABLE` block rather than omitting the section —
absence stated is safer than absence implied.

## `backend/llm/llm_service.py` — Phase 4

OpenAI wrapper. Temperature defaults to 0.1 because this is grounded explanation,
not creative writing.

**Graceful degradation:** with no API key it reports unavailable rather than
raising, and never throws on an API error — failures come back on the response
object so an investigator never sees a blank answer with no explanation.

## `backend/rag/rag_pipeline.py` — Phase 4

Orchestrates one question end to end: route → retrieve knowledge → query data →
query model → assemble prompt → generate → return.

**The pipeline decides what to fetch; the LLM only phrases what came back.**

`_fallback_answer()` matters: if the LLM is unavailable, it returns the retrieved
knowledge chunks verbatim. Degraded, but never fabricated — the system stays
usable without an API key.

---

## `backend/api/chat.py` and `backend/main.py` — Phase 5

`POST /api/chat` and `GET /api/status`.

**The response contract is fixed now and does not change as later phases land:**

```
answer, question_type, sources, data_evidence,
model_information, risk_score, risk_factors
```

`data_evidence`, `model_information`, `risk_score` and `risk_factors` return
`null` today. When Phase 8 and 9 connect, the same fields populate — no client
change required. **This is why the UI will not need rewriting when the datasets
arrive.** Fields are never filled with placeholders to make a response look
complete.

`GET /api/status` reports which of the four sources (knowledge, data, model, LLM)
are connected. The UI calls it on load to decide which panels to show.

Run it:

```bash
uvicorn backend.main:app --reload --port 8000
# docs at http://localhost:8000/docs
```

## `scripts/ask.py`

Full pipeline from the terminal — shows the routing decision, answer, sources and
warnings. Useful for demonstrating routing without the UI.

---

## More questions you may be asked

**What happens when someone asks a data question today?**
It routes to `DATA`, the service reports not connected, and the answer says the
figure cannot be provided. It does not invent one, and it does not fall back to
semantic search.

**Why is the response contract fixed before the sources exist?**
So the frontend and any other client are written once. Adding a field later means
changing every consumer; returning `null` in a stable field means the UI just
starts rendering a panel when real data appears.

**Why is temperature 0.1 rather than 0?**
Near-deterministic output while avoiding the degenerate repetition that exact-0
sampling can produce. The grounding comes from retrieval and prompt rules, not
from temperature.

---

# Phase 8: Structured data layer

## What the inspection found

Three groups, not one dataset. **They are never joined across groups**, because
they share no identifiers.

| Group | Files | Key | Years |
| --- | --- | --- | --- |
| **A — Medicare analytics** | provider_service, provider_features, geo_benchmark | 10-digit NPI | 2020–2024 |
| **B — CMS claims** | outpatient, inpatient, carrier | CLM_ID, org NPI, CCN, BENE_ID | 2015–2022 |
| **C — OIG exclusions** | LEIE | NPI + name | — |

Measured overlaps: Group A ∩ Group B = 5 NPIs out of thousands (coincidence —
the CMS claims use synthetic NPIs). Within Group B, outpatient and inpatient
share **1,665 providers and 5,665 beneficiaries**, so claims *are* joinable to
each other.

`provider_service` ∩ `provider_features` = 141 NPIs (1.6%), so those two are
also treated as separate sources rather than merged.

## Why DuckDB

~950,000 rows needing rankings, aggregations and joins. DuckDB gives real SQL in
a single portable file with no server. Pandas would need every groupby
hand-written and would re-parse the CSVs on every start. `scripts/build_data.py`
converts CSVs to `data_store/warehouse.duckdb` once; the backend opens it
**read-only**, so the assistant can never modify source data.

## The derived `provider_summary` table

`provider_service` is one row per NPI × HCPCS × year — 200,000 rows for 8,848
providers. Almost every provider question needs it aggregated to one row per
NPI, so that aggregation is computed once at build time. Provider lookups are
then instant.

## Peer comparison — three methods

The spec calls peer comparison a core feature, and the data supports three
genuinely different kinds:

**1. Specialty cohort percentile.** Same specialty + same state, falling back to
a national cohort when the state cohort has fewer than `MIN_PEER_COHORT` (20)
providers — a handful of providers cannot define a distribution. Returns the
provider's percentile on seven metrics against the cohort median.

**2. Procedure-level benchmark.** The provider's own HCPCS codes joined to
`geo_benchmark` state averages for those same codes. This compares like with
like, so it answers "is their reimbursement unusually high?" without the
distortion of comparing different procedure mixes.

**3. Published z-scores.** `provider_features` already carries peer deviation
scores; where a provider appears there, those are read rather than recomputed.

**"Which metrics differ most from peers?"** is answered by sorting metrics on
distance from the 50th percentile and returning the top three.

Every comparison reports its basis — *"compared against 61 Internal Medicine
providers in CA"* — because the knowledge base itself identifies a wrong peer
group as the leading cause of false positives.

## LEIE exclusion screening

Only 8,840 of 83,816 LEIE rows carry an NPI, so **exact NPI match is the only
reliable link** and is what the service uses.

Name+state matching was tested and rejected for automatic use: it produced 31
matches against provider_service, but most were false positives — an excluded
*paramedic technician* matching an *anesthesiologist* of the same name and
state, with only 3 of 31 agreeing on city. Asserting an exclusion from a name
match would be exactly the kind of unfounded accusation this system exists to
avoid.

## Router changes for real identifiers

Entity patterns now match the real formats: NPI as 10 digits beginning 1 or 2,
CLM_ID as a negative 12–15 digit integer, CCN keyword-gated because six
alphanumeric characters is too common a shape to match safely. Captured values
are normalised, so "NPI 1003053851" yields `1003053851`.

A negative claim ID also matches the provider digit pattern, so the claim
reading wins and the spurious provider hit is dropped.

Comparison vocabulary (*compare, peer, outlier, unusually high, deviation,
benchmark, percentile*) routes to DATA, because peer comparison is computed from
the datasets. But a **definitional opener with no identifier** overrides that:
"what is peer comparison?" is KNOWLEDGE, while "compare 1003053851 with peers"
is DATA. Routing tests: 22/22.

## The dispatcher

`StructuredDataService.query()` maps a DATA question onto the right method by
rule, not by model. The spec requires that numeric questions never be answered
by semantic similarity, and a deterministic mapping is auditable — you can point
at the rule that fired.

Order: claim lookup → provider comparison → provider lookup → ranking →
threshold → dataset overview → "needs a specific identifier".

## Anomaly flags are data, not risk scores

`inpatient_features` carries `claim_anomaly_count`, `high_payment_to_charge_flag`
and similar. These are **exposed as data evidence, never as `risk_score`**. The
spec is explicit that risk scores come from the fraud engine and the assistant
never presents its own computation as model output. If the team intends these to
be the risk signal, wiring them to the MODEL source is a one-line change — but
that is their decision to make, not the assistant's.

---

# Phase 9: Risk engine integration

## What the platform's model produces

An Isolation Forest over 46 features, trained on 36,108 providers, blended into
a 0-100 `Provider_Risk_Score`:

| Component | Weight |
| --- | --- |
| Statistical anomaly (Isolation Forest) | 0.35 |
| Peer deviation (specialty z-scores) | 0.30 |
| Service pattern concentration (HHI) | — |
| Geographic price deviation | — |

Tiers: Low 0–29, Moderate 30–59, High 60–79, Critical 80–100.

**5,328 of our 8,848 warehouse providers have a score**, so the join is real.

## Risk factors are derived, not invented

The model emits no named factors. It emits five peer-compared metrics — payment
per service, charge per service, services per beneficiary, payment-to-charge
ratio, service concentration — each with the provider's value, peer median,
percentile and deviation ratio.

Those **are** the factors, and they carry more evidence than a bare label: a
factor reads *"payment per service 100th percentile, 5.30x the peer median,
$400.57 vs $75.49"*.

A metric becomes a factor only when it is genuinely deviant (≥90th or ≤10th
percentile). Listing every metric regardless of deviation would bury the signal.

**No scoring logic exists in this module and none should be added.** If the
assistant could compute a score it would become a second, unvalidated detection
engine and an investigator could not tell which number came from where.

The platform's own metadata states that no fraud ground-truth label was used and
that the model flags statistical anomalies rather than confirmed fraud. That
statement is passed into the prompt with every model block.

---

# Phase 10: Hybrid retrieval

## Why hybrid

Dense search matches meaning but is weak on exact tokens, and this corpus is
full of them — HCPCS codes (`Q4205`), exclusion statutes (`1128B4`), NPIs.
BM25 matches those exactly. Conversely BM25 cannot connect *"billing more than
was documented"* to a document about upcoding, because they share no words.
Each covers the other's failure mode.

## Why Reciprocal Rank Fusion

Dense returns cosine similarity (0–1); BM25 returns unbounded term-frequency
scores. The scales are not comparable and normalising them is arbitrary and
corpus-dependent. RRF discards scores and uses rank only:

```
fused(d) = Σ  1 / (k + rank(d))        k = 60
```

A document ranked highly by either retriever scores well; one ranked highly by
both scores best. No tuning, no scale mismatch.

## One deliberate asymmetry

A chunk found **only** by keyword search has no cosine similarity, so the
similarity floor cannot apply to it. That is intended — an exact code match is
strong evidence of relevance on its own. The floor still applies to anything the
dense retriever returned.

Every source now reports `matched_by`: `dense`, `keyword`, or `both`.

## A gap hybrid search exposed

Testing `"1128B4 exclusion"` returned keyword matches for nothing, because the
knowledge base had no document on OIG exclusions — even though the risk model
reports LEIE status. `investigation/exclusions_and_risk_scores.md` was added to
close it, covering exclusion authorities, risk score interpretation, each
component signal, and how to read deviation ratios versus percentiles.

Corpus is now 21 documents, 215 chunks.

---

# Latency metrics

`backend/eval/latency.py` and `scripts/benchmark.py`. Three metrics only:

| Metric | Meaning |
| --- | --- |
| **TTFT** | Time to first token — perceived responsiveness. Covers network round-trip, prefill and queueing. |
| **ITL** | Inter-token latency — the gap between consecutive tokens. Reported as mean, p50 and p95. |
| **TPOT** | Time per output token — `(total − TTFT) / (tokens − 1)`, the steady-state cost with prefill removed. |

**Why p95 on ITL matters more than the mean:** a stall is far more noticeable
than a slightly slower average. Verified with an injected-stall test — 60 ms
stalls appeared correctly in p95 while p50 stayed at 12 ms.

TPOT and mean ITL measure the same interval and normally agree; both are
reported because TPOT is the conventional serving metric while ITL exposes the
distribution, and divergence between them indicates stalls.

Measuring TTFT required adding `LLMService.stream()`. Without streaming, only
total round-trip time is observable and the prefill cost cannot be separated
from generation.

Retrieval time is timed separately and reported alongside, so the split between
retrieval and generation is visible.

```bash
python scripts/benchmark.py --runs 3 --json bench.json
```

---

# Reading from the ETL

## Why

The assistant used to build its own warehouse from raw CSVs. So did the ML
pipeline. Two modules parsing the same files independently compute the same fact
slightly differently — and then contradict each other in front of an
investigator.

`backend/data/curated_loader.py` points the assistant at the ETL's conformed
tables instead, where every fact is computed once.

## Precedence

Curated tables win when present. The assistant's own warehouse remains as a
fallback so it still runs before the ETL has been executed — but which source is
in use is **reported**, never silent. `wh.source()` returns `curated`,
`local warehouse`, or `both`. A number's provenance should never be ambiguous.

Tables are registered as **views**, not copies, so re-running the ETL updates the
assistant with no rebuild.

## Two details that mattered

**Views are built column-aware.** Claim column names differ by type — carrier
extracts carry `submitted_charge_amount`, institutional ones carry
`total_charge_amount`. Assuming a fixed schema broke the load; the views now
check what actually exists.

**`provider_summary` is rebuilt, not recomputed.** The service layer queries one
row per provider; the ETL splits that across `dim_provider` and
`fact_provider_year`. The loader rejoins them at the grain the service expects,
keeping the ETL's definitions rather than deriving its own.

---

# Entity profiles

`backend/data/profile.py`. The dispatcher answers narrow questions ("total
payment?"); a profile answers the broad one ("tell me about this provider"),
which needs breadth rather than precision.

A provider profile assembles identity, activity totals, year-by-year trend, top
procedures **benchmarked against state averages**, the model's peer percentiles,
claims activity, and exclusion screening.

## Missing sources are named, not omitted

If a provider is absent from the risk model, or a claim carries only a facility
CCN so peer comparison is impossible, the profile says so explicitly. An
investigator must be able to tell "no finding" from "not checked" — and the
agents' own output makes the same distinction, skipping the peer agent with the
reason `Provider NPI unavailable; claim contains PRVDR_NUM only`.

## Routing

Profile phrasing ("tell me about", "details of", "who is") routes to DATA, but
only alongside an identifier — the entity boost is what lifts it above the
definitional route, so "what is peer comparison?" stays KNOWLEDGE.

A narrow comparison question still gets the dedicated peer analysis; anything
broader gets the full profile, which already carries the model's percentiles.

---

# Multi-agent integration

## The contract

The multi-agent system emits one artifact per case, `RAGExplanationRequest`,
built by `multi_agent.rag.handoff.build_rag_handoff()`. Their integration guide
sets the boundary explicitly:

**May use** — case, evidence, findings, risk_synthesis, agent_results,
genai_context, metadata, provenance, limitations.

**Must not** — re-run risk scoring, recompute overall risk or risk category,
improvise peer baselines or provider statistics, or reinterpret a case while
ignoring the stated evidence and limitations.

`backend/model/handoff.py` parses that payload. **Nothing in it computes a
score.** Findings resolve their evidence through `evidence_ids`, and the parser
tolerates both payload shapes their code produces — `risk_synthesis` at the top
level or nested inside `case`, evidence attached to findings or held separately.

Tested against their own `examples/rag_handoff_example.json`.

## What this module adds that theirs cannot

Their guide lists the RAG team's responsibilities, and the first is *"retrieve
policy/domain knowledge relevant to the evidence."* Their pipeline has no
knowledge base, so it can report that `outpatient_high_procedure_volume` fired
but not what a high line count means in payment-integrity terms, what legitimately
produces it, or what to examine next.

---

# Flag quality assessment

`backend/model/flag_quality.py`. The question it answers is **"is this flag worth
acting on?"** — which is not the same as "how high is the score?", and is the
question an investigator actually faces when triaging a queue.

## Why this is not a second score

The contract forbids recomputing their risk. Assessing **reliability** is not
recomputing: this module reads only what the handoff already states — peer
sample size, agent coverage, stated limitations, synthesis completeness — and
applies the standards already written in the knowledge base.

It never changes the score, never overrides the risk category, and never clears
a provider.

## The standards applied

| Signal | Reading |
| --- | --- |
| Peer cohort under 20 | Cannot define a stable distribution; percentile may be an artefact |
| Findings from 2+ agents | Convergence across independent methods — the strongest available evidence |
| A single finding | Weak; the pattern most often explained by case-mix |
| 99th percentile **and** 3×+ median | Rare *and* large — hard to explain by case-mix alone |
| 90th+ percentile but under 1.5× | The peer distribution is tight, not the provider extreme |
| Skipped agent / unavailable data | A dimension never checked, **not** a clean result |

## Verified behaviour

Against their sample payload — a cohort of 184, one finding, temporal data
unavailable — it returns **limited** confidence and recommends confirming the
comparison basis first.

Altering that same payload to a cohort of 6 at 1.2× the median produces three
distinct objections: the lone finding, the unstable cohort, and the high rank
with a small margin.

That distinction is the point. A score of 84 against 184 peers and a score of 84
against 6 peers are not the same finding, and nothing else in the pipeline says so.

---

# Repo integration

## Finding the data wherever this module lands

This module is developed standalone but deployed inside the main project repo,
and its position there is not fixed — it may sit at the root, under `rag/`, or
under `backend/rag/`. A hardcoded relative path breaks on integration, and
breaks **silently**: the assistant falls back to its own warehouse and starts
reporting different numbers from the rest of the platform.

`find_curated_dir()` therefore walks up from this file looking for
`data/curated`, then checks sibling directories.

## The boundary matters

An unbounded upward walk eventually reaches a shared directory such as `/tmp` or
`C:\\Users` and can match an unrelated folder that happens to contain curated
output — worse than finding nothing, because the assistant would silently read
wrong data.

So the walk stops at a repo marker (`.git` or `pyproject.toml`), or at the
user's home directory if there is none. Sibling scanning happens only at that
boundary level.

`_looks_curated()` requires `dim_provider` specifically rather than any parquet
file, so a folder of unrelated parquet files is never mistaken for ETL output.

## Verified layouts

| Layout | Result |
| --- | --- |
| module at `repo/rag/`, data at `repo/data/curated` | found |
| module at repo root | found |
| module at `repo/backend/rag/` | found |
| sibling projects `RAG/` and `ETL/` | found |
| no curated data anywhere | correctly **not found** — no false match |
| curated directory exists but is empty | correctly **not found** |

`CURATED_DIR` overrides all of it for unusual deployments.

## Provenance is visible

`GET /api/status` now reports `reading_from` (`curated`, `local warehouse`, or
`both`) and `curated_path`. On integration, one request confirms the assistant
is reading the platform's shared tables rather than a stale local copy — a
number's provenance should never require inspecting code to establish.

---

# Fixes from live testing

Five bugs surfaced by running the full question set against real curated data.

**Column name mismatch broke every provider question.** The ETL renamed
`total_beneficiaries` to `beneficiary_service_count` (because the value is not
an unduplicated patient count), but `profile.py` still queried the old name.
Any curated build from before that rename produced
`BinderException: Referenced column not found`.

Fixed by resolving the column from the table at query time via
`warehouse.columns()`, so either vintage of ETL output works. Hardcoding a
column name across a version boundary is exactly the kind of coupling that
breaks silently on integration.

**Risk scores were lost when switching to curated.** The scores are a *model*
artifact, not ETL output, so they were not in `data/curated/` and the MODEL
source went dark. `register_risk()` now locates the risk file separately —
beside the curated directory, in `data_raw/`, or in `models/provider/output/` —
and maps the model's own column names (`Provider_Risk_Score`,
`Svc_HHI_Concentration_Peer_Pctile`) onto the names the service queries.
`PROVIDER_RISK_FILE` overrides the search.

**Methodology questions routed to DATA.** *"What should I look for when a
provider is an outlier?"* contains "outlier", a DATA keyword, but has no
identifier — there is no case to query. It answered "the datasets are not
connected", which is both wrong and unhelpful.

`METHODOLOGY_RE` now routes these to KNOWLEDGE when no identifier is present.
The boost had to be **additive**: these questions match no KNOWLEDGE pattern at
all, and multiplying zero leaves zero.

**Synthetic NPIs were not recognised.** The pattern required a leading 1 or 2,
which is correct for real NPIs — but the CMS synthetic claims use placeholders
beginning `999999`, and an investigator may paste one. Now recognised, so the
lookup reports honestly that the identifier is not in the scored population
rather than misrouting the question.

**Definitions were over-answered.** "What is upcoding?" returned four headings
and twenty bullets. `SHORT_KNOWLEDGE_INSTRUCTION` now applies to definitional
phrasing only — analytical questions ("why is X suspicious?") keep the full
structure, because there the depth is the answer.

Routing after these fixes: **17/17**.

## What held up

Every guardrail passed under test. Asked for a risk score on an NPI that was
never scored, it said so rather than inventing one. Asked outright whether a
provider is committing fraud, it refused to conclude, gave what the data shows,
and listed legitimate explanations. Asked how to bake bread, it declined.

---

# Live multi-agent bridge

`backend/model/agent_bridge.py` calls the orchestrator directly when this module
runs inside the main project repo:

```python
Orchestrator().investigate_provider(npi)   # their method, line 140
Orchestrator().investigate_claim(claim_id)
```

The result is converted using **their own** `build_rag_handoff()` rather than by
reading the result object here. Their guide forbids recomputing risk, so the
contract, its validation and its limitations are produced by the system that
owns them.

## Precedence

The multi-agent synthesis wins when available — it is the platform's final
answer and drives triage priority. The provider risk model's score is one of its
five components (weighted 0.30) and appears in the component breakdown, so
nothing is lost by leading with the synthesis.

When the orchestrator is unavailable, the assistant falls back to the provider
risk model rather than reporting nothing.

## Degradation is silent-safe, not silent

Outside the repo `multi_agent` is not importable. Every entry point returns
`None` instead of raising, and `/api/status` reports why:

```
"multi_agent": {"connected": false,
                "message": "The multi_agent package is not importable ..."}
```

## Caching

Investigating a provider runs several agents. Results are cached (64 entries) so
a follow-up question about the same case does not re-run the pipeline.

## Verified

Against a stand-in orchestrator exposing the same surface:

```
SCORE  : 79.25 / 100   HIGH   priority P1
LABEL  : Overall risk (multi-agent synthesis)
COMPONENTS:
   Claim anomaly (upstream ML)              62   (weight 30)
   Provider anomaly (provider risk model)   98.7 (weight 30)  <- provider model
   Peer benchmark                           81   (weight 20)
   Billing analysis                         70   (weight 10)
   Rule-based                               58   (weight 10)
agents executed: peer, billing | skipped: clinical_rule
limitations: Temporal evidence unavailable.
```

Both numbers present, neither mistakable for the other, and the skipped agent
surfaced rather than dropped.

---

# Integration hardening

Four failure modes that would each have looked like "the integration is broken".

**The repo root may not be on `sys.path`.** Deployed at `repo/rag/` and started
from that directory, `multi_agent` (at `repo/`) is not importable even though it
is present — and the failure is indistinguishable from "not integrated yet".
`_ensure_repo_on_path()` locates the repo root and adds it explicitly.

**A hung investigation must not hold the request.** Investigating a provider
runs several agents over the claim store. `AGENT_TIMEOUT_SECONDS` (45 by
default) caps it, and the assistant falls back to the provider risk model.

The executor is module-level and deliberately **not** used as a context
manager: `with ThreadPoolExecutor(...)` blocks on exit until the worker
finishes, which would make the timeout meaningless — the call would still take
as long as the hung run. Measured before the fix: a 3-second timeout returned
after 90 seconds. After: 3.0 seconds.

**Failures are cached.** Without this, a provider the orchestrator cannot
investigate is retried on every follow-up question — and a *timeout* failure
would cost the full timeout each time. Measured: first attempt 3.0s, retry
0.0ms.

**Weights removed from display.** The synthesis weights are their internal
formula and an investigator cannot act on them. The component *values* remain,
because "provider anomaly 98.7, claim anomaly 62" is a real finding — it says
the provider looked extreme while the claims did not.

## Verified with agents live

```
knowledge: True | data: True (curated) | model: True
multi_agent: True - Multi-agent orchestrator available.

  KNOWLEDGE      score=None     What is upcoding?
  DATA           score=None     Tell me about provider 1003056821
  INVESTIGATION  score=79.25    Overall risk (multi-agent synthesis)
  MODEL          score=79.25    Overall risk (multi-agent synthesis)
  INVESTIGATION  score=79.25    Overall risk (multi-agent synthesis)
  KNOWLEDGE      score=None     How do I bake bread?
```

And with the orchestrator absent, the same questions return the provider risk
score (98.6, "Provider risk score") with `/api/status` reporting why.
