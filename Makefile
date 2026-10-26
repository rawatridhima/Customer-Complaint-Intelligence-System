.PHONY: up down logs test test-unit coverage fmt seed shell pregenerate prod-up prod-down prod-logs prod-ps prod-seed prod-seed-history prod-admin prod-pregenerate prod-backup migrate migration db-reset seed-history seed-history-clear

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api worker

# All tests (unit + integration). Integration tests use their own database,
# cis_test, created automatically; your development data is never touched.
test:
	docker compose run --rm api pytest

# Fast: no database, no Docker needed (run from your own Python environment).
test-unit:
	cd backend && python -m pytest tests/unit

# All tests with a coverage report; fails under 70% (NFR-19), as CI does.
coverage:
	docker compose run --rm api pytest --cov=app --cov-report=term-missing:skip-covered --cov-fail-under=70

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

# Generate AI replies ahead of a demo: make pregenerate (or n=25)
n ?= 10
pregenerate:
	docker compose run --rm api python -m app.pregenerate -n $(n)

# ---- Production (docker-compose.prod.yml, see docs/DEPLOYMENT.md) ------------

PROD = docker compose -f docker-compose.prod.yml

prod-up:
	$(PROD) up -d --build
	@echo "Starting. Check with: make prod-ps   (all services should become healthy)"

prod-down:
	$(PROD) down

prod-logs:
	$(PROD) logs -f --tail 100 api worker web

prod-ps:
	$(PROD) ps

# Demo accounts with well-known passwords: only for a demo, see DEPLOYMENT.md.
prod-seed:
	$(PROD) exec api python -m app.seed

prod-seed-history:
	$(PROD) exec api python -m app.seed_history

# Create the first real administrator (asks for a password).
prod-admin:
	$(PROD) exec api python -m app.create_user --username $(user) --email $(email) --role admin

prod-pregenerate:
	$(PROD) exec api python -m app.pregenerate -n $(n)

# Database backup to ./backups (restore steps in DEPLOYMENT.md).
prod-backup:
	mkdir -p backups
	$(PROD) exec -T db pg_dump -U cis cis | gzip > backups/cis-$$(date +%Y%m%d-%H%M).sql.gz
	@ls -lh backups | tail -1
