# Testing

Tests live under `tests/` and run with pytest.

## Running

```zsh
make test            # uv run pytest -v  (unit tests + docstring doctests)
make unittest        # uv run pytest tests/ -v
make doctest         # uv run pytest --doctest-modules src/{{ cookiecutter.__package_snake }} -v
uv run pytest -k name_pattern
make coverage        # uv run coverage run -m pytest && uv run coverage report
```

## Structure

Tests mirror the `src/{{ cookiecutter.__package_snake }}/` layout one-for-one:

- Each source file `src/{{ cookiecutter.__package_snake }}/<path>/<name>.py` gets a test file at `tests/<path>/test_<name>.py`.
- Tests for a subpackage's `__init__.py` (or tests that span multiple files in the same folder) live at `tests/<path>/test_module.py`.
- Tests that cut across subpackages live at `tests/test_module.py` at the level that contains them all.
- Add a `conftest.py` at the level where a shared fixture, marker, or pytest hook is first needed.

```text
src/{{ cookiecutter.__package_snake }}/objects/strings.py   →  tests/objects/test_strings.py
src/{{ cookiecutter.__package_snake }}/_extras.py           →  tests/test__extras.py
src/{{ cookiecutter.__package_snake }}/__init__.py          →  tests/test_module.py
```

Tests that require an optional extra should `pytest.importorskip(...)` the relevant dependency so the suite still passes on a minimal install.

```python
import pytest

plotly = pytest.importorskip("plotly")
```

## Doctests

Docstring `Examples` blocks are executed as part of the default pytest run: `addopts` enables `--doctest-modules` and `testpaths` includes `src/{{ cookiecutter.__package_snake }}`, so `uv run pytest` (and `make test`) run the unit tests *and* every docstring example.

- Write examples that actually run. Reserve `# doctest: +SKIP` for examples that need external resources (network, credentials), write files, render output, or are otherwise non-deterministic.
- `ELLIPSIS` and `NORMALIZE_WHITESPACE` are enabled, so `...` and flexible whitespace are allowed in expected output.
- Run only the doctests with `make doctest`.

## CI

The `ci.yaml` workflow runs, on every PR to `main`: pre-commit, type checks, the unit suite (`pytest tests/` on a minimal install, keeping the `importorskip` graceful-degradation contract honest), the docstring doctests (`pytest --doctest-modules src/{{ cookiecutter.__package_snake }}` on a full `--all-extras` install), and `cz check`. See `.github/workflows/ci.yaml`.
