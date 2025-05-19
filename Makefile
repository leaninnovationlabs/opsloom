.PHONY: dev backend frontend start-db stop-db migrate test

	PYTHONPATH := $(CURDIR)

start-db:
	sh db/start_postgres.sh

stop-db:
	sh db/stop_postgres.sh

migrate: start-db
	PYTHONPATH=$(PYTHONPATH) uv run alembic upgrade head

backend: migrate
	PYTHONPATH=$(PYTHONPATH) uv run uvicorn server:app --reload --port 8080

frontend:
	cd frontend && npm install && npm run dev

dev: migrate
	PYTHONPATH=$(PYTHONPATH) uv run uvicorn server:app --reload --port 8080 &
	cd frontend && npm install && npm run dev

test: start-db
	PYTHONPATH=$(PYTHONPATH) uv run alembic upgrade head
	PYTHONPATH=$(PYTHONPATH) uv run pytest -q
	sh db/stop_postgres.sh
