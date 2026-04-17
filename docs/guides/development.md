# Development

## Local Setup

```zsh
make init
source .venv/bin/activate
```

This runs `uv sync`, installs dev/docs/testing groups, and installs pre-commit hooks (including the commit-msg hook).

## Linting

```zsh
make lint    # ruff check + ruff format --check
make format  # ruff check --fix + ruff format
```

Ruff rules live in `ruff.toml`. The project uses the `ALL` rule set with a small ignore list (see `ruff.toml` for specifics).

## Type Checking

```zsh
uv run ty check src/ tests/
```

`make init` runs `uv sync --all-extras`, so every optional extra is available locally and `ty` resolves all imports. If you sync without extras (e.g. `uv sync` only), `ty` will report unresolved imports for modules gated behind extras.

## Pre-commit

All hooks are declared in `.pre-commit-config.yaml`:

- `ruff-check` / `ruff-format` — Python lint + format
- `commitizen` (commit-msg stage) — rejects non-conventional commits
- `uv-lock` — ensures `uv.lock` is up to date
- `mdformat` — formats Markdown
- `ty` — runs `ty check`
- `sqlfluff-lint` / `sqlfluff-fix` — lint Snowflake SQL
- `renovate-config-validator` — validates `renovate.json`

Run the whole suite manually:

```zsh
uv run pre-commit run --all-files
```

## Building

```zsh
uv build
```

The project uses `uv_build` as its build backend — see `pyproject.toml`.
