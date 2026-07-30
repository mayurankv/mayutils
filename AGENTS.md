# AGENTS.md

Agent context for the `mayutils` repository — a single-maintainer Python utility library published to PyPI. The core install is intentionally small; heavy dependencies are grouped behind optional **extras**.

This file is the top-level brief: it maps the codebase and states the conventions. Deeper how-tos live in `docs/` and the docstring-generated API reference, and this file links to them rather than duplicating them.

## Start Here

- `README.md` — project overview and the dependency-group table.
- `docs/getting-started.md` — install and first usage.
- `docs/guides/development.md` — local setup, linting, type-checking, git hooks, building.
- `docs/guides/testing.md` — how the test suite is laid out and run.
- `docs/guides/dependency-groups.md` — which extra maps to which submodule.
- `docs/guides/documentation.md` — building and serving the docs site.
- `CONTRIBUTING.md` — commit conventions and the release flow.
- API reference — auto-generated from docstrings via `mkdocstrings`; see the published docs site.

`docs/` is the source of truth. Keep READMEs, docs, and docstrings in sync when you change behaviour, APIs, or configuration.

## Repo Map

| Path                                  | What it is                                                                             |
| ------------------------------------- | -------------------------------------------------------------------------------------- |
| `src/mayutils/`                       | The package (src layout). See the component map below.                                 |
| `tests/`                              | pytest suite; mirrors `src/mayutils/` one-for-one.                                     |
| `docs/`                               | mkdocs-material site plus generators (`gen_ref_pages.py`, `hooks/`).                   |
| `Notebooks/`                          | Scratch and example notebooks.                                                         |
| `Templates/`                          | Cookiecutter project template(s).                                                      |
| `Makefile`                            | Task runner — setup, lint, type, test, docs, release.                                  |
| `pyproject.toml`                      | Dependencies, optional extras, console scripts, tool config.                           |
| `ruff.toml` / `ty.toml` / `prek.toml` | Linter / type-checker / git-hook configuration.                                        |
| `.github/workflows/`                  | CI (`ci.yaml`), docs (`docs.yaml`), release (`release.yml`), stub refresh, merge gate. |

## Component Map (`src/mayutils/`)

Entry point: `import mayutils; mayutils.setup()` configures logging, Plotly templates, IPython display hooks, and pandas options. Each step is guarded and is a safe no-op when its extra is missing.

- `core/` — foundational, dependency-light. `constants`; `extras` houses the `may_require_extras()` / `requires_extras()` machinery (see Dependency Groups below).
- `objects/` — general-purpose helpers with no heavy deps by default: `classes`, `colours`, `decorators`, `dictionaries`, `functions`, `hashing`, `numbers`, `paths`, `strings`, `types`, `versions`.
    - `objects/dataframes/` — the `Backend` type token (`backends.py`) plus per-engine adapters: `pandas/`, `polars/`, `dask/`, `modin/`, `pyarrow/`, `snowflake/`.
    - `objects/datetime/` — `datetime`, `interval`, `timezone`, `traveller`, `constants`, `numpy` (numpy `datetime64` coercion and Pydantic-compatible annotated type; requires `numerics`).
- `data/` — data access. **`read` is the canonical reader — use it for reading data.** Also `live` and `queries/`.
- `environment/` — runtime and environment glue: `logging` (Rich console + rotating file handlers), `secrets`, `oauth`, `databases`, `benchmarking`, `webdrivers`, `filesystem/`, `memoisation/`.
- `export/` — rendering and export: `html`, `images`, `nbconvert`, `quarto`.
- `interfaces/` — external-system and file-format adapters: `cloud/google`, `streamlit`, and `filetypes/` (csv, docs, docx, feather, markdown, parquet, pdf, pptx, sheets, slides, tex, xlsx).
- `mathematics/` — `numpy` (array helpers), `numba`, `experiments` (deterministic hash-based experiment assignment; requires `numerics`), `statistics/`, `machine_learning/`.
- `visualisation/` — `console`, `notebook` (IPython display setup), and `graphs/`: **`graphs/plotly/` is the canonical plotting entry point — use it for charts**, alongside `matplotlib/` and `combine`.
- `scripts/` — console entry points declared in `[project.scripts]`: `clear_cache`, `refresh_stubs`, `generate_plotly_stubs`.
- `testing/` — shared test helpers and utilities.

