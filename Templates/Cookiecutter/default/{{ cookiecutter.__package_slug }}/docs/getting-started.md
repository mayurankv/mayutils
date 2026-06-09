# Getting Started

## Prerequisites

- Python {{ cookiecutter.python_version }}+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

Add {{ cookiecutter.project_name }} to your project:

```zsh
uv add {{ cookiecutter.__package_slug }}
```

## For Development

```zsh
git clone git@github.com:{{ cookiecutter.__gh_slug }}.git
cd {{ cookiecutter.__package_slug }}
make init
source .venv/bin/activate
```

`make init` creates a virtual environment, installs the dev + docs + testing groups, and installs [prek](https://prek.j178.dev) git hooks (pre-commit, commit-msg, and pre-push).

## Quick Usage

```python
import {{ cookiecutter.__package_snake }}
```

## Next Steps

- [Development](guides/development.md) — local workflow, linting, typing
- [Testing](guides/testing.md) — how to write and run tests
- [Documentation](guides/documentation.md) — building and deploying the docs site
- [Contributing](contributing.md) — commit conventions and release process
- [Roadmap](roadmap.md) — planned work
