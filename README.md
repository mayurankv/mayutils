# mayutils

[![CI](https://github.com/mayuran-visakan/mayutils/actions/workflows/ci.yaml/badge.svg)](https://github.com/mayuran-visakan/mayutils/actions/workflows/ci.yaml) [![Documentation](https://img.shields.io/badge/Documentation-mkdocs%20material-indigo.svg)](https://mayuran-visakan.github.io/mayutils/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Utilities for Python — plotting helpers, dataframe adapters, Snowflake/SQL glue, PowerPoint/PDF export, notebook display tweaks, OAuth helpers, and a fistful of miscellaneous object helpers. Heavy dependencies are grouped behind extras so the core install stays small.

## Quick Start

```zsh
uv add mayutils                   # core only
uv add "mayutils[plotting]"       # + plotly/kaleido/matplotlib/scipy
uv add "mayutils[recommended]"    # curated data-analysis set (plotting+notebook+dataframes+datetime+stats)
uv add "mayutils[all]"            # everything
```

```python
import mayutils
from mayutils.objects.numbers import prettify

mayutils.setup()
print(prettify(num=1_234_567))  # "1.23M"
```

## Dependency Groups

| Group         | Use it for                                                          |
| ------------- | ------------------------------------------------------------------- |
| `plotting`    | `plotly`, `kaleido`, `matplotlib`, `scipy`, `great-tables`          |
| `notebook`    | `jupyter`, `ipykernel`, `nbconvert`, `itables`, `jupysql`           |
| `dataframes`  | `polars`, `modin`                                                   |
| `stats`       | `scikit-learn`, `scipy`, `numba`, `numpy-financial`                 |
| `google`      | Google Drive / Sheets / Cloud Storage + auth                        |
| `microsoft`   | `python-pptx`, `openpyxl`                                           |
| `snowflake`   | `snowflake-connector-python`, `snowflake-sqlalchemy`                |
| `streamlit`   | `streamlit`                                                         |
| `web`         | `selenium`, `playwright`, `chromedriver-autoinstaller`              |
| `pdf`         | `pymupdf`, `pillow`                                                 |
| `datetime`    | `pendulum`                                                          |
| `cli`         | `typer`, `cookiecutter`                                             |
| `filesystem`  | `gitpython`, `watchdog`                                             |
| `recommended` | meta: `plotting` + `notebook` + `dataframes` + `datetime` + `stats` |
| `all`         | Every runtime extra                                                 |

Full details: [docs/guides/dependency-groups.md](docs/guides/dependency-groups.md).

## Documentation

- [Getting Started](docs/getting-started.md)
- [Development](docs/guides/development.md)
- [Testing](docs/guides/testing.md)
- [Documentation](docs/guides/documentation.md)
- [Roadmap](docs/roadmap.md) — translated from the legacy `.todo` file
- [Changelog](docs/changelog.md)
- [API Reference](https://mayuran-visakan.github.io/mayutils/reference/) — auto-generated from docstrings

## Contributing

See the [contributing guide](docs/contributing.md) for setup, commit conventions (Conventional Commits), and release flow.

## License

MIT — see [LICENSE](LICENSE).
