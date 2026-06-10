ROOT := $(shell git rev-parse --show-toplevel)
PACKAGE_NAME := $(shell uv version | awk '{print $$1}' | sed 's/-/_/g')
VERSION := $(shell uv version --short)

.PHONY: env
env:
	uv sync --all-extras --all-groups

.PHONY: init
init:
	uv venv
	$(MAKE) env
	uv run prek install -t pre-commit -t commit-msg -t pre-push

.PHONY: update
update:
	uv lock --upgrade --prerelease=allow
	$(MAKE) env

.PHONY: uncache
uncache:
	uv run clear_cache

.PHONY: lint
lint:
	uv run ruff check
	uv run ruff format --check
	$(MAKE) lint-docs

.PHONY: lint-docs
lint-docs:
	uv run prek run numpydoc-validation --all-files --hook-stage pre-push

.PHONY: format
format:
	uv run ruff check --fix
	uv run ruff format

.PHONY: type
type:
	uv run ty check src/ tests/

.PHONY: test
test:
	uv run pytest -v

.PHONY: unittest
unittest:
	uv run pytest tests/ -v

.PHONY: doctest
doctest:
	uv run pytest --doctest-modules src/mayutils -v

.PHONY: coverage
coverage:
	uv run coverage run -m pytest tests/
	uv run coverage report

.PHONY: docs-serve
docs-serve:
	uv run --group docs mkdocs serve

.PHONY: docs-build
docs-build:
	uv run --group docs mkdocs build --strict

.PHONY: release
release:
	uv run cz bump
	git push origin main
	git push origin --tags

.PHONY: publish
publish:
	uv build
	uv publish

.PHONY: stubs
stubs:
	uv run --all-extras refresh_stubs

.PHONY: run
run:
	uv run main.py

.PHONY: cli
cli:
	uv run src/$(PACKAGE_NAME)/cli/main.py

.PHONY: app
app:
	uv run streamlit run src/$(PACKAGE_NAME)/app/main.py

.PHONY: dev
dev:
	uv run streamlit run src/$(PACKAGE_NAME)/app/main.py --server.runOnSave=true

.PHONY: containerise
containerise:
	podman build \
		--secret id=GITHUB_PAT_TOKEN,src=./.secrets/GITHUB_PAT_TOKEN.token \
		-t $(PACKAGE_NAME) \
		.

.PHONY: run_container
run_container:
	podman run -p 8501:8501 $(PACKAGE_NAME):latest

.PHONY: clean
clean: clean-build clean-pyc clean-test

.PHONY: clean-build
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	rm -fr site/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -type d \( -name "__pycache__" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +

.PHONY: clean-test
clean-test:
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
