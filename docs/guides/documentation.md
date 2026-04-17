# Documentation

The documentation site is built with [mkdocs-material](https://squidfunk.github.io/mkdocs-material/) and the [mkdocstrings](https://mkdocstrings.github.io/) Python handler.

## Local Preview

```zsh
make docs-serve   # live-reload server on http://127.0.0.1:8000
make docs-build   # strict build into site/
```

## Layout

- `mkdocs.yml` — site configuration and navigation
- `docs/index.md` — generated from `README.md` at build time by `docs/hooks/readme_to_index.py`
- `docs/getting-started.md`, `docs/guides/*.md`, `docs/contributing.md`, `docs/changelog.md`, `docs/roadmap.md` — handwritten pages
- `docs/reference/` — auto-generated API reference, written into the build output by `docs/gen_ref_pages.py` (one page per module, discovered from `src/`)
- `docs/includes/abbreviations.md` — term abbreviations auto-appended to every page via `pymdownx.snippets`

## Writing Docstrings

Use the [numpy](https://numpydoc.readthedocs.io/en/latest/format.html) docstring style. The mkdocstrings config in `mkdocs.yml` expects it.

```python
def f(x: int) -> int:
    """Double ``x``.

    Parameters
    ----------
    x : int
        The input.

    Returns
    -------
    int
        Twice ``x``.
    """
    return 2 * x
```

## Deployment

The `docs.yaml` workflow builds the site on every push to `main` and publishes to GitHub Pages.