## Setup & Key Commands

```zsh
make init                 # uv venv + sync all extras/groups + install prek git hooks
source ./.venv/bin/activate
```

| Command                          | What it does                                                |
| -------------------------------- | ----------------------------------------------------------- |
| `make lint`                      | `ruff check` + `ruff format --check` + docstring validation |
| `make format`                    | `ruff check --fix` + `ruff format`                          |
| `make type`                      | `ty check src/ tests/`                                      |
| `make test`                      | `pytest tests/ -v`                                          |
| `make coverage`                  | `coverage run` + `coverage report`                          |
| `make docs-serve` / `docs-build` | Serve / strict-build the docs site                          |

Always use `uv` to manage the environment; activate it with `source ./.venv/bin/activate`. `make init` syncs **all** extras, so `ty` and `pyright` can resolve imports gated behind optional groups — a bare `uv sync` will report unresolved imports for those modules. Full detail: `docs/guides/development.md` and the `Makefile`.

## Coding Styles

### Typing

- Use `typing.Sequence` over `list`/`tuple` for inputs where possible.
- Use `typing.Mapping` over `dict` for inputs where possible.
- Allow `ArrayLike` alongside an `NDArray` type hint and coerce types at the input boundary (unless a purely internal function).

### Style & tooling

- Always use trailing commas (especially for function arguments).
- Always lint with `ruff`; type-check with `ty`.
- Maintain numpy-style docstrings (configured via `ruff.toml` `[lint.pydocstyle]` and `mkdocstrings`).

### Standard-library idioms

- Use `pathlib.Path` for path manipulation — never `os.path.join`, `os.path.exists`, etc. If you need a `str`, call `str(path)` at the boundary.
- When opening a file in text mode, **always** set `encoding="utf-8"` explicitly (`open(path, encoding="utf-8")` or `Path.read_text(encoding="utf-8")`). The implicit locale default is a portability landmine.
- Use `argparse` for CLIs — not `optparse` (removed from the stdlib's supported surface) and not hand-rolled `sys.argv` parsing. For richer CLIs, Typer (in the `cli` extra) is already available.
- Reach for `itertools` built-ins (`chain`, `groupby`, `islice`, `accumulate`, `batched`, `pairwise`, …) before writing manual loops over iterables.

### Design & testing

- Assert numeric closeness with `np.allclose` / `np.isclose` — never `pytest.approx`.
- Tests that need an optional extra call `pytest.importorskip("pkg")` so the suite stays green on a core-only install. Test layout mirrors `src/` one-for-one (see `docs/guides/testing.md`).
- Fix type-checker errors at the root cause — don't add blanket suppressions (`# type: ignore`). The project runs `ty` and `pyright` in strict mode.
- Prefer decomposing logic into public classes/functions over `_private` helpers.
- Keep `Backend` a lean type token: infer operations from the backend rather than adding frame operations or domain logic to it.
- Function signatures: split arguments over multiple lines with trailing commas; allow at most one positional argument before `/`; make the rest keyword-only with `*`.

## Dependency Groups

Heavy dependencies live in `[project.optional-dependencies]` — never add a heavy import to a core runtime module without declaring the matching extra. See `docs/guides/dependency-groups.md` for the current mapping.

Any submodule that imports from an optional extra at module level **must** wrap those imports with `mayutils.core.extras.may_require_extras()` — the context manager auto-resolves the matching extra from `pyproject.toml` so users get an actionable install hint (`mayutils[<group>]`) instead of a bare `ModuleNotFoundError`. Fall back to `requires_extras("<group>", ...)` only when you need to force a specific hint (e.g. a namespaced import not present in the extras map).

## Commits & Releases

All commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/). Use `uv run cz commit` for a guided prompt or let the commit-msg hook reject anything malformed. Versioning and the PyPI release flow (`uv run cz bump`, `make release`) are documented in `CONTRIBUTING.md`.
