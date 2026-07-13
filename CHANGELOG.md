# Changelog

All notable changes to `mayutils` will be documented here.

This project follows [Semantic Versioning](https://semver.org/) and the [Keep a Changelog](https://keepachangelog.com/) conventions. Releases are produced by [commitizen](https://commitizen-tools.github.io/commitizen/) from [Conventional Commits](https://www.conventionalcommits.org/) — `feat` bumps the minor version, `fix` bumps the patch, and a `!` or `BREAKING CHANGE:` footer bumps the major.

## v3.8.0 (2026-07-13)

### Feat

- **src/mayutils/interfaces/data/snowflake/__init__.py**: Add streaming and reading methods to SnowflakeExtendedSession

### Fix

- **cache**: Fix caching

## v3.7.0 (2026-07-10)

### Feat

- **repo**: Fix up query reading and parsing issues

## v3.6.0 (2026-07-08)

### Feat

- **src/mayutils/data/read.py**: Add skip_trailing_semicolon to the query readers which is true by default for read_query

## v3.5.1 (2026-06-26)

### Fix

- **src/mayutils/data/queries**: Add filter to ensure query folders exist

## v3.5.0 (2026-06-24)

### Feat

- **src/mayutils/mathenatics/analytics/attribution**: Add grouped attribution

## v3.4.0 (2026-06-23)

### Feat

- **repo**: Add equality and hashing to intervals and add hash_callable

## v3.3.0 (2026-06-15)

### Feat

- **src/mayutils/interfaces/data/snowflake/__init__.py**: Add additional args to snowpark modin pandas reading
- **pyproject.toml**: Add commitizen auto-push

### Fix

- **src/mayutils/interfaces/data/snowflake/__init__.py**: Add in downstream arguments

## v3.2.0 (2026-06-15)

### Fix

- **src/mayutils/interfaces/filetypes/pptx/__init__.py**: Fix pyright error

### Refactor

- **repo**: make lazy importing better

## v3.1.0 (2026-06-12)

### Feat

- **objects**: add numpy datetime64 coercion and pydantic NpDatetime64 type
- **mathematics**: add deterministic hash-based experiment assignment
- **objects**: add time-effective versioned module and value resolution to versions
- **mathematics**: add numpy array broadcast, merge, lookup, and length-check helpers

### Fix

- **objects/datetime**: Make coerce_datetime64 argument positional-only and allowlist module in lazy-import test
- **objects**: preserve np.datetime64 static type on NpDatetime64 via GetPydanticSchema

## v3.0.0 (2026-06-11)

### BREAKING CHANGE

- the jinja_kwargs parameter introduced in this release cycle is named template_kwargs in the released API.
- StreamingQuery and WindowedQuery accept jinja_kwargs mappings instead of \*\*fixed_format_kwargs / \*\*extra_kwargs.
- inline SQL templates use Jinja {{ name }} placeholders and substitutions are passed as the jinja_kwargs mapping instead of \*\*format_kwargs; make_cache_stem's format_kwargs keyword is renamed jinja_kwargs.
- query templates use Jinja {{ name }} placeholders and substitutions are passed as the jinja_kwargs mapping instead of \*\*format_kwargs.

### Feat

- **src/mayutils/data/read.py**: Automatically parse temporal columns in read_query and stream_query
- **src/mayutils/objects/dataframes/polars/dataframes.py**: Add automatic temporal column parsing
- **src/mayutils/objects/dataframes/pandas/dataframes.py**: Add automatic temporal column parsing
- **src/mayutils/objects/dataframes/temporal.py**: Add temporal detection and backend dispatcher
- **src/mayutils/data/live.py**: Pass template variables as jinja_kwargs mappings
- **src/mayutils/data/read.py**: Render inline SQL with Jinja via jinja_kwargs
- **src/mayutils/data/queries**: Render file query templates with Jinja via jinja_kwargs
- **src/mayutils/interfaces/data/snowflake/__init__.py**: Default client session keep alive and temporary credential caching in connection arguments
- **src/mayutils/data/queries/templating.py**: Add Jinja template rendering module
- **src/mayutils/interfaces/data**: Add env_overrides to get_env_reader and overrides to SnowflakeConfig.from_env
- **src/mayutils/data/read.py**: Add default reader and streamer and update roadmap

### Fix

- **src/mayutils/objects/dataframes/temporal.py**: Widen detection input contract and document pattern permissiveness
- **src/mayutils/data/queries/templating.py**: Scan template text not rendered output for legacy placeholders
- **src/mayutils/data/read.py**: Defer interfaces.data imports to break circular import
- **repo**: Improve the docs

### Refactor

- **src/mayutils/interfaces/filetypes/slides**: Defer googleapiclient import to call time
- **src/mayutils**: Defer remaining extra imports to call time
- **src/mayutils**: Defer keystone extra imports to call time
- **src/mayutils**: Rename jinja_kwargs to template_kwargs

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
