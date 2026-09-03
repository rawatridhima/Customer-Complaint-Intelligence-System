# Low Level Design Document

## AI-Powered Customer Complaint Intelligence System

**Document Version:** 1.0
**Date:** September 2026
**Companion to:** SRS v1.0
**Prepared by:** [Team Member 1], [Team Member 2], [Team Member 3], [Team Member 4]

---

## Table of Contents

1. Purpose and Scope
2. Module Decomposition
3. Database Design
4. Backend Class Design
5. ML Subsystem Design
6. LLM Subsystem Design
7. Asynchronous Processing Design
8. API Contract Specification
9. Frontend Component Design
10. Sequence Flows
11. Algorithms
12. Error Handling and Fault Tolerance
13. Configuration and Environment
14. Testing Design
15. Deployment Design

---

# 1. Purpose and Scope

The SRS states *what* the system must do. This document states *how* each requirement is realised in code.

Every section here traces back to one or more requirements in the SRS. Where a design decision has a meaningful alternative, the rejected option and the reason for rejection are recorded, because those are the questions asked during evaluation.

**Traceability convention.** Design elements reference their originating requirement in square brackets, e.g. `[FR-09]`.

---

# 2. Module Decomposition

## 2.1 Module Hierarchy

```
complaint-intelligence/
│
├── backend/app/
│   ├── main.py                    Application entry, middleware registration
│   ├── core/
│   │   ├── config.py              Settings via pydantic-settings
│   │   ├── security.py            Password hashing, JWT encode/decode
│   │   ├── database.py            Engine, SessionLocal, Base
│   │   ├── logging.py             Structured JSON logger, correlation IDs
│   │   └── exceptions.py          Custom exception hierarchy
│   ├── models/                    SQLAlchemy ORM classes
│   │   ├── user.py
│   │   ├── complaint.py
│   │   ├── prediction.py
│   │   ├── generated_content.py
│   │   ├── knowledge_article.py
│   │   ├── feedback.py
│   │   └── audit_log.py
│   ├── schemas/                   Pydantic request/response models
│   │   ├── complaint.py
│   │   ├── prediction.py
│   │   ├── analytics.py
│   │   └── auth.py
│   ├── repositories/              Data access layer
│   │   ├── base.py
│   │   ├── complaint_repo.py
│   │   └── analytics_repo.py
│   ├── services/                  Business logic
│   │   ├── complaint_service.py
│   │   ├── classifier_service.py
│   │   ├── sentiment_service.py
│   │   ├── priority_service.py
│   │   ├── llm_service.py
│   │   ├── retrieval_service.py
│   │   ├── redaction_service.py
│   │   └── analytics_service.py
│   ├── workers/
│   │   ├── celery_app.py
│   │   └── tasks.py
│   ├── api/v1/
│   │   ├── router.py
│   │   ├── complaints.py
│   │   ├── analytics.py
│   │   ├── auth.py
│   │   └── deps.py                Dependency injection helpers
│   └── prompts/
│       ├── summarise_v1.txt
│       ├── suggest_resolution_v1.txt
│       └── draft_response_v1.txt
│
├── ml/src/
│   ├── preprocess.py
│   ├── label_mapping.py
│   ├── train_baseline.py
│   ├── train_transformer.py
│   ├── evaluate.py
│   └── registry.py                Model versioning and artifact loading
│
└── frontend/src/                  (see Section 9)
```

## 2.2 Layering Rules

The backend follows a strict four-layer architecture. Calls flow downward only.

```
   API layer          routes, request validation, auth guards
        │
        ▼
   Service layer      business logic, orchestration
        │
        ▼
   Repository layer   all database access
        │
        ▼
   Model layer        ORM entities
```

**Enforced rules:**

- API handlers shall not import SQLAlchemy models directly. They call services.
- Services shall not execute raw queries. They call repositories.
- Repositories shall not contain business logic. They return entities or primitives.
- No layer imports from a layer above it.

This is checked in review. Violations are the main cause of untestable code in projects of this size.

## 2.3 Module Ownership

| Module | Owner | Reviewer |
|---|---|---|
| `ml/`, `services/classifier_service.py`, `services/sentiment_service.py`, `services/priority_service.py` | Person A | Person B |
| `api/`, `services/llm_service.py`, `repositories/`, `models/`, `workers/` | Person B | Person A |
| `frontend/` | Person C | Person D |
| `docker/`, CI, `core/config.py`, `core/logging.py`, docs | Person D | Person C |

---

# 3. Database Design

## 3.1 Schema DDL

```sql
CREATE TYPE user_role     AS ENUM ('agent', 'manager', 'admin');
CREATE TYPE complaint_status AS ENUM ('new','in_review','awaiting_customer','resolved','escalated');
CREATE TYPE analysis_status  AS ENUM ('pending','processing','completed','failed');
CREATE TYPE category_enum  AS ENUM ('billing','delivery','product_defect','service_quality','technical','refund');
CREATE TYPE sentiment_enum AS ENUM ('positive','neutral','negative');
CREATE TYPE priority_enum  AS ENUM ('P0','P1','P2','P3');

CREATE TABLE users (
    user_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username       VARCHAR(64)  NOT NULL UNIQUE,
    email          VARCHAR(255) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           user_role    NOT NULL DEFAULT 'agent',
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE TABLE complaints (
    complaint_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_ref     VARCHAR(128),
    raw_text         TEXT             NOT NULL,
    redacted_text    TEXT             NOT NULL,
    text_hash        CHAR(64)         NOT NULL,
    channel          VARCHAR(32)      NOT NULL DEFAULT 'web',
    status           complaint_status NOT NULL DEFAULT 'new',
    analysis_status  analysis_status  NOT NULL DEFAULT 'pending',
    assigned_to      UUID REFERENCES users(user_id) ON DELETE SET NULL,
    duplicate_of     UUID REFERENCES complaints(complaint_id) ON DELETE SET NULL,
    submitted_at     TIMESTAMPTZ      NOT NULL DEFAULT now(),
    resolved_at      TIMESTAMPTZ,
    CONSTRAINT chk_text_len CHECK (char_length(raw_text) BETWEEN 20 AND 5000)
);

CREATE INDEX idx_complaints_status      ON complaints(status);
CREATE INDEX idx_complaints_submitted   ON complaints(submitted_at DESC);
CREATE INDEX idx_complaints_assigned    ON complaints(assigned_to);
CREATE INDEX idx_complaints_hash        ON complaints(text_hash, customer_ref);
CREATE INDEX idx_complaints_analysis    ON complaints(analysis_status)
    WHERE analysis_status IN ('pending','processing');

CREATE TABLE predictions (
    prediction_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id        UUID NOT NULL UNIQUE REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    category            category_enum  NOT NULL,
    category_confidence NUMERIC(4,3)   NOT NULL CHECK (category_confidence BETWEEN 0 AND 1),
    sentiment_label     sentiment_enum NOT NULL,
    sentiment_score     NUMERIC(4,3)   NOT NULL CHECK (sentiment_score BETWEEN 0 AND 1),
    priority_score      NUMERIC(4,3)   NOT NULL,
    priority_bucket     priority_enum  NOT NULL,
    priority_breakdown  JSONB          NOT NULL,
    needs_review        BOOLEAN        NOT NULL DEFAULT FALSE,
    model_version       VARCHAR(32)    NOT NULL,
    inference_ms        INTEGER,
    created_at          TIMESTAMPTZ    NOT NULL DEFAULT now()
);

CREATE INDEX idx_predictions_category ON predictions(category);
CREATE INDEX idx_predictions_priority ON predictions(priority_bucket);
CREATE INDEX idx_predictions_review   ON predictions(needs_review) WHERE needs_review = TRUE;

CREATE TABLE knowledge_articles (
    article_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title       VARCHAR(255)  NOT NULL,
    body        TEXT          NOT NULL,
    category    category_enum NOT NULL,
    embedding   VECTOR(384),
    created_at  TIMESTAMPTZ   NOT NULL DEFAULT now()
);

CREATE TABLE generated_content (
    content_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id         UUID NOT NULL UNIQUE REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    summary              TEXT,
    suggested_resolution TEXT,
    draft_response       TEXT,
    final_response       TEXT,
    cited_article_ids    UUID[],
    prompt_version       VARCHAR(32) NOT NULL,
    llm_model            VARCHAR(64),
    token_count          INTEGER,
    was_edited           BOOLEAN     NOT NULL DEFAULT FALSE,
    approved_by          UUID REFERENCES users(user_id) ON DELETE SET NULL,
    approved_at          TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE feedback (
    feedback_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    complaint_id    UUID NOT NULL REFERENCES complaints(complaint_id) ON DELETE CASCADE,
    field_corrected VARCHAR(32) NOT NULL,
    original_value  VARCHAR(64) NOT NULL,
    corrected_value VARCHAR(64) NOT NULL,
    corrected_by    UUID NOT NULL REFERENCES users(user_id),
    model_version   VARCHAR(32) NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_feedback_created ON feedback(created_at DESC);

CREATE TABLE audit_log (
    log_id      BIGSERIAL PRIMARY KEY,
    user_id     UUID REFERENCES users(user_id),
    action      VARCHAR(64) NOT NULL,
    entity_type VARCHAR(32) NOT NULL,
    entity_id   UUID,
    detail      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
```

## 3.2 Design Notes

**Why `predictions` is a separate table rather than columns on `complaints`.** Predictions carry a model version and may be regenerated when a new model is deployed. Keeping them separate means a re-run does not mutate the complaint record, and the 1:1 constraint can be relaxed to 1:N later for prediction history without a schema rewrite.

**Why `priority_breakdown` is JSONB.** [FR-16] requires displaying each factor's contribution. The factor set is configurable [FR-17], so a fixed column per factor would require migration on every weight change. Stored shape:

```json
{
  "sentiment_negativity":   {"raw": 0.91, "weight": 0.40, "contribution": 0.364},
  "category_severity":      {"raw": 0.70, "weight": 0.25, "contribution": 0.175},
  "urgency_keywords":       {"raw": 0.50, "weight": 0.20, "contribution": 0.100},
  "repeat_complaint":       {"raw": 1.00, "weight": 0.15, "contribution": 0.150}
}
```

**Why `text_hash`.** Supports both duplicate detection [FR-05] and LLM response caching [FR-24] with a single indexed lookup. SHA-256 of the normalised (lowercased, whitespace-collapsed) text.

**Why both `raw_text` and `redacted_text`.** [FR-06] and [NFR-12] require PII redaction before external transmission, but the agent must still see the original. Only `redacted_text` is ever passed to `llm_service`.

**pgvector fallback.** If installing the `vector` extension proves difficult, drop the `embedding` column and store embeddings in a FAISS index on disk, loaded by `retrieval_service`. Record whichever path you take in the report.

---

# 4. Backend Class Design

## 4.1 Service Layer Signatures

```python
# services/complaint_service.py

class ComplaintService:
    def __init__(self, repo: ComplaintRepository, redactor: RedactionService):
        self._repo = repo
        self._redactor = redactor

    def create(self, payload: ComplaintCreate) -> Complaint:
        """[FR-01..FR-06] Validate, redact, hash, dedupe, persist, enqueue.
        Returns immediately; analysis runs asynchronously."""

    def get(self, complaint_id: UUID) -> ComplaintDetail:
        """Returns complaint joined with prediction and generated content."""

    def list(self, filters: ComplaintFilters, page: Page) -> Paginated[ComplaintSummary]:
        """[FR-26] Filterable, sortable, paginated listing."""

    def update_status(self, complaint_id: UUID, new_status: Status,
                      actor: User) -> Complaint:
        """[FR-28, FR-30] Validates transition against state machine, writes audit."""

    def override_category(self, complaint_id: UUID, new_category: Category,
                          actor: User) -> None:
        """[FR-10, FR-41] Updates prediction and records a feedback row."""

    def approve_response(self, complaint_id: UUID, final_text: str,
                         actor: User) -> None:
        """[FR-22, FR-23] Stores final text, flags was_edited, writes audit."""
```

```python
# services/priority_service.py

@dataclass(frozen=True)
class PriorityWeights:
    sentiment: float = 0.40
    category:  float = 0.25
    urgency:   float = 0.20
    repeat:    float = 0.15

    def __post_init__(self):
        total = self.sentiment + self.category + self.urgency + self.repeat
        if abs(total - 1.0) > 1e-6:
            raise ConfigurationError(f"weights must sum to 1.0, got {total}")


class PriorityService:
    CATEGORY_SEVERITY = {
        Category.BILLING:         0.70,
        Category.TECHNICAL:       0.65,
        Category.PRODUCT_DEFECT:  0.80,
        Category.REFUND:          0.75,
        Category.DELIVERY:        0.50,
        Category.SERVICE_QUALITY: 0.45,
    }

    URGENCY_TERMS = frozenset({
        "urgent", "immediately", "asap", "emergency", "legal", "lawyer",
        "consumer court", "fraud", "unauthorised", "escalate", "third time",
    })

    def compute(self, text: str, category: Category,
                sentiment: SentimentResult,
                repeat_count: int) -> PriorityResult:
        """[FR-14, FR-15, FR-16] Returns score, bucket, and factor breakdown."""
```

```python
# services/llm_service.py

class LLMService:
    def __init__(self, client: LLMClient, cache: CacheBackend,
                 retriever: RetrievalService, prompt_version: str = "v1"):
        ...

    def summarise(self, redacted_text: str) -> str:
        """[FR-19] Two sentences, 60-word ceiling."""

    def suggest_resolution(self, redacted_text: str,
                           category: Category) -> ResolutionResult:
        """[FR-20] RAG-grounded. Returns text plus cited article IDs."""

    def draft_response(self, redacted_text: str, sentiment: SentimentLabel,
                       priority: PriorityBucket, resolution: str) -> str:
        """[FR-21] Tone selected from sentiment and priority."""

    def analyse(self, complaint: Complaint, prediction: Prediction) -> GeneratedContent:
        """Orchestrates all three above with a single cache lookup [FR-24]."""
```

## 4.2 Exception Hierarchy

```python
# core/exceptions.py

class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

class ValidationError(AppError):      status_code, code = 422, "validation_error"
class NotFoundError(AppError):        status_code, code = 404, "not_found"
class UnauthorisedError(AppError):    status_code, code = 401, "unauthorised"
class ForbiddenError(AppError):       status_code, code = 403, "forbidden"
class InvalidTransitionError(AppError): status_code, code = 409, "invalid_transition"
class ConfigurationError(AppError):   status_code, code = 500, "configuration_error"

class LLMUnavailableError(AppError):  status_code, code = 503, "llm_unavailable"
class ModelLoadError(AppError):       status_code, code = 503, "model_unavailable"
```

A single exception handler registered in `main.py` converts any `AppError` into the standard error envelope defined in Section 8.3. Unhandled exceptions are logged with the correlation ID and returned as a generic 500 — internal detail is never leaked to the client.

## 4.3 Repository Base

```python
# repositories/base.py

T = TypeVar("T")

class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: Session):
        self._s = session

    def get(self, pk: UUID) -> T | None:
        return self._s.get(self.model, pk)

    def add(self, entity: T) -> T:
        self._s.add(entity)
        self._s.flush()
        return entity

    def commit(self) -> None:
        self._s.commit()
```

All queries use SQLAlchemy's expression language. Raw string SQL is prohibited [NFR-13].

---

# 5. ML Subsystem Design

## 5.1 Preprocessing Pipeline

```python
# ml/src/preprocess.py

def normalise(text: str) -> str:
    """Deterministic, shared by training and inference.
    Any change here invalidates the trained model."""
    text = text.lower().strip()
    text = re.sub(r"x{2,}", " ", text)          # CFPB redaction markers
    text = re.sub(r"http\S+", " <url> ", text)
    text = re.sub(r"\d{6,}", " <num> ", text)
    text = re.sub(r"\s+", " ", text)
    return text
```

**Critical constraint.** This function must be imported by both the training script and `classifier_service`. Duplicating the logic causes train-serve skew, where the model sees differently-formatted text at inference than it did during training. This is the single most common silent failure in student ML projects.

## 5.2 Model Interface

```python
# services/classifier_service.py

class ClassifierService:
    """Singleton. Model is loaded once at process start, never per request."""

    _instance: "ClassifierService | None" = None

    def __init__(self, model_path: Path, version: str):
        self._tokenizer = AutoTokenizer.from_pretrained(model_path)
        self._model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self._model.eval()
        self._version = version
        self._labels = json.loads((model_path / "labels.json").read_text())

    @torch.inference_mode()
    def predict(self, text: str) -> ClassificationResult:
        start = time.perf_counter()
        enc = self._tokenizer(normalise(text), truncation=True,
                              max_length=256, return_tensors="pt")
        logits = self._model(**enc).logits
        probs = torch.softmax(logits, dim=-1)[0]
        idx = int(probs.argmax())
        return ClassificationResult(
            category=self._labels[idx],
            confidence=float(probs[idx]),
            needs_review=float(probs[idx]) < settings.CONFIDENCE_THRESHOLD,  # [FR-09]
            model_version=self._version,
            inference_ms=int((time.perf_counter() - start) * 1000),
        )
```

**Why `max_length=256`.** Empirically covers the 95th percentile of complaint length in the CFPB corpus while keeping CPU inference under the 200ms target [NFR-01]. Raising it to 512 roughly doubles latency.

**Why singleton.** Loading a DistilBERT checkpoint takes 2–4 seconds. Loading per request would breach NFR-01 by an order of magnitude.

## 5.3 Training Configuration

```python
# ml/src/train_transformer.py

CONFIG = {
    "base_model":      "distilbert-base-uncased",
    "max_length":      256,
    "batch_size":      32,
    "learning_rate":   2e-5,
    "epochs":          4,
    "warmup_ratio":    0.1,
    "weight_decay":    0.01,
    "seed":            42,
    "early_stopping_patience": 2,
    "metric_for_best_model":   "eval_macro_f1",
}
```

Class imbalance is handled with weights computed as `n_samples / (n_classes * class_count)`, passed to a weighted `CrossEntropyLoss` [DR-04].

## 5.4 Model Registry

```python
# ml/src/registry.py

class ModelRegistry:
    """Filesystem-backed. Each version is a directory containing
    model weights, tokenizer, labels.json, and metrics.json."""

    def register(self, path: Path, metrics: dict) -> str:
        version = f"v{datetime.utcnow():%Y%m%d-%H%M%S}"
        ...

    def load_active(self) -> tuple[Path, str]:
        """Reads models/ACTIVE containing the active version string."""
```

Promotion to active is a manual step: verify metrics meet NFR-26 through NFR-28, then write the version string to `models/ACTIVE`. No automatic promotion — a model that fails the recall floor must never reach production.

---

# 6. LLM Subsystem Design

## 6.1 Prompt Templates

Prompts are files, not string literals [NFR-22]. Filename encodes version.

**`prompts/summarise_v1.txt`**

```
You are summarising a customer complaint for a support agent.

Rules:
- Exactly two sentences. Maximum 60 words total.
- Neutral, factual tone. Do not apologise or editorialise.
- State the core issue and any concrete detail (dates, amounts, order numbers).
- Do not invent facts not present in the complaint.

Return JSON only, no markdown fences:
{"summary": "<your two sentences>"}

Complaint:
---
{complaint_text}
---
```

**`prompts/suggest_resolution_v1.txt`**

