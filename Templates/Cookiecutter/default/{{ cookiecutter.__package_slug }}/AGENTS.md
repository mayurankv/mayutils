# AGENTS.md

Agent context for the `{{ cookiecutter.__package_slug }}` repository — {{ cookiecutter.project_short_description }}

This file is the top-level brief: it maps the codebase and states the conventions. Deeper how-tos live in `docs/` and the docstring-generated API reference, and this file links to them rather than duplicating them.

## Start Here

- `README.md` — project overview.
- `docs/getting-started.md` — install and first usage.
- `docs/guides/development.md` — local setup, linting, type-checking, git hooks, building.
- `docs/guides/testing.md` — how the test suite is laid out and run.
- `docs/guides/documentation.md` — building and serving the docs site.
- `CONTRIBUTING.md` — commit conventions and the release flow.
- API reference — auto-generated from docstrings via `mkdocstrings`; see the published docs site.

`docs/` is the source of truth. Keep READMEs, docs, and docstrings in sync when you change behaviour, APIs, or configuration.

## Repo Map

| Path                                      | What it is                                                                  |
| ----------------------------------------- | --------------------------------------------------------------------------- |
| `src/{{ cookiecutter.__package_snake }}/` | The package (src layout); includes `app/` (Streamlit) and `cli/` (Typer).   |
| `tests/`                                  | pytest suite; mirrors `src/{{ cookiecutter.__package_snake }}/` one-for-one. |
| `docs/`                                   | mkdocs-material site plus generators (`gen_ref_pages.py`, `hooks/`).        |
| `Notebooks/`                              | Scratch and example notebooks.                                              |
| `Makefile`                                | Task runner — setup, lint, type, test, docs, release.                       |
| `pyproject.toml`                          | Dependencies, dependency groups, console scripts, tool config.             |
| `ruff.toml` / `prek.toml`                 | Linter / git-hook configuration.                                            |
| `.github/workflows/`                      | CI (`ci.yaml`), docs (`docs.yaml`), release (`release.yml`).                |

## Setup & Key Commands

```zsh
make init                 # uv venv + sync all extras/groups + install prek git hooks
source ./.venv/bin/activate
```

| Command                          | What it does                              |
| -------------------------------- | ----------------------------------------- |
| `make lint`                      | `ruff check` + `ruff format --check`      |
| `make format`                    | `ruff check --fix` + `ruff format`        |
| `make type`                      | `ty check src/ tests/` + `pyright`        |
| `make test`                      | `pytest -v`                               |
| `make coverage`                  | `coverage run` + `coverage report`        |
| `make docs-serve` / `docs-build` | Serve / strict-build the docs site        |
| `make app` / `make cli`          | Run the Streamlit app / Typer CLI         |

Always use `uv` to manage the environment; activate it with `source ./.venv/bin/activate`. Full detail: `docs/guides/development.md` and the `Makefile`.

## Coding Styles

### Typing

- Use `typing.Sequence` over `list`/`tuple` for inputs where possible.
- Use `typing.Mapping` over `dict` for inputs where possible.
- Allow `ArrayLike` alongside an `NDArray` type hint and coerce types at the input boundary (unless a purely internal function).

### Style & tooling

- Always use trailing commas (especially for function arguments).
- Always lint with `ruff`; type-check with `ty` and `pyright`.
- Maintain numpy-style docstrings (configured via `ruff.toml` `[lint.pydocstyle]` and `mkdocstrings`).

### Standard-library idioms

- Use `pathlib.Path` for path manipulation — never `os.path.join`, `os.path.exists`, etc. If you need a `str`, call `str(path)` at the boundary.
- When opening a file in text mode, **always** set `encoding="utf-8"` explicitly. The implicit locale default is a portability landmine.
- Use `argparse` for simple CLIs, or Typer (already a dependency) for richer ones.
- Reach for `itertools` built-ins (`chain`, `groupby`, `islice`, `accumulate`, `batched`, `pairwise`, …) before writing manual loops over iterables.

### Design & testing

- Assert numeric closeness with `np.allclose` / `np.isclose` — never `pytest.approx`.
- Tests that need an optional dependency call `pytest.importorskip("pkg")` so the suite stays green on a minimal install. Test layout mirrors `src/` one-for-one (see `docs/guides/testing.md`).
- Fix type-checker errors at the root cause — don't add blanket suppressions (`# type: ignore`). The project runs `ty` and `pyright` in strict mode.
- Prefer decomposing logic into public classes/functions over `_private` helpers.
- Function signatures: split arguments over multiple lines with trailing commas; allow at most one positional argument before `/`; make the rest keyword-only with `*`.

## Commits & Releases

All commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/). Use `uv run cz commit` for a guided prompt or let the commit-msg hook reject anything malformed. Versioning and the PyPI release flow (`uv run cz bump`, `make release`) are documented in `CONTRIBUTING.md`.
