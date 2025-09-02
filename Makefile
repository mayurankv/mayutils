ROOT := $(shell git rev-parse --show-toplevel)
VERSION := $(shell uv version | awk '{print $$2}')

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

.phony: release
release:
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
