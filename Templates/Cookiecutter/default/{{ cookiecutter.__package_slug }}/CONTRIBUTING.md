# Contributing

## Setup

See [Development](guides/development.md) for local setup, linting, type checking, git hooks, and testing.

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
feat!: drop Python 3.12 support

BREAKING CHANGE: minimum supported Python is now 3.13.
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

The `release.yml` workflow builds and publishes to PyPI when a `v*` tag is pushed (e.g. by `make release`).

## Dependency Groups

Runtime dependencies live in `[project.dependencies]`; dev-only deps are split into `[dependency-groups]` (`dev`, `docs`, `testing`). Add a dependency to the group that matches its usage, not to the core runtime unless it is required at import time.
