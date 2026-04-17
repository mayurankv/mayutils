# Dependency Groups

`mayutils` is organised so that the core package stays light and heavy or domain-specific dependencies live in [extras](https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras). Install only what you need.

## Core

Always installed: `numpy`, `pandas`, `pyarrow`, `pydantic`, `pydantic-settings`, `python-dotenv`, `requests`, `rich`.

These back `mayutils.core`, `mayutils.objects.*` (except where noted below), `mayutils.mathematics.numpy`, `mayutils.environment.logging`, and `mayutils.environment.secrets`.

## Extras

The table below is **generated at docs build time** from `[project.optional-dependencies]` and `[tool.mayutils.extras.module-overrides]` in `pyproject.toml` — it's always in sync with the installed package.

<!-- BEGIN AUTO-GENERATED GROUPS TABLE -->

| Extra         | Install                          | Distributions                                                                                                                                                                                                                      |
| ------------- | -------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `all`         | `uv add "mayutils[all]"`         | meta: `async` + `cli` + `dataframes` + `datetime` + `filesystem` + `google` + `keyring` + `microsoft` + `notebook` + `pdf` + `plotting` + `snowflake` + `stats` + `streamlit` + `web`                                              |
| `async`       | `uv add "mayutils[async]"`       | `asyncer`                                                                                                                                                                                                                          |
| `cli`         | `uv add "mayutils[cli]"`         | `cookiecutter`, `typer`                                                                                                                                                                                                            |
| `dataframes`  | `uv add "mayutils[dataframes]"`  | `modin`, `polars`                                                                                                                                                                                                                  |
| `datetime`    | `uv add "mayutils[datetime]"`    | `pendulum`                                                                                                                                                                                                                         |
| `filesystem`  | `uv add "mayutils[filesystem]"`  | `gitpython`, `watchdog`                                                                                                                                                                                                            |
| `google`      | `uv add "mayutils[google]"`      | `google-api-python-client`, `google-auth`, `google-auth-httplib2`, `google-auth-oauthlib`, `google-cloud-storage`                                                                                                                  |
| `keyring`     | `uv add "mayutils[keyring]"`     | `keyring`                                                                                                                                                                                                                          |
| `microsoft`   | `uv add "mayutils[microsoft]"`   | `openpyxl`, `python-pptx`                                                                                                                                                                                                          |
| `notebook`    | `uv add "mayutils[notebook]"`    | `ipykernel`, `itables`, `jupyter`, `jupysql`, `nbconvert`, `unicodeit`                                                                                                                                                             |
| `pdf`         | `uv add "mayutils[pdf]"`         | `pillow`, `pymupdf`                                                                                                                                                                                                                |
| `plotting`    | `uv add "mayutils[plotting]"`    | `dataframe-image`, `great-tables`, `html2image`, `kaleido`, `markdown`, `matplotlib`, `mistune`, `pillow`, `plotly`, `scipy`                                                                                                       |
| `recommended` | `uv add "mayutils[recommended]"` | meta: `dataframes` + `datetime` + `notebook` + `plotting` + `stats`                                                                                                                                                                |
| `snowflake`   | `uv add "mayutils[snowflake]"`   | `snowflake-connector-python`, `snowflake-sqlalchemy`, `sqlalchemy`                                                                                                                                                                 |
| `stats`       | `uv add "mayutils[stats]"`       | `numba`, `numpy-financial`, `scikit-learn`, `scipy`                                                                                                                                                                                |
| `streamlit`   | `uv add "mayutils[streamlit]"`   | `streamlit`                                                                                                                                                                                                                        |
| `types`       | `uv add "mayutils[types]"`       | `pandas-stubs`, `scipy-stubs`, `types-cachetools`, `types-decorator`, `types-markdown`, `types-openpyxl`, `types-pycurl`, `types-python-dateutil`, `types-pyyaml`, `types-requests`, `types-simplejson`, `types-six`, `types-toml` |
| `web`         | `uv add "mayutils[web]"`         | `chromedriver-autoinstaller`, `playwright`, `selenium`                                                                                                                                                                             |

<!-- END AUTO-GENERATED GROUPS TABLE -->

### Submodule Mapping

| Extra         | Primary submodules unlocked                                                                         |
| ------------- | --------------------------------------------------------------------------------------------------- |
| `plotting`    | `visualisation.graphs.plotly`, `visualisation.graphs.matplotlib`, `export.html`                     |
| `notebook`    | `visualisation.notebook`, `visualisation.console`, `itables`, Jupyter kernels                       |
| `dataframes`  | Polars / Modin backends in `data.read` and `objects.dataframes`                                     |
| `stats`       | `mathematics.numba`, scikit-learn, scipy, numpy-financial                                           |
| `google`      | `interfaces.google` (Drive, Sheets, Cloud Storage) and `environment.oauth`                          |
| `microsoft`   | `interfaces.microsoft.powerpoint`, openpyxl export                                                  |
| `snowflake`   | `environment.databases` Snowflake engine + SQLAlchemy                                               |
| `streamlit`   | `interfaces.streamlit`                                                                              |
| `web`         | `environment.webdrivers` (Selenium, Playwright, Chromedriver)                                       |
| `pdf`         | `interfaces.pdf`, `visualisation.graphs.combine` (PyMuPDF + Pillow)                                 |
| `datetime`    | Pendulum-backed helpers in `objects.datetime` and `objects.hashing`                                 |
| `cli`         | `scripts.clear_cache` (Typer), cookiecutter scaffolding                                             |
| `filesystem`  | `environment.filesystem` git-aware helpers, watchdog file watchers                                  |
| `keyring`     | OS keyring integration used by `environment.oauth`                                                  |
| `async`       | `asyncer` helpers                                                                                   |
| `types`       | Type stubs for dev-time checking                                                                    |
| `recommended` | Meta: `plotting` + `notebook` + `dataframes` + `datetime` + `stats` — the default data-analysis set |
| `all`         | Every runtime extra above                                                                           |

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

Any submodule that imports from an optional extra at module level **must** wrap those imports with :class:`mayutils.core.extras.requires_extras`:

```python
from mayutils.core.extras import requires_extras

with requires_extras("plotting"):
    import plotly.graph_objects as go
    from scipy.stats import gaussian_kde
```

Passing the extras explicitly makes the hint authoritative even when the failing module name isn't in the override table (e.g. for namespaced Google / Snowflake imports). When the submodule spans multiple extras, list them all:

```python
with requires_extras("plotting", "microsoft"):
    from PIL.ImageColor import getrgb
    from pptx.dml.color import RGBColor
```

If no extras are passed, `requires_extras()` falls back to auto-resolution via :func:`mayutils.core.extras.extras_for_module` — useful for ad-hoc use but less precise.
