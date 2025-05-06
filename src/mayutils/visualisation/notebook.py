import os
from typing import Optional


from IPython.display import display
from IPython.core.display import Markdown, Math

from mayutils.core.constants import DISPLAY_TYPE_ENV_VAR
from mayutils.visualisation.console import setup_printing


def apply_css(
    *css,
) -> None:
    try:
        from IPython import get_ipython  # type: ignore
        from IPython.display import display
        from IPython.core.display import HTML, Javascript

        ipython = get_ipython()

        if ipython is not None:
            for css_string in css:
                Javascript(
                    """
                        (function() {
                            const style = document.createElement('style');
                            style.innerHTML = `{css_to_fill}`
                            document.body.appendChild(style);
                        })();
                    """.replace("{css_to_fill}", css_string)
                )
                display(HTML(data="<style>" + css_string + "</style>"))

    except ImportError:
        pass


def is_interactive() -> bool:
    return os.getenv(key=DISPLAY_TYPE_ENV_VAR, default=None) is None


def export(
    slides: bool = True,
    file_name: str = "report.ipynb",
    title: Optional[str] = None,
) -> None:
    from mayutils.export.slides import export_slides

    if slides:
        export_slides(
            file_name=file_name,
            title=title,
        )


def write_markdown(
    *args,
) -> None:
    for arg in args:
        display(Markdown(data=arg))


def write_latex(
    *args,
) -> None:
    for arg in args:
        display(Math(data=arg))


def add_default_css(
    *args,
    **kwargs,
) -> None:
    # from IPython.display import clear_output
    apply_css(
        """
            .cell-output-ipywidget-background {
                background-color: transparent !important;
            }
            .jp-OutputArea-output {
                background-color: transparent;
            }
            .updatemenu-button > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"],
            .updatemenu-header > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"],
            .updatemenu-dropdown-button > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"] {
                fill: rgba(80, 103, 132, 0.4) !important;
            }
            .updatemenu-button:hover > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"],
            .updatemenu-header:hover > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"],
            .updatemenu-dropdown-button:hover > rect.updatemenu-item-rect[style*="fill: rgb(244, 250, 255)"] {
                fill: rgba(80, 103, 132, 0.6) !important;
            }
        """
    )
    # with replace_print(PRINT):
    #     ipython.run_line_magic("clear", "")
    # clear_output(wait=True)
    # original_print("\033[2K\r", end="")


def setup_notebooks() -> None:
    try:
        from IPython import get_ipython  # type: ignore

        ipython = get_ipython()

        if ipython is not None:
            from mayutils.visualisation.notebook import add_default_css

            setup_printing()
            ipython.events.register("pre_run_cell", add_default_css)
            add_default_css()

    except ImportError:
        pass
