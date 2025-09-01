ROOT := $(shell git rev-parse --show-toplevel)

.phony: uncache
uncache:
	uv run clear_cache

.phony: env
env:
	uv sync

.phony: lint
lint:
	uv run ruff check
	uv run ruff format --check

.phony: fmt
fmt:
	uv run ruff check --fix
	uv run ruff format

.phony: clean
clean:
	find . -type d \( -name "__pycache__" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +

.phony: publish
publish:
	uv build
	uv publish
