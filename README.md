# Customer Complaint Intelligence System

Minor project, B.Tech. An AI system that classifies, prioritises, and drafts responses to customer complaints, with a dashboard for support teams.

Intake, storage, classification, sentiment, priority scoring, AI-drafted replies and the dashboard work end to end. Without an LLM configured, every complaint gets a template reply flagged for manual handling. The ML services fall back to rule-based stubs when the model files are absent, so the application runs without them.

---

## Run it

You need Docker. Nothing else. Windows, macOS, and Linux all work.

```bash
cp .env.example .env      # edit JWT_SECRET before doing anything real
docker compose up --build
```

Then:

- Dashboard — http://localhost:5173
- API docs — http://localhost:8000/docs
- Health — http://localhost:8000/health

The API container applies database migrations on every start, so a fresh
clone needs nothing extra. Load sample complaints:

```bash
make seed
```

Sign in at http://localhost:5173 with one of the demo accounts the seed creates:

| Username | Password | Role | Can |
|---|---|---|---|
| `agent` | `agent-demo-pass` | Agent | work complaints, give feedback, approve drafts |
| `manager` | `manager-demo-pass` | Manager | everything an agent can, plus audit logs and knowledge articles |
| `admin` | `admin-demo-pass` | Admin | everything, plus user management |

These are for local use only. On a real deployment, skip the seed and create
the first administrator with `docker compose run --rm api python -m app.create_user --username <name> --email <email> --role admin`.

**Upgrading an existing local database.** If your database volume was created
before migrations existed (by the old `create_all` startup), the first
migration will fail with "relation already exists". It is only seed data, so
reset it:

```bash
make db-reset      # wipes the volume, runs migrations, reseeds
```

Run the tests:

```bash
make test          # everything, inside Docker (needs `docker compose up` running)
make coverage      # the same, with a coverage report; fails under 70%
make test-unit     # unit tests only, no database or Docker needed
```

The unit tests need no database and no Docker. That is deliberate — if a unit test requires infrastructure, it is an integration test.

Integration tests run against a **separate database, `cis_test`**, created
automatically next to your `cis` database. They create complaints and drop
every table while checking migrations, so they never touch your development
data. Set `TEST_DATABASE_URL` to use a different one.

`tests/integration/test_end_to_end.py` follows one complaint through the whole
system (submit, classify, AI reply, category correction, approval, resolution,
analytics, export). It is the demo in test form.

GitHub Actions runs the full suite against Postgres + pgvector and Redis on
every pull request and push to `main`, fails under 70% coverage (NFR-19), and
builds the frontend. See `.github/workflows/ci.yml`.

---

## Database migrations

