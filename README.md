# Claims Fraud, Waste & Abuse Risk Detector

An AI-powered **healthcare insurance payment-integrity system** that analyzes claim and provider-level patterns to identify potentially suspicious billing behavior, explain why a claim or provider appears high-risk, and prioritize cases for investigation.

> **Cognizant Hackathon — Claims / Payment Integrity Use Case**

---

## 1. Use Case

### Claims Fraud, Waste and Abuse Risk Detector

**Type:** Claims / Payment Integrity

### Use Case Description

US payers process billions of healthcare claims every year. Even a small rate of inappropriate billing can create significant financial leakage.

A real payment-integrity team cannot rely on a bare fraud label. Investigators need:

* Explainable reasons for a risk flag
* Provider peer comparisons
* Evidence supporting the risk assessment
* A defensible investigation queue
* Appropriate prioritization of suspicious cases

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

Build a system that analyzes **claim-and-provider-level patterns** to:

> **Flag potentially suspicious billing behavior, explain in plain language why a claim or provider looks high-risk, and prioritize the flagged cases into an investigation queue.**

The system is intended to support **payment-integrity investigators** by helping them focus their attention on higher-priority cases.

---

## 4. Important Distinction: Fraud, Waste & Abuse

The project considers Fraud, Waste and Abuse as related but distinct risk categories.

### Fraud

Intentional deception or misrepresentation for financial gain.

**Example:**

A provider intentionally submits a claim for a service that was not actually performed.

### Waste

Unnecessary or inefficient use of healthcare resources that results in avoidable costs.

**Example:**

Repeated or excessive utilization that may not be medically necessary.

### Abuse

Practices that are inconsistent with accepted healthcare or payment practices and may result in unnecessary costs.

**Example:**

Billing practices that exploit reimbursement rules without necessarily establishing intentional fraud.

### Important

A model-generated risk flag is **not proof of fraud, waste, or abuse**.

The system is designed to identify **potential risk and provide evidence for human investigation**.

---

# 5. Data Sources

The hackathon organizers have provided the following data sources for this use case.

## 5.1 CMS Synthetic Medicare Enrollment, FFS Claims & Prescription Drug Event

**Source:** Centers for Medicare & Medicaid Services (CMS)

This dataset provides synthetic Medicare-related enrollment, fee-for-service claims, and prescription drug event data.

Official source:

https://data.cms.gov/collection/synthetic-medicare-enrollment-fee-for-service-claims-and-prescription-drug-event

The data will be investigated for:

* Claim-level patterns
* Beneficiary-related patterns
* Service utilization
* Provider activity
* Prescription-related activity
* Temporal patterns
* Potential anomalies

---

## 5.2 HHS OIG LEIE Exclusions

**Source:** U.S. Department of Health and Human Services — Office of Inspector General (HHS OIG)

The **List of Excluded Individuals/Entities (LEIE)** is provided through monthly CSV downloads.

Official source:

https://oig.hhs.gov/exclusions/leie-database-supplement-downloads/

The dataset can potentially support risk analysis involving excluded individuals or entities.

Potential use:

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

The exact matching methodology will be determined during data analysis.

---

## 5.3 CMS Medicare Physician & Other Practitioners

**Source:** Centers for Medicare & Medicaid Services

Official source:

https://data.cms.gov/provider-summary-by-type-of-service/medicare-physician-other-practitioners

This source provides provider-level information that can potentially be used for:

* Provider profiling
* Service patterns
* Utilization analysis
* Provider-level comparisons
* Peer benchmarking
* Outlier detection

---

## 5.4 Kaggle Healthcare Provider Fraud Detection Dataset

**Source:** Kaggle

Healthcare Provider Fraud Detection dataset:

https://www.kaggle.com/datasets/rohitrox/healthcare-provider-fraud-detection-analysis

This dataset contains labelled healthcare provider fraud information and may be investigated as an additional source for supervised learning and experimentation.

### Important

The dataset's labels, provenance, licensing, and suitability must be verified before being used in the final system.

---

# 6. Data Strategy

The project will not assume that every provided dataset should automatically be combined.

Each source will first be evaluated for:

* Data structure
* Relevance
* Available identifiers
* Data quality
* Temporal coverage
* Label availability
* Compatibility with other sources
* Licensing / usage constraints

The final data pipeline will be determined after data profiling and exploratory analysis.

---

# 7. Proposed Solution

The proposed system will combine **data analytics, machine learning, anomaly detection, explainability, and investigation support**.

### High-Level Architecture