```
You are advising a support agent on how to resolve a complaint.
You may only propose steps supported by the reference articles below.

Rules:
- Three to five numbered steps, each one sentence.
- If the articles do not cover the issue, say so and set "grounded": false.
- Cite the article IDs you relied on.

Return JSON only, no markdown fences:
{"steps": ["..."], "cited_article_ids": ["..."], "grounded": true}

Reference articles:
---
{retrieved_articles}
---

Complaint (category: {category}):
---
{complaint_text}
---
```

**`prompts/draft_response_v1.txt`**

```
Draft a reply from a support agent to a customer.

Tone: {tone}
Rules:
- 80 to 150 words.
- Acknowledge the specific issue. Do not use generic filler.
- State what will happen next and by when, based only on the resolution steps.
- Never promise refunds, compensation, or timelines not present in the steps.
- Sign off as "Customer Support Team". Do not invent an agent name.

Return JSON only, no markdown fences:
{"response": "<your draft>"}

Resolution steps:
{resolution_steps}

Original complaint:
---
{complaint_text}
---
```

## 6.2 Tone Selection Matrix

[FR-21] requires tone matched to sentiment and priority.

| Sentiment | Priority | Tone token |
|---|---|---|
| Negative | P0 | `urgent and apologetic` |
| Negative | P1 | `apologetic and reassuring` |
| Negative | P2, P3 | `empathetic and practical` |
| Neutral | any | `professional and direct` |
| Positive | any | `appreciative and helpful` |

## 6.3 Caching Design

```python
CACHE_KEY = f"llm:{prompt_version}:{text_hash}"
CACHE_TTL = 60 * 60 * 24 * 7   # 7 days
```

Key includes `prompt_version` so that editing a prompt invalidates all prior cached results automatically [FR-24]. Without that, a prompt change would silently serve stale output — a bug that is very hard to notice during a demo.

## 6.4 Structured Output Handling

```python
def _parse(raw: str) -> dict:
    """LLMs occasionally wrap JSON in markdown fences despite instructions."""
    cleaned = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError as exc:
        raise LLMUnavailableError(f"unparseable LLM response: {exc}") from exc
```

Where the provider supports native structured output or function calling, use it in preference to this parser and keep the parser as a fallback.

---

# 7. Asynchronous Processing Design

## 7.1 Task Definitions

```python
# workers/tasks.py

@celery_app.task(
    bind=True,
    max_retries=3,
    autoretry_for=(LLMUnavailableError, ConnectionError),
    retry_backoff=True,          # 1s, 2s, 4s  [NFR-08]
    retry_jitter=True,
    acks_late=True,              # requeue if worker dies  [NFR-09]
    time_limit=60,
    soft_time_limit=45,
)
def analyse_complaint(self, complaint_id: str) -> None:
    """Full analysis pipeline for one complaint."""
    with session_scope() as db:
        complaint = ComplaintRepository(db).get(UUID(complaint_id))
        if complaint is None:
            return
        complaint.analysis_status = AnalysisStatus.PROCESSING
        db.commit()

    try:
        prediction = run_ml_stage(complaint)      # fast, always attempted
        persist(prediction)
        content = run_llm_stage(complaint, prediction)   # may fail
        persist(content)
        mark_completed(complaint_id)
    except SoftTimeLimitExceeded:
        mark_failed(complaint_id, reason="timeout")
        raise
```

## 7.2 Stage Isolation

The ML stage and the LLM stage are separated deliberately [NFR-07]. If the LLM provider is unreachable, classification, sentiment, and priority still complete and the complaint remains fully triageable — only the generated text is missing, replaced by a template [FR-25].

```
enqueue → ML stage ──✓──→ LLM stage ──✓──→ completed
             │                 │
             ✗                 ✗
             ▼                 ▼
          failed        completed_partial
                        (template response,
                         flagged for manual handling)
```

## 7.3 Queue Configuration

```python
# workers/celery_app.py

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,     # long tasks: fair distribution
    task_acks_late=True,
    broker_transport_options={"visibility_timeout": 120},
    task_routes={
        "tasks.analyse_complaint": {"queue": "analysis"},
        "tasks.recompute_hotspots": {"queue": "periodic"},
    },
)

celery_app.conf.beat_schedule = {
    "hotspot-scan": {
        "task": "tasks.recompute_hotspots",
        "schedule": crontab(minute="*/15"),
    },
}
```

`worker_prefetch_multiplier=1` matters here: with the default of 4, one worker grabs four LLM tasks and holds them while others idle, which is exactly wrong for long-running heterogeneous work.

---

# 8. API Contract Specification

## 8.1 Create Complaint

`POST /api/v1/complaints`

**Request**
```json
{
  "text": "I was charged twice for order 88421 on 12 August and support has not replied in 5 days.",
  "customer_ref": "CUST-1029",
  "channel": "web"
}
```

**Response — 201**
```json
{
  "complaint_id": "3f1a...",
  "status": "new",
  "analysis_status": "pending",
  "submitted_at": "2026-09-03T10:14:22Z",
  "duplicate_of": null
}
```

