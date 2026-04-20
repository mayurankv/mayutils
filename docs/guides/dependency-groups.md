# Dependency Groups

`mayutils` is organised so that the core package stays light and heavy or domain-specific dependencies live in [extras](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras). Install only what you need.

## Core

Always installed: `pydantic`, `pydantic-settings`.

These back `mayutils.core`, the pure-Python helpers in `mayutils.objects.*` that do not depend on NumPy, and the extras-resolution machinery in `mayutils.core.extras`. Everything else — including NumPy, Rich console output, `python-dotenv` secrets loading, HTTP clients and dataframes — lives in an extra and must be opted into.

## Extras

The table below is **generated at docs build time** from `[project.optional-dependencies]` and `[tool.mayutils.extras.module-overrides]` in `pyproject.toml` — it's always in sync with the installed package.

<!-- BEGIN AUTO-GENERATED GROUPS TABLE -->

| Extra         | Install                          | Distributions                                                                                                                                                                                                                                                         |
| ------------- | -------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `all`         | `uv add "mayutils[all]"`         | meta: `async` + `cli` + `console` + `dataframes` + `datetime` + `filesystem` + `financials` + `google` + `mathematics` + `microsoft` + `notebook` + `numerics` + `pandas` + `pdf` + `plotting` + `secrets` + `snowflake` + `sql` + `statistics` + `streamlit` + `web` |
| `async`       | `uv add "mayutils[async]"`       | `asyncer`                                                                                                                                                                                                                                                             |
| `cli`         | `uv add "mayutils[cli]"`         | `cookiecutter`, meta: `console`, `typer`                                                                                                                                                                                                                              |
| `console`     | `uv add "mayutils[console]"`     | `rich`                                                                                                                                                                                                                                                                |
| `dataframes`  | `uv add "mayutils[dataframes]"`  | meta: `pandas`, `modin`, `polars`, `dask`                                                                                                                                                                                                                             |
| `datetime`    | `uv add "mayutils[datetime]"`    | meta: `numerics`, `pendulum`                                                                                                                                                                                                                                          |
| `filesystem`  | `uv add "mayutils[filesystem]"`  | `gitpython`, `watchdog`                                                                                                                                                                                                                                               |
| `financials`  | `uv add "mayutils[financials]"`  | meta: `numerics`, `numpy-financial`                                                                                                                                                                                                                                   |
| `google`      | `uv add "mayutils[google]"`      | `google-api-python-client`, `google-auth`, `google-auth-httplib2`, `google-auth-oauthlib`, `google-cloud-storage`                                                                                                                                                     |
| `mathematics` | `uv add "mayutils[mathematics]"` | meta: `numerics`, `sympy`, `numba`                                                                                                                                                                                                                                    |
| `microsoft`   | `uv add "mayutils[microsoft]"`   | `openpyxl`, `python-pptx`                                                                                                                                                                                                                                             |
| `notebook`    | `uv add "mayutils[notebook]"`    | `ipykernel`, `itables`, `jupyter`, `jupysql`, meta: `console`, `nbconvert`, `unicodeit`, `quarto-cli`                                                                                                                                                                 |
| `numerics`    | `uv add "mayutils[numerics]"`    | `numpy`                                                                                                                                                                                                                                                               |
| `pandas`      | `uv add "mayutils[pandas]"`      | meta: `numerics`, `pandas`, `pyarrow`                                                                                                                                                                                                                                 |
| `pdf`         | `uv add "mayutils[pdf]"`         | `pillow`, `pymupdf`                                                                                                                                                                                                                                                   |
| `plotting`    | `uv add "mayutils[plotting]"`    | meta: `numerics`, `dataframe-image`, `great-tables`, `html2image`, `kaleido`, `markdown`, `matplotlib`, `mistune`, `pillow`, `plotly`, `scipy`                                                                                                                        |
| `recommended` | `uv add "mayutils[recommended]"` | meta: `console` + `pandas` + `datetime` + `notebook` + `plotting` + `secrets`                                                                                                                                                                                         |
| `secrets`     | `uv add "mayutils[secrets]"`     | `python-dotenv`, `keyring`                                                                                                                                                                                                                                            |
| `snowflake`   | `uv add "mayutils[snowflake]"`   | meta: `sql`, `snowflake-connector-python`, `snowflake-sqlalchemy`                                                                                                                                                                                                     |
| `sql`         | `uv add "mayutils[sql]"`         | `sqlalchemy`                                                                                                                                                                                                                                                          |
| `statistics`  | `uv add "mayutils[statistics]"`  | meta: `numerics`, `scikit-learn`, `scipy`, `statsmodels`                                                                                                                                                                                                              |
| `streamlit`   | `uv add "mayutils[streamlit]"`   | `streamlit`                                                                                                                                                                                                                                                           |
| `types`       | `uv add "mayutils[types]"`       | `google-api-python-client-stubs`, `pandas-stubs`, `scipy-stubs`, `types-cachetools`, `types-decorator`, `types-markdown`, `types-openpyxl`, `types-pycurl`, `types-python-dateutil`, `types-pyyaml`, `types-requests`, `types-simplejson`, `types-six`, `types-toml`  |
| `web`         | `uv add "mayutils[web]"`         | `chromedriver-autoinstaller`, `playwright`, `selenium`                                                                                                                                                                                                                |

