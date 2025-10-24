ROOT := $(shell git rev-parse --show-toplevel)
PACKAGE_NAME := $(shell uv version | awk '{print $$1}' | sed 's/-/_/g')
VERSION := $(shell uv version --short)

.PHONY: uncache
uncache:
	uv run clear_cache

.PHONY: env
env:
	uv sync

.PHONY: init
init:
	uv venv
	uv sync

.PHONY: update
update:
	uv lock --upgrade --prerelease=allow
	uv sync

.PHONY: lint
lint:
	uv run ruff check
	uv run ruff format --check

.PHONY: format
format:
	uv run ruff check --fix
	uv run ruff format

.PHONY: release
release:
	$(MAKE) update
	@echo "Releasing version $(VERSION)"
	git add pyproject.toml uv.lock || true
	-git commit -m "Release v$(VERSION)" || true
	git tag "v$(VERSION)"
	git push origin main --tags
	gh release create "v$(VERSION)" --title "v$(VERSION)" --notes "Release v$(VERSION)"

.PHONY: publish
publish:
	uv build
	uv publish

.PHONY: clean
clean:
	clean-build
	clean-pyc
	clean-test

.PHONY: clean-build
clean-build:
	# Remove build artifacts
	rm -fr build/
	rm -fr dist/
	rm -fr .eggs/
	find . -name '*.egg-info' -exec rm -fr {} +
	find . -name '*.egg' -exec rm -f {} +

.PHONY: clean-pyc
clean-pyc:
	# Remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +
	find . -type d \( -name "__pycache__" -o -name ".ruff_cache" -o -name ".mypy_cache" -o -name ".pytest_cache" \) -exec rm -rf {} +

.PHONY: clean-test
clean-test:
	# Remove test and coverage artifacts
	rm -f .coverage
	rm -fr htmlcov/
	rm -fr .pytest_cache

.PHONY: stubs
stubs:
	PYTHONPATH=src uv run stubgen -p $(PACKAGE_NAME) --include-docstrings --output typings
	$(MAKE) format

.PHONY: type
type:
	uv run mypy --strict src/$(PACKAGE_NAME)

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
