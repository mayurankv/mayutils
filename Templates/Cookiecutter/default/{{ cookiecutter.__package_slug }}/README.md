# {{ cookiecutter.project_name }}

[![CI](https://github.com/{{ cookiecutter.__gh_slug }}/actions/workflows/ci.yaml/badge.svg)](https://github.com/{{ cookiecutter.__gh_slug }}/actions/workflows/ci.yaml) [![Documentation](https://img.shields.io/badge/Documentation-mkdocs%20material-indigo.svg)](https://{{ cookiecutter.github_username }}.github.io/{{ cookiecutter.__package_slug }}/) [![PyPI version](https://img.shields.io/pypi/v/{{ cookiecutter.__package_slug }}.svg)](https://pypi.org/project/{{ cookiecutter.__package_slug }}/)

{{ cookiecutter.project_short_description }}

## Quick Start

```zsh
uv add {{ cookiecutter.__package_slug }}
```

```python
import {{ cookiecutter.__package_snake }}
```

## Documentation

- [Getting Started](docs/getting-started.md)
- [Development](docs/guides/development.md)
- [Testing](docs/guides/testing.md)
- [Documentation](docs/guides/documentation.md)
- [Changelog](docs/changelog.md)
- [API Reference](https://{{ cookiecutter.github_username }}.github.io/{{ cookiecutter.__package_slug }}/reference/) — auto-generated from docstrings

## Contributing

See the [contributing guide](docs/contributing.md) for setup, commit conventions (Conventional Commits), and release flow.

## License

{{ cookiecutter.license }} — see [LICENSE](LICENSE).
