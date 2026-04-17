# Roadmap

Translated from the legacy `.todo` file. Priority tags carry through: **critical**, **high**, **medium**, **low**, **hard** indicates difficulty rather than priority. Use `- [ ]` / `- [x]` checkboxes — they are interactive in the mkdocs site.

## Tooling (critical)

### Presentations

- [ ] Improve the Presentation text interface
    - [ ] Ingest text directly from Markdown
    - Reference: [python-pptx#1019](https://github.com/scanny/python-pptx/issues/1019)
    - Reference: [md2pptx user guide](https://github.com/MartinPacker/md2pptx/blob/master/docs/user-guide.md)
    - Reference: [python-pptx bullet search](https://python-pptx.readthedocs.io/en/latest/search.html?q=bullet&check_keywords=yes&area=default)
    - Reference: [python-pptx movie analysis](https://python-pptx.readthedocs.io/en/latest/dev/analysis/shp-movie.html?highlight=animation)

### Tables

- [ ] Add `itables` support
    - Reference: [quick start](https://mwouts.github.io/itables/quick_start.html)
    - Reference: [formatting](https://mwouts.github.io/itables/formatting.html)

### Numbers

- [ ] Prettify: SI units and configurable decimal places.

### Plots (critical)

- [ ] `trace_info` `@property` to infer colour / trace type from a trace, and refactor callers to consume it. **critical**

- [ ] `Subplot.from_plots` `@classmethod` using double-nested array notation for rows/columns. **critical**

- [ ] Error bounds **critical**

    - [ ] Fan Chart — new `Fan` trace type

    - [ ] Scatter-style error bounds

        ```python
        go.Scatter(
            x=[1, 2, 3, 4],
            y=[2, 1, 3, 4],
            error_y=dict(
                type="data",
                symmetric=False,
                array=[0.1, 0.2, 0.1, 0.1],
                arrayminus=[0.2, 0.4, 1, 0.2],
            ),
        )
        ```

- [ ] Marginals and rugs **critical**

    - [ ] Rugs — add histogram type ([2D histogram contour](https://plotly.com/python/2d-histogram-contour/))
    - [ ] Convert rugs to work independently for x and y axis depending on trace type
        - [ ] 2D: Scatter ([2D histogram contour](https://plotly.com/python/2d-histogram-contour/))
        - [ ] 1D: Histogram

- [ ] 3D Histogram **critical, high** — heatmap / contour alternative.

- [ ] Categorical 3D axes **critical, medium** ([docs](https://plotly.com/python/categorical-axes/))

- [ ] Animations **low**

    - [Plotly animations](https://plotly.com/python/animations/)
    - [Single-subplot animations](https://community.plotly.com/t/single-subplot-animations/35235/2)
    - [Animating traces in subplots](https://plotly.com/~empet/15243/animating-traces-in-subplotsbr/#/)

- [ ] Subplot enlargement **low, hard**

    - [ ] Plot from subplot axis + traces ([forum](https://community.plotly.com/t/how-to-remove-subplots-or-create-new-plot-from-a-subplot/72117/2))
    - [ ] Zoom-in behaviour
        - [CodePen A](https://codepen.io/saratoga01/pen/QwWydeV)
        - [CodePen B](https://codepen.io/saratoga01/pen/WbNQygR)
        - [Extract / highlight a subplot](https://community.plotly.com/t/make-subplots-extract-highlight-one-subplot/74188/2)
    - [ ] Full-screen button (Streamlit parity)
        - [plotly.js#6287](https://github.com/plotly/plotly.js/issues/6287)
        - [gist: p1-rde fullscreen helper](https://gist.github.com/p1-rde/2120938f1c7f44c26755cfd83f8562e8)

### Classification plots (low)

- [ ] [KNN classification](https://plotly.com/python/knn-classification/)
- [ ] [ROC & PR curves](https://plotly.com/python/roc-and-pr-curves/)
- [ ] [PCA visualisation](https://plotly.com/python/pca-visualization/)
- [ ] [SHAP values explainer](https://towardsdatascience.com/using-shap-values-to-explain-how-your-machine-learning-model-works-732b3f40e137/)

### Maps (low)

- [ ] [Map subplots & small multiples](https://plotly.com/python/map-subplots-and-small-multiples/)
- [ ] [Tile county choropleths](https://plotly.com/python/tile-county-choropleth/)
- [ ] [Tile scatter maps](https://plotly.com/python/tile-scatter-maps/)
- [ ] [Map configuration](https://plotly.com/python/map-configuration/)
- [ ] [Scatter plots on maps](https://plotly.com/python/scatter-plots-on-maps/)
- [ ] [Density heatmaps](https://plotly.com/python/density-heatmaps/)
- [ ] [Choropleth maps](https://plotly.com/python/choropleth-maps/)

### Logging (critical)

- [ ] Classmethod / staticmethod to change the default logging level.
- [ ] Re-add a file handler to the logger.
- [ ] Surface `logger.name` in the rich handler output ([rich#850](https://github.com/Textualize/rich/issues/850)).

### Pydantic (low)

- Reference: [`model_construct`](https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_construct)
- Reference: [ecosystem](https://docs.pydantic.dev/latest/why/#ecosystem)
- [ ] Set up a couple of things using pydantic.
- [ ] Translate dataclasses to pydantic dataclasses where helpful.
- [ ] Explore `BaseModel`.

### Decorators (low)

- [ ] Implement other broadly-useful decorators as they come up.

### Classes (low)

- [ ] Add default class methods.

### Tables (low)

- [ ] Great Tables theming ([theme options](https://posit-dev.github.io/great-tables/get-started/table-theme-options.html))

### DataFrames (low)

- [ ] Polars functionality (wait until the surrounding code is more familiar with it).

### Mathematics (low)

- [ ] JIT compilation with [numba](https://numba.pydata.org/numba-doc/dev/user/jit.html).

### Filesystem / Webdrivers (low)

- [ ] Fix Chrome webdriver **hard** — fix all Chromium variants.
- [ ] Fix Firefox webdriver **hard**.

### Apps (low)

- [ ] [Typer](https://typer.tiangolo.com)
- [ ] Streamlit exploration

### Package (medium)

- [x] Set `[project.optional-dependencies]` (done 2026-04 — heavy deps split into extras).
    - Ensure the package is still safe to use without additional dependencies, and also when used from plain Python rather than IPython.

## Productivity (medium)

### Assistive AI

- [ ] Cursor — set up (**critical**)
- [ ] [Cline](https://cline.bot/) — set up (**high**)
    - Gather rules:
        - [Cursor rules](https://docs.cursor.com/context/rules)
        - [cursorrules.org](https://www.cursorrules.org)
        - [awesome-cursorrules](https://github.com/PatrickJS/awesome-cursorrules)
        - Search `cursorrules`
- [ ] Copilot
    - Rules:
        - [Personal custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-personal-custom-instructions-for-github-copilot)
        - [Repository custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot)
    - [Customize the Copilot coding agent env](https://docs.github.com/en/copilot/customizing-copilot/customizing-the-development-environment-for-copilot-coding-agent)
    - [ ] Understand Copilot Workspace
        - [Project page](https://githubnext.com/projects/copilot-workspace/)
        - [User manual](https://github.com/githubnext/copilot-workspace-user-manual)
    - Agents:
        - [GitBook for Copilot](https://github.com/marketplace/gitbook-for-github-copilot)
        - [Docker for Copilot](https://github.com/marketplace/docker-for-github-copilot)
    - Models:
        - [Marketplace models](https://github.com/marketplace/models)
        - [All models](https://github.com/marketplace?type=models)
    - Prompts:
        - [Enabling or disabling repo custom instructions](https://docs.github.com/en/copilot/customizing-copilot/adding-repository-custom-instructions-for-github-copilot#enabling-or-disabling-repository-custom-instructions)
- [ ] Obsidian
- Reading: [ChatGPTCoding comparison thread](https://www.reddit.com/r/ChatGPTCoding/comments/1ilg9zl/cursor_vs_aider_vs_vscode_copilot_which_ai_coding/)

## Understand (low)

- [pyutils reference](https://github.com/scottgasch/pyutils)
- [What is a data lake? (AWS)](https://aws.amazon.com/what-is/data-lake/)

## Tools (low)

### Drawing

- [tldraw](https://www.tldraw.com/)
- [Excalidraw](https://excalidraw.com)

### Writing

- [StackEdit](https://stackedit.io/)