<!-- END AUTO-GENERATED GROUPS TABLE -->

### Submodule Mapping

| Extra         | Primary submodules unlocked                                                                                                      |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `plotting`    | `visualisation.graphs.plotly`, `visualisation.graphs.matplotlib`, `export.html`                                                  |
| `notebook`    | `visualisation.notebook`, `visualisation.console`, `itables`, Jupyter kernels, `export.quarto`, `export.nbconvert`               |
| `pandas`      | Pandas / PyArrow backends in `data.read` and `objects.dataframes`                                                                |
| `dataframes`  | Polars / Modin / Dask backends in `data.read` and `objects.dataframes` (transitively pulls in `pandas`)                          |
| `mathematics` | `mathematics.numba`, SymPy helpers                                                                                               |
| `statistics`  | scikit-learn, scipy, statsmodels                                                                                                 |
| `financials`  | numpy-financial helpers                                                                                                          |
| `google`      | `interfaces.filetypes.sheets`, `interfaces.filetypes.slides`, `interfaces.cloud.google` (Drive), and `environment.oauth`         |
| `microsoft`   | `interfaces.filetypes.pptx`, openpyxl export                                                                                     |
| `sql`         | SQLAlchemy engine plumbing in `environment.databases`                                                                            |
| `snowflake`   | `environment.databases` Snowflake engine (transitively pulls in `sql`)                                                           |
| `streamlit`   | `interfaces.streamlit`                                                                                                           |
| `web`         | `environment.webdrivers` (Selenium, Playwright, Chromedriver)                                                                    |
| `pdf`         | `interfaces.filetypes.pdf`, `visualisation.graphs.combine` (PyMuPDF + Pillow)                                                    |
| `datetime`    | Pendulum-backed helpers in `objects.datetime` and `objects.hashing`                                                              |
| `cli`         | `scripts.clear_cache` (Typer), cookiecutter scaffolding                                                                          |
| `filesystem`  | `environment.filesystem` git-aware helpers, watchdog file watchers                                                               |
| `async`       | `asyncer` helpers                                                                                                                |
| `numerics`    | NumPy-backed code paths (pulled in transitively by `pandas`, `datetime`, `plotting`, `mathematics`, `statistics`, `financials`)  |
| `console`     | `rich`-powered output in `environment.logging.Logger.configure`, `visualisation.console`, `scripts.clear_cache`, `export.slides` |
| `secrets`     | `environment.secrets.load_secrets`, `.env` fallback and OS keyring integration inside `environment.oauth`                        |
| `types`       | Type stubs for dev-time checking                                                                                                 |
| `recommended` | Meta: `console` + `pandas` + `datetime` + `notebook` + `plotting` + `secrets` — the default data-analysis set                    |
| `all`         | Every runtime extra above                                                                                                        |

## Import-time Safety

`mayutils.setup()` lazily attempts to configure notebook display, dataframe defaults, and plotly templates. Missing extras log a warning instead of raising — so installing just the core package will never crash at import.

```python
import mayutils

mayutils.setup()  # no plotting extra? silently skipped.
```

If you need a specific submodule to be available unconditionally, depend on the corresponding extra in your own project's `pyproject.toml`.

## Actionable Error Messages

When you import a submodule that needs an optional extra, `mayutils` re-raises the underlying `ImportError` with a hint pointing at the exact `mayutils[<extra>]` you need to install:

```pycon
>>> from mayutils.visualisation.graphs.plotly.charts import histogram
ImportError: No module named 'plotly'
Optional dependency 'plotly' is not installed. Install it with: uv add "mayutils[plotting]" (or pip install "mayutils[plotting]").
```

The mapping is resolved dynamically from `pyproject.toml`:

- **Extras → distributions** come from the installed package's `Requires-Dist` metadata (`Provides-Extra` + `extra == '<name>'` markers).
- **Distribution → importable modules** — `[tool.mayutils.extras.module-overrides]` is the source of truth for any distribution whose top-level module name doesn't match `dist.replace("-", "_")` (e.g. `scikit-learn` → `sklearn`, `python-pptx` → `pptx`, `pillow` → `PIL`).
- For installed distributions, `top_level.txt` provides a secondary source (no override needed for well-behaved packages).
- For everything else, `dist.replace("-", "_")` is the final fallback.

Add a new override whenever you introduce a dependency whose import name diverges — the runtime hint automatically picks it up.

## Writing a Heavy Submodule

Any submodule that imports from an optional extra at module level **must** wrap those imports with :func:`mayutils.core.extras.may_require_extras`:

```python
from mayutils.core.extras import may_require_extras

with may_require_extras():
    import plotly.graph_objects as go
    from scipy.stats import gaussian_kde
```

`may_require_extras` takes no arguments — the matching extra is auto-resolved from `pyproject.toml` at `ImportError` time via :func:`mayutils.core.extras.extras_for_module`, so you never need to keep the group name in sync by hand.

When you need to force a specific hint (e.g. because the failing module name isn't in the mapping, or you want to combine several extras in a single message), fall back to the lower-level :func:`mayutils.core.extras.requires_extras`:

```python
from mayutils.core.extras import requires_extras

with requires_extras("plotting", "microsoft"):
    from PIL.ImageColor import getrgb
    from pptx.dml.color import RGBColor
```
