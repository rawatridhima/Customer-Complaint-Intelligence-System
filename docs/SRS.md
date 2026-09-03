# Software Requirements Specification

## AI-Powered Customer Complaint Intelligence System

**Document Version:** 1.0
**Date:** September 2026
**Prepared by:** [Team Member 1], [Team Member 2], [Team Member 3], [Team Member 4]
**Project Guide:** [Guide Name]
**Department:** [Department], [College Name]
**Document Status:** Draft for Review

---

## Revision History

| Version | Date | Author | Description |
|---|---|---|---|
| 0.1 | [Date] | Team | Initial outline |
| 1.0 | [Date] | Team | First complete draft submitted for guide review |

---

## Table of Contents

1. Introduction
2. Overall Description
3. Functional Requirements
4. Non-Functional Requirements
5. External Interface Requirements
6. System Models and Diagrams
7. Data Requirements
8. Constraints, Assumptions and Dependencies
9. Acceptance Criteria
10. Appendices

---

# 1. Introduction

## 1.1 Purpose

This document specifies the complete software requirements for the **AI-Powered Customer Complaint Intelligence System (CIS)**. It defines the system's functional behaviour, performance characteristics, interfaces, and design constraints.

The document serves three audiences:

- **The development team**, as the authoritative definition of what must be built.
- **The project guide and evaluation panel**, as the basis against which the delivered system is assessed.
- **Future maintainers**, as a record of intended behaviour and the reasoning behind key decisions.

This SRS describes *what* the system must do. It deliberately avoids prescribing *how* each requirement is implemented, except where a technology choice is itself a binding constraint (recorded in Section 8).

## 1.2 Scope

The Customer Complaint Intelligence System is a web-based platform that automates the intake, understanding, and triage of customer complaints for a support organisation.

**The system will:**

- Accept complaint text through a REST API and a web submission form.
- Automatically classify each complaint into a predefined business category.
- Determine the emotional sentiment expressed in the complaint.
- Compute an explainable priority score and assign a severity bucket (P0–P3).
- Generate a concise summary of each complaint using a Large Language Model.
- Suggest a resolution grounded in an internal knowledge base.
- Draft a customer-facing response for agent review and approval.
- Provide an analytics dashboard showing volume, category distribution, sentiment trends, and emerging issue clusters.
- Route low-confidence predictions to a human review queue and capture agent corrections as retraining data.

**The system will not:**

- Send emails or messages directly to customers without explicit agent approval.
- Process complaints in languages other than English.
- Accept voice, video, or image-based complaints.
- Integrate with any live production CRM, ticketing system, or telephony platform.
- Provide a native mobile application.
- Perform automated financial actions such as issuing refunds.

**Benefits.** Manual triage of unstructured complaint text is slow and inconsistent. Urgent issues are frequently buried beneath routine ones. By automating classification and prioritisation, the system is intended to reduce the time an agent spends per complaint and to surface critical cases immediately.

## 1.3 Definitions, Acronyms and Abbreviations

| Term | Definition |
|---|---|
| **API** | Application Programming Interface |
| **CIS** | Customer Complaint Intelligence System (this product) |
| **Complaint** | A unit of unstructured customer text expressing dissatisfaction, submitted for resolution |
| **Category** | One of six predefined business classes a complaint is assigned to |
| **Confidence Score** | The classifier's probability estimate for its predicted label, in the range 0.0–1.0 |
| **CRUD** | Create, Read, Update, Delete |
| **Drift** | A statistically significant change over time in the distribution of input data or predictions |
| **F1 (Macro)** | The unweighted mean of per-class F1 scores; the primary classification metric for this project |
| **Human-in-the-Loop (HITL)** | A workflow in which a human reviews or approves an automated decision before it takes effect |
| **JWT** | JSON Web Token, used for stateless authentication |
| **KPI** | Key Performance Indicator |
| **LLM** | Large Language Model |
| **NLP** | Natural Language Processing |
| **P0–P3** | Priority buckets, where P0 is most severe and P3 least |
| **PII** | Personally Identifiable Information |
| **RAG** | Retrieval-Augmented Generation |
| **REST** | Representational State Transfer |
| **RBAC** | Role-Based Access Control |
| **ROUGE-L** | A recall-oriented metric used to evaluate generated summaries |
| **SLA** | Service Level Agreement |
| **SRS** | Software Requirements Specification (this document) |
| **Triage** | The process of sorting complaints by urgency and routing them appropriately |
| **UAT** | User Acceptance Testing |

