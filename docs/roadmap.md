# Roadmap

## Tooling

Priority: #critical

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

### Plots

Priority: #critical

- [ ] `trace_info` `@property` to infer colour / trace type from a trace, and refactor callers to consume it. #critical

- [ ] `Subplot.from_plots` `@classmethod` using double-nested array notation for rows/columns. #critical

- [ ] Error bounds #critical

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

- [ ] Marginals and rugs #critical

    - [ ] Rugs — add histogram type ([2D histogram contour](https://plotly.com/python/2d-histogram-contour/))
    - [ ] Convert rugs to work independently for x and y axis depending on trace type
        - [ ] 2D: Scatter ([2D histogram contour](https://plotly.com/python/2d-histogram-contour/))
        - [ ] 1D: Histogram

- [ ] 3D Histogram #critical #high — heatmap / contour alternative.

- [ ] Categorical 3D axes #critical #medium ([docs](https://plotly.com/python/categorical-axes/))

- [ ] Animations #low

    - [Plotly animations](https://plotly.com/python/animations/)
    - [Single-subplot animations](https://community.plotly.com/t/single-subplot-animations/35235/2)
    - [Animating traces in subplots](https://plotly.com/~empet/15243/animating-traces-in-subplotsbr/#/)

- [ ] Subplot enlargement #low #hard

    - [ ] Plot from subplot axis + traces ([forum](https://community.plotly.com/t/how-to-remove-subplots-or-create-new-plot-from-a-subplot/72117/2))
    - [ ] Zoom-in behaviour
        - [CodePen A](https://codepen.io/saratoga01/pen/QwWydeV)
        - [CodePen B](https://codepen.io/saratoga01/pen/WbNQygR)
        - [Extract / highlight a subplot](https://community.plotly.com/t/make-subplots-extract-highlight-one-subplot/74188/2)
    - [ ] Full-screen button (Streamlit parity)
        - [plotly.js#6287](https://github.com/plotly/plotly.js/issues/6287)
        - [gist: p1-rde fullscreen helper](https://gist.github.com/p1-rde/2120938f1c7f44c26755cfd83f8562e8)

### Classification plots

Priority: #low

- [ ] [KNN classification](https://plotly.com/python/knn-classification/)
- [ ] [ROC & PR curves](https://plotly.com/python/roc-and-pr-curves/)
- [ ] [PCA visualisation](https://plotly.com/python/pca-visualization/)
- [ ] [SHAP values explainer](https://towardsdatascience.com/using-shap-values-to-explain-how-your-machine-learning-model-works-732b3f40e137/)

### Maps

Priority: #low

- [ ] [Map subplots & small multiples](https://plotly.com/python/map-subplots-and-small-multiples/)
- [ ] [Tile county choropleths](https://plotly.com/python/tile-county-choropleth/)
- [ ] [Tile scatter maps](https://plotly.com/python/tile-scatter-maps/)
- [ ] [Map configuration](https://plotly.com/python/map-configuration/)
- [ ] [Scatter plots on maps](https://plotly.com/python/scatter-plots-on-maps/)
- [ ] [Density heatmaps](https://plotly.com/python/density-heatmaps/)
- [ ] [Choropleth maps](https://plotly.com/python/choropleth-maps/)

### Logging

Priority: #critical

- [ ] Classmethod / staticmethod to change the default logging level.
- [ ] Re-add a file handler to the logger.
- [ ] Surface `logger.name` in the rich handler output ([rich#850](https://github.com/Textualize/rich/issues/850)).

### Pydantic

Priority: #low

- Reference: [`model_construct`](https://docs.pydantic.dev/latest/api/base_model/#pydantic.BaseModel.model_construct)
- Reference: [ecosystem](https://docs.pydantic.dev/latest/why/#ecosystem)
- [ ] Set up a couple of things using pydantic.
- [ ] Translate dataclasses to pydantic dataclasses where helpful.
- [ ] Explore `BaseModel`.

### Decorators

Priority: #low

- [ ] Implement other broadly-useful decorators as they come up.

### Classes

Priority: #low

- [ ] Add default class methods.

### Tables

Priority: #low

- [ ] Great Tables theming ([theme options](https://posit-dev.github.io/great-tables/get-started/table-theme-options.html))

### DataFrames

Priority: #low

- [ ] Polars functionality (wait until the surrounding code is more familiar with it).

### Mathematics

Priority: #low

- [ ] JIT compilation with [numba](https://numba.pydata.org/numba-doc/dev/user/jit.html).

### Filesystem / Webdrivers

Priority: #low

- [ ] Fix Chrome webdriver #hard — fix all Chromium variants.
- [ ] Fix Firefox webdriver #hard.

### Apps

Priority: #low

- [ ] [Typer](https://typer.tiangolo.com)
- [ ] Streamlit exploration

## Understand

Priority: #low

- [pyutils reference](https://github.com/scottgasch/pyutils)
- [What is a data lake? (AWS)](https://aws.amazon.com/what-is/data-lake/)

## Tools

Priority: #low

### Drawing

- [tldraw](https://www.tldraw.com/)
- [Excalidraw](https://excalidraw.com)

### Writing

- [StackEdit](https://stackedit.io/)
