ROOT := $(shell git rev-parse --show-toplevel)
MODULE_NAME := $(shell uv version | awk '{print $$1}' | sed 's/-/_/g')
VERSION := $(shell uv version --short)

.phony: uncache
uncache:
	uv run clear_cache

.phony: env
env:
	uv sync

.phony: init
init:
	uv venv
	uv sync

.phony: update
update:
	uv lock --upgrade --prerelease=allow
	uv sync

.phony: lint
lint:
	uv run ruff check
	uv run ruff format --check

.phony: fmt
fmt:
	uv run ruff check --fix
	uv run ruff format

.phony: release
release:
	$(MAKE) update
	@echo "Releasing version $(VERSION)"
	git add pyproject.toml uv.lock || true
	-git commit -m "Release v$(VERSION)" || true
	git tag "v$(VERSION)"
	git push origin main --tags
	gh release create "v$(VERSION)" --title "v$(VERSION)" --notes "Release v$(VERSION)"

.phony: publish
publish:
	uv build
	uv publish

.phony: clean
clean:
	clean-build
	clean-pyc
	clean-test

.phony: clean-build
clean-build:
	# Remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.phony: clean-pyc
clean-pyc:
	# Remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	find . -type d \( -name "__pycache__" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +

.phony: clean-test
clean-test:
	# Remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache
