# Development

## Local Setup

```zsh
make init
source .venv/bin/activate
```

This runs `uv sync`, installs dev/docs/testing groups, and installs [prek](https://prek.j178.dev) git hooks (pre-commit, commit-msg, and pre-push).

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

## Git Hooks

All hooks are declared in `prek.toml` and managed by [prek](https://prek.j178.dev):

| Hook                        | Stage      | What it does                             |
| --------------------------- | ---------- | ---------------------------------------- |
| `ruff-format`               | pre-commit | Formats Python files                     |
| `uv-lock`                   | pre-commit | Ensures `uv.lock` is up to date          |
| `sort-pyproject`            | pre-commit | Keeps `pyproject.toml` sorted            |
| `check-yaml`                | pre-commit | Validates YAML                           |
| `end-of-file-fixer`         | pre-commit | Ensures trailing newline                 |
| `trailing-whitespace`       | pre-commit | Trims trailing whitespace                |
| `mdformat`                  | pre-commit | Formats Markdown                         |
| `sqlfluff-fix`              | pre-commit | Fixes Snowflake SQL                      |
| `commitizen`                | commit-msg | Rejects non-conventional commit messages |
| `ruff-check`                | pre-push   | Lints Python files and auto-fixes issues |
| `ty`                        | pre-push   | Runs `ty check`                          |
| `pyright`                   | pre-push   | Runs `pyright`                           |
| `uv-sync`                   | pre-push   | Syncs the venv to the lockfile           |
| `refresh-stubs`             | pre-push   | Refreshes pyright type stubs             |
| `numpydoc-validation`       | pre-push   | Validates docstrings                     |
| `sqlfluff-lint`             | pre-push   | Lints Snowflake SQL                      |
| `renovate-config-validator` | pre-push   | Validates `renovate.json`                |
| `pre-commit-update`         | pre-push   | Auto-updates hook revisions              |

Run the whole suite manually:

```zsh
uv run prek run --all-files                    # all hooks, all files
uv run prek run --stage pre-push --all-files   # only pre-push hooks
```

To skip hooks for a WIP commit (CI still enforces the checks):

```zsh
git commit --no-verify -m "wip: temporary checkpoint"
```

## Testing

```zsh
make test                         # pytest tests/ -v
uv run pytest -k name_pattern     # filter by name
make coverage                     # coverage run + report
```

Tests that need an optional extra should call `pytest.importorskip("pkg")` so the suite stays green on a core-only install.

## Building

```zsh
uv build
```

The project uses `uv_build` as its build backend — see `pyproject.toml`.
