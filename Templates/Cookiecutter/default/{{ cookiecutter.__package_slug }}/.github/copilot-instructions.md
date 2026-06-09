# GitHub Copilot Instructions

Follow the conventions documented in [`AGENTS.md`](../AGENTS.md).

Key points:

- `src` layout under `src/{{ cookiecutter.__package_snake }}/`; tests mirror it one-for-one.
- Use `uv` to manage the environment; `ruff` for linting and formatting; `ty` and `pyright` (strict) for type checking.
- Use modern Python {{ cookiecutter.python_version.split('.')[0] }}.{{ cookiecutter.python_version.split('.')[1] }}+ syntax, PEP 585 generics, the `|` union operator, and `pathlib` over `os.path`.
- Always set `encoding="utf-8"` when opening files in text mode, and use type annotations in function signatures.
- Maintain numpy-style docstrings and write commit messages following [Conventional Commits](https://www.conventionalcommits.org/).