```text
               Claims Data
     │
     ▼
Data Cleaning & Validation
     │
     ▼
Feature Engineering
     │
     ├──────────────► Claim-level features
     │
     ├──────────────► Provider-level features
     │
     └──────────────► Peer-comparison features
     │
     ▼
Risk Detection Engine
     │
     ├── Supervised ML
     │     └── XGBoost / Random Forest
     │
     ├── Anomaly Detection
     │     └── Isolation Forest
     │
     └── Rule Engine
     │
     ▼
Risk Score
     │
     ▼
Explainability Layer
     │
     ├── SHAP
     ├── Rule-based reasons
     └── Peer comparison
     │
     ▼
GenAI Explanation
     │
     ▼
Investigation Queue
     │
     └── High → Medium → Low priority
     │
     ▼
Dashboard
```

The architecture will evolve based on research and experimentation.

---

# 8. Key System Capabilities

## 8.1 Claim-Level Risk Detection

Analyze individual claims for potentially unusual or suspicious characteristics.

Potential indicators may include:

* Unusual claim amounts
* Unusual service combinations
* Repeated procedures
* Abnormal utilization
* Temporal anomalies
* Duplicate or highly similar claims
* Unexpected provider-beneficiary patterns

---

## 8.2 Provider-Level Risk Detection

Analyze provider behavior across multiple claims.

Potential indicators may include:

* Unusually high claim volume
* High-cost billing patterns
* Unusual procedure distributions
* Deviation from peer providers
* Abnormal utilization patterns
* Repeated suspicious claim patterns
* Potential exclusion-related indicators

---

## 8.3 Provider Peer Comparison

A key requirement of the use case is to provide **provider peer comparisons**.

Instead of simply saying:

> "Provider X is high-risk."

the system should aim to provide context such as:

> "Provider X's billing pattern is substantially different from comparable providers for similar services."

The exact peer-group methodology will be determined during development.

Possible comparison dimensions may include:

* Specialty
* Service type
* Geography where appropriate
* Provider characteristics
* Patient volume
* Procedure mix
* Claim volume

---

# 9. Explainability

The system should not produce only:

```text
Risk Score: 0.91
```

Instead, it should provide understandable evidence such as:

```text
Risk Score: HIGH

Potential contributing factors:

1. Claim amount is substantially above the provider peer range.
2. Provider has an unusually high frequency of a particular procedure.
3. The provider's utilization pattern differs from comparable providers.
4. Additional claim-level anomalies were detected.

Recommended Action:
Prioritize for investigator review.
```

The final explanation methodology will be determined through experimentation with appropriate explainability techniques.

---

# 10. Investigation Queue

The output of the system should be a **prioritized investigation queue**, rather than simply a binary fraud label.

Example:

| Priority | Case               | Risk   | Key Reason                | Recommended Action |
| -------- | ------------------ | ------ | ------------------------- | ------------------ |
| 1        | Claim / Provider A | High   | Multiple unusual patterns | Investigate        |
| 2        | Claim / Provider B | High   | Strong peer deviation     | Investigate        |
| 3        | Claim / Provider C | Medium | Utilization anomaly       | Review             |
| 4        | Claim / Provider D | Low    | Minor deviation           | Monitor            |

This allows investigators to focus resources where they may have the greatest value.

---

# 11. Machine Learning Strategy

The project will evaluate appropriate approaches rather than selecting a model arbitrarily.

Potential approaches include:

### Supervised Learning

Where reliable labels are available:

* Logistic Regression
* Random Forest
* XGBoost / Gradient Boosting

### Unsupervised / Anomaly Detection

Where reliable labels are unavailable:

* Statistical outlier detection
* Isolation Forest
* Clustering-based approaches
* Other appropriate anomaly detection methods

### Hybrid Risk Scoring

A potential final approach is to combine multiple signals:

```text
ML Prediction
      +
Anomaly Score
      +
Provider Peer Deviation
      +
Rule-Based Indicators
      +
Additional Evidence
      │
      ▼
Composite Risk Score
```

The final methodology will be determined through experimentation and validation.

---

# 12. Explainable AI & Investigation Support

The system may incorporate explainability and intelligent investigation capabilities to transform model outputs into investigator-friendly insights.

Potential capabilities include:

* Risk explanation
* Evidence summarization
* Provider profile generation
* Related claim analysis
* Peer comparison summaries
* Investigation recommendations
* Natural-language querying of investigation evidence

Any LLM-based component will be used as an **interpretation and investigation-support layer**, rather than replacing the core risk-detection model.

---

# 13. Technology Stack

The final technology stack will be selected based on experimentation and project requirements.

### Data & Machine Learning

* Python
* Pandas
* NumPy
* Scikit-learn
* XGBoost

### Explainability

* SHAP
* Other appropriate explainability techniques

### Backend

* FastAPI

### Frontend

* React
* TypeScript
* Tailwind CSS

### AI / LLM

* Google Gemini
* LangChain / LangGraph where appropriate

### Database / Retrieval

* PostgreSQL
* Vector database if required

---

# 14. Team

### Cognizant Hackathon 2026

Team members and responsibilities will be added here.

