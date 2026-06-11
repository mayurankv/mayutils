# Changelog

All notable changes to `mayutils` will be documented here.

This project follows [Semantic Versioning](https://semver.org/) and the [Keep a Changelog](https://keepachangelog.com/) conventions. Releases are produced by [commitizen](https://commitizen-tools.github.io/commitizen/) from [Conventional Commits](https://www.conventionalcommits.org/) — `feat` bumps the minor version, `fix` bumps the patch, and a `!` or `BREAKING CHANGE:` footer bumps the major.

## v2.1.0 (2026-06-11)

### Feat

- **src/mayutils/data/read.py**: Add default reader and streamer and update roadmap

### Fix

- **repo**: Improve the docs

## v2.0.0 (2026-06-10)

### Feat

- **pyproject.toml**: Update commitizen settings and .todo
- **scripts**: Add stub generation in correct order
- **AGENTS**: Add agents md details + markdown fix
- **src/mayutils/data**: Update live.py to two proper query live data structures

### Fix

- **pyproject.toml**: Allow commitizen bumps
- **src/mayutils/data/read.py**: Fix docstring
- **typings**: Fix type issues
- **.github/workflows**: Skip auto updates in CI
- **docs**: Make build work and minor fixes
- **.github/workflows**: Add workflow dispatches
- **tests/export/test_nbconvert.py**: Add pandoc requirement to test
- **.github/workflows**: Add extra dependencies to relevant jobs
- **src/mayutils/mathematics/numba.py**: Fix docstring test
- **prek.toml**: Update prek hook versions
- **src/mayutils/core/extras.py**: Fix import names when different
- **prek.toml**: Update prek hook versions
- **prek.toml**: Remove pyright jupyter checks due to known issues
- **tests/data/test_live.py**: Fix docstring
- **src/mayutils/visualisation/graphs**: Add docstrings and minor fixes
- **tests/data/test_live.py**: Add docstrings
- **repo**: General fixes across a few different files
- **tests/data/test_live.py**: Fix data attribute reference
- **prek**: Update cookiecutter template to not trigger prek

### Refactor

- **repo**: More wide changes adding some new features and cleaning up other stuff
- **repo**: Wider changes adding some new features and cleaning up other stuff
- **Templates**: Make Templates match mayutils
- **repo**: Update tests and typings knockon effects
- **repo**: Update tests and typings
- **repo**: Update tests and minor issues
- **repo**: Update prek hook versions and stubs
- **repo**: Fix tests and issues across the repo
- **src/mayutils/visualisation/graphs/plotly**: Stub generation + wider repo aikido fixes
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 7
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 6
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 5
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic Part 5
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic Part 4
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 4
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 3
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic part 2
- **src/mayutils/visualisation/graphs/plotly**: Refactor logic
- **repo**: Refactor part 33
- **repo**: Refactor part 32
- **repo**: Refactor part 32
- **repo**: Refactor part 31
- **repo**: Refactor part 30
- **repo**: Refactor part 29
- **repo**: Refactor part 28
- **repo**: Refactor part 27
- **repo**: Refactor part 26
- **repo**: Refactor part 25
- **repo**: Refactor part 24
- **repo**: Refactor part 23
- **repo**: Refactor part 22
- **repo**: Refactor part 20
- **repo**: Refactor part 19
- **repo**: Refactor part 18
- **repo**: Refactor part 17
- **repo**: Refactor part 16
- **repo**: Refactor part 15
- **repo**: Refactor part 14
- **repo**: Refactor part 14
- **repo**: Refactor part 13
- **repo**: Refactor part 12
- **repo**: Refactor part 11
- **repo**: Refactor part 10
- **repo**: Refactor part 9
- **repo**: Refactor part 8
- **repo**: Refactor part 7
- **repo**: Refactor part 6
- **repo**: Refactor part 5
- **repo**: Refactor part 4
- **repo**: Refactor part 3
- **repo**: Refactor part 2
- **repo**: Refactor part 1

## v1.2.52

### Added

- Initial commitizen-managed changelog.
- Optional-dependency groups (`plotting`, `notebook`, `google`, `microsoft`, `snowflake`, `streamlit`, `stats`, `dataframes`, `datetime`, `pdf`, `web`, `cli`, `async`, `filesystem`, `keyring`, `types`, `all`).
- `docs` and `testing` dependency groups for mkdocs-material site and pytest.
- mkdocs-material documentation site with auto-generated API reference.
- CI workflows (`ci.yaml`, `docs.yaml`, `merge-gatekeeper.yaml`) and renovate config.
- Contributing guide, security policy, roadmap (translated from `.todo`).
