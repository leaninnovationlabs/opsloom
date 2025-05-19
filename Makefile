.PHONY: test

test:
	uv run --system -m pytest -q