## 1.4 References

1. IEEE Std 830-1998, *IEEE Recommended Practice for Software Requirements Specifications*.
2. Consumer Financial Protection Bureau, *Consumer Complaint Database*, U.S. Government public dataset.
3. Devlin, J. et al., "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding," NAACL, 2019.
4. Sanh, V. et al., "DistilBERT, a distilled version of BERT: smaller, faster, cheaper and lighter," 2019.
5. Barbieri, F. et al., "TweetEval: Unified Benchmark and Comparative Evaluation for Tweet Classification," EMNLP Findings, 2020.
6. Lewis, P. et al., "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks," NeurIPS, 2020.
7. Amershi, S. et al., "Software Engineering for Machine Learning: A Case Study," ICSE-SEIP, 2019.
8. Sculley, D. et al., "Hidden Technical Debt in Machine Learning Systems," NeurIPS, 2015.

> *Note to team: replace or extend this list with the 8–10 papers from your own literature review. Each reference cited here should be discussed somewhere in your project report.*

## 1.5 Document Conventions

- The keyword **shall** denotes a mandatory requirement.
- The keyword **should** denotes a desirable but non-blocking requirement.
- Functional requirements are numbered **FR-nn**; non-functional requirements **NFR-nn**.
- Each requirement is stated so that a corresponding test case can be written for it. Requirements that cannot be tested are defects in this document.

---

# 2. Overall Description

## 2.1 Product Perspective

The CIS is a new, self-contained system. It is not a replacement for or extension of any existing product within the institution.

In a real deployment it would sit between a company's complaint intake channels (email, web forms, social media) and its human support team, acting as an intelligence layer that enriches every incoming complaint before an agent sees it. For the purposes of this project, intake is simulated through the system's own API and web form, and a historical public dataset is used in place of live traffic.

The system is composed of four logically separate subsystems:

1. **Ingestion and API subsystem** — receives complaints, validates them, and persists them.
2. **Machine Learning subsystem** — performs classification, sentiment analysis, and priority scoring.
3. **LLM subsystem** — produces summaries, suggested resolutions, and draft responses.
4. **Presentation subsystem** — the analytics dashboard and agent workspace.

## 2.2 Product Functions

At a high level, the system provides:

- **Complaint intake** with validation, deduplication, and persistence.
- **Automatic categorisation** into six business categories.
- **Sentiment detection** across three polarity classes with an intensity score.
- **Explainable priority scoring** combining sentiment, category severity, urgency signals, and repeat-complaint history.
- **Summarisation** of long complaint narratives into two sentences.
- **Resolution suggestion** retrieved and grounded against an internal policy knowledge base.
- **Response drafting** in a tone matched to the detected sentiment, subject to mandatory agent approval.
- **Confidence-based routing** of uncertain predictions to a manual review queue.
- **Analytics and trend monitoring** across categories, sentiment, priority, and time.
- **Feedback capture**, recording every agent correction for future model retraining.

## 2.3 User Classes and Characteristics