The schema is managed by [Alembic](https://alembic.sqlalchemy.org/). Tables are
never created from the models at runtime.

| Task | Command |
|---|---|
| Apply pending migrations | `make migrate` |
| After changing a model | `make migration m="add users.last_login"` |
| Start over with a clean database | `make db-reset` |

After `make migration`, open the new file in `backend/migrations/versions/`
and read it before committing. Autogenerate misses some changes (renames look
like drop + add, and new enum values need `ALTER TYPE ... ADD VALUE`). A model
change and its migration go in the same PR. The integration test
`test_models_match_migrations` fails if they drift apart.

---

## Authentication and roles

`POST /api/v1/auth/login` takes a username and password and returns a signed
JWT (FR-37). Every other route needs `Authorization: Bearer <token>`, except
`POST /api/v1/complaints`, which stays public because customers submit
complaints without an account. In `/docs`, use the **Authorize** button to sign
in once for all requests.

- Tokens expire after `JWT_EXPIRY_MINUTES` (default 480); the dashboard then
  returns to the login page (FR-40).
- The user's role and active flag are re-read from the database on every
  request, so deactivating an account or changing a role takes effect
  immediately, not when the token expires.
- Who did something (`corrected_by`, `approved_by`, audit `actor_id`) is taken
  from the token, never from the request body.
- Role checks live in `api/v1/deps.py` (`StaffUser`, `ManagerUser`,
  `AdminUser`). The dashboard hides what a role cannot use, but the API is what
  enforces it (FR-38, FR-39).

---

## Working a complaint

| Action | Where | API |
|---|---|---|
| Filter by status, category, priority, sentiment, assignee, date; sort by priority | Inbox | `GET /complaints?…&sort=priority` |
| Change status (only moves the state machine allows) | Detail page | `PATCH /complaints/{id}` |
| Change status of many at once | Inbox checkboxes | `PATCH /complaints/bulk-status` |
| Correct a wrong category | Detail page | `PATCH /complaints/{id}/category` |
| Assign to yourself | Detail page | `PATCH /complaints/{id}/assignee` |
| See who did what | Detail page, History | `GET /complaints/{id}/history` |

Correcting a category (FR-10) keeps the model's original answer, records who
changed it and when, recalculates priority (category severity is one of its
factors), and saves the correction as a training example (FR-41).

Bulk updates check each complaint on its own: if one in the selection is
already resolved, it is reported back as failed and the rest still update.

Every status change, category correction, assignment and approval is written
to the audit log with the user who did it (FR-30).

A red banner appears at the top of every page when a new P0 complaint arrives
(FR-18). Dismissing it hides the current ones; the next P0 brings it back.

---

## AI-drafted replies (LLM stage)

After a complaint is classified, the worker asks an LLM for three things:

- a **summary** of at most two sentences and 60 words (FR-19)
- a **suggested resolution**, grounded in the knowledge base articles for the
  complaint's category, with the articles it used listed underneath (FR-20)
- a **draft reply** in a tone picked from sentiment and priority: *urgent* for
  P0, *empathetic* for negative, *professional* otherwise (FR-21)

The agent can edit the reply, regenerate it in another tone, and approve it.
Nothing counts as sent until it is approved, and approval locks it (FR-22).
The generated draft is kept next to the edited version (FR-23).

### Setting up a provider

Set these in `.env`, then `docker compose up`. Any one of:

| Provider | Settings |
|---|---|
| Claude | `LLM_PROVIDER=anthropic` `LLM_MODEL=claude-haiku-4-5` `LLM_API_KEY=...` |
| Gemini (free tier) | `LLM_PROVIDER=openai` `LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai` `LLM_MODEL=<model id>` `LLM_API_KEY=...` |
| Groq (free tier) | `LLM_PROVIDER=openai` `LLM_BASE_URL=https://api.groq.com/openai/v1` `LLM_MODEL=<model id>` `LLM_API_KEY=...` |
| Ollama (local, free) | `LLM_PROVIDER=openai` `LLM_BASE_URL=http://host.docker.internal:11434/v1` `LLM_MODEL=llama3.2` `LLM_API_KEY=ollama` |

Leave `LLM_PROVIDER` empty to run without an LLM.

### When the LLM is not available

- A failed call (timeout, error, unusable reply) is retried 3 times with
  backoff: 10s, 20s, 40s (NFR-08).
- After the last retry, or immediately if no provider is configured, the
  complaint gets the template reply from `prompts/fallback_v2.txt`, marked
  **handle manually** with the reason (FR-25). Agents can press *Try the AI
  again* later.
- Classification, priority and the dashboard keep working throughout (NFR-07).

### Details worth knowing

- **Privacy.** Only the redacted text is sent: emails, phone numbers and
  card/account numbers are replaced first (FR-06, C-03).
- **Prompt injection.** The system prompt tells the model the complaint is data
  and never to follow instructions inside it.
- **Invented citations are dropped.** The model can only cite the `KB-n` labels
  it was given; anything else is discarded.
- **Cache.** Identical complaint text reuses earlier content with no new LLM
  call (FR-24). The dashboard shows "reused from an identical complaint".
- **Prompts are versioned files** in `backend/app/prompts/` (NFR-22). To change
  a prompt, add `*_v3.txt` files and set `PROMPT_VERSION=v3`; stored content
  records the version that produced it.
- **Knowledge base.** `make seed` adds 12 sample procedure articles, two per
  category (`backend/app/knowledge_base.py`). Managers can add more through
  `POST /api/v1/knowledge-articles`.

---

## Deploying

`docker-compose.prod.yml` runs the whole system behind one web server (Caddy)
on ports 80/443, with automatic HTTPS when given a domain name, secrets checked
at startup, and automatic restarts. It works on a cloud server or on a laptop.
Step-by-step guide, including a free cloud server: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

```bash
make prod-up            # build and start in production mode
make prod-ps            # status
make prod-backup        # database backup to ./backups
```

**Before a demo**, generate AI replies ahead of time so nothing depends on the
LLM being available on the day: `make pregenerate n=10` (or `make
prod-pregenerate`).

**Resilience.** Submitting a complaint answers in well under a second even if
Redis is down; the complaint is saved, and the worker re-queues anything left
unanalysed when it starts.

---

## Analytics and manager tools

Managers and admins get three extra pages; agents do not see them, and the
API refuses them (403).

**Analytics** (`/analytics`)
- KPIs for any date range: volume, still open, average time to resolve, P0,
  escalated (FR-31)
- daily volume stacked by category (FR-32), sentiment and priority mix (FR-33)
- **emerging issues** (FR-34): a category is flagged when its last 7 days are
  more than two standard deviations above its normal week, measured over every
  7-day window in the 30 days before. At least 5 complaints are needed, so a
  quiet category going from 0 to 2 is not an alert.

**Model health** (`/analytics/model`)
- live: share of predictions below the 0.95 threshold (FR-36), how often agents
  corrected the category and to what, confidence distribution (FR-35), model
  versions in use (FR-43)
- AI replies: generated, template fallbacks, cache reuse, tokens, approvals
- held-out test set: per-category precision, recall and F1, confusion matrix
  and confidence distribution (FR-35). Generate these once from `ml/src`:
  ```bash
  python evaluate_model.py --model-dir ../models/distilbert-v1-512 --data-dir ../data
  ```
  It reuses the test predictions you already have, so no GPU is needed.

**Settings** (`/settings`)
- priority weights (FR-17): change the four factor weights without a
  redeploy; they must add up to 1. Optionally re-score every open complaint.
  Changes are audited, and *Reset to defaults* returns to the `.env` values.
- `feedback.csv` (FR-42): every category correction with the redacted text, the
  predicted and the corrected label, ready for retraining.

**Users** (`/users`, admins only): add accounts, change roles, deactivate.

### Demo data for the charts

`make seed` adds a handful of complaints, all from today. For three months of
history:

```bash
make seed-history          # ~600 synthetic complaints over 90 days
make seed-history-clear    # remove them again
```

They are marked `DEMO-` / channel `demo`, include a debt-collection surge in
the last week (so an emerging issue shows), and never call the LLM.

### LLM rate limits

The worker sends at most `LLM_RATE_LIMIT` complaints a minute to the LLM
(default `5/m`, i.e. 10 requests), so a batch queues up instead of hitting the
provider's limit. On HTTP 429 it waits as long as the provider asks; if the
**daily** quota is used up it saves the template straight away instead of
retrying.

---

## What works today

| Piece | State |
|---|---|
| Complaint intake, validation, PII redaction | Working |
| Duplicate detection (hash + customer + 24h) | Working |
| Async dispatch to Celery worker | Working |
| Priority scoring with explainable breakdown | Working |
| Complaint list with filters, sorting and pagination | Working |
| Status changes, bulk status, category override, assignment | Working |
| Audit trail per complaint | Working |
| CI: unit, integration and end-to-end tests, 89% coverage | Working |
| Production deployment: Caddy + HTTPS, startup secret checks, backups | Working |
| Pre-generated AI replies for demos; recovery of unqueued complaints | Working |
| P0 alert banner | Working |
| React dashboard with polling | Working |
| Category classification | Working — DistilBERT, test macro-F1 0.866 |
| Sentiment analysis | Working — pretrained RoBERTa |
| Summary, grounded resolution with citations, draft reply (Claude or any OpenAI-compatible API) | Working |
| Edit, regenerate in another tone, approve | Working |
| LLM cache, retries and template fallback | Working |
| Database migrations (Alembic) | Working |
| Login, JWT auth and roles (agent, manager, admin) | Working |
| User management API (admin) | Working |
| Analytics: KPIs, volume, sentiment, emerging issues | Working |
| Model health: threshold share, corrections, test-set metrics | Working |
| Priority weights in the dashboard, feedback CSV export, user admin | Working |

The stubs return the same shape as the real thing. Replacing `ClassifierService.predict()` with a DistilBERT call changes one file.

---

## Layout

```
backend/app/
  core/          config, database, security, logging, exceptions
backend/migrations/  Alembic migrations (schema history)
  models/        SQLAlchemy tables
  schemas/       Pydantic request and response shapes
  repositories/  all database access
  services/      business logic
  workers/       Celery app and tasks
  api/v1/        routes
ml/src/          training and preprocessing
frontend/src/    React dashboard
docs/            SRS and LLD
```

**Layering rule, enforced in review:** API calls services, services call repositories, repositories touch models. Never skip a layer, never call upward. An API handler that imports a SQLAlchemy model is a rejected PR.

---

## Working agreement

Branch from `develop`, never commit to `main`.

```bash
git checkout develop && git pull
git checkout -b feature/short-description
# work, commit
git push -u origin feature/short-description
# open a PR, get one approval, merge, delete the branch
```

Commit messages: `type(scope): summary` — for example `feat(ml): add distilbert classifier`.

`main` is protected and requires one approving review. This is not bureaucracy; it is the record of who built what, and you will be asked.

---

## Ownership

| Area | Owner |
|---|---|
| `ml/`, classifier and sentiment services | Person A |
| `api/`, `services/`, `repositories/`, `workers/` | Person B |
| `frontend/` | Person C |
| Docker, CI, config, docs | Person D |

Every PR needs a reviewer who is not the author.

---

## Next steps

1. Everyone gets `docker compose up` working locally. Nobody moves past this.
2. Person A downloads the CFPB dataset and produces the EDA notebook.
3. Person A fills in `ml/src/train_baseline.py` and records the macro-F1.
4. Person B replaces `create_all` with Alembic migrations.
5. Person B adds auth and the feedback endpoint.
6. Person C builds the analytics page.
7. Person D adds integration tests to CI and gets a deployment running.


---

## Documents

- `docs/SRS.md` — Software Requirements Specification
- `docs/LLD.md` — Low Level Design

Both are living documents. If you change an API contract, a database column, or a class signature, update the LLD in the same PR.


## ML results

### Dataset

Consumer Financial Protection Bureau (CFPB) Consumer Complaint Database,
archived snapshot covering **May 2017 – May 2019**, filtered to records with a
non-empty consumer narrative (212,356 rows). The CFPB
[ceased publishing narratives on 14 August 2026](https://www.consumerfinance.gov/about-us/newsroom/the-cfpb-to-cease-discretionary-publication-of-complaint-narratives-and-visualizations/),
so this snapshot is frozen and cannot be refreshed from the official source.

After dropping short and duplicate texts, the corpus was balanced by
down-sampling to **10,000 complaints per category (60,000 total)** and split
70/15/15, stratified by category, with seed 42.

### Categories (label mapping v2)

CFPB covers financial products only, so the six placeholder categories in the
original design (billing, delivery, product defect, …) had no training data —
nothing in the corpus maps to *delivery* or *product defect*. The categories
were redefined around what the data actually contains, mapping from the CFPB
`Product` field, with the credit-reporting product split on `Issue`:

| Category | Built from |
|---|---|
| `credit_report_dispute` | Credit reporting, all issues except "Improper use of your report" |
| `report_misuse` | Credit reporting, issue = "Improper use of your report" |
| `debt_collection` | Debt collection |
| `cards_and_accounts` | Credit card or prepaid card; checking or savings; money transfer |
| `mortgage` | Mortgage |
| `consumer_loans` | Student loan; vehicle loan or lease; payday, title or personal loan |

The mapping lives in `ml/src/label_mapping.py` and is versioned. Changing it
invalidates every trained model.

### Classification

| Model | Val macro-F1 | Test macro-F1 |
|---|---|---|
| TF-IDF + Logistic Regression (baseline) | 0.848 | 0.849 |
| DistilBERT, max_length 256 | 0.857 | 0.859 |
| **DistilBERT, max_length 512 (shipped)** | **0.863** | **0.866** |

Hyperparameters: `distilbert-base-uncased`, lr 2e-5, batch 16, 4 epochs, 10%
warmup, weight decay 0.01, class-weighted cross-entropy, early stopping on
validation macro-F1. Trained on a Colab T4; see `ml/src/train_transformer.py`.

Per-class F1 on the test set: mortgage 0.944, cards_and_accounts 0.909,
report_misuse 0.889, consumer_loans 0.875, debt_collection 0.832,
credit_report_dispute 0.750.

**Why the gain over the baseline is modest.** Raising the input window from 256
to 512 tokens added only 0.007 macro-F1, and error analysis showed why: the
limit is label ambiguity, not truncation. The three credit-reporting categories
describe overlapping real-world situations — a collection account that appears
on a credit report can legitimately be filed under any of three products — and
those pairs account for over a third of all errors.

### Error analysis

50 high-confidence errors were tagged independently by the author and by an LLM
(Claude) as `label_wrong`, `ambiguous`, `truncated`, or `model_error`.
Agreement was 66% (Cohen's κ = 0.48, moderate); on the binary question of model
error vs not, 82%. All disagreements involved the `ambiguous` tag, mostly on
short complaints that never name a product. The author's tags were final.

| Reason | Count |
|---|---|
| `label_wrong` — the prediction is more correct than the CFPB label | 25 |
| `ambiguous` — genuinely fits both categories | 12 |
| `model_error` — clear case, model wrong | 12 |
| `truncated` — key detail past the 512-token window | 1 |

So 74% of these errors are not attributable to the model. Two caveats: the
sample was drawn from the *most confident* errors, which over-represents label
problems, and the largest confusion pair
(`credit_report_dispute` → `report_misuse`) does not appear in it.

A counter-intuitive finding: accuracy is *lowest* on short complaints (83.9%
under 100 words) and highest on long ones (89.1% over 200 words). Short
complaints often omit the product entirely — "my original loan was sold to a new
company who doubled my interest rate" could be any lending product. The
hypothesis that truncation was the main limitation was disproved.

### Confidence threshold (FR-09)

Swept on the validation set and confirmed on the held-out test set. Chosen
value **0.95**:

| | Validation | Test |
|---|---|---|
| Auto-labelled (coverage) | 79.0% | 78.5% |
| Accuracy on auto-labelled | 93.3% | 93.9% |
| Errors routed to human review | 61.0% | 63.8% |

At 0.95, roughly one complaint in five reaches a human, and that fifth contains
about 63% of the model's mistakes. Accuracy on the flagged subset is still
60.6%, so the prediction remains useful to the reviewer as a suggestion. The
model is overconfident — half of all wrong predictions still score above 0.90 —
which is why the operating point sits so high.

### Sentiment (FR-11, FR-12)

Pretrained `cardiffnlp/twitter-roberta-base-sentiment-latest`, not fine-tuned:
CFPB carries no sentiment labels. On a 500-complaint sample, 72% score negative
and 27% neutral, and the negative probability spreads widely (p10 0.17, median
0.71, p90 0.88). That spread — not the label — is what the priority engine
consumes as an intensity measure.

The input window was cut from 512 to **128 tokens** after measurement: p95
latency falls from 182 ms to 56 ms while the score correlates 0.987 with the
full-length score (mean absolute difference 0.025, label agreement 97.2%).
Category needs the long window because the product is often named late in a
complaint; emotional tone is clear in the opening sentences.

### Latency (NFR-01)

Single-complaint CPU inference, PyTorch limited to 2 threads, including
preprocessing and tokenisation:

| Stage | p50 | p95 |
|---|---|---|
| TF-IDF baseline | 0.4 ms | 0.9 ms |
| DistilBERT, 256 tokens | 30.1 ms | 44.3 ms |
| **DistilBERT, 512 tokens (shipped)** | **33.0 ms** | **88.4 ms** |
| **RoBERTa sentiment, 128 tokens** | **51.0 ms** | **55.7 ms** |
| Combined pipeline | ~84 ms | ~144 ms |

Measured on Apple Silicon; a cloud server CPU may be 1.5–2× slower, which would
still leave the combined p95 inside the 200 ms budget. Cold start is ~630 ms
versus ~50 ms warm, so both models are loaded and given a dummy inference at
Celery worker startup rather than inside the first task.

### Reproducing

```bash
cd ml && python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd src
python prepare_data.py --raw ../data/raw/complaints.csv --out ../data/processed.csv
python train_baseline.py --data ../data/processed.csv          # writes the splits
python train_transformer.py --data-dir ../data --max-length 512 --batch-size 16
python benchmark_latency.py --data ../data/test.csv
```

Model artifacts are not in Git — see `ml/models/README.md`. The backend falls
back to the rule-based stub when they are absent, so the application runs
without them.