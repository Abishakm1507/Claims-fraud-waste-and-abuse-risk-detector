cd Claims-fraud-waste-and-abuse-risk-detector# Claims Fraud, Waste & Abuse Risk Detector

An AI-powered **healthcare insurance payment-integrity system** that analyzes claim and provider-level patterns to identify potentially suspicious billing behavior, explain why a claim or provider appears high-risk, and prioritize cases for investigation.

> **Cognizant Hackathon — Claims / Payment Integrity Use Case**

---

## 1. Use Case: Claims Fraud, Waste and Abuse Risk Detector

**Type:** Claims / Payment Integrity

### Use Case Description

US payers process billions of healthcare claims every year. Even a small rate of inappropriate billing can create significant financial leakage.

A real payment-integrity team cannot rely on a bare fraud label. Investigators need:

- Explainable reasons for a risk flag
- Provider peer comparisons
- Evidence supporting the risk assessment
- A defensible investigation queue
- Appropriate prioritization of suspicious cases

Incorrectly flagging a legitimate provider can also have significant consequences.

The goal of this project is therefore to build a system that goes beyond simply predicting whether something is "fraud."

---

## 2. Problem Statement

A **claim** is the bill submitted by a healthcare provider to an insurer for payment.

The system should analyze **claim-level and provider-level patterns** to:

1. Identify potentially suspicious billing behavior.
2. Detect patterns associated with potential Fraud, Waste, and Abuse (FWA).
3. Explain in plain language why a claim or provider appears high-risk.
4. Compare providers against relevant peers.
5. Prioritize suspicious cases into an investigation queue.
6. Support human investigators rather than automatically making a final fraud determination.

---

## 3. Objective

Build a system that analyzes **claim- and provider-level patterns** to:

> **Flag potentially suspicious billing behavior, explain in plain language why a claim or provider looks high-risk, and prioritize the flagged cases into an investigation queue.**

The system is intended to support **payment-integrity investigators** by helping them focus their attention on higher-priority cases.

---

## 4. Important Distinction: Fraud, Waste & Abuse

The project treats Fraud, Waste, and Abuse as related but distinct risk categories.

| Category | Definition | Example |
|---|---|---|
| **Fraud** | Intentional deception or misrepresentation for financial gain. | A provider intentionally submits a claim for a service that was not actually performed. |
| **Waste** | Unnecessary or inefficient use of healthcare resources that results in avoidable costs. | Repeated or excessive utilization that may not be medically necessary. |
| **Abuse** | Practices inconsistent with accepted healthcare or payment practices that may result in unnecessary costs. | Billing practices that exploit reimbursement rules without necessarily establishing intentional fraud. |

> **Important:** A model-generated risk flag is **not proof** of fraud, waste, or abuse. The system is designed to identify potential risk and provide evidence for human investigation.

---

## 5. Data Sources