| User Class | Description | Technical Skill | Frequency of Use | Key Needs |
|---|---|---|---|---|
| **Support Agent** | Handles individual complaints day to day | Low | Continuous, all day | Fast triage, accurate suggestions, ability to edit any AI output |
| **Support Manager** | Oversees team performance and complaint trends | Low to medium | Several times daily | Aggregate dashboards, SLA visibility, escalation alerts |
| **System Administrator** | Manages users, roles, and system configuration | High | Weekly | User management, model configuration, audit logs |
| **ML Engineer** | Monitors and retrains models | High | Weekly | Model metrics, drift indicators, access to feedback dataset |
| **Customer** | Submits a complaint | Low | Rare, per incident | Simple submission form, acknowledgement, status visibility |

The **Support Agent** is the primary user class. Where requirements conflict, agent efficiency takes precedence.

## 2.4 Operating Environment

| Component | Requirement |
|---|---|
| **Client** | Modern desktop browser — Chrome, Firefox, Edge, or Safari, current major version. Minimum viewport width 1280px. |
| **Server OS** | Linux (Ubuntu 22.04 LTS or equivalent) |
| **Runtime** | Python 3.11 or higher, Node.js 20 or higher |
| **Database** | PostgreSQL 15 or higher |
| **Cache / Broker** | Redis 7 or higher |
| **Containerisation** | Docker and Docker Compose |
| **External services** | An LLM inference endpoint, reachable over HTTPS |

## 2.5 Design and Implementation Constraints

- **C-01** The system shall be deployable via a single `docker compose up` command on a machine with 8 GB RAM.
- **C-02** All source code shall reside in a single version-controlled repository with protected main branch and mandatory peer review.
- **C-03** The system shall not transmit unredacted PII to any third-party LLM endpoint.
- **C-04** Model inference shall run on CPU. GPU availability shall not be assumed at deployment time.
- **C-05** The project shall be completed within a twelve-week academic schedule by a team of four.
- **C-06** The system shall operate within the free or student tier limits of any third-party service it uses.

## 2.6 User Documentation

The following shall be delivered alongside the software:

- A README covering local setup, environment variables, and how to run tests.
- API reference documentation, auto-generated from the OpenAPI specification.
- A short agent user guide describing the triage workflow.
- The project report and this SRS.

---

# 3. Functional Requirements

## 3.1 Complaint Intake

**FR-01** The system shall accept a complaint submission containing complaint text, an optional customer identifier, an optional channel label, and a submission timestamp.

**FR-02** The system shall reject a submission whose complaint text is shorter than 20 characters or longer than 5,000 characters, returning a descriptive validation error.

**FR-03** The system shall assign every accepted complaint a unique, immutable identifier and persist it before any analysis begins.

**FR-04** The system shall return an acknowledgement to the submitter within 500 milliseconds of accepting a complaint, without waiting for analysis to complete.

**FR-05** The system shall detect a duplicate submission — identical text from the same customer within a 24-hour window — and link it to the original rather than creating a new record.

**FR-06** The system shall redact detected email addresses, phone numbers, and account numbers from complaint text before that text is transmitted to any external LLM service.

## 3.2 Classification

**FR-07** The system shall classify every complaint into exactly one of the following six categories: *Billing and Payments*, *Delivery and Logistics*, *Product Defect*, *Service Quality*, *Technical Issue*, *Refund and Returns*.

**FR-08** The system shall store, alongside each classification, a confidence score in the range 0.0 to 1.0.

**FR-09** The system shall route any complaint whose classification confidence falls below 0.75 to a manual review queue, flagged for agent verification.

**FR-10** The system shall allow an authorised agent to override any predicted category, and shall record the original prediction, the corrected value, the agent identity, and the timestamp.

## 3.3 Sentiment Analysis

**FR-11** The system shall assign each complaint a sentiment label of *Positive*, *Neutral*, or *Negative*.

**FR-12** The system shall compute a sentiment intensity score in the range 0.0 to 1.0 representing the strength of the detected polarity.

**FR-13** The system shall make both the sentiment label and intensity score available through the API and visible on the complaint detail screen.

## 3.4 Priority Scoring

