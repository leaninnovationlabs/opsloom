[andrew@localhost opsloom]$ cat AGENTS.md 
## environment

we use Astral's uv. You may not change the Python version in the pyproject.toml. All tests ar run with 'uv run pytest ... (whatever arg)'. Use 'uv' and 'uv run', etc for running all Python related commands. We use alembic for migrations. Alembic is also run with Astral's uv. We use Pydantic and SQLAlchemy. Pydantic is all you need. Please don't add bloatware like langchain. Make sure whatever you do works with Python 3.12+

This is an application which allows users to easily configure AI assistants using RAG, agents, or just system prompts. It takes a config driven approach. 

On the tests we prefer to use a small Postgres container and run the migration on it before running unit tests. The 'make test' target should handle the setup and teardown of this. 

Right now we have unit tests for the repository and service layers. We need more tests for the modules that remain untested. 

Tests should follow the arrange, act, assert pattern. Tests should be idempotent. Assertions must be meaningful or else the test is worthless.

Don't touch the UI for now. 
