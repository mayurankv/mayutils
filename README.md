# mayutils

[![CI](https://img.shields.io/github/actions/workflow/status/mayurankv/mayutils/ci.yaml?branch=main&style=for-the-badge&logo=githubactions&logoColor=white&label=CI)](https://github.com/mayurankv/mayutils/actions/workflows/ci.yaml) [![PyPI](https://img.shields.io/pypi/v/mayutils?style=for-the-badge&logo=pypi&logoColor=white&label=PyPI&color=3775A9)](https://pypi.org/project/mayutils/) [![Python](https://img.shields.io/badge/python-3.13%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/downloads/) [![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge&logo=opensourceinitiative&logoColor=white)](./LICENSE) [![Docs](https://img.shields.io/badge/docs-mkdocs--material-3F51B5?style=for-the-badge&logo=materialformkdocs&logoColor=white)](https://mayurankv.github.io/mayutils/)

Utilities for Python — plotting helpers, dataframe adapters, Snowflake/SQL glue, PowerPoint/PDF export, notebook display tweaks, OAuth helpers, and a fistful of miscellaneous object helpers. Heavy dependencies are grouped behind extras so the core install stays small.

## Quick Start

```zsh
uv add mayutils                   # core only
uv add "mayutils[plotting]"       # + plotly/kaleido/matplotlib/scipy
uv add "mayutils[recommended]"    # curated data-analysis set (console+pandas+datetime+notebook+plotting+secrets)
uv add "mayutils[all]"            # everything
```

```python
import mayutils
from mayutils.objects.numbers import prettify

mayutils.setup()
print(prettify(num=1_234_567))  # "1.23M"
```

## Dependency Groups

| Group         | Use it for                                                                    |
| ------------- | ----------------------------------------------------------------------------- |
| `plotting`    | `plotly`, `kaleido`, `matplotlib`, `scipy`, `great-tables`                    |
| `notebook`    | `jupyter`, `ipykernel`, `nbconvert`, `itables`, `jupysql`, `quarto-cli`       |
| `pandas`      | `pandas`, `pyarrow`                                                           |
| `dataframes`  | `polars`, `modin`, `dask` (+ `pandas`)                                        |
| `mathematics` | `sympy`, `numba`                                                              |
| `statistics`  | `scikit-learn`, `scipy`, `statsmodels`                                        |
| `financials`  | `numpy-financial`                                                             |
| `google`      | Google Drive / Sheets / Cloud Storage + auth                                  |
| `microsoft`   | `python-pptx`, `openpyxl`                                                     |
| `sql`         | `sqlalchemy`                                                                  |
| `snowflake`   | `snowflake-connector-python`, `snowflake-sqlalchemy` (+ `sql`)                |
| `streamlit`   | `streamlit`                                                                   |
| `web`         | `selenium`, `playwright`, `chromedriver-autoinstaller`                        |
| `pdf`         | `pymupdf`, `pillow`                                                           |
| `datetime`    | `pendulum`                                                                    |
| `cli`         | `typer`, `cookiecutter`                                                       |
| `filesystem`  | `gitpython`, `watchdog`                                                       |
| `secrets`     | `python-dotenv`, `keyring`                                                    |
| `recommended` | meta: `console` + `pandas` + `datetime` + `notebook` + `plotting` + `secrets` |
| `all`         | Every runtime extra                                                           |

Full details: [docs/guides/dependency-groups.md](docs/guides/dependency-groups.md).

## Documentation

- [Getting Started](docs/getting-started.md)
- [Development](docs/guides/development.md)
- [Testing](docs/guides/testing.md)
- [Documentation](docs/guides/documentation.md)
- [Roadmap](docs/roadmap.md) — translated from the legacy `.todo` file
- [Changelog](docs/changelog.md)
- [API Reference](https://mayurankv.github.io/mayutils/reference/) — auto-generated from docstrings

## Contributing

See the [contributing guide](docs/contributing.md) for setup, commit conventions (Conventional Commits), and release flow.

## License

MIT — see [LICENSE](LICENSE).