**FR-14** The system shall compute a priority score for every complaint using a weighted, explainable combination of: sentiment negativity, category severity weight, urgency keyword presence, and repeat-complaint history.

**FR-15** The system shall map each priority score to exactly one bucket: **P0** (critical), **P1** (high), **P2** (medium), or **P3** (low).

**FR-16** The system shall display, on request, the individual contribution of each factor to a complaint's final priority score.

**FR-17** The system shall allow a Support Manager to adjust the factor weights through configuration without requiring a code change or redeployment.

**FR-18** The system shall raise a visible alert on the dashboard whenever a complaint is assigned P0.

## 3.5 LLM-Generated Content

**FR-19** The system shall generate a summary of each complaint not exceeding two sentences and not exceeding 60 words.

**FR-20** The system shall generate a suggested resolution for each complaint, grounded in documents retrieved from the internal knowledge base, and shall cite which knowledge base entries were used.

**FR-21** The system shall generate a draft customer-facing response whose tone is selected according to the detected sentiment and priority bucket.

**FR-22** The system shall not dispatch any generated response to a customer without explicit agent approval.

**FR-23** The system shall allow an agent to edit any generated text before approval, and shall store both the generated version and the final edited version.

**FR-24** The system shall cache generated content keyed on a hash of the complaint text, and shall reuse the cached result for identical text rather than issuing a repeat LLM request.

**FR-25** The system shall fall back to a predefined template response and mark the complaint for manual handling if the LLM service is unreachable or exceeds its timeout.

## 3.6 Agent Workspace

**FR-26** The system shall present agents with a filterable, sortable list of complaints supporting filters on category, priority, sentiment, status, date range, and assigned agent.

**FR-27** The system shall display, on a single complaint detail screen: the original text, the predicted category with confidence, the sentiment, the priority breakdown, the generated summary, the suggested resolution, and the editable draft response.

**FR-28** The system shall allow an agent to change a complaint's status among *New*, *In Review*, *Awaiting Customer*, *Resolved*, and *Escalated*.

**FR-29** The system shall allow bulk status updates on multiple selected complaints.

**FR-30** The system shall maintain a complete audit trail of every status change, override, and approval, attributable to a specific user.

## 3.7 Analytics and Monitoring

**FR-31** The dashboard shall display total complaint volume, open complaint count, average resolution time, and P0 count for a user-selected date range.

**FR-32** The dashboard shall display complaint volume as a time series, segmented by category.

**FR-33** The dashboard shall display the distribution of sentiment across the selected period.

**FR-34** The system shall identify and highlight emerging issues, defined as any category whose seven-day volume exceeds its trailing thirty-day mean by more than two standard deviations.

**FR-35** The system shall display model performance indicators including the confusion matrix, per-class precision and recall, and the distribution of confidence scores.

**FR-36** The system shall report the proportion of predictions falling below the confidence threshold as a proxy for model health.

## 3.8 User Management and Security

**FR-37** The system shall authenticate users via username and password, issuing a signed token on success.

**FR-38** The system shall enforce role-based access control across the roles Agent, Manager, and Administrator.

**FR-39** The system shall restrict weight configuration (FR-17) and user management to Manager and Administrator roles respectively.

**FR-40** The system shall expire authentication tokens after a configurable period and require re-authentication.

## 3.9 Feedback and Retraining Support

**FR-41** The system shall persist every agent correction as a labelled training example, including original text, predicted label, corrected label, and correction timestamp.

**FR-42** The system shall allow an ML Engineer to export the accumulated feedback dataset in a machine-readable format.

**FR-43** The system shall record the model version responsible for every stored prediction.

---

# 4. Non-Functional Requirements

## 4.1 Performance

