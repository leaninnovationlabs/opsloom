.PHONY: dev backend frontend start-db stop-db migrate test

start-db:
	sh db/start_postgres.sh

stop-db:
	sh db/stop_postgres.sh

migrate: start-db
	uv run alembic upgrade head

backend: migrate
	uv run uvicorn server:app --reload --port 8080

frontend:
	cd frontend && npm install && npm run dev

dev: migrate
	uv run uvicorn server:app --reload --port 8080 &
	cd frontend && npm install && npm run dev

test: start-db
	uv run alembic upgrade head
	uv run pytest
	sh db/stop_postgres.sh