## 8.2 Get Complaint Detail

`GET /api/v1/complaints/{id}` — **Response 200**

```json
{
  "complaint_id": "3f1a...",
  "raw_text": "...",
  "status": "new",
  "analysis_status": "completed",
  "submitted_at": "2026-09-03T10:14:22Z",
  "assigned_to": null,
  "prediction": {
    "category": "billing",
    "category_confidence": 0.912,
    "sentiment_label": "negative",
    "sentiment_score": 0.874,
    "priority_score": 0.789,
    "priority_bucket": "P1",
    "needs_review": false,
    "priority_breakdown": {
      "sentiment_negativity": {"raw": 0.874, "weight": 0.40, "contribution": 0.350},
      "category_severity":    {"raw": 0.700, "weight": 0.25, "contribution": 0.175},
      "urgency_keywords":     {"raw": 0.500, "weight": 0.20, "contribution": 0.100},
      "repeat_complaint":     {"raw": 1.000, "weight": 0.15, "contribution": 0.150}
    },
    "model_version": "v20260903-101422",
    "inference_ms": 143
  },
  "generated": {
    "summary": "The customer was charged twice for order 88421 on 12 August. They report no response from support after five days.",
    "suggested_resolution": "1. Verify the duplicate charge...",
    "draft_response": "Thank you for writing in...",
    "cited_article_ids": ["a1b2...", "c3d4..."],
    "prompt_version": "v1",
    "was_edited": false,
    "approved_at": null
  }
}
```

When `analysis_status` is `pending` or `processing`, `prediction` and `generated` are `null`. The frontend polls on this field.

## 8.3 Error Envelope

Every error response, without exception:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Complaint text must be between 20 and 5000 characters.",
    "details": [{"field": "text", "issue": "too_short", "value_length": 8}],
    "correlation_id": "req_7f3c1a90"
  }
}
```

`correlation_id` appears in the response and in every log line for that request [NFR-23], so a user-reported failure can be traced end to end.

## 8.4 Pagination

All list endpoints accept `?page=1&size=25` and return:

```json
{
  "items": [ ... ],
  "page": 1,
  "size": 25,
  "total": 1284,
  "pages": 52
}
```

---

# 9. Frontend Component Design

## 9.1 Component Contracts

| Component | Props | Responsibility |
|---|---|---|
| `ComplaintTable` | `items, sort, onSort, selected, onSelect` | Dense listing. Pure presentational. |
| `FilterPanel` | `value, onChange` | Controlled filter state. Emits filter object only. |
| `PriorityBadge` | `bucket` | Colour + label + shape [NFR-16] |
| `ConfidenceBar` | `value, threshold` | Bar with threshold marker, review flag below it |
| `AIField` | `label, children, isLoading` | Marks machine-generated content [NFR-17] |
| `PriorityBreakdown` | `breakdown` | Stacked bar of factor contributions [FR-16] |
| `ResponseEditor` | `draft, onApprove, onReject, onRegenerate` | Tracks dirty state to set `was_edited` |
| `AnalysisPending` | — | Skeleton shown while `analysis_status !== 'completed'` |

## 9.2 State Ownership

- **Server state** — TanStack Query. Complaints, analytics, model metrics. Never mirrored into `useState`.
- **URL state** — filters, sort, page. Stored in query params so a filtered view is shareable and survives refresh.
- **Local state** — form drafts, modal open/closed, row selection.
- **Global state** — authenticated user only, via context.

No Redux. At this scale it is overhead without benefit, and you should be able to say why when asked.

## 9.3 Polling Contract

```javascript
useQuery({
  queryKey: ['complaint', id],
  queryFn: () => api.getComplaint(id),
  refetchInterval: (query) =>
    query.state.data?.analysis_status === 'completed' ? false : 2000,
});
```

Polling stops automatically once analysis completes. Interval is 2s, matching the 5s LLM target in NFR-02 with headroom.

---

# 10. Sequence Flows

## 10.1 Complaint Submission and Analysis

```
Client      API          DB        Queue      Worker      ML       LLM
  │          │            │          │          │          │        │
  ├─ POST ──▶│            │          │          │          │        │
  │          ├─ validate  │          │          │          │        │
  │          ├─ redact    │          │          │          │        │
  │          ├─ hash      │          │          │          │        │
  │          ├─ dedupe ──▶│          │          │          │        │
  │          │◀───────────┤          │          │          │        │
  │          ├─ insert ──▶│          │          │          │        │
  │          ├─ enqueue ─────────────▶│         │          │        │
  │◀─ 201 ───┤            │          │          │          │        │
  │          │            │          ├─ deliver▶│          │        │
  │          │            │          │          ├─ predict▶│        │
  │          │            │          │          │◀─────────┤        │
  │          │            │◀── save prediction ─┤          │        │
  │          │            │          │          ├─ retrieve articles │
  │          │            │          │          ├─ generate ────────▶│
  │          │            │          │          │◀───────────────────┤
  │          │            │◀── save content ────┤          │        │
  │          │            │◀── status=completed ┤          │        │
  │          │            │          │          │          │        │
  ├─ GET (poll) ─────────▶│          │          │          │        │
  │◀─ 200 full payload ───┤          │          │          │        │