| ID | Requirement |
|---|---|
| **NFR-01** | Category classification shall complete within 200 milliseconds at the 95th percentile on CPU inference. |
| **NFR-02** | LLM-generated analysis shall complete within 5 seconds at the 95th percentile, executed asynchronously. |
| **NFR-03** | Any dashboard view shall render within 2 seconds for a dataset of up to 100,000 complaints. |
| **NFR-04** | The system shall sustain 100 concurrent authenticated users without degradation beyond the stated latency targets. |
| **NFR-05** | The complaint submission endpoint shall sustain 50 requests per second. |

## 4.2 Reliability and Availability

| ID | Requirement |
|---|---|
| **NFR-06** | The system shall maintain 99% availability during the demonstration and evaluation period. |
| **NFR-07** | Failure of the LLM subsystem shall not prevent complaint intake, classification, or dashboard access. |
| **NFR-08** | Failed asynchronous analysis tasks shall be retried up to three times with exponential backoff before being marked failed. |
| **NFR-09** | No accepted complaint shall be lost as a result of a worker process crash. |

## 4.3 Security

| ID | Requirement |
|---|---|
| **NFR-10** | All passwords shall be stored using a salted, adaptive hashing algorithm. Plaintext storage is prohibited. |
| **NFR-11** | All client-server communication shall use HTTPS in any deployed environment. |
| **NFR-12** | PII shall be redacted from any text leaving the system boundary. |
| **NFR-13** | All database access shall use parameterised queries. String-concatenated SQL is prohibited. |
| **NFR-14** | API credentials and secrets shall be supplied through environment variables and shall never be committed to version control. |

## 4.4 Usability

| ID | Requirement |
|---|---|
| **NFR-15** | An agent shall be able to triage a single complaint — read, verify, and act — in under 30 seconds. |
| **NFR-16** | Priority buckets shall be distinguishable by more than colour alone, to remain legible to colour-blind users. |
| **NFR-17** | Every AI-generated field shall be visually marked as machine-generated. |
| **NFR-18** | All destructive actions shall require explicit confirmation. |

## 4.5 Maintainability and Portability

| ID | Requirement |
|---|---|
| **NFR-19** | Automated test coverage of backend business logic shall be at least 70%. |
| **NFR-20** | The system shall run identically on Linux, macOS, and Windows via Docker. |
| **NFR-21** | Every trained model artifact shall carry a version identifier and its evaluation metrics. |
| **NFR-22** | LLM prompts shall be stored as versioned files, not embedded as inline string literals. |
| **NFR-23** | The system shall emit structured logs with correlation identifiers linking a complaint through every processing stage. |

## 4.6 Scalability

| ID | Requirement |
|---|---|
| **NFR-24** | The analysis workers shall scale horizontally without modification to application code. |
| **NFR-25** | The database schema shall support at least one million complaint records with indexed query performance. |

## 4.7 Model Quality

| ID | Requirement |
|---|---|
| **NFR-26** | The classification model shall achieve a macro-F1 score of at least 0.75 on a held-out test set. |
| **NFR-27** | The classification model shall demonstrably outperform the TF-IDF baseline on macro-F1. |
| **NFR-28** | No single category shall have recall below 0.60 on the held-out test set. |
| **NFR-29** | Generated summaries shall achieve a ROUGE-L score of at least 0.30 against reference summaries on the evaluation sample. |

---

# 5. External Interface Requirements

## 5.1 User Interfaces

The system provides five primary screens.

**Screen 1 — Overview Dashboard.** KPI cards for total volume, open complaints, average resolution time, and P0 count. Below them, a volume time series, a category distribution chart, and a sentiment gauge.

**Screen 2 — Complaint Inbox.** A dense, sortable table with a filter sidebar. Columns: ID, truncated text, category, priority, sentiment, status, age, assigned agent. Priority is indicated by both colour and a text label. Supports row selection and bulk actions.

**Screen 3 — Complaint Detail.** Two-column layout. Left: original complaint text and metadata. Right: AI outputs — summary, category with confidence bar, sentiment, priority breakdown, suggested resolution with knowledge base citations, and an editable draft response with Approve and Reject controls.

