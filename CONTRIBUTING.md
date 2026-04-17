# Contributing

## Setup

```zsh
git clone git@github.com:mayuran-visakan/mayutils.git
cd mayutils
make init
source .venv/bin/activate
```

`make init` creates a venv, runs `uv sync`, and installs pre-commit hooks (including the commit-msg hook for commitizen). The commit-msg hook is required — it validates that every commit follows the Conventional Commits format.

## Pre-commit Hooks

Hooks are declared in `.pre-commit-config.yaml`:

| Hook                        | Stage      | What it does                             |
| --------------------------- | ---------- | ---------------------------------------- |
| `ruff-check`                | pre-commit | Lints Python files and auto-fixes issues |
| `ruff-format`               | pre-commit | Formats Python files                     |
| `commitizen`                | commit-msg | Rejects non-conventional commit messages |
| `uv-lock`                   | pre-commit | Ensures `uv.lock` is up to date          |
| `uv-sync`                   | pre-push   | Syncs the venv to the lockfile           |
| `sort-pyproject`            | pre-commit | Keeps `pyproject.toml` sorted            |
| `mdformat`                  | pre-commit | Formats Markdown                         |
| `check-yaml`                | pre-commit | Validates YAML                           |
| `end-of-file-fixer`         | pre-commit | Ensures trailing newline                 |
| `trailing-whitespace`       | pre-commit | Trims trailing whitespace                |
| `ty`                        | pre-commit | Runs `ty check`                          |
| `sqlfluff-lint` / `fix`     | pre-commit | Lints Snowflake SQL                      |
| `renovate-config-validator` | pre-commit | Validates `renovate.json`                |
| `pre-commit-update`         | pre-commit | Auto-updates hook revisions              |

### Running Manually

```zsh
uv run pre-commit run --all-files   # all files
uv run pre-commit run               # only staged files
```

### Skipping Hooks

Only when a WIP commit genuinely needs it — CI still enforces the checks:

```zsh
git commit --no-verify -m "wip: temporary checkpoint"
```

## Conventional Commits

Every commit message must follow [Conventional Commits](https://www.conventionalcommits.org/):

```txt
<type>(<scope>): <description>
```

### Types

| Type       | When to use                                             | Version bump |
| ---------- | ------------------------------------------------------- | ------------ |
| `feat`     | New feature or capability                               | Minor        |
| `fix`      | Bug fix                                                 | Patch        |
| `docs`     | Documentation only                                      | Patch        |
| `refactor` | Code change that neither fixes a bug nor adds a feature | Patch        |
| `test`     | Adding or updating tests                                | Patch        |
| `ci`       | CI/CD changes                                           | Patch        |
| `chore`    | Maintenance (deps, config)                              | Patch        |
| `perf`     | Performance improvement                                 | Patch        |

### Breaking Changes

Append `!` after the type or add a `BREAKING CHANGE:` footer — triggers a major version bump.

```txt
feat!: drop Python 3.11 support

BREAKING CHANGE: minimum supported Python is now 3.12.
```

### Interactive

```zsh
uv run cz commit   # guided prompt
```

## Versioning and Releases

[Semantic Versioning](https://semver.org/) via [commitizen](https://commitizen-tools.github.io/commitizen/):

```zsh
uv run cz bump             # bump version, update CHANGELOG.md, create tag
uv run cz bump --dry-run   # preview
make release               # bump + push tags
```

The `release.yml` workflow publishes to PyPI when a GitHub release is published.

## Tests

```zsh
make test                         # pytest tests/ -v
uv run pytest -k name_pattern     # filter by name
make coverage                     # coverage run + report
```

Tests that need an optional extra should call `pytest.importorskip("pkg")` so the suite stays green on a core-only install.

## Dependency Groups

Heavy deps are split into extras (`[project.optional-dependencies]`) and dev-only deps into groups (`[dependency-groups]`). See the **Dependency Groups** guide in the docs before adding a dependency — add it to the group that matches its usage, not to the core runtime.

## Linting & Types

```zsh
make lint       # ruff check + format check
make format     # ruff check --fix + format
make type       # ty check
```