```

## 10.2 Agent Override and Feedback Capture

```
Agent           API              Service            DB
  │              │                 │                │
  ├─ PATCH ─────▶│                 │                │
  │  category    ├─ authorise ────▶│                │
  │              │                 ├─ read current ▶│
  │              │                 │◀───────────────┤
  │              │                 ├─ update prediction ▶
  │              │                 ├─ insert feedback  ▶   [FR-41]
  │              │                 ├─ insert audit_log ▶   [FR-30]
  │              │                 ├─ commit (single txn) ▶
  │◀─ 200 ───────┤◀────────────────┤                │
```

All three writes occur in one transaction. A feedback row without its corresponding prediction update would corrupt the retraining dataset.

## 10.3 LLM Failure Path

```
Worker         LLM Provider        DB
  │                 │               │
  ├─ request ──────▶│               │
  │                 ╳ timeout       │
  ├─ retry 1 (1s) ─▶│               │
  │                 ╳               │
  ├─ retry 2 (2s) ─▶│               │
  │                 ╳               │
  ├─ retry 3 (4s) ─▶│               │
  │                 ╳               │
  ├─ build template response ──────▶│   [FR-25]
  ├─ analysis_status = completed ──▶│
  ├─ flag needs_manual_handling ───▶│
  │
  └─ log with correlation_id
```

The complaint remains fully usable — category, sentiment, and priority all came from the ML stage, which already succeeded.

---

# 11. Algorithms

## 11.1 Priority Scoring

```
Algorithm: ComputePriority
Input:  text T, category C, sentiment S, repeat count R, weights W
Output: score P ∈ [0,1], bucket B, breakdown D

1.  s_neg ← (S.label = negative) ? S.score : 0.0
2.  c_sev ← CATEGORY_SEVERITY[C]
3.  matched ← | { term ∈ URGENCY_TERMS : term ∈ lower(T) } |
4.  u_score ← min(matched / 3, 1.0)              // saturates at 3 terms
5.  r_flag  ← min(R / 2, 1.0)                    // saturates at 2 priors
6.  P ← W.sentiment·s_neg + W.category·c_sev
        + W.urgency·u_score + W.repeat·r_flag
7.  B ← P ≥ 0.80 → P0
        P ≥ 0.60 → P1
        P ≥ 0.35 → P2
        else     → P3
8.  D ← per-factor {raw, weight, contribution}
9.  return (P, B, D)
```

Time complexity O(|T|) dominated by the keyword scan. Every term is bounded to [0,1] and weights sum to 1, so P is guaranteed to lie in [0,1] — this is why the weight validation in `PriorityWeights.__post_init__` is not optional.

**Why a formula rather than a learned model.** Priority is a business policy, not a fact to be predicted. A manager must be able to change it [FR-17] and an agent must be able to see why a complaint is P0 [FR-16]. A regression model gives you neither. State this in your viva — it is a defensible engineering decision, not a shortcut.

## 11.2 Duplicate Detection

```
Algorithm: DetectDuplicate
Input:  normalised text T, customer reference K
Output: complaint_id of original, or NULL

1.  h ← SHA256(T)
2.  candidates ← SELECT complaint_id FROM complaints
                 WHERE text_hash = h AND customer_ref = K
                   AND submitted_at > now() - INTERVAL '24 hours'
                 ORDER BY submitted_at ASC LIMIT 1
3.  return candidates[0] if any else NULL
```

Exact-hash matching only. Near-duplicate detection via embedding similarity is explicitly out of scope — mention it as future work rather than attempting it.

## 11.3 Emerging Issue Detection

```
Algorithm: DetectHotspots                              [FR-34]
Input:  category set C, current date d
Output: set of flagged categories