**Screen 4 — Trends and Insights.** Category volume over time, sentiment trend line, keyword frequency visualisation, and an emerging-issues alert panel.

**Screen 5 — Model Insights.** Confusion matrix heatmap, per-class precision and recall table, confidence score histogram, and the current size of the low-confidence review queue.

*Wireframes for each screen shall be attached in Appendix C.*

## 5.2 Software Interfaces

| Interface | Purpose | Protocol / Format |
|---|---|---|
| PostgreSQL | Persistent storage of complaints, predictions, users, and feedback | TCP, SQL |
| Redis | Message brokering for asynchronous tasks and result caching | TCP, Redis protocol |
| LLM inference endpoint | Summarisation, resolution suggestion, response drafting | HTTPS, JSON |
| Object storage or local volume | Trained model artifacts | Filesystem |

## 5.3 Application Programming Interface

All endpoints are prefixed `/api/v1` and require a valid bearer token except where noted.

| Method | Endpoint | Description | Role |
|---|---|---|---|
| POST | `/auth/login` | Authenticate and obtain a token | Public |
| POST | `/complaints` | Submit a new complaint | Public |
| GET | `/complaints` | List complaints with filters and pagination | Agent |
| GET | `/complaints/{id}` | Retrieve one complaint with all AI outputs | Agent |
| PATCH | `/complaints/{id}` | Update status, category, or assignment | Agent |
| POST | `/complaints/{id}/respond` | Approve and record a response | Agent |
| POST | `/complaints/{id}/feedback` | Record a correction to a prediction | Agent |
| GET | `/complaints/review-queue` | List low-confidence complaints | Agent |
| GET | `/analytics/overview` | KPI summary for a date range | Agent |
| GET | `/analytics/trends` | Time series and distributions | Agent |
| GET | `/analytics/hotspots` | Emerging issue detection | Manager |
| GET | `/models/metrics` | Current model performance metrics | Manager |
| PUT | `/config/priority-weights` | Update priority scoring weights | Manager |
| GET | `/health` | Liveness probe | Public |

All responses use JSON. Errors follow a consistent envelope containing an error code, a human-readable message, and, where applicable, field-level validation detail.

## 5.4 Communication Interfaces

- Client to server: HTTPS, REST, JSON.
- Server to LLM provider: HTTPS, JSON.
- Internal service to service: TCP within the container network.

---

# 6. System Models and Diagrams

## 6.1 Use Case Diagram

The following actors and use cases apply. *(Render as a formal UML use case diagram in your report.)*

**Actor: Customer**
- Submit complaint
- View complaint status

**Actor: Support Agent**
- View complaint inbox
- View complaint detail
- Override predicted category
- Edit and approve draft response
- Update complaint status
- Process review queue

**Actor: Support Manager**
- View analytics dashboard
- View emerging issues
- Configure priority weights
- View model performance

**Actor: System Administrator**
- Manage users and roles
- View audit logs

**Actor: CIS (system, as secondary actor)**
- Classify complaint
- Analyse sentiment
- Compute priority
- Generate summary, resolution, and response

## 6.2 Data Flow Diagram — Level 0 (Context)

```
                    complaint text
   [ Customer ] ─────────────────────▶ ┌──────────────────────────┐
                                       │                          │
                 acknowledgement       │   Customer Complaint     │
             ◀───────────────────────  │   Intelligence System    │
                                       │                          │
   [ Support  ] ─── queries ──────────▶│         (0)              │
   [  Agent   ] ◀── enriched ───────── │                          │
                    complaints         └──────────────────────────┘
                                              │         ▲
                                    prompt    │         │  generated
                                              ▼         │  content
                                       [ LLM Service ]
```

## 6.3 Data Flow Diagram — Level 1

