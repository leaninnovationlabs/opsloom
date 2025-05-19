[andrew@localhost opsloom]$ cat AGENTS.md 
## environment

we use Astral's uv. You may not change the Python version in the pyproject.toml. All tests ar run with 'uv run pytest ... (whatever arg)'. Use 'uv' and 'uv run', etc for running all Python related commands. We use alembic for migrations. Alembic is also run with Astral's uv. 

On the tests we prefer to use a small Postgres container and run the migration on it before running unit tests. The 'make test' target should handle the setup and teardown of this. 

Right now we have unit tests for the repository and service layers. We need more tests for the modules that remain untested. 

Don't touch the UI for now. 
