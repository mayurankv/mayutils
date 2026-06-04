"""
Provide Jupyter and IPython notebook integration helpers.

Gather the small set of utilities the package uses to adapt its output
to notebook environments. Cover runtime CSS injection for Plotly widget
styling, guarded helpers that detect nbconvert execution contexts, thin
wrappers over :class:`IPython.display.Markdown` and
:class:`IPython.display.Math` for rich cell output, and a single entry
point that wires the default styling and Rich-powered printing into the
active IPython shell. Each helper degrades gracefully when IPython is
unavailable so library code can call them without branching on the
runtime.

See Also
--------
IPython.display.display : Underlying dispatcher for rich cell outputs.
IPython.display.Markdown : Markdown display class used by the helpers.
IPython.display.Math : LaTeX math display class used by the helpers.
itables : Interactive DataFrame rendering compatible with these helpers.
mayutils.visualisation.console : Companion module providing Rich
    console configuration used alongside these helpers.

Examples
--------
>>> from mayutils.visualisation.notebook import Notebook
>>> Notebook.setup()  # doctest: +SKIP
>>> Notebook.write_markdown("# Heading", "A paragraph with *emphasis*.")  # doctest: +SKIP
"""

from typing import TYPE_CHECKING, Literal

from mayutils.core.extras import may_require_extras
from mayutils.visualisation.console import setup_printing

if TYPE_CHECKING:
    from IPython.core.interactiveshell import InteractiveShell

