# AGENTS.md

Agent context for the `mayutils` repository.

- Read `README.md` for an overview, `docs/getting-started.md` for install, `CONTRIBUTING.md` for workflow.
- Keep READMEs, docs and docstrings in sync when you change behaviour, APIs, or configuration.

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

## Dependency Groups

Heavy dependencies live in `[project.optional-dependencies]` — never add a heavy import to a core runtime module without declaring the matching extra. See `docs/guides/dependency-groups.md` for the current mapping.

Any submodule that imports from an optional extra at module level **must** wrap those imports with `mayutils.core.extras.requires_extras("<group>", ...)` — pass the extras explicitly so users get an actionable install hint (`mayutils[<group>]`) instead of a bare `ModuleNotFoundError`, regardless of whether the missing dist has a non-obvious import name.

## Commits

All commit messages must follow [Conventional Commits](https://www.conventionalcommits.org/). Use `uv run cz commit` for a guided prompt or let the commit-msg hook reject anything malformed.
