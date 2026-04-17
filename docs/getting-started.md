# Getting Started

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

Install the core package (minimal runtime deps: numpy, pandas, pydantic, rich, requests):

```zsh
uv add mayutils
```

Install specific optional groups for the functionality you need:

```zsh
# plotting helpers (plotly, kaleido, matplotlib, scipy, etc.)
uv add "mayutils[plotting]"

# Snowflake + SQLAlchemy integrations
uv add "mayutils[snowflake]"

# Curated default for notebook-based data analysis
# (plotting + notebook + dataframes + datetime + stats)
uv add "mayutils[recommended]"

# Everything
uv add "mayutils[all]"
```

See [Dependency Groups](guides/dependency-groups.md) for the full mapping of groups to submodules.

## For Development

```zsh
git clone git@github.com:mayuran-visakan/mayutils.git
cd mayutils
make init
source .venv/bin/activate
```

`make init` creates a virtual environment, installs the dev + docs + testing groups, and installs pre-commit hooks (including the commit-msg hook for commitizen).

## Quick Usage

```python
import mayutils
from mayutils.objects.numbers import format_number

mayutils.setup()  # configure logging + notebook/dataframe niceties (safe no-op without extras)

print(format_number(value=1_234_567))
```

For plotting (requires the `plotting` extra):

```python
from mayutils.visualisation.graphs.plotly import charts

charts.histogram(...)
```

## Next Steps

- [Dependency Groups](guides/dependency-groups.md) — which extras map to which submodules
- [Development](guides/development.md) — local workflow, linting, typing
- [Testing](guides/testing.md) — how to write and run tests
- [Contributing](contributing.md) — commit conventions and release process
- [Roadmap](roadmap.md) — planned work, translated from the legacy `.todo` file