```
 complaint ──▶ (1.0) Validate &  ──▶ [D1 Complaints] ──▶ (2.0) Classify &
                    Persist                                   Score
                                                                 │
                                                                 ▼
                                                        [D2 Predictions]
                                                                 │
                                                                 ▼
              [D3 Knowledge Base] ──▶ (3.0) Generate Content ◀────┘
                                              │
                                              ▼
                                     [D4 Generated Content]
                                              │
                                              ▼
                        (4.0) Present to Agent ──▶ (5.0) Capture Feedback
                                                          │
                                                          ▼
                                                   [D5 Feedback]
```

## 6.4 Entity Relationship Model

**Entities and key attributes:**

- **User** — `user_id (PK)`, `username`, `password_hash`, `role`, `created_at`
- **Complaint** — `complaint_id (PK)`, `customer_ref`, `raw_text`, `redacted_text`, `channel`, `status`, `assigned_to (FK→User)`, `submitted_at`, `resolved_at`, `duplicate_of (FK→Complaint)`
- **Prediction** — `prediction_id (PK)`, `complaint_id (FK)`, `category`, `category_confidence`, `sentiment_label`, `sentiment_score`, `priority_score`, `priority_bucket`, `model_version`, `created_at`
- **GeneratedContent** — `content_id (PK)`, `complaint_id (FK)`, `summary`, `suggested_resolution`, `draft_response`, `final_response`, `prompt_version`, `approved_by (FK→User)`, `approved_at`
- **KnowledgeArticle** — `article_id (PK)`, `title`, `body`, `category`, `embedding`
- **Feedback** — `feedback_id (PK)`, `complaint_id (FK)`, `field_corrected`, `original_value`, `corrected_value`, `corrected_by (FK→User)`, `created_at`
- **AuditLog** — `log_id (PK)`, `user_id (FK)`, `action`, `entity_type`, `entity_id`, `timestamp`

**Relationships:**

- One Complaint has one Prediction *(1:1)*
- One Complaint has one GeneratedContent *(1:1)*
- One Complaint has many Feedback entries *(1:N)*
- One User is assigned many Complaints *(1:N)*
- One Complaint may reference another as its duplicate origin *(self-referential, 0:1)*
- GeneratedContent references many KnowledgeArticles *(N:M, via a join table)*

## 6.5 Complaint State Machine

```
   [New] ──▶ [In Review] ──▶ [Awaiting Customer] ──▶ [Resolved]
     │            │                                      ▲
     │            └──────────▶ [Escalated] ──────────────┘
     │                              ▲
     └──────────────────────────────┘
```

Transitions are permitted only as shown. Every transition is written to the audit log.

---

# 7. Data Requirements

## 7.1 Training Data

The classification and sentiment models shall be trained on a publicly available complaint corpus. The Consumer Financial Protection Bureau Consumer Complaint Database is the primary source, filtered to records containing a non-empty narrative field.

**DR-01** The training dataset shall contain at least 30,000 labelled complaint narratives.

**DR-02** Source categories shall be mapped to the six system categories through an explicit, version-controlled mapping definition.

**DR-03** The dataset shall be split into training, validation, and test partitions in a 70/15/15 ratio, stratified by category, with a fixed random seed for reproducibility.

**DR-04** Class imbalance shall be addressed through class weighting or resampling, and the chosen approach documented.

## 7.2 Knowledge Base

**DR-05** The knowledge base shall contain at least 50 resolution articles distributed across all six categories.

**DR-06** Each article shall carry a vector embedding to support semantic retrieval.

## 7.3 Data Retention

**DR-07** Complaint records shall be retained for the duration of the project.

**DR-08** Raw unredacted text shall be stored only within the system database and shall never appear in application logs.

---

# 8. Constraints, Assumptions and Dependencies

## 8.1 Assumptions

- **A-01** All complaint text is in English.
- **A-02** The complaint corpus is representative of the categories the deployed system would encounter.
- **A-03** A support agent is available to review any complaint routed for manual verification.
- **A-04** The LLM provider maintains a stable API contract for the project duration.
- **A-05** Evaluation is conducted on a machine meeting the minimum specification in Section 2.4.

