ROOT := $(shell git rev-parse --show-toplevel)

.phony: uncache
uncache:
	clear_cache

.phony: env
env:
	poetry install

.phony: lint
lint:
	poetry run ruff check
	poetry run ruff format --check

.phony: fmt
fmt:
	poetry run ruff check --fix
	poetry run ruff format

.phony: clean
clean:
	find . -type d \( -name "__pycache__" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +
