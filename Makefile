.PHONY: up down logs test fmt seed shell migrate migration db-reset seed-history seed-history-clear

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

test:
	docker compose run --rm api pytest -v

seed:
	docker compose run --rm api python -m app.seed

# ~3 months of synthetic complaints for the analytics charts. No LLM calls.
seed-history:
	docker compose run --rm api python -m app.seed_history

seed-history-clear:
	docker compose run --rm api python -m app.seed_history --clear

shell:
	docker compose exec api bash

# ---- Database migrations (Alembic) -------------------------------------------

# Apply all pending migrations.
migrate:
	docker compose run --rm api alembic upgrade head

# Create a migration after changing a model: make migration m="add users.last_login"
migration:
	docker compose run --rm api alembic revision --autogenerate -m "$(m)"

# Wipe the database volume and rebuild from migrations + seed data.
db-reset:
	docker compose down -v
	docker compose up -d db redis
	docker compose run --rm api alembic upgrade head
	docker compose run --rm api python -m app.seed
