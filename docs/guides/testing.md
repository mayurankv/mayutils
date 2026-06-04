# Testing

Tests live under `tests/` and run with pytest.

## Running

```zsh
make test            # uv run pytest -v  (unit tests + docstring doctests)
make doctest         # uv run pytest --doctest-modules src/mayutils -v
uv run pytest -k name_pattern
uv run coverage run -m pytest && uv run coverage report
```

## Structure

Tests mirror the `src/mayutils/` layout one-for-one:

- Each source file `src/mayutils/<path>/<name>.py` gets a test file at `tests/<path>/test_<name>.py`.
- Tests for a subpackage's `__init__.py` (or tests that span multiple files in the same folder) live at `tests/<path>/test_module.py`.
- Tests that cut across subpackages live at `tests/test_module.py` at the level that contains them all.
- Add a `conftest.py` at the level where a shared fixture, marker, or pytest hook is first needed — the suite ships without one today.

```text
src/mayutils/objects/strings.py          →  tests/objects/test_strings.py
src/mayutils/_extras.py                  →  tests/test__extras.py
src/mayutils/__init__.py                 →  tests/test_module.py
src/mayutils/visualisation/graphs/...    →  tests/visualisation/graphs/...
```

Tests that require an optional extra should `pytest.importorskip(...)` the relevant dependency so the suite still passes on a minimal install.

```python
import pytest

plotly = pytest.importorskip("plotly")
```

## Doctests

Docstring `Examples` blocks are executed as part of the default pytest run: `addopts` enables `--doctest-modules` and `testpaths` includes `src/mayutils`, so `uv run pytest` (and `make test`) run the unit tests *and* every docstring example.

- Write examples that actually run. Reserve `# doctest: +SKIP` for examples that need external resources (network, credentials), write files, render output, or are otherwise non-deterministic.
- `ELLIPSIS` and `NORMALIZE_WHITESPACE` are enabled, so `...` and flexible whitespace are allowed in expected output.
- Run only the doctests with `make doctest`.

## CI

The `ci.yaml` workflow runs, on every PR to `main`: pre-commit, `ty check`, the unit suite (`pytest tests/` on a minimal install, keeping the `importorskip` graceful-degradation contract honest), the docstring doctests (`pytest --doctest-modules src/mayutils` on a full `--all-extras` install), and `cz check`. See `.github/workflows/ci.yaml`.