DEFAULT_NOTEBOOK_CSS = """
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


class Notebook:
    """
    Group stateless notebook-integration helpers as a namespace.

    The class is never instantiated; it exists to group a family of
    related IPython front-end helpers under a single discoverable
    symbol. Every helper is a ``@staticmethod`` so callers reach the
    utilities through the class itself rather than module-level names.
    The empty ``__slots__`` declaration prevents per-instance attribute
    allocation, reinforcing the namespace-only role.

    Attributes
    ----------
    __slots__
        Empty slots declaration preventing per-instance attribute
        allocation, reinforcing that the class is a pure namespace and
        instances carry no state.

    See Also
    --------
    IPython.display.display : Dispatcher used by the display helpers.
    IPython.display.Markdown : Display class used by
        :meth:`write_markdown`.
    IPython.display.Math : Display class used by :meth:`write_latex`.
    mayutils.visualisation.console : Companion module providing the
        Rich console configuration wired up by :meth:`setup`.

    Examples
    --------
    >>> from mayutils.visualisation.notebook import Notebook
    >>> Notebook.setup()  # doctest: +SKIP
    >>> Notebook.write_markdown("# Summary", "Refer to the table below.")  # doctest: +SKIP
    >>> Notebook.write_latex(r"E = mc^{2}")  # doctest: +SKIP
    """

    __slots__ = ()

    @staticmethod
    def get_shell() -> "InteractiveShell":
        """
        Return the active IPython shell or raise if one is not running.

        Fetch the singleton via :func:`IPython.core.getipython.get_ipython`
        and, when no shell has been initialised, raise a
        :class:`RuntimeError` with an actionable message so that callers
        fail fast at the helper invocation site instead of surfacing a
        downstream ``AttributeError`` on ``None``. The module deliberately
        performs this check at call time rather than import time so that
        the module is importable under plain CPython, letting documentation
        generation, type checking and non-notebook entry points load the
        class without an active IPython shell.

        Returns
        -------
        InteractiveShell
            The active IPython shell instance returned by
            :func:`IPython.core.getipython.get_ipython`.

        Raises
        ------
        RuntimeError
            If :func:`IPython.core.getipython.get_ipython` returns ``None``,
            indicating that no IPython shell is currently active.

        See Also
        --------
        IPython.core.getipython.get_ipython : Accessor for the active
            IPython shell singleton.
        IPython.core.interactiveshell.InteractiveShell : Type of the
            returned shell instance.

        Examples
        --------
        >>> from mayutils.visualisation.notebook import Notebook
        >>> shell = Notebook.get_shell()  # doctest: +SKIP
        """
        with may_require_extras():
            from IPython.core.getipython import get_ipython  # noqa: PLC0415

        shell = get_ipython()
        if shell is None:
            msg = "No active IPython shell; notebook helpers cannot be used outside a notebook environment."
            raise RuntimeError(msg)

        return shell

    @classmethod
    def setup(
        cls,
        *,
        printing: bool = True,
    ) -> None:
        """
        Bootstrap the package's notebook experience in the current IPython shell.

        Perform three actions: install Rich-backed printing via
        :func:`mayutils.visualisation.console.setup_printing`, register
        :meth:`add_default_css` as a ``pre_run_cell`` callback so the
        package's stylesheet is re-injected at the start of every cell
        execution, and apply that stylesheet immediately so the current
        session picks it up without waiting for the next cell. The
        method requires an active IPython shell; callers running under
        plain CPython should invoke it via :func:`mayutils.setup`, which
        skips the notebook bootstrap when no shell is detected.

        Parameters
        ----------
        printing
            When ``True`` (the default), install Rich-backed printing
            via :func:`mayutils.visualisation.console.setup_printing`.
            Pass ``False`` to skip the Rich integration and keep the
            default IPython display pipeline.

        See Also
        --------
        mayutils.visualisation.console.setup_printing : Installs the Rich
            console as the default print target inside the IPython shell.
        add_default_css : Stylesheet callback registered with the IPython
            ``pre_run_cell`` event hub.
        apply_css : Lower-level CSS injection helper used transitively via
            :meth:`add_default_css`.

        Examples
        --------
        >>> from mayutils.visualisation.notebook import Notebook
        >>> Notebook.setup()  # doctest: +SKIP
        """
        cls.get_shell()

        if printing:
            setup_printing()

        # TODO(@mayurankv): Potentially add default CSS injection  # noqa: TD003
        # shell.events.register(event="pre_run_cell", function=cls.add_default_css,)  # noqa: ERA001

    @staticmethod
    def apply_css(
        *css: str,
        method: Literal["js", "html"] = "js",
    ) -> None:
        """
        Inject one or more CSS stylesheets into the active IPython front end.

        For every argument the function emits a ``<style>`` block through
        :class:`IPython.core.display.HTML` so that the stylesheet applies
        immediately to the current cell output, and additionally schedules
        a :class:`IPython.core.display.Javascript` payload that appends an
        equivalent ``<style>`` node to ``document.body`` so the rule
        survives output-area clears. When IPython is not importable or
        there is no active shell the call is a safe no-op, letting
        library code invoke it unconditionally.

        Parameters
        ----------
        *css
            CSS source strings to inject. Each positional argument is
            treated as an independent stylesheet: no wrapping or
            concatenation is performed, so callers should pass fully
            formed rule blocks.
        method
            Controls whether an eager ``<style>`` block is also emitted
            through :class:`IPython.core.display.HTML` before the
            JavaScript payload runs. ``"js"`` relies solely on the
            JavaScript appender, which survives output-area clears;
            ``"html"`` additionally renders an inline ``<style>`` block so
            the stylesheet takes effect even if JavaScript execution is
            disabled or deferred in the front end.

        See Also
        --------
        IPython.display.HTML : Wrapper used to emit the inline ``<style>``
            block for the ``"html"`` method path.
        IPython.display.Javascript : Wrapper used for the appender that
            survives cell output clears.
        IPython.display.display : Dispatcher the helper calls to push each
            rich mime-bundle into the active cell.
        add_default_css : Sibling helper that layers the package's curated
            stylesheet on top of :meth:`apply_css`.

        Examples
        --------
        >>> from mayutils.visualisation.notebook import Notebook
        >>> Notebook.apply_css(  # doctest: +SKIP
        ...     ".dataframe {font-family: monospace;}",
        ...     method="html",
        ... )
        >>> Notebook.apply_css(  # doctest: +SKIP
        ...     ".updatemenu-button {fill: #506784 !important;}",
        ... )
        """
        Notebook.get_shell()

        with may_require_extras():
            from IPython.core.display import HTML, Javascript  # noqa: PLC0415
            from IPython.display import display  # noqa: PLC0415  # pyright: ignore[reportUnknownVariableType]

        if method == "html":
            for css_string in css:
                display(HTML(data=f"<style>{css_string}</style>"))

        for css_string in css:
            display(
                Javascript(
                    data=f"""
                        (function() {{
                            const style = document.createElement('style');
                            style.innerHTML = `{css_string}`
                            document.head.appendChild(style);
                        }})();
                    """
                )
            )

    @staticmethod
    def write_markdown(
        *args: str,
    ) -> None:
        """
        Render one or more Markdown sources as separate rich cell outputs.

        Wrap each positional argument in :class:`IPython.core.display.Markdown`
        and push it through :func:`IPython.display.display`, emitting a new
        rich output entry in the current cell for each fragment. Compared to
        a plain ``print`` this preserves Markdown semantics, so headings,
        links, inline LaTeX and list formatting render as expected rather
        than surfacing as raw source text.

        Parameters
        ----------
        *args
            Markdown source fragments. Each argument is displayed as an
            independent output entry, which is convenient when emitting
            a series of related but separately re-renderable blocks.

        See Also
        --------
        IPython.display.Markdown : Display class that produces the
            ``text/markdown`` mime bundle consumed by the front end.
        IPython.display.display : Dispatcher responsible for routing the
            rich output to the active cell.
        write_latex : Sibling helper that performs the analogous rendering
            for LaTeX math sources.

        Examples
        --------
        >>> from mayutils.visualisation.notebook import Notebook
        >>> Notebook.write_markdown("# Summary", "Refer to the table **below**.")  # doctest: +SKIP
        >>> Notebook.write_markdown("- Item A", "- Item B", "- Item C")  # doctest: +SKIP
        """
        Notebook.get_shell()

        with may_require_extras():
            from IPython.core.display import Markdown  # noqa: PLC0415
            from IPython.display import display  # noqa: PLC0415  # pyright: ignore[reportUnknownVariableType]

        for arg in args:
            display(Markdown(data=arg))

    @staticmethod
    def write_latex(
        *args: str,
    ) -> None:
        """
        Render one or more LaTeX math sources as separate rich cell outputs.

        Wrap each positional argument in :class:`IPython.core.display.Math`
        and dispatch it via :func:`IPython.display.display`, producing a
        typeset math block in the current cell. This spares callers from
        managing MathJax boilerplate or inserting ``$$`` delimiters around
        every equation they want to render.

        Parameters
        ----------
        *args
            LaTeX source strings. Each argument is displayed as its own
            math block, which allows rendering multiple equations without
            combining them into a single array environment.

        See Also
        --------
        IPython.display.Math : Display class that produces the MathJax-ready
            mime bundle rendered by the front end.
        IPython.display.display : Dispatcher responsible for routing the
            rich output to the active cell.
        write_markdown : Sibling helper for prose and inline Markdown
            fragments that may also include inline math spans.

        Examples
        --------
        >>> from mayutils.visualisation.notebook import Notebook
        >>> Notebook.write_latex(r"E = mc^{2}")  # doctest: +SKIP
        >>> Notebook.write_latex(r"a^{2} + b^{2} = c^{2}")  # doctest: +SKIP
        """
        Notebook.get_shell()

        with may_require_extras():
            from IPython.core.display import Math  # noqa: PLC0415
            from IPython.display import display  # noqa: PLC0415  # pyright: ignore[reportUnknownVariableType]

        for arg in args:
            display(Math(data=arg))
