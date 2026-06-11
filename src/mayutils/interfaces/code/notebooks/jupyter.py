"""
Expose ``mayutils`` query execution as IPython line and cell magics.

This module bridges the :func:`mayutils.data.read.read_query` pipeline
into interactive Jupyter sessions through a ``%sql`` / ``%%sql`` magic.
The magic renders ``{{ name }}`` Jinja template variables from
variables in the notebook's user namespace, executes the query through a
:class:`~mayutils.data.read.QueryReader`, and assigns the resulting
DataFrame back into the namespace under a caller-chosen name. The
reader defaults to a cached
:func:`mayutils.interfaces.data.get_env_reader` connection driven by
``SNOWFLAKE_*`` environment variables, but any reader satisfying the
protocol can be injected by naming a namespace variable with
``--reader``. Registration is opt-in, either explicitly via
:func:`setup_magic` or through the standard
``%load_ext mayutils.interfaces.code.notebooks.jupyter`` mechanism
handled by :func:`load_ipython_extension`.

See Also
--------
mayutils.data.read.read_query : Cached query execution invoked by the magic.
mayutils.data.read.QueryReader : Protocol the injected reader must satisfy.
mayutils.interfaces.data.get_env_reader : Environment-driven reader factory.
mayutils.objects.dataframes.backends.Backend : Token selecting the result backend.

Examples
--------
>>> from mayutils.interfaces.code.notebooks.jupyter import MagicUtils
>>> MagicUtils.magics["cell"]["sql"]
'sql'
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol, cast

from jinja2 import meta

from mayutils.core.extras import may_require_extras, requires_extras
from mayutils.data.queries.templating import get_environment
from mayutils.data.read import read_query
from mayutils.environment.logging import Logger
from mayutils.objects.dataframes.backends import Backend, DataFrames
from mayutils.objects.types import SQL

with requires_extras("notebook"):
    from IPython.core.getipython import get_ipython
    from IPython.core.magic import Magics, line_cell_magic, magics_class
    from IPython.core.magic_arguments import (
        argument,
        magic_arguments,
        parse_argstring,  # pyright: ignore[reportUnknownVariableType]
    )

with may_require_extras():
    import pandas as pd
    import polars as pl

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from IPython.core.interactiveshell import InteractiveShell

    from mayutils.data.read import QueryReader


logger = Logger.spawn()


class SqlArguments(Protocol):
    """
    Structural type of the parsed ``%sql`` magic arguments.

    Mirrors the :mod:`argparse` namespace produced by
    :func:`IPython.core.magic_arguments.parse_argstring` for the
    arguments declared on :meth:`MagicUtils.sql`, giving the magic body
    a fully typed view over the otherwise untyped namespace object.

    Attributes
    ----------
    var_name
        User-namespace variable name the resulting DataFrame is
        assigned to.
    reader
        User-namespace variable name holding the
        :class:`~mayutils.data.read.QueryReader` to execute with, or
        ``None`` to fall back to
        :func:`mayutils.interfaces.data.get_env_reader`.
    backend
        DataFrame backend library name (``"pandas"`` or ``"polars"``).
    query_string
        Remaining positional tokens: empty for the cell magic, and for
        the line magic either a single query-variable name or the
        whitespace-split query itself.

    See Also
    --------
    MagicUtils.sql : Magic whose parsed arguments take this shape.
    IPython.core.magic_arguments.parse_argstring : Producer of the namespace.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import SqlArguments
    >>> SqlArguments.__protocol_attrs__ == {"var_name", "reader", "backend", "query_string"}
    True
    """

    var_name: str
    reader: str | None
    backend: str
    query_string: list[str]


def resolve_backend(
    name: str,
    /,
) -> Backend[DataFrames]:
    """
    Resolve a backend name to its :class:`Backend` token.

    Maps the user-facing library names accepted by the ``--backend``
    magic argument onto the concrete
    :class:`~mayutils.objects.dataframes.backends.Backend` tokens that
    the data layer dispatches on.

    Parameters
    ----------
    name
        Backend library name; one of ``"pandas"`` or ``"polars"``.

    Returns
    -------
        Backend token wrapping the corresponding DataFrame class.

    Raises
    ------
    ValueError
        If *name* is not a supported backend library name.

    See Also
    --------
    mayutils.objects.dataframes.backends.Backend : The token type returned.
    mayutils.objects.dataframes.backends.default_backend : Pandas default token.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import resolve_backend
    >>> resolve_backend("pandas").name
    'pandas'
    >>> resolve_backend("polars").name
    'polars'
    """
    if name == "pandas":
        return cast("Backend[DataFrames]", Backend(pd.DataFrame))
    if name == "polars":
        return cast("Backend[DataFrames]", Backend(pl.DataFrame))

    msg = f"Unsupported backend: {name!r}"
    raise ValueError(msg)


def template_fields(
    query_string: str,
    /,
) -> tuple[str, ...]:
    """
    Extract the user-namespace variable names referenced by a template.

    Parses *query_string* as a Jinja template and collects its
    undeclared variables via
    :func:`jinja2.meta.find_undeclared_variables`, so that expressions
    using attribute access (``{{ config.table }}``) or indexing
    (``{{ tables[0] }}``) resolve to the variable that must exist in
    the namespace.

    Parameters
    ----------
    query_string
        Query template containing ``{{ name }}`` Jinja variables.

    Returns
    -------
        Sorted unique names of the undeclared template variables.

    See Also
    --------
    jinja2.meta.find_undeclared_variables : Underlying variable discovery.
    mayutils.data.queries.templating.get_environment : Source of the
        Jinja environment used for parsing.
    MagicUtils.sql : Magic that substitutes these fields from the namespace.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import template_fields
    >>> template_fields("SELECT * FROM {{ table }} WHERE id = {{ config.id }}")
    ('config', 'table')
    """
    return tuple(sorted(meta.find_undeclared_variables(ast=get_environment(()).parse(source=query_string))))


def resolve_query_string(
    query_tokens: Sequence[str],
    /,
    *,
    cell: str | None,
    user_ns: Mapping[str, Any],
) -> str:
    r"""
    Resolve the query template from the magic's line and cell inputs.

    Encodes the line/cell calling convention of :meth:`MagicUtils.sql`:
    a cell body is the template itself (and excludes inline tokens), a
    single line token names a user-namespace variable holding the
    template, and multiple line tokens are joined into an inline
    template.

    Parameters
    ----------
    query_tokens
        Positional query tokens parsed from the magic line.
    cell
        Cell body when invoked as a cell magic, ``None`` for the line
        magic.
    user_ns
        User namespace consulted when a single token names a query
        variable.

    Returns
    -------
        The query template to render and execute.

    Raises
    ------
    ValueError
        If a query string is passed alongside a cell body, no query is
        supplied as a line magic, or the named query variable is not
        defined in the user namespace.

    See Also
    --------
    MagicUtils.sql : Magic whose inputs are resolved here.
    template_fields : Discovery of substitution fields in the result.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import resolve_query_string
    >>> resolve_query_string([], cell="SELECT 1\n", user_ns={})
    'SELECT 1'
    >>> resolve_query_string(["my_query"], cell=None, user_ns={"my_query": "SELECT 2"})
    'SELECT 2'
    >>> resolve_query_string(["SELECT", "3"], cell=None, user_ns={})
    'SELECT 3'
    """
    if cell is not None and len(query_tokens) > 0:
        msg = "Cannot pass a query string when invoked as a cell magic"
        raise ValueError(msg)
    if cell is None and len(query_tokens) == 0:
        msg = "A query string or query variable name is required when invoked as a line magic"
        raise ValueError(msg)

    if cell is not None:
        return cell.strip()

    if len(query_tokens) == 1:
        try:
            return cast("str", user_ns[query_tokens[0]])
        except KeyError as err:
            msg = f"Query variable {err.args[0]!r} is not defined in the user namespace"
            raise ValueError(msg) from err

    return " ".join(query_tokens)


@magics_class
class MagicUtils(Magics):
    """
    IPython magics exposing the ``mayutils`` data layer in notebooks.

    Bundles the ``%sql`` / ``%%sql`` magic, which renders a query
    template from user-namespace variables, executes it through an
    injected :class:`~mayutils.data.read.QueryReader`, and assigns the
    resulting DataFrame back into the namespace. Register the class on a
    running shell with :func:`setup_magic` or
    ``%load_ext mayutils.interfaces.code.notebooks.jupyter``. The
    constructor is inherited unchanged from
    :class:`IPython.core.magic.Magics`, which binds the magics to the
    interactive shell they are registered on.

    Attributes
    ----------
    env_reader
        Cached fallback :class:`~mayutils.data.read.QueryReader` built
        by :func:`mayutils.interfaces.data.get_env_reader` the first
        time the magic runs without an explicit ``--reader``.

    See Also
    --------
    setup_magic : Register these magics on the current shell.
    load_ipython_extension : ``%load_ext`` entry point doing the same.
    mayutils.data.read.read_query : Execution pipeline behind the magic.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import MagicUtils
    >>> MagicUtils.magics["line"]["sql"]
    'sql'
    """

    env_reader: QueryReader | None = None

    def resolve_reader(
        self,
        reader_name: str | None,
        /,
        *,
        user_ns: Mapping[str, Any],
    ) -> QueryReader:
        """
        Resolve the reader the ``%sql`` magic should execute with.

        When *reader_name* is given, the reader is looked up in the user
        namespace. When it is ``None``, a fallback reader is built once
        via :func:`mayutils.interfaces.data.get_env_reader` and cached on
        the instance as :attr:`env_reader` so subsequent cells reuse the
        same connection.

        Parameters
        ----------
        reader_name
            User-namespace variable name holding the reader, or ``None``
            to use the cached environment fallback.
        user_ns
            User namespace consulted when *reader_name* is given.

        Returns
        -------
            Reader satisfying :class:`~mayutils.data.read.QueryReader`.

        Raises
        ------
        ValueError
            If the named reader variable is not defined in the user
            namespace, or no fallback reader can be built from the
            environment.
        TypeError
            If the named reader variable is not callable.

        See Also
        --------
        MagicUtils.sql : Magic that executes through the resolved reader.
        mayutils.interfaces.data.get_env_reader : Fallback reader factory.

        Examples
        --------
        >>> from mayutils.interfaces.code.notebooks.jupyter import MagicUtils
        >>> MagicUtils.resolve_reader.__name__
        'resolve_reader'
        """
        if reader_name is None:
            if self.env_reader is None:
                with may_require_extras():
                    from mayutils.interfaces.data import get_env_reader  # noqa: PLC0415

                self.env_reader = get_env_reader()

            return self.env_reader

        try:
            reader = user_ns[reader_name]
        except KeyError as err:
            msg = f"No QueryReader found at user-namespace variable {err.args[0]!r}"
            raise ValueError(msg) from err
        if not callable(reader):
            msg = f"User-namespace variable {reader_name!r} is not callable and cannot be used as a QueryReader"
            raise TypeError(msg)

        return cast("QueryReader", reader)

    @line_cell_magic
    @magic_arguments()  # pyright: ignore[reportUntypedFunctionDecorator]
    @argument(  # pyright: ignore[reportUntypedFunctionDecorator]
        "var_name",
        type=str,
        help="The variable name to assign the resulting DataFrame to",
    )
    @argument(  # pyright: ignore[reportUntypedFunctionDecorator]
        "-r",
        "--reader",
        default=None,
        type=str,
        help="Name of a user-namespace variable holding a QueryReader; defaults to get_env_reader()",
    )
    @argument(  # pyright: ignore[reportUntypedFunctionDecorator]
        "-b",
        "--backend",
        default="pandas",
        type=str,
        help="The DataFrame backend to use (pandas or polars)",
    )
    @argument(  # pyright: ignore[reportUntypedFunctionDecorator]
        "query_string",
        nargs="*",
        help="The name of a query string variable, or the query string itself (line magic only)",
    )
    def sql(
        self,
        line: str,
        cell: str | None = None,
    ) -> DataFrames:
        """
        Execute a SQL template and assign the result into the namespace.

        As a cell magic the cell body is the query template; as a line
        magic the query is given inline or as the name of a namespace
        variable holding it. ``{{ name }}`` Jinja variables in the
        template are substituted from user-namespace variables and
        execution is
        delegated to :func:`mayutils.data.read.read_query`, using the
        reader found at the ``--reader`` namespace variable or, when no
        ``--reader`` is given, a cached fallback built by
        :func:`mayutils.interfaces.data.get_env_reader`. The resulting
        DataFrame is both assigned to ``var_name`` and returned for
        display.

        Parameters
        ----------
        line
            Magic argument string: ``var_name`` followed by options and,
            for the line magic, the query string or query variable name.
        cell
            Cell body holding the query template when invoked as a cell
            magic, ``None`` when invoked as a line magic.

        Returns
        -------
            DataFrame produced by the query, in the requested backend.

        Raises
        ------
        RuntimeError
            If the magic is invoked without a bound IPython shell.
        ValueError
            If a template field is not defined in the user namespace.
            :func:`resolve_query_string` and :meth:`resolve_reader`
            additionally raise for invalid query and reader inputs.

        See Also
        --------
        mayutils.data.read.read_query : Underlying execution and caching.
        resolve_query_string : Resolution of the query template inputs.
        MagicUtils.resolve_reader : Resolution of the executing reader.
        resolve_backend : Mapping from ``--backend`` names to tokens.
        template_fields : Discovery of ``{{ name }}`` template variables.

        Examples
        --------
        In a notebook, after assigning ``reader`` in the namespace::

            %load_ext mayutils.interfaces.code.notebooks.jupyter

            %%sql loans
            SELECT * FROM loans WHERE product = '{{ product }}'

        >>> from mayutils.interfaces.code.notebooks.jupyter import MagicUtils
        >>> MagicUtils.sql.__name__
        'sql'
        """
        if self.shell is None:
            msg = "No IPython shell found"
            raise RuntimeError(msg)

        user_ns = cast(
            "dict[str, Any]",
            self.shell.user_ns,  # pyright: ignore[reportUnknownMemberType]
        )
        args = cast(
            "SqlArguments",
            parse_argstring(
                magic_func=self.sql,
                argstring=line,
            ),
        )

        query_string = resolve_query_string(
            args.query_string,
            cell=cell,
            user_ns=user_ns,
        )
        reader = self.resolve_reader(
            args.reader,
            user_ns=user_ns,
        )

        try:
            jinja_kwargs = {field: user_ns[field] for field in template_fields(query_string)}
        except KeyError as err:
            msg = f"Template field {err.args[0]!r} is not defined in the user namespace"
            raise ValueError(msg) from err

        logger.debug(f"Running %sql magic into {args.var_name!r} with backend={args.backend!r} and reader={args.reader!r}")

        df = read_query(
            SQL(query_string),
            reader=reader,
            backend=resolve_backend(args.backend),
            jinja_kwargs=jinja_kwargs,
        )

        user_ns[args.var_name] = df

        return df


def setup_magic() -> None:
    """
    Register :class:`MagicUtils` on the running IPython shell.

    Looks up the active interactive shell and registers the magics class
    so that ``%sql`` / ``%%sql`` become available. Use this from notebook
    bootstrap code; ``%load_ext mayutils.interfaces.code.notebooks.jupyter``
    achieves the same through :func:`load_ipython_extension`.

    Raises
    ------
    RuntimeError
        If no IPython shell is currently running.

    See Also
    --------
    load_ipython_extension : ``%load_ext`` entry point.
    MagicUtils : The magics class being registered.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import setup_magic
    >>> setup_magic()  # doctest: +SKIP
    """
    ipython = get_ipython()
    if ipython is None:
        msg = "No running IPython shell found to register magics on"
        raise RuntimeError(msg)

    ipython.register_magics(MagicUtils)

    logger.debug("Registered MagicUtils magics on the running IPython shell")


def load_ipython_extension(
    ipython: InteractiveShell,
    /,
) -> None:
    """
    Register the magics when loaded via ``%load_ext``.

    Standard IPython extension hook invoked by
    ``%load_ext mayutils.interfaces.code.notebooks.jupyter``, registering
    :class:`MagicUtils` on the supplied shell.

    Parameters
    ----------
    ipython
        Interactive shell performing the extension load.

    See Also
    --------
    setup_magic : Equivalent registration from bootstrap code.
    MagicUtils : The magics class being registered.

    Examples
    --------
    >>> from mayutils.interfaces.code.notebooks.jupyter import load_ipython_extension
    >>> load_ipython_extension.__name__
    'load_ipython_extension'
    """
    ipython.register_magics(MagicUtils)

    logger.debug("Registered MagicUtils magics via %load_ext")


__all__ = [
    "MagicUtils",
    "SqlArguments",
    "load_ipython_extension",
    "resolve_backend",
    "resolve_query_string",
    "setup_magic",
    "template_fields",
]