## 8.2 Dependencies

- **D-01** Availability of the CFPB public dataset.
- **D-02** Availability and quota limits of the chosen LLM provider.
- **D-03** Availability of pretrained transformer weights from a public model hub.
- **D-04** Availability of the team's four members for the twelve-week schedule.

## 8.3 Risks

| Risk | Impact | Mitigation |
|---|---|---|
| LLM API quota exhausted before demonstration | High | Response caching (FR-24); local model fallback; pre-generate demo content |
| Classification accuracy below target | High | Baseline established early; ensemble or additional feature engineering as fallback |
| Severe class imbalance degrades minority recall | Medium | Class weighting; per-class recall floor enforced by NFR-28 |
| Team member unavailable | Medium | Mandatory peer review means no module has a single owner |
| Scope expansion late in schedule | High | Exclusions in Section 1.2 are treated as binding |

---

# 9. Acceptance Criteria

The system shall be considered complete when all of the following hold:

1. Every requirement marked **shall** in Sections 3 and 4 is implemented and has a corresponding passing test.
2. The classification model meets NFR-26, NFR-27, and NFR-28 on the held-out test set.
3. The complete pipeline — submission through to agent-approved response — is demonstrable end to end without manual intervention between stages.
4. The system starts from a clean checkout with a single `docker compose up`.
5. Backend test coverage meets NFR-19.
6. All five dashboard screens are functional against live data.
7. The requirements traceability matrix in Appendix A is complete, with every requirement mapped to a test case.

---

# 10. Appendices

## Appendix A — Requirements Traceability Matrix

| Req ID | Description | Module | Test Case ID | Status |
|---|---|---|---|---|
| FR-01 | Accept complaint submission | Ingestion | TC-01 | |
| FR-07 | Six-category classification | ML | TC-07 | |
| FR-09 | Low-confidence routing | ML | TC-09 | |
| FR-14 | Priority scoring | ML | TC-14 | |
| FR-19 | Summary generation | LLM | TC-19 | |
| FR-22 | Mandatory approval before dispatch | LLM | TC-22 | |
| FR-31 | Dashboard KPIs | Frontend | TC-31 | |
| NFR-01 | Classification latency | ML | TC-P01 | |
| NFR-26 | Macro-F1 threshold | ML | TC-M01 | |

*Complete this table for all requirements before the final review.*

## Appendix B — Priority Scoring Definition

```
priority_score = w1 · sentiment_negativity
               + w2 · category_severity_weight
               + w3 · urgency_keyword_score
               + w4 · repeat_complaint_flag

Default weights:  w1 = 0.40,  w2 = 0.25,  w3 = 0.20,  w4 = 0.15
Constraint:       w1 + w2 + w3 + w4 = 1.0

Bucket mapping:
   score ≥ 0.80  →  P0  (critical)
   0.60 – 0.79   →  P1  (high)
   0.35 – 0.59   →  P2  (medium)
   score < 0.35  →  P3  (low)
```

Each term is normalised to the range 0.0–1.0. Category severity weights are configurable per FR-17.

## Appendix C — Wireframes

*Attach hand-drawn or Figma wireframes for all five screens described in Section 5.1.*

## Appendix D — Glossary of Business Categories

| Category | Includes |
|---|---|
| Billing and Payments | Incorrect charges, failed payments, subscription disputes |
| Delivery and Logistics | Late, missing, or damaged-in-transit shipments |
| Product Defect | Faulty, broken, or non-functioning goods |
| Service Quality | Agent behaviour, wait times, unresolved prior contacts |
| Technical Issue | App or website faults, login failures, integration errors |
| Refund and Returns | Refund delays, return rejections, exchange disputes |

---

**End of Document**

*This SRS is a living document. Any change to a numbered requirement shall be recorded in the revision history with a stated rationale.*
