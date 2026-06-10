# Development

## Local Setup

```zsh
make init
source .venv/bin/activate
```

This runs `uv venv` + `uv sync --all-extras --all-groups`, and installs [prek](https://prek.j178.dev) git hooks (pre-commit, commit-msg, and pre-push).

## Linting

```zsh
make lint    # ruff check + ruff format --check
make format  # ruff check --fix + ruff format
```

Ruff rules live in `ruff.toml`. The project uses the `ALL` rule set with a small ignore list (see `ruff.toml` for specifics).

## Type Checking

```zsh
make type    # ty check src/ tests/ + pyright
```

`make init` runs `uv sync --all-extras --all-groups`, so every optional extra is available locally and the type checkers resolve all imports. If you sync without extras, they will report unresolved imports for modules gated behind extras.

## Git Hooks

All hooks are declared in `prek.toml` and managed by [prek](https://prek.j178.dev):

| Hook                  | Stage      | What it does                             |
| --------------------- | ---------- | ---------------------------------------- |
| `ruff-format`         | pre-commit | Formats Python files                     |
| `uv-lock`             | pre-commit | Ensures `uv.lock` is up to date          |
| `sort-pyproject`      | pre-commit | Keeps `pyproject.toml` sorted            |
| `check-yaml`          | pre-commit | Validates YAML                           |
| `end-of-file-fixer`   | pre-commit | Ensures trailing newline                 |
| `trailing-whitespace` | pre-commit | Trims trailing whitespace                |
| `mdformat`            | pre-commit | Formats Markdown                         |
| `sqlfluff-fix`        | pre-commit | Fixes Snowflake SQL                      |
| `commitizen`          | commit-msg | Rejects non-conventional commit messages |
| `ruff-check`          | pre-push   | Lints Python files and auto-fixes issues |
| `ty`                  | pre-push   | Runs `ty check`                          |
| `pyright`             | pre-push   | Runs `pyright`                           |
| `uv-sync`             | pre-push   | Syncs the venv to the lockfile           |
| `numpydoc-validation` | pre-push   | Validates docstrings                     |
| `sqlfluff-lint`       | pre-push   | Lints Snowflake SQL                      |
| `prek-auto-update`    | pre-push   | Auto-updates hook revisions              |

Run the whole suite manually:

```zsh
uv run prek run --all-files                    # all hooks, all files
uv run prek run --stage pre-push --all-files   # only pre-push hooks
```

To skip hooks for a WIP commit (CI still enforces the checks):

```zsh
git commit --no-verify -m "wip: temporary checkpoint"
```

## Commits

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) and are enforced by the `commitizen` commit-msg hook. The changelog and version bumps are derived from this history — see [Contributing](../contributing.md) and the [Changelog](../changelog.md).

## Testing

```zsh
make test                         # pytest -v (unit tests + docstring doctests)
make unittest                     # pytest tests/ -v
make doctest                      # pytest --doctest-modules src/{{ cookiecutter.__package_snake }} -v
uv run pytest -k name_pattern     # filter by name
make coverage                     # coverage run + report
```

See [Testing](testing.md) for the full layout and conventions.

## Building

```zsh
uv build
```

The project uses `uv_build` as its build backend — see `pyproject.toml`.