| # | Dataset | Source | Purpose |
|---|---|---|---|
| 5.1 | CMS Synthetic Medicare Enrollment, FFS Claims & Prescription Drug Event | [CMS](https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event) | Claim-level, beneficiary, service utilization, provider activity, prescription, and temporal patterns; potential anomalies |
| 5.2 | HHS OIG LEIE Exclusions | [HHS OIG](https://oig.hhs.gov/exclusions/leie-database-supplement-downloads/) | List of Excluded Individuals/Entities; supports provider exclusion risk evidence |
| 5.3 | CMS Medicare Physician & Other Practitioners | [CMS](https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners) | Provider profiling, service patterns, utilization, peer benchmarking, outlier detection |
| 5.4 | Kaggle Healthcare Provider Fraud Detection | [Kaggle](https://www.kaggle.com/datasets/rohitrox/healthcare-provider-fraud-detection-analysis) | Labelled fraud data for supplementary supervised experimentation *(labels, provenance, licensing, and suitability to be verified before use)* |

**5.2 — LEIE matching flow** (exact methodology to be finalized during data analysis):

```text
Provider Information
       │
       ▼
LEIE Matching / Validation
       │
       ▼
Potential Exclusion Indicator
       │
       ▼
Provider Risk Evidence
```

---

## 6. Overview

Healthcare fraud, waste, and abuse (FWA) investigation can involve large volumes of claims and provider records. Reviewing every case manually is inefficient and makes it difficult to identify the highest-priority cases quickly.

This project addresses that problem with a two-level detection and investigation pipeline:

```text
                 DATA SOURCES
                      │
          ┌───────────┴───────────┐
          ▼                       ▼
       CLAIMS                  PROVIDERS
          │                       │
          ▼                       ▼
   Claim Features          Provider Features
          │                       │
          ▼                       ▼
  Claim Isolation          Provider Isolation
      Forest                    Forest
          │                       │
          ▼                       ▼
  Claim Anomaly             Provider Anomaly
      Score                      Score
          └───────────┬───────────┘
                       ▼
                 ORCHESTRATOR
                       │
          ┌────────────┼────────────┐
          ▼             ▼            ▼
       Billing        Peer       Clinical/
        Agent         Agent      Rule Agent
          └────────────┼────────────┘
                       ▼
                   SYNTHESIS
                       │
                       ▼
             RAG-based Explainability
                       │
                       ▼
              INVESTIGATION UI
```

---

## 7. Key Objectives

- Detect unusual **claim-level behavior**
- Detect unusual **provider-level behavior**
- Compare providers against relevant peers and geographic/service benchmarks
- Investigate suspicious patterns using specialized agents
- Combine multiple evidence signals into a transparent risk score
- Retrieve supporting evidence using RAG
- Generate investigator-friendly explanations using generative AI
- Prioritize cases through an investigation queue
- Keep humans in the decision-making loop

---

## 8. Key Features

### 8.1 Dual-Level Anomaly Detection

The system uses two independent Isolation Forest models:

**Claim Isolation Forest** — detects unusual individual claim behavior using features such as:
- Claim amount
- Claim frequency
- Service frequency
- Procedure patterns
- Diagnosis/procedure combinations
- Temporal behavior
- Provider-related claim statistics

**Provider Isolation Forest** — detects unusual overall provider behavior using features such as:
- Total services
- Beneficiary count
- Charges and allowed amounts
- Medicare payments
- Services per beneficiary
- Payment per service
- Unique service count
- Service concentration
- Peer deviation
- Geographic deviation

### 8.2 Peer Benchmarking

Providers are compared against relevant peer groups rather than only fixed global thresholds, allowing the system to identify providers whose behavior is unusual relative to similar providers.

### 8.3 Multi-Agent Investigation

An orchestrator selects investigation specialists based on the available risk signals.

| Agent | Investigates |
|---|---|
| **Billing Agent** | Claim amount deviations, claim/service frequency, repeated or similar claims, temporal spikes, procedure patterns |
| **Peer Benchmark Agent** | Utilization, service volume, payment per service, service mix, geographic benchmarks, peer deviations |
| **Clinical / Rule Agent** | Unusual service combinations, procedure/diagnosis consistency, excessive utilization, coding-related patterns, other predefined domain rules, relevant external evidence signals |

Each agent produces structured findings and evidence rather than simply declaring a case fraudulent.

### 8.4 Transparent Risk Synthesis

Risk is calculated from multiple signals rather than allowing an LLM to arbitrarily decide the final numerical score:

```text
Claim Anomaly
      +
Provider Anomaly
      +
Agent Investigation Scores
      +
Peer Evidence
      +
Rule Evidence
      │
      ▼
Overall Risk Score
      │
      ├── LOW
      ├── MEDIUM
      ├── HIGH
      └── CRITICAL
```

The exact weighting can be configured in the scoring service.

### 8.5 LEIE Evidence Integration

The system matches provider NPIs against the CMS List of Excluded Individuals/Entities (LEIE):

```text
Provider NPI
     │
     ▼
LEIE Lookup
     │
 ┌───┴────┐
 ▼        ▼
Match    No Match
 │
 ▼
Evidence Signal
```

A LEIE match is treated as an **investigation/evidence signal**, not automatic proof of fraud.

### 8.6 RAG-Based Explainability

The RAG layer retrieves relevant evidence for a case, including agent findings, provider metrics, claim metrics, peer benchmark evidence, rule evidence, LEIE evidence, and relevant CMS-derived context. The retrieved evidence is then passed to the LLM to generate a concise explanation:

```text
Structured Case
      +
Agent Findings
      +
Evidence
      │
      ▼
     RAG
      │
      ▼
Retrieved Context
      │
      ▼
     LLM
      │
      ▼
Investigator Explanation
```

### 8.7 Investigator Dashboard

**Dashboard:** total cases, high/medium-risk cases, risk distribution, top suspicious providers, investigation queue.

**Investigation Queue** — ranks cases by risk and priority:

| Priority | Case | Risk | Main Reason | Action |
|---|---|---:|---|---|
| P0 | CLM10231 | 92 | Multiple anomalies | Investigate |
| P1 | P10045 | 87 | Strong peer deviation | Investigate |
| P2 | CLM10982 | 61 | Utilization anomaly | Review |
| P3 | P10342 | 32 | Minor deviation | Monitor |

**Case Investigation** displays: overall risk, claim anomaly, provider anomaly, agent findings, evidence, peer comparison, rule hits, AI-generated explanation, and recommended investigation action.

**Provider Analytics:** provider-level trends and peer comparisons.

**System Analytics:** risk by state, risk by provider type, risk by year, high-risk service categories, anomaly distributions.

---

## 9. System Architecture

```text
                         ┌──────────────────────┐
                         │     DATA SOURCES      │
                         ├──────────────────────┤
                         │ Claims                │
                         │ CMS By Provider       │
                         │ Provider & Service    │
                         │ Geography & Service   │
                         │ LEIE                  │
                         └───────────┬───────────┘
                                     │
                         ┌───────────▼───────────┐
                         │  DATA ENGINEERING     │
                         │                       │
                         │ Cleaning              │
                         │ Aggregation           │
                         │ Entity Resolution     │
                         │ Feature Engineering   │
                         └───────────┬───────────┘
                                     │
                   ┌─────────────────┴─────────────────┐
                   │                                    │
         ┌─────────▼──────────┐              ┌──────────▼─────────┐
         │  CLAIM PIPELINE     │              │ PROVIDER PIPELINE  │
         │                     │              │                    │
         │ Claim Features      │              │ Provider Features  │
         │        ↓            │              │        ↓           │
         │ Isolation Forest    │              │ Isolation Forest   │
         │        ↓            │              │        ↓           │
         │ Claim Risk          │              │ Provider Risk      │
         └─────────┬──────────┘              └──────────┬─────────┘
                   │                                    │
                   └─────────────────┬──────────────────┘
                                      ▼
                         ┌───────────────────────┐
                         │     ORCHESTRATOR       │
                         └───────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                 ▼
              ┌──────────┐     ┌──────────┐     ┌───────────────┐
              │ Billing  │     │   Peer    │     │   Clinical /  │
              │  Agent   │     │  Agent    │     │  Rule Agent   │
              └────┬─────┘     └────┬─────┘     └───────┬───────┘
                   │                │                    │
                   └────────────────┼────────────────────┘
                                     ▼
                         ┌───────────────────────┐
                         │       SYNTHESIS        │
                         │                        │
                         │ Risk Aggregation       │
                         │ Evidence Aggregation   │
                         │ Priority Assignment    │
                         └───────────┬───────────┘
                                     ▼
                         ┌──────────────────────────┐
                         |  EXPLAINABILITY LAYER    │
                         │                          │
                         │ RAG(Evidence Retrieval   │
                         │ FAISS + Embeddings)      |
                         |        AND               |
                         │     uses LLM  for        |  
                         │    Explanation           │
                         └───────────┬──────────────┘
                                     ▼
                         ┌───────────────────────┐
                         │   INVESTIGATION UI    │
                         │                       │
                         │ Dashboard             │
                         │ Investigation Queue   │
                         │ Case Details          │
                         │ Provider Analytics    │
                         └───────────────────────┘
```

---

## 10. Machine Learning

### Why Isolation Forest?

Reliable labels for every fraudulent claim or provider are generally unavailable for this type of problem. Therefore, the system uses **unsupervised anomaly detection** to learn patterns of normal behavior and identify observations that significantly differ from the learned population.

```text
Normal Behavior
      │
      ▼
Isolation Forest
      │
      ▼
Unusual Observation
      │
      ▼
Anomaly Score
```

The anomaly score is interpreted as a **risk signal**, not a confirmed fraud label.

---

## 11. Technology Stack

| Layer | Technology |
|---|---|
| Programming | Python |
| Data Processing | Pandas |
| Storage | Parquet |
| Machine Learning | scikit-learn |
| Anomaly Detection | Isolation Forest |
| Agent Layer | CrewAI / LangGraph |
| Embeddings | Sentence Transformers |
| Vector Store | FAISS |
| Generative AI | Gemini / Groq |
| Backend | FastAPI |
| Frontend | React |
| Visualization | Recharts |
| Styling | Tailwind CSS / Bootstrap |
| Deployment | Docker / Azure |

---

## 12. End-to-End Workflow

**Offline Pipeline**

```text
Raw CMS / Claims Data
        ↓
Data Cleaning
        ↓
Feature Engineering
        ↓
Peer Benchmark Generation
        ↓
Train Isolation Forest Models
        ↓
Generate Anomaly Scores
        ↓
Generate Evidence Documents
        ↓
Create FAISS Index
```

**Real-Time Investigation**

```text
User selects case
        ↓
Load case features
        ↓
Retrieve anomaly scores
        ↓
Orchestrator
        ↓
Select investigation agents
        ↓
Run Billing / Peer / Rule agents
        ↓
Aggregate evidence
        ↓
Calculate final risk
        ↓
Retrieve supporting evidence
        ↓
Generate AI explanation
        ↓
Display investigation case
```

---

## 13. Example Case Walkthrough

**Key Evidence**

```text
• Claim frequency significantly above baseline
• Provider utilization 3.8× peer median
• Payment/service substantially above peer benchmark
• Rule R07 triggered
```

**AI Explanation**

> The provider was prioritized because both claim-level and provider-level behavior showed significant deviations from expected patterns. The system identified abnormal claim frequency, substantial peer-level utilization deviation, and an additional rule-based consistency concern.

The investigator can then decide whether to **Investigate**, **Review**, or **Monitor** the case.

---

## 14. Future Enhancements

- Graph-based provider/claim relationship analysis
- Advanced temporal anomaly detection
- Human feedback loops for investigator decisions
- Supervised learning when reliable fraud labels become available
- More sophisticated peer-group construction
- Automated case management
- Additional healthcare data sources
- Model monitoring and drift detection
- Role-based investigator access
- Production-grade PostgreSQL deployment
- Cloud deployment and scalable batch processing

---

## 👥 Team

**Team Number:** 7
**Team Name:** Tech Vanguard

**Team Members:**

| Name | Register No. |
|---|---|
| Abisha K M | 111723201002 |
| Kaviya Priya S | 111723201050 |
| Kavya S | 111723201051 |
| N Saranya | 111723201070 |
| S M Pooja Shree | 111723201085 |
| Y. Sanvi Reddy | 111723201113 |
| N. Sri Nakshatra | 111723201117 |
| M. Nitheesha | 111723201121 |

**Faculty Mentors:** Dr. P. Shoba Rani, Dr. Muthazhagan B
**Alumni Mentor:** Prathiksha

This project was developed as part of the **Cognizant Hackathon 2026**.