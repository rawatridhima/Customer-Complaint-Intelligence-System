.PHONY: up down logs test fmt seed shell

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

shell:
	docker compose exec api bash
