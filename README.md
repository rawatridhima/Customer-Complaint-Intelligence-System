# Customer Complaint Intelligence System

Minor project, B.Tech. An AI system that classifies, prioritises, and drafts responses to customer complaints, with a dashboard for support teams.

**This is the skeleton build.** Intake, storage, priority scoring, and the dashboard work end to end. The ML and LLM stages are stubbed behind fixed interfaces so they can be swapped in without touching anything else.

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

Load sample complaints:

```bash
make seed
```

Run the tests:

```bash
cd backend && python -m pytest tests/unit -v
```

The unit tests need no database and no Docker. That is deliberate — if a unit test requires infrastructure, it is an integration test.

---

## What works today

| Piece | State |
|---|---|
| Complaint intake, validation, PII redaction | Working |
| Duplicate detection (hash + customer + 24h) | Working |
| Async dispatch to Celery worker | Working |
| Priority scoring with explainable breakdown | Working |
| Complaint list and detail API | Working |
| React dashboard with polling | Working |
| Category classification | **Stub** — keyword rules, `ClassifierService` |
| Sentiment analysis | **Stub** — keyword rules, `SentimentService` |
| Summary, suggested resolution, draft response | **Not built** — week 7 |
| Auth and RBAC | **Not built** — week 6 |
| Analytics dashboard | **Not built** — week 8 |

The stubs return the same shape as the real thing. Replacing `ClassifierService.predict()` with a DistilBERT call changes one file.

---

## Layout

```
backend/app/
  core/          config, database, security, logging, exceptions
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

Do not start the LLM layer until the classifier baseline is measurable.

---

## Documents

- `docs/SRS.md` — Software Requirements Specification
- `docs/LLD.md` — Low Level Design

Both are living documents. If you change an API contract, a database column, or a class signature, update the LLD in the same PR.