1.  for each c ∈ C:
2.      recent  ← count(complaints in c, [d-7,  d])
3.      history ← daily counts of c over [d-37, d-7]
4.      μ ← mean(history) × 7
5.      σ ← stdev(history) × sqrt(7)
6.      if σ = 0: continue                    // no variance, skip
7.      z ← (recent − μ) / σ
8.      if z > 2.0: flag c with z-score
9.  return flagged
```

Runs every 15 minutes via Celery Beat and writes results to a cache key the dashboard reads. Computing this per dashboard request would breach NFR-03.

---

# 12. Error Handling and Fault Tolerance

## 12.1 Failure Matrix

| Failure | Detection | Response | Requirement |
|---|---|---|---|
| Invalid complaint text | Pydantic validator | 422 with field detail | FR-02 |
| Model file missing at startup | `ModelLoadError` on init | Container fails fast, does not serve traffic | NFR-06 |
| Classifier inference exception | try/except in task | Mark analysis failed, complaint still visible | NFR-07 |
| LLM timeout | Celery `autoretry_for` | 3 retries, then template fallback | NFR-08, FR-25 |
| LLM returns malformed JSON | Parse failure in `_parse` | Treated as LLM failure, same retry path | FR-25 |
| Worker process killed | `acks_late` | Task redelivered to another worker | NFR-09 |
| Database connection lost | SQLAlchemy pool | Request fails 503, pool recycles | — |
| Invalid status transition | State machine check | 409 `invalid_transition` | FR-28 |
| Expired token | JWT decode failure | 401, frontend redirects to login | FR-40 |

## 12.2 Logging Contract

Every log line is a single JSON object:

```json
{
  "ts": "2026-09-03T10:14:22.481Z",
  "level": "info",
  "correlation_id": "req_7f3c1a90",
  "complaint_id": "3f1a...",
  "stage": "ml_inference",
  "event": "classification_complete",
  "category": "billing",
  "confidence": 0.912,
  "duration_ms": 143
}
```

`raw_text` is never logged [DR-08]. Log `complaint_id` and look the text up in the database if needed.

---

# 13. Configuration and Environment

```python
# core/config.py

class Settings(BaseSettings):
    DATABASE_URL: PostgresDsn
    REDIS_URL: RedisDsn

    JWT_SECRET: SecretStr
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 480

    MODEL_DIR: Path = Path("/models")
    CONFIDENCE_THRESHOLD: float = 0.75          # [FR-09]

    LLM_API_KEY: SecretStr
    LLM_MODEL: str
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_CACHE_TTL_SECONDS: int = 604800
    PROMPT_VERSION: str = "v1"

    PRIORITY_W_SENTIMENT: float = 0.40
    PRIORITY_W_CATEGORY:  float = 0.25
    PRIORITY_W_URGENCY:   float = 0.20
    PRIORITY_W_REPEAT:    float = 0.15

    model_config = SettingsConfigDict(env_file=".env")
```

`.env` is gitignored. `.env.example` with dummy values is committed [NFR-14].

---

# 14. Testing Design

## 14.1 Test Layout

```
backend/tests/
├── unit/
│   ├── test_priority_service.py     # pure logic, no DB
│   ├── test_redaction_service.py
│   ├── test_state_machine.py
│   └── test_llm_parser.py
├── integration/
│   ├── test_complaint_api.py        # TestClient + test DB
│   ├── test_auth.py
│   └── test_analytics.py
└── conftest.py                      # fixtures: db_session, client, auth_headers
```

## 14.2 Representative Cases

| Test ID | Target | Assertion |
|---|---|---|
| TC-02 | Text length validation | 19 chars → 422; 20 chars → 201 |
| TC-05 | Duplicate detection | Same text + customer within 24h → `duplicate_of` set |
| TC-06 | PII redaction | Email, phone, and 12-digit number absent from `redacted_text` |
| TC-09 | Confidence routing | Confidence 0.74 → `needs_review=true`; 0.76 → false |
| TC-14 | Priority determinism | Fixed inputs always produce identical score |
| TC-14b | Priority bounds | Randomised inputs always yield score in [0,1] |
| TC-15 | Bucket boundaries | 0.799→P1, 0.800→P0, 0.349→P3, 0.350→P2 |
| TC-25 | LLM failure fallback | Mocked provider raising → template response, status completed |
| TC-28 | Invalid transition | `resolved` → `new` returns 409 |
| TC-M01 | Model quality gate | Held-out macro-F1 ≥ 0.75, no class recall < 0.60 |

External services are mocked in all tests. No test may call a real LLM endpoint — it makes the suite non-deterministic and burns quota.

---

# 15. Deployment Design

## 15.1 Compose Topology

```yaml
services:
  db:      { image: pgvector/pgvector:pg16, volumes: [pgdata:/var/lib/postgresql/data] }
  redis:   { image: redis:7-alpine }
  api:     { build: ./backend, depends_on: [db, redis], ports: ["8000:8000"] }
  worker:  { build: ./backend, command: celery -A app.workers.celery_app worker -Q analysis -c 2 }
  beat:    { build: ./backend, command: celery -A app.workers.celery_app beat }
  frontend:{ build: ./frontend, ports: ["5173:80"], depends_on: [api] }
```

`api` and `worker` share one image. Same code, different entrypoint — this guarantees the worker runs identical model and service code to the API.

## 15.2 Startup Order

1. `db` and `redis` reach healthy state
2. `api` runs Alembic migrations, then loads the active model, then serves
3. `worker` loads the active model, then consumes the queue
4. `frontend` serves the built bundle

Migrations run only from `api`, never from `worker`, to avoid two processes racing on the same migration.

## 15.3 Health Check

```python
@router.get("/health")
def health():
    return {
        "status": "ok",
        "model_version": classifier.version,
        "db": check_db(),
        "queue_depth": get_queue_depth(),
    }
```

---

**End of Document**

*This LLD is versioned alongside the SRS. Any design change that alters a class signature, database column, or API contract requires an update here and a note in the revision history.*
