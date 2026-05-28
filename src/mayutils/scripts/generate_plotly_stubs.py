"""
Generate all plotly-related type stubs.

Generates:
- Trace ``.pyi`` stubs (from plotly-stubs + trace ``.py`` files)
- Chart ``.pyi`` stubs (from plotly-stubs ``_figure.pyi`` + chart ``.py`` files)
- Dev-only ``typings/plotly/`` overrides (basedatatypes with Self, missing stubs)

Run after upgrading ``plotly`` or ``plotly-stubs`` to keep autocomplete and
type checking in sync.
"""

from __future__ import annotations

import ast
import copy
import re
import site
import subprocess
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from typer import Argument, Exit, Option, Typer

from mayutils.visualisation.console import CONSOLE

app = Typer()

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TYPINGS_DIR = PROJECT_ROOT / "typings"
TRACES_DIR = PROJECT_ROOT / "src" / "mayutils" / "visualisation" / "graphs" / "plotly" / "traces"
CHARTS_DIR = PROJECT_ROOT / "src" / "mayutils" / "visualisation" / "graphs" / "plotly" / "charts"

CHAINING_METHODS_BASEFIGURE = {
    "update",
    "for_each_trace",
    "update_traces",
    "update_layout",
    "add_trace",
    "add_traces",
    "add_vline",
    "add_hline",
    "add_vrect",
    "add_hrect",
    "set_subplots",
}

BASETRACETYPE_PROPERTIES: dict[str, str] = {
    "xaxis": "str | None",
    "yaxis": "str | None",
    "type": "str | None",
    "x": "Any",
    "y": "Any",
    "z": "Any",
    "meta": "Any",
    "customdata": "Any",
    "textfont": "Any",
    "line": "Any",
    "marker": "Any",
    "fillcolor": "str | None",
    "opacity": "float | None",
    "legendgroup": "str | int | None",
    "fill": "str | None",
    "name": "str | int | None",
    "visible": "bool | str | None",
    "scene": "str | None",
    "showlegend": "bool | None",
    "hoverinfo": "str | None",
    "mode": "str | None",
    "text": "Any",
}


## Shared utilities


def find_stubs_root() -> Path:
    """
    Locate the ``plotly-stubs`` package in site-packages.

    Iterates over all site-package directories and returns the first
    path that contains a ``plotly-stubs`` folder.

    Returns
    -------
        Resolved path to the ``plotly-stubs`` root directory.

    Raises
    ------
    FileNotFoundError
        If no ``plotly-stubs`` directory is found in any site-package.

    See Also
    --------
    check_upstream : Validates whether found stubs are out of date.
    generate : Entry point that calls this at startup.

    Examples
    --------
    >>> find_stubs_root()  # doctest: +SKIP
    PosixPath('.../site-packages/plotly-stubs')
    """
    for sp in site.getsitepackages():
        candidate = Path(sp) / "plotly-stubs"
        if candidate.exists():
            return candidate

    msg = "plotly-stubs not found in site-packages"
    raise FileNotFoundError(msg)


@dataclass
class StubParam:
    """
    A single parameter extracted from a stub ``__init__`` signature.

    Holds the name, type annotation, and default value as raw strings
    for later rendering into ``.pyi`` output.

    Attributes
    ----------
    name
        Parameter name (may include ``*`` or ``**`` prefix).
    type_str
        Type annotation as a raw string.
    default_str
        Default value as a raw string, or empty if none.

    See Also
    --------
    parse_param_line : Constructs a ``StubParam`` from a raw text line.
    parse_stub_init : Returns a list of ``StubParam`` instances.

    Examples
    --------
    >>> StubParam(name="x", type_str="int", default_str="0")
    StubParam(name='x', type_str='int', default_str='0')
    """

    name: str
    type_str: str
    default_str: str


@dataclass
class TraceStubConfig:
    """
    Configuration for generating a single trace ``.pyi`` stub.

    Each instance describes how to build a stub class by combining a
    base plotly-stubs ``__init__`` with parameters from the subclass
    source file.

    Attributes
    ----------
    module
        Trace module filename (without ``.py``).
    class_name
        Name of the trace class to generate.
    base_stub_file
        Relative path to the upstream ``.pyi`` file used as a template.
    base_class_name
        Class name inside the base stub file.
    exclude_params
        Parameter names to omit from the generated stub.
    parent_module
        Optional parent module name when the trace inherits from
        another custom trace.
    parent_class_name
        Optional parent class name for multi-level inheritance.
    use_typings_stubs
        If ``True``, read base stubs from ``typings/`` instead of
        site-packages.

    See Also
    --------
    generate_trace_stub : Consumes a config to produce stub text.
    TRACE_CONFIGS : Module-level list of all trace configurations.

    Examples
    --------
    >>> TraceStubConfig(  # doctest: +SKIP
    ...     module="line",
    ...     class_name="Line",
    ...     base_stub_file="graph_objs/_scatter.pyi",
    ...     base_class_name="Scatter",
    ... )
    """

    module: str
    class_name: str
    base_stub_file: str
    base_class_name: str
    exclude_params: set[str] = field(default_factory=set[str])
    parent_module: str | None = None
    parent_class_name: str | None = None
    use_typings_stubs: bool = False


## Upstream staleness checks


def check_upstream(
    stubs_root: Path,
    /,
) -> None:
    """
    Warn when upstream plotly-stubs provides files we override locally.

    Checks whether plotly-stubs has started shipping stubs that were
    previously missing (Mesh3d, Icicle, Template, _subplots) or has
    adopted ``Self`` return types in ``basedatatypes.pyi``.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.

    See Also
    --------
    find_stubs_root : Locates the stubs directory checked here.
    generate : Orchestrator that calls this before generation.

    Examples
    --------
    >>> check_upstream(Path(".../plotly-stubs"))  # doctest: +SKIP
    """
    checks: list[tuple[str, Path, str]] = [
        (
            "Mesh3d trace stubs",
            stubs_root / "graph_objs" / "_mesh3d.pyi",
            "typings/plotly/graph_objs/_mesh3d.pyi",
        ),
        (
            "Icicle trace stubs",
            stubs_root / "graph_objs" / "_icicle.pyi",
            "typings/plotly/graph_objs/_icicle.pyi",
        ),
        (
            "Template layout stubs",
            stubs_root / "graph_objs" / "layout" / "_template.pyi",
            "typings/plotly/graph_objs/layout/_template.pyi",
        ),
        (
            "_subplots stubs",
            stubs_root / "_subplots.pyi",
            "typings/plotly/_subplots.pyi",
        ),
    ]

    for label, upstream_path, custom_path in checks:
        if upstream_path.exists():
            CONSOLE.print(f"[yellow][WARN] plotly-stubs now provides {label} — custom {custom_path} may be obsolete[/yellow]")

    basedatatypes = stubs_root / "basedatatypes.pyi"
    if basedatatypes.exists():
        text = basedatatypes.read_text()
        non_comment_self = any("-> Self" in line.split("#")[0] for line in text.splitlines())
        if non_comment_self:
            CONSOLE.print(
                "[yellow][WARN] plotly-stubs basedatatypes.pyi now uses Self "
                "returns — custom typings/plotly/basedatatypes.pyi may be obsolete[/yellow]"
            )

        for prop in ("xaxis", "yaxis", "meta"):
            pattern = rf"(?:def|:)\s+{prop}\b"
            if re.search(pattern, text) and "BaseTraceType" in text:
                CONSOLE.print(f"[yellow][WARN] plotly-stubs BaseTraceType now declares '{prop}' — custom property may be obsolete[/yellow]")


## Trace stub generation

TRACE_CONFIGS = [
    TraceStubConfig(
        module="null",
        class_name="Null",
        base_stub_file="graph_objs/_scatter.pyi",
        base_class_name="Scatter",
        exclude_params={"x", "y"},
    ),
    TraceStubConfig(
        module="line",
        class_name="Line",
        base_stub_file="graph_objs/_scatter.pyi",
        base_class_name="Scatter",
        exclude_params=set(),
    ),
    TraceStubConfig(
        module="ecdf",
        class_name="Ecdf",
        base_stub_file="graph_objs/_scatter.pyi",
        base_class_name="Scatter",
        exclude_params={"x", "y", "customdata"},
        parent_module="line",
        parent_class_name="Line",
    ),
    TraceStubConfig(
        module="kde",
        class_name="Kde",
        base_stub_file="graph_objs/_scatter.pyi",
        base_class_name="Scatter",
        exclude_params={"x", "y", "customdata", "fill"},
        parent_module="line",
        parent_class_name="Line",
    ),
    TraceStubConfig(
        module="icicle",
        class_name="Icicle",
        base_stub_file="plotly/graph_objs/_icicle.pyi",
        base_class_name="Icicle",
        exclude_params=set[str](),
        use_typings_stubs=True,
    ),
    TraceStubConfig(
        module="mesh3d",
        class_name="Cuboid",
        base_stub_file="plotly/graph_objs/_mesh3d.pyi",
        base_class_name="Mesh3d",
        exclude_params={"x", "y", "z", "i", "j", "k", "intensity"},
        use_typings_stubs=True,
    ),
    TraceStubConfig(
        module="mesh3d",
        class_name="Bar3d",
        base_stub_file="plotly/graph_objs/_mesh3d.pyi",
        base_class_name="Mesh3d",
        exclude_params={"x", "y", "z", "i", "j", "k", "intensity", "hovertemplate", "customdata", "meta"},
        use_typings_stubs=True,
    ),
    TraceStubConfig(
        module="scatter",
        class_name="Scatter",
        base_stub_file="graph_objs/_scatter.pyi",
        base_class_name="Scatter",
        exclude_params=set(),
    ),
]


def parse_stub_init(  # noqa: C901, PLR0912, PLR0915
    *,
    stub_path: Path,
    class_name: str,
) -> tuple[str, list[StubParam]]:
    """
    Parse the ``__init__`` signature from an upstream ``.pyi`` stub file.

    Extracts the import preamble and every parameter (name, type, default)
    from the ``__init__`` method of *class_name* inside *stub_path*.

    Parameters
    ----------
    stub_path
        Path to the ``.pyi`` file to parse.
    class_name
        Name of the class whose ``__init__`` is extracted.

    Returns
    -------
        A ``(imports_text, params)`` pair where *imports_text* is the
        raw import block and *params* is the ordered parameter list.

    Raises
    ------
    ValueError
        If the ``__init__`` method or its parameters cannot be located
        in the stub file.

    See Also
    --------
    parse_param_line : Parses individual parameter lines returned here.
    parse_subclass_init : Complementary parser for ``.py`` subclasses.

    Examples
    --------
    >>> imports, params = parse_stub_init(  # doctest: +SKIP
    ...     stub_path=Path("graph_objs/_scatter.pyi"),
    ...     class_name="Scatter",
    ... )
    """
    text = stub_path.read_text()
    lines = text.splitlines()

    import_lines: list[str] = []
    in_multiline = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("class ") and not in_multiline:
            break
        if in_multiline:
            import_lines.append(line)
            if ")" in stripped:
                in_multiline = False
            continue
        if stripped.startswith(("import ", "from ", "#")) or not stripped:
            if "from plotly.basedatatypes" in stripped:
                continue
            import_lines.append(line)
            if "(" in stripped and ")" not in stripped:
                in_multiline = True
        elif not stripped:
            import_lines.append("")
    imports = "\n".join(import_lines).rstrip()

    init_match = re.search(
        rf"(class\s+{class_name}\b.*?)\n(\s+def __init__\()",
        text,
        re.DOTALL,
    )
    if not init_match:
        msg = f"Could not find {class_name}.__init__ in {stub_path}"
        raise ValueError(msg)

    init_start = init_match.start(2)
    paren_depth = 0
    init_end = init_start
    for i, ch in enumerate(text[init_start:], init_start):
        if ch == "(":
            paren_depth += 1
        elif ch == ")":
            paren_depth -= 1
            if paren_depth == 0:
                init_end = i + 1
                break

    init_text = text[init_start:init_end]
    inner_match = re.search(r"\((.*)\)", init_text, re.DOTALL)
    if not inner_match:
        msg = f"Could not parse __init__ params in {stub_path}"
        raise ValueError(msg)

    raw_params_text = inner_match.group(1)
    params: list[StubParam] = []
    current_lines: list[str] = []

    for line in raw_params_text.splitlines():
        stripped = line.strip().rstrip(",")
        if not stripped:
            continue
        if stripped == "self":
            continue

        if ":" in line and not current_lines:
            if "=" in stripped or stripped.endswith("..."):
                params.append(parse_param_line(stripped))
            else:
                current_lines.append(stripped)
        elif current_lines:
            current_lines.append(stripped)
            if "=" in stripped:
                params.append(parse_param_line(" ".join(current_lines)))
                current_lines = []
        elif stripped.startswith("**"):
            param_name = stripped.split(":")[0].replace("**", "").strip()
            type_str = stripped.split(":")[1].split("=")[0].strip() if ":" in stripped else "Any"
            params.append(StubParam(name=f"**{param_name}", type_str=type_str, default_str=""))
        elif stripped.startswith("*"):
            params.append(StubParam(name="*", type_str="", default_str=""))

    return imports, params


def parse_param_line(
    text: str,
    /,
) -> StubParam:
    """
    Parse a single parameter line into a ``StubParam``.

    Handles positional, keyword-only, and ``**kwargs`` forms, splitting
    the raw text into name, type annotation, and default value.

    Parameters
    ----------
    text
        A single parameter line from a stub ``__init__`` signature.

    Returns
    -------
        Parsed parameter with name, type, and default strings.

    See Also
    --------
    StubParam : Dataclass returned by this function.
    parse_stub_init : Caller that feeds raw lines into this parser.

    Examples
    --------
    >>> parse_param_line("x: int = 0")
    StubParam(name='x', type_str='int', default_str='0')
    """
    text = text.strip().rstrip(",")

    if text.startswith("**"):
        name_type, _, default = text.partition("=")
        name_part, _, type_part = name_type.partition(":")
        return StubParam(
            name=name_part.strip(),
            type_str=type_part.strip(),
            default_str=default.strip() or "",
        )

    eq_idx = text.rfind("=")
    if eq_idx == -1:
        name_part, _, type_part = text.partition(":")
        return StubParam(name=name_part.strip(), type_str=type_part.strip(), default_str="...")

    before_eq = text[:eq_idx].rstrip()
    default = text[eq_idx + 1 :].strip()
    name_part, _, type_part = before_eq.partition(":")
    return StubParam(
        name=name_part.strip(),
        type_str=type_part.strip(),
        default_str=default,
    )


def parse_subclass_init(  # noqa: C901, PLR0912
    *,
    py_path: Path,
    class_name: str,
) -> tuple[list[StubParam], dict[str, str]]:
    """
    Parse ``__init__`` of a custom trace subclass from its ``.py`` source.

    Extracts the subclass's own parameters and any default overrides
    passed to the parent ``super().__init__()`` call.

    Parameters
    ----------
    py_path
        Path to the ``.py`` source file.
    class_name
        Name of the class whose ``__init__`` is parsed.

    Returns
    -------
        A ``(own_params, overrides)`` pair where *own_params* are
        parameters declared directly and *overrides* maps parent
        parameter names to their overridden default values.

    See Also
    --------
    parse_stub_init : Parses the base class stub that this complements.
    generate_trace_stub : Consumer that merges subclass and base params.

    Examples
    --------
    >>> own, overrides = parse_subclass_init(  # doctest: +SKIP
    ...     py_path=Path("traces/line.py"),
    ...     class_name="Line",
    ... )
    """
    tree = ast.parse(py_path.read_text())

    own_params: list[StubParam] = []
    overrides: dict[str, str] = {}

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue

        for item in node.body:
            if not (isinstance(item, ast.FunctionDef) and item.name == "__init__"):
                continue

            args = item.args
            defaults_offset = len(args.args) - len(args.defaults)

            for i, a in enumerate(args.args[1:], 1):
                if a.arg in ("args", "kwargs"):
                    continue
                ann = ast.unparse(a.annotation) if a.annotation else "Any"
                di = i - defaults_offset
                default = ast.unparse(args.defaults[di]) if di >= 0 else "..."
                own_params.append(StubParam(name=a.arg, type_str=ann, default_str=default))

            for a, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
                if a.arg in ("args", "kwargs"):
                    continue
                ann = ast.unparse(a.annotation) if a.annotation else "Any"
                default = ast.unparse(kw_default) if kw_default else "..."
                own_params.append(StubParam(name=a.arg, type_str=ann, default_str=default))

            for sub in ast.walk(item):
                if not isinstance(sub, ast.Call):
                    continue
                func_str = ast.dump(sub.func)
                if "super" not in func_str or "__init__" not in func_str:
                    continue
                for kw in sub.keywords:
                    if kw.arg is None:
                        continue
                    if isinstance(kw.value, ast.Constant):
                        overrides[kw.arg] = repr(kw.value.value)
                    elif isinstance(kw.value, ast.Name) and kw.value.id == kw.arg:
                        pass
                    elif isinstance(kw.value, ast.Name):
                        for op in own_params:
                            if op.name == kw.value.id:
                                overrides[kw.arg] = op.default_str
                                break

    return own_params, overrides


@dataclass
class ClassMethodStub:
    """
    Parsed signature of a ``@classmethod`` from a trace source file.

    Stores the method name, separated positional and keyword parameters,
    return type, and whether a positional-only marker is present.

    Attributes
    ----------
    name
        Method name.
    positional_params
        Positional parameters (excluding ``cls``).
    keyword_params
        Keyword-only parameters.
    return_type
        Return type annotation as a raw string.
    has_pos_only
        Whether the method uses a ``/`` positional-only separator.

    See Also
    --------
    parse_classmethods : Factory that produces these instances.
    generate_trace_stub : Consumer that renders them into stub text.

    Examples
    --------
    >>> ClassMethodStub(  # doctest: +SKIP
    ...     name="from_dict",
    ...     positional_params=[],
    ...     keyword_params=[],
    ...     return_type="Self",
    ... )
    """

    name: str
    positional_params: list[StubParam]
    keyword_params: list[StubParam]
    return_type: str
    has_pos_only: bool = False


def parse_classmethods(  # noqa: C901
    *,
    py_path: Path,
    class_name: str,
) -> list[ClassMethodStub]:
    """
    Extract ``@classmethod`` signatures from a trace source file.

    Only methods that accept ``**kwargs`` are included, since those
    are the constructor alternatives that need stub expansion.

    Parameters
    ----------
    py_path
        Path to the ``.py`` source file.
    class_name
        Name of the class to inspect.

    Returns
    -------
        List of parsed classmethod stubs.

    See Also
    --------
    ClassMethodStub : Dataclass returned by this function.
    generate_trace_stub : Consumer that renders the classmethods.

    Examples
    --------
    >>> parse_classmethods(  # doctest: +SKIP
    ...     py_path=Path("traces/line.py"),
    ...     class_name="Line",
    ... )
    """
    tree = ast.parse(py_path.read_text())
    methods: list[ClassMethodStub] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == class_name):
            continue

        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            is_classmethod = any(isinstance(d, ast.Name) and d.id == "classmethod" for d in item.decorator_list)
            if not is_classmethod:
                continue

            args = item.args
            if args.kwarg is None:
                continue

            positional: list[StubParam] = []
            keyword: list[StubParam] = []
            has_pos_only = bool(args.posonlyargs) and len(args.posonlyargs) > 1
            all_positional = list(args.posonlyargs) + list(args.args)
            defaults_offset = len(all_positional) - len(args.defaults)

            for i, a in enumerate(all_positional[1:], 1):
                if a.arg in ("args", "kwargs"):
                    continue
                ann = ast.unparse(a.annotation) if a.annotation else "Any"
                di = i - defaults_offset
                default = ast.unparse(args.defaults[di]) if di >= 0 else ""
                positional.append(StubParam(name=a.arg, type_str=ann, default_str=default))

            for a, kw_default in zip(args.kwonlyargs, args.kw_defaults, strict=True):
                if a.arg in ("args", "kwargs"):
                    continue
                ann = ast.unparse(a.annotation) if a.annotation else "Any"
                default = ast.unparse(kw_default) if kw_default else ""
                keyword.append(StubParam(name=a.arg, type_str=ann, default_str=default))

            ret = ast.unparse(item.returns) if item.returns else "Any"

            methods.append(
                ClassMethodStub(
                    name=item.name,
                    positional_params=positional,
                    keyword_params=keyword,
                    return_type=ret,
                    has_pos_only=has_pos_only,
                )
            )

    return methods


def parse_module_functions(
    py_path: Path,
    /,
) -> tuple[list[str], list[str]]:
    """
    Extract top-level function stubs and their imports from a trace module.

    Returns (import_lines, function_stubs) where each function stub is a
    fully formatted multi-line string ready for a .pyi file.

    Parameters
    ----------
    py_path
        Path to the trace ``.py`` module.

    Returns
    -------
        A ``(import_lines, function_stubs)`` pair of string lists.

    See Also
    --------
    append_module_functions : Inserts these stubs into an existing file.
    generate_trace_stubs : Caller that appends module functions.

    Examples
    --------
    >>> imports, stubs = parse_module_functions(  # doctest: +SKIP
    ...     Path("traces/line.py"),
    ... )
    """
    source = py_path.read_text()
    tree = ast.parse(source)

    import_lines: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [f"{alias.name} as {alias.asname}" if alias.asname else alias.name for alias in node.names if alias.name != "*"]
            if names:
                import_lines.append(f"from {node.module} import {', '.join(names)}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    import_lines.append(f"import {alias.name} as {alias.asname}")
                else:
                    import_lines.append(f"import {alias.name}")

    functions: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        stub_node = copy.deepcopy(node)
        stub_node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
        raw = ast.unparse(stub_node)
        functions.append(format_pyi_method(raw, indent=""))

    return import_lines, functions


def format_param(
    *,
    name: str,
    type_str: str,
    default: str,
) -> str:
    """
    Format a single parameter as an indented stub line.

    Appends a ``# noqa: ANN401`` comment when the type is ``Any`` or
    the parameter is ``**kwargs``.

    Parameters
    ----------
    name
        Parameter name (may include ``**`` prefix).
    type_str
        Type annotation string.
    default
        Default value string, or empty for no default.

    Returns
    -------
        An indented, comma-terminated parameter line.

    See Also
    --------
    generate_trace_stub : Primary consumer of formatted param lines.
    StubParam : Dataclass whose fields feed into this formatter.

    Examples
    --------
    >>> format_param(name="x", type_str="int", default="0")
    '        x: int = 0,'
    """
    noqa = "  # noqa: ANN401" if type_str == "Any" or name.startswith("**") else ""
    if default:
        return f"        {name}: {type_str} = {default},{noqa}"
    return f"        {name}: {type_str},{noqa}"


def collect_source_imports(
    py_path: Path,
    /,
) -> dict[str, list[str]]:
    """
    Collect ``from ... import ...`` statements from a source file.

    Builds a mapping from the full import line to the list of imported
    names, used to decide which extra imports the generated stub needs.

    Parameters
    ----------
    py_path
        Path to the ``.py`` source file.

    Returns
    -------
        Mapping from import line text to imported name strings.

    See Also
    --------
    generate_trace_stub : Consumer that checks which imports are needed.
    parse_stub_init : Extracts imports from ``.pyi`` files instead.

    Examples
    --------
    >>> collect_source_imports(Path("traces/line.py"))  # doctest: +SKIP
    {'from typing import Literal': ['Literal']}
    """
    tree = ast.parse(py_path.read_text())
    result: dict[str, list[str]] = {}

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.names:
            names = [alias.asname or alias.name for alias in node.names if alias.name != "*"]
            if not names:
                continue
            import_line = f"from {node.module} import {', '.join(alias.name for alias in node.names if alias.name != '*')}"
            result[import_line] = names

    return result


def generate_trace_stub(  # noqa: C901, PLR0912, PLR0915
    *,
    config: TraceStubConfig,
    stubs_root: Path,
    traces_dir: Path,
) -> str:
    """
    Generate the full ``.pyi`` text for a single trace class.

    Merges parameters from the upstream stub, the subclass source, and
    any parent trace into one ``__init__`` signature, then appends
    expanded ``@classmethod`` stubs.

    Parameters
    ----------
    config
        Trace stub configuration describing the class to generate.
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.
    traces_dir
        Directory containing the trace ``.py`` source modules.

    Returns
    -------
        Complete ``.pyi`` file content as a string.

    See Also
    --------
    TraceStubConfig : Configuration dataclass consumed here.
    generate_trace_stubs : Batch caller that writes results to disk.

    Examples
    --------
    >>> text = generate_trace_stub(  # doctest: +SKIP
    ...     config=TRACE_CONFIGS[0],
    ...     stubs_root=find_stubs_root(),
    ...     traces_dir=TRACES_DIR,
    ... )
    """
    stub_root = TYPINGS_DIR if config.use_typings_stubs else stubs_root
    base_imports, base_params = parse_stub_init(
        stub_path=stub_root / config.base_stub_file,
        class_name=config.base_class_name,
    )
    py_path = traces_dir / f"{config.module}.py"
    own_params, overrides = parse_subclass_init(
        py_path=py_path,
        class_name=config.class_name,
    )

    parent_params: list[StubParam] = []
    if config.parent_module and config.parent_class_name:
        parent_py = traces_dir / f"{config.parent_module}.py"
        parent_own, _ = parse_subclass_init(
            py_path=parent_py,
            class_name=config.parent_class_name,
        )
        parent_params = [p for p in parent_own if p.name not in config.exclude_params and p.name not in {op.name for op in own_params}]

    own_param_names = {p.name for p in own_params}
    parent_param_names = {p.name for p in parent_params}

    filtered_base = [
        p
        for p in base_params
        if p.name not in config.exclude_params
        and p.name not in own_param_names
        and p.name not in parent_param_names
        and p.name not in {"**kwargs", "*", "arg"}
    ]

    for bp in filtered_base:
        if bp.name in overrides:
            bp.default_str = overrides[bp.name]

    import_lines = base_imports.splitlines()
    aliased_imports: list[str] = []
    for line in import_lines:
        for bp in filtered_base:
            if bp.type_str and config.class_name in bp.type_str:
                pass
        aliased_imports.append(line)

    names_to_shield = {config.class_name}
    if config.parent_class_name:
        names_to_shield.add(config.parent_class_name)

    collision_names: set[str] = set()
    for bp in filtered_base:
        parts = re.findall(r"\b([A-Z]\w+)\b", bp.type_str)
        for part in parts:
            if part in names_to_shield:
                collision_names.add(part)

    for name in names_to_shield:
        if f"    {name}," in base_imports:
            collision_names.add(name)

    final_import_text = base_imports
    for collision in collision_names:
        old_import = f"    {collision},"
        new_import = f"    {collision} as _{collision},"
        final_import_text = final_import_text.replace(old_import, new_import)

    for bp in filtered_base:
        for collision in collision_names:
            bp.type_str = re.sub(
                rf"\b{collision}\b",
                f"_{collision}",
                bp.type_str,
            )

    for p in [*own_params, *parent_params]:
        p.type_str = p.type_str.replace("'", '"')
        p.default_str = p.default_str.replace("'", '"')

    classmethods = parse_classmethods(
        py_path=py_path,
        class_name=config.class_name,
    )
    if config.parent_module and config.parent_class_name:
        parent_py = traces_dir / f"{config.parent_module}.py"
        classmethods.extend(
            parse_classmethods(
                py_path=parent_py,
                class_name=config.parent_class_name,
            )
        )

    cm_type_strs = " ".join(
        " ".join(
            [p.type_str for p in cm.positional_params] + [p.type_str for p in cm.keyword_params] + [cm.return_type],
        )
        for cm in classmethods
    )
    all_type_strs = " ".join(p.type_str for p in [*own_params, *parent_params]) + " " + cm_type_strs
    extra_typing: list[str] = [name for name in ("Literal", "Optional", "Self") if name in all_type_strs and name not in final_import_text]
    extra_numpy: list[str] = [name for name in ("ArrayLike",) if name in all_type_strs and name not in final_import_text]
    source_imports = collect_source_imports(py_path)
    if config.parent_module:
        source_imports.update(collect_source_imports(traces_dir / f"{config.parent_module}.py"))

    extra_source: list[str] = []
    for imp_line, names in source_imports.items():
        needed = [n for n in names if n in all_type_strs and n not in final_import_text]
        if needed:
            extra_source.append(imp_line)

    extra_import_lines: list[str] = []
    if extra_typing:
        extra_import_lines.append(f"from typing import {', '.join(extra_typing)}")
    if extra_numpy:
        extra_import_lines.append(f"from numpy.typing import {', '.join(extra_numpy)}")
    extra_import_lines.extend(extra_source)
    extra_import_text = "\n".join(extra_import_lines)

    pragma = "# pyright: reportPropertyTypeMismatch=false\n"
    header = (
        (pragma if pragma.strip() not in final_import_text else "")
        + f"{final_import_text}\n"
        + (f"{extra_import_text}\n" if extra_import_text else "")
        + "import plotly.graph_objects as go\n"
    )

    if config.parent_module and config.parent_class_name:
        stub_base = config.parent_class_name
        parent_import = f"from mayutils.visualisation.graphs.plotly.traces.{config.parent_module} import {config.parent_class_name}"
        header += f"{parent_import}\n"
    else:
        stub_base = f"go.{config.base_class_name}"

    lines = [
        header,
        "",
        f"class {config.class_name}({stub_base}):",
        "    def __init__(",
        "        self,",
    ]

    lines.extend(
        format_param(
            name=p.name,
            type_str=p.type_str,
            default=p.default_str,
        )
        for p in own_params
    )

    has_keyword_only = own_params or parent_params
    if has_keyword_only and (parent_params or filtered_base):
        lines.append("        *,")

    lines.extend(
        format_param(
            name=p.name,
            type_str=p.type_str,
            default=p.default_str,
        )
        for p in parent_params
    )
    lines.extend(
        format_param(
            name=p.name,
            type_str=p.type_str,
            default=p.default_str,
        )
        for p in filtered_base
    )

    lines.append("        **kwargs: Any,  # noqa: ANN401")
    lines.append("    ) -> None: ...")

    init_keyword_params = [*parent_params, *filtered_base]

    for cm in classmethods:
        cm_param_names = {p.name for p in cm.positional_params} | {p.name for p in cm.keyword_params}
        expanded_kwargs = [p for p in init_keyword_params if p.name not in cm_param_names]

        ret = cm.return_type.replace("Self", config.class_name)

        lines.append("")
        lines.append("    @classmethod")
        lines.append(f"    def {cm.name}(")
        lines.append("        cls,")

        lines.extend(
            format_param(
                name=p.name,
                type_str=p.type_str,
                default=p.default_str,
            )
            for p in cm.positional_params
        )

        if cm.has_pos_only and cm.positional_params:
            lines.append("        /,")

        if cm.keyword_params or expanded_kwargs:
            lines.append("        *,")
            lines.extend(
                format_param(
                    name=p.name,
                    type_str=p.type_str,
                    default=p.default_str,
                )
                for p in cm.keyword_params
            )

        lines.extend(
            format_param(
                name=p.name,
                type_str=p.type_str,
                default=p.default_str,
            )
            for p in expanded_kwargs
        )

        lines.append("        **kwargs: Any,  # noqa: ANN401")
        lines.append(f"    ) -> {ret}: ...")

    lines.append("")

    return "\n".join(lines)


def generate_trace_stubs(
    *,
    stubs_root: Path,
    traces_dir: Path,
    dry_run: bool = False,
) -> list[str]:
    """
    Generate ``.pyi`` stubs for all configured trace classes.

    Iterates over ``TRACE_CONFIGS``, builds each stub, merges stubs
    that share a module, appends module-level functions, and writes the
    result to disk.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.
    traces_dir
        Directory containing the trace ``.py`` source modules.
    dry_run
        If ``True``, print what would be generated without writing.

    Returns
    -------
        List of module names that were (or would be) generated.

    Raises
    ------
    FileNotFoundError
        If the resolved output path falls outside *traces_dir*.

    See Also
    --------
    generate_trace_stub : Builds an individual trace stub.
    generate : Top-level orchestrator that calls this.

    Examples
    --------
    >>> generate_trace_stubs(  # doctest: +SKIP
    ...     stubs_root=find_stubs_root(),
    ...     traces_dir=TRACES_DIR,
    ... )
    """
    generated: list[str] = []
    module_contents: dict[str, list[str]] = {}

    for config in TRACE_CONFIGS:
        py_path = traces_dir / f"{config.module}.py"

        if not py_path.exists():
            CONSOLE.print(f"[yellow]Skipping trace {config.module}: {py_path} not found[/yellow]")
            continue

        stub_root = TYPINGS_DIR if config.use_typings_stubs else stubs_root
        stub_path = stub_root / config.base_stub_file
        if not stub_path.exists():
            CONSOLE.print(f"[yellow]Skipping trace {config.module}: base stub {stub_path} not found[/yellow]")
            continue

        if dry_run:
            CONSOLE.print(f"[cyan]Would generate {config.class_name} in {config.module}.pyi[/cyan]")
            generated.append(config.module)
            continue

        content = generate_trace_stub(
            config=config,
            stubs_root=stubs_root,
            traces_dir=traces_dir,
        )
        module_contents.setdefault(config.module, []).append(content)
        generated.append(config.module)

    for module, contents in module_contents.items():
        pyi_path = traces_dir / f"{module}.pyi"

        merged = contents[0] if len(contents) == 1 else merge_stub_contents(contents)

        py_path = traces_dir / f"{module}.py"
        func_imports, func_stubs = parse_module_functions(py_path)
        if func_stubs:
            merged = append_module_functions(
                stub_text=merged,
                func_imports=func_imports,
                func_stubs=func_stubs,
            )

        traces_dir_resolved = traces_dir.resolve()
        pyi_path_resolved = pyi_path.resolve()
        try:
            pyi_path_resolved.relative_to(traces_dir_resolved)
        except ValueError as err:
            msg = "Invalid file path"
            raise FileNotFoundError(msg) from err

        pyi_path_resolved.write_text(merged)
        CONSOLE.print(f"[green]Generated {pyi_path}[/green]")

    return generated


def merge_stub_contents(
    contents: list[str],
    /,
) -> str:
    r"""
    Merge multiple stub strings that share a single ``.pyi`` module.

    De-duplicates imports and pragmas, then concatenates class bodies
    so that several trace classes can coexist in one file.

    Parameters
    ----------
    contents
        List of complete stub texts to merge.

    Returns
    -------
        Combined stub text with unified imports and all classes.

    See Also
    --------
    generate_trace_stubs : Caller that merges multi-class modules.
    append_module_functions : Subsequent step that adds functions.

    Examples
    --------
    >>> merge_stub_contents(  # doctest: +SKIP
    ...     ["import a\\nclass A: ...", "import b\\nclass B: ..."],
    ... )
    """
    all_imports: list[str] = []
    all_classes: list[str] = []
    pragmas: set[str] = set()

    for content in contents:
        lines = content.splitlines()
        class_start = next(
            (i for i, line in enumerate(lines) if line.startswith("class ")),
            len(lines),
        )
        header_lines = lines[:class_start]
        class_lines = lines[class_start:]

        for line in header_lines:
            if line.startswith("# pyright:"):
                pragmas.add(line)
            elif line.strip():
                all_imports.append(line)

        all_classes.append("\n".join(class_lines))

    unique_imports = list(dict.fromkeys(all_imports))

    parts = list(pragmas) + unique_imports + ["", ""] + all_classes
    return "\n".join(parts) + "\n"


def append_module_functions(
    *,
    stub_text: str,
    func_imports: list[str],
    func_stubs: list[str],
) -> str:
    """
    Append top-level function stubs to an existing stub file text.

    Inserts any missing import lines into the header, then appends the
    formatted function stubs after the existing class definitions.

    Parameters
    ----------
    stub_text
        Existing ``.pyi`` content to extend.
    func_imports
        Import lines required by the function stubs.
    func_stubs
        Formatted function stub strings to append.

    Returns
    -------
        Updated stub text with functions appended.

    See Also
    --------
    parse_module_functions : Produces the imports and stubs consumed here.
    generate_trace_stubs : Caller that passes merged stub text in.

    Examples
    --------
    >>> append_module_functions(  # doctest: +SKIP
    ...     stub_text="class A: ...",
    ...     func_imports=["from typing import Any"],
    ...     func_stubs=["def foo() -> None: ..."],
    ... )
    """
    lines = stub_text.splitlines()

    pragma_end = 0
    first_import = 0
    for i, line in enumerate(lines):
        if line.startswith("# pyright:"):
            pragma_end = i + 1
        elif line.startswith(("import ", "from ")):
            if not first_import:
                first_import = i
            pragma_end = max(pragma_end, i + 1)

    existing_imports = {line.strip() for line in lines[:pragma_end] if line.startswith(("import ", "from "))}
    new_imports = [imp for imp in func_imports if imp not in existing_imports]

    if new_imports:
        insert_at = pragma_end
        for imp in new_imports:
            lines.insert(insert_at, imp)
            insert_at += 1

    text = "\n".join(lines).rstrip()
    text += "\n\n" + "\n\n".join(func_stubs) + "\n"
    return text


## Chart stub generation (plot.pyi, subplot.pyi)


def extract_class_own_methods(  # noqa: C901
    *,
    source: str,
    class_name: str,
) -> tuple[list[str], list[tuple[str, str | None]]]:
    """
    Extract imports and method stub signatures from a .py file.

    Returns (import_lines, method_stubs) where each method stub is a
    ``(raw_signature, pragma_or_none)`` tuple ready for a .pyi file.

    Parameters
    ----------
    source
        Full source text of the ``.py`` file.
    class_name
        Name of the class whose methods are extracted.

    Returns
    -------
        A ``(import_lines, method_stubs)`` pair where each method stub
        is a ``(raw_signature, pragma_or_none)`` tuple.

    See Also
    --------
    generate_chart_stub : Consumer that renders the extracted methods.
    extract_figure_chaining_methods : Complementary extractor for Figure.

    Examples
    --------
    >>> imports, methods = extract_class_own_methods(  # doctest: +SKIP
    ...     source=Path("charts/plot.py").read_text(),
    ...     class_name="Plot",
    ... )
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        CONSOLE.print(f"[yellow]Warning: syntax error in source ({e}), skipping own methods[/yellow]")
        return [], []
    source_lines = source.splitlines()

    def _collect_import_text(node: ast.Import | ast.ImportFrom) -> str:
        """
        Reconstruct the original import text from AST line numbers.

        Joins the source lines spanned by *node* to recover the
        original ``import`` or ``from … import`` statement verbatim.

        Parameters
        ----------
        node
            An ``ast.Import`` or ``ast.ImportFrom`` node.

        Returns
        -------
            The original import statement as a stripped string.

        See Also
        --------
        extract_class_own_methods : Outer function that calls this.

        Examples
        --------
        >>> _collect_import_text(node)  # doctest: +SKIP
        'from typing import Any'
        """
        start = node.lineno - 1
        end = node.end_lineno or node.lineno
        return "\n".join(source_lines[start:end]).strip()

    import_texts: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            import_texts.append(_collect_import_text(node))
        elif isinstance(node, ast.With):
            import_texts.extend(_collect_import_text(child) for child in ast.walk(node) if isinstance(child, (ast.Import, ast.ImportFrom)))

    cleaned_imports: list[str] = []
    for text in import_texts:
        if "may_require_extras" in text:
            continue
        cleaned_imports.append(text)

    target_class: ast.ClassDef | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            target_class = node
            break

    if target_class is None:
        return cleaned_imports, []

    method_stubs: list[tuple[str, str | None]] = []
    for item in target_class.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stub_node = copy.deepcopy(item)
            stub_node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
            raw = ast.unparse(stub_node)

            def_line = source_lines[item.lineno - 1]
            pragma_match = re.search(r"(#\s*pyright:\s*ignore\[.+)", def_line)
            pragma = pragma_match.group(1).rstrip() if pragma_match else None

            method_stubs.append((raw, pragma))
        elif (isinstance(item, ast.AnnAssign) and item.target) or isinstance(item, ast.Assign):
            raw = ast.unparse(item)
            method_stubs.append((raw, None))

    return cleaned_imports, method_stubs


def extract_figure_chaining_methods(
    figure_stub_path: Path,
    /,
) -> tuple[list[str], list[str]]:
    """
    Extract chaining method signatures and their required imports from _figure.pyi.

    Uses text-based parsing to preserve ``# pyright: ignore`` comments.
    Returns (import_lines, method_stubs) where method stubs have
    ``-> Figure`` replaced by ``-> Self``.

    Parameters
    ----------
    figure_stub_path
        Path to the ``_figure.pyi`` stub file.

    Returns
    -------
        A ``(import_lines, method_stubs)`` pair of string lists.

    See Also
    --------
    extract_class_own_methods : Complementary extractor for own methods.
    generate_chart_stub : Consumer that merges chaining methods.

    Examples
    --------
    >>> imports, methods = extract_figure_chaining_methods(  # doctest: +SKIP
    ...     Path(".../graph_objs/_figure.pyi"),
    ... )
    """
    text = figure_stub_path.read_text()
    tree = ast.parse(text)
    source_lines = text.splitlines()

    import_lines: list[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno or node.lineno
            import_lines.append("\n".join(source_lines[start:end]).strip())

    methods: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ClassDef) and node.name == "Figure"):
            continue

        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue

            returns = item.returns
            if returns is None:
                continue

            return_str = ast.unparse(returns)
            if return_str != "Figure":
                continue

            start = item.lineno - 1
            end = item.body[0].end_lineno or item.body[0].lineno
            method_lines = source_lines[start:end]

            method_text = "\n".join(line for line in method_lines if line.strip())

            method_text = re.sub(
                r"->\s*Figure\s*:",
                "-> Self:",
                method_text,
            )

            methods.append(method_text)

    return import_lines, methods


def format_pyi_method(
    raw: str,
    /,
    *,
    indent: str = "    ",
    pragma: str | None = None,
) -> str:
    """
    Format a single-line ``ast.unparse`` output into readable multi-line stub.

    Splits the signature across multiple lines when it exceeds the line
    length limit or has more than two parameters.

    Parameters
    ----------
    raw
        Single-line string produced by ``ast.unparse``.
    indent
        Indentation prefix for each output line.
    pragma
        Optional ``# pyright: ignore[...]`` comment to attach.

    Returns
    -------
        Formatted multi-line stub string.

    See Also
    --------
    split_params : Tokeniser used to split the parameter string.
    extract_class_own_methods : Produces raw signatures formatted here.

    Examples
    --------
    >>> format_pyi_method("def foo(self) -> None: ...")  # doctest: +SKIP
    '    def foo(self) -> None: ...'
    """
    decorators: list[str] = []
    remaining = raw
    while remaining.startswith("@"):
        newline_idx = remaining.index("\n") if "\n" in remaining else len(remaining)
        decorators.append(remaining[:newline_idx].strip())
        remaining = remaining[newline_idx + 1 :].lstrip() if "\n" in remaining else ""

    match = re.match(r"def\s+(\w+)\((.*)\)\s*->\s*(.+):\s*\.\.\.", remaining, re.DOTALL)
    if not match:
        match = re.match(r"def\s+(\w+)\((.*)\):\s*\.\.\.", remaining, re.DOTALL)
        if not match:
            return f"{indent}{raw}"
        name, params, ret = match.group(1), match.group(2), "None"
    else:
        name, params, ret = match.groups()

    param_list = split_params(params)

    pragma_suffix = f"  {pragma}" if pragma else ""

    max_params = 2
    max_sig_length = 80

    full_sig = f"def {name}({params}) -> {ret}: ..."
    if len(param_list) <= max_params and len(full_sig) <= max_sig_length and not pragma:
        lines = [f"{indent}{d}" for d in decorators]
        lines.append(f"{indent}{full_sig}")
        return "\n".join(lines)

    lines = [f"{indent}{d}" for d in decorators]
    lines.append(f"{indent}def {name}({pragma_suffix}")
    for p in param_list:
        p_stripped = p.strip()
        if p_stripped:
            lines.append(f"{indent}    {p_stripped},")
    lines.append(f"{indent}) -> {ret}: ...")

    return "\n".join(lines)


def split_params(
    params_str: str,
    /,
) -> list[str]:
    """
    Split a parameter string respecting brackets and parentheses.

    Splits on commas at depth zero only, preserving nested generics,
    tuple literals, and default-value expressions.

    Parameters
    ----------
    params_str
        Comma-separated parameter text, potentially containing nested
        brackets.

    Returns
    -------
        List of individual parameter strings.

    See Also
    --------
    format_pyi_method : Primary consumer of the split result.

    Examples
    --------
    >>> split_params("self, x: int, y: str")
    ['self', 'x: int', 'y: str']
    """
    params: list[str] = []
    depth = 0
    current: list[str] = []
    for char in params_str:
        if char in "([{":
            depth += 1
            current.append(char)
        elif char in ")]}":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            params.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        params.append("".join(current).strip())
    return [p for p in params if p]


def generate_chart_stub(  # noqa: C901, PLR0912, PLR0915
    *,
    py_path: Path,
    class_name: str,
    base_class: str,
    figure_stub_path: Path,
) -> str:
    """
    Generate a ``.pyi`` stub for a chart class (Plot or SubPlot).

    Combines the class's own methods with chaining methods inherited
    from ``Figure``, de-duplicates imports, and assembles the output.

    Parameters
    ----------
    py_path
        Path to the chart ``.py`` source file.
    class_name
        Name of the chart class to generate.
    base_class
        Base class name for the stub (e.g. ``go.Figure``).
    figure_stub_path
        Path to the ``_figure.pyi`` stub for chaining methods.

    Returns
    -------
        Complete ``.pyi`` file content as a string.

    See Also
    --------
    extract_class_own_methods : Extracts the class's own methods.
    generate_chart_stubs : Batch caller that writes results to disk.

    Examples
    --------
    >>> text = generate_chart_stub(  # doctest: +SKIP
    ...     py_path=Path("charts/plot.py"),
    ...     class_name="Plot",
    ...     base_class="go.Figure",
    ...     figure_stub_path=Path("graph_objs/_figure.pyi"),
    ... )
    """
    source = py_path.read_text()
    own_imports, own_methods = extract_class_own_methods(
        source=source,
        class_name=class_name,
    )
    figure_imports, chaining_methods = extract_figure_chaining_methods(figure_stub_path)

    own_method_names: set[str] = set()
    for raw, _pragma in own_methods:
        m = re.match(r"(?:@\w+\s+)?def\s+(\w+)\(", raw)
        if m:
            own_method_names.add(m.group(1))

    filtered_chaining = [m for m in chaining_methods if not any(re.match(rf"(?:@\w+\s+)?def\s+{name}\(", m) for name in own_method_names)]

    import_set: set[str] = set()
    for imp in own_imports:
        if imp.startswith(("import ", "from ")):
            import_set.add(imp)
    for imp in figure_imports:
        if imp.startswith(("import ", "from ")):
            import_set.add(imp)

    graph_objs_names: set[str] = set()
    for imp in import_set:
        if "from plotly.graph_objs import" not in imp:
            continue
        for node in ast.parse(imp).body:
            if isinstance(node, ast.ImportFrom):
                graph_objs_names.update(alias.name for alias in node.names)
    to_remove: set[str] = set()
    for imp in import_set:
        if not imp.startswith("from plotly.graph_objects import "):
            continue
        for node in ast.parse(imp).body:
            if isinstance(node, ast.ImportFrom) and all(alias.name in graph_objs_names for alias in node.names):
                to_remove.add(imp)
    import_set -= to_remove

    has_self = any("Self" in imp for imp in import_set)
    has_any = any("Any" in imp for imp in import_set)
    if not has_self or not has_any:
        typing_import = next((imp for imp in import_set if imp.startswith("from typing import")), None)
        if typing_import:
            new_typing = typing_import
            if not has_self:
                new_typing = new_typing.replace("from typing import ", "from typing import Self, ", 1)
            import_set.discard(typing_import)
            import_set.add(new_typing)
        else:
            import_set.add("from typing import Any, Self")

    sorted_imports = sorted(import_set)

    lines: list[str] = ["# pyright: reportUnusedImport=false"]
    lines.extend(sorted_imports)
    lines.append("")
    lines.append("")
    lines.append(f"class {class_name}({base_class}):")

    for raw, pragma in own_methods:
        lines.append(format_pyi_method(raw, pragma=pragma))
        lines.append("")

    if filtered_chaining:
        for raw in filtered_chaining:
            if raw.strip().startswith("def ") or raw.strip().startswith("@"):
                lines.append(raw)
            else:
                lines.append(format_pyi_method(raw))
            lines.append("")

    if not own_methods and not filtered_chaining:
        lines.append("    ...")

    lines.append("")
    return "\n".join(lines)


_CONSTANT_TYPES: dict[type, str] = {
    int: "int",
    float: "float",
    str: "str",
    bool: "bool",
    bytes: "bytes",
}


def collect_cross_module_imports(
    *,
    charts_dir: Path,
    module_stem: str,
) -> set[str]:
    """
    Find names that other chart modules import from *module_stem*.

    Scans every ``.py`` file in *charts_dir* for ``from ... import``
    statements that reference *module_stem*.

    Parameters
    ----------
    charts_dir
        Directory containing chart ``.py`` modules.
    module_stem
        Stem of the module to search for cross-module imports of.

    Returns
    -------
        Set of imported names used by other chart modules.

    See Also
    --------
    parse_chart_module_items : Consumer that uses these names to filter.

    Examples
    --------
    >>> collect_cross_module_imports(  # doctest: +SKIP
    ...     charts_dir=CHARTS_DIR,
    ...     module_stem="plot",
    ... )
    """
    needed: set[str] = set()
    module_dotted = f"mayutils.visualisation.graphs.plotly.charts.{module_stem}"

    for py_path in charts_dir.glob("*.py"):
        if py_path.stem in {module_stem, "__init__"}:
            continue
        tree = ast.parse(py_path.read_text())
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ImportFrom) and node.module == module_dotted:
                for alias in node.names:
                    needed.add(alias.name)
    return needed


def parse_chart_module_items(  # noqa: C901, PLR0912
    *,
    py_path: Path,
    charts_dir: Path,
) -> tuple[list[str], list[str]]:
    """
    Extract module-level constants, re-exports, and functions from a chart .py.

    Only emits names that other chart modules import from this module
    (cross-module re-exports), locally defined constants, and top-level
    ``def``s outside the chart class.

    Parameters
    ----------
    py_path
        Path to the chart ``.py`` source file.
    charts_dir
        Directory containing chart ``.py`` modules.

    Returns
    -------
        A ``(import_lines, stubs)`` pair ready for
        ``append_module_functions``.

    See Also
    --------
    collect_cross_module_imports : Finds which names need stubs.
    generate_chart_stubs : Caller that appends these items.

    Examples
    --------
    >>> imports, stubs = parse_chart_module_items(  # doctest: +SKIP
    ...     py_path=Path("charts/plot.py"),
    ...     charts_dir=CHARTS_DIR,
    ... )
    """
    source = py_path.read_text()
    tree = ast.parse(source)
    module_stem = py_path.stem

    needed_names = collect_cross_module_imports(
        charts_dir=charts_dir,
        module_stem=module_stem,
    )

    class_names = {node.name for node in ast.iter_child_nodes(tree) if isinstance(node, ast.ClassDef)}
    needed_names -= class_names

    import_lines: list[str] = []
    stubs: list[str] = []
    emitted: set[str] = set()

    for node in ast.iter_child_nodes(tree):
        if not (isinstance(node, ast.ImportFrom) and node.module):
            continue
        for alias in node.names:
            name = alias.asname or alias.name
            if name not in needed_names or name in emitted:
                continue
            import_lines.append(f"from {node.module} import {alias.name}")
            stubs.append(f"{name}: int")
            emitted.add(name)

    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                if target.id not in needed_names or target.id in emitted:
                    continue
                if isinstance(node.value, ast.Constant):
                    py_type = _CONSTANT_TYPES.get(type(node.value.value), "Any")
                    stubs.append(f"{target.id}: {py_type}")
                else:
                    stubs.append(f"{target.id}: Any")
                emitted.add(target.id)

    for node in ast.iter_child_nodes(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        stub_node = copy.deepcopy(node)
        stub_node.body = [ast.Expr(value=ast.Constant(value=Ellipsis))]
        raw = ast.unparse(stub_node)
        stubs.append(format_pyi_method(raw, indent=""))

    return import_lines, stubs


def generate_chart_stubs(
    *,
    stubs_root: Path,
    charts_dir: Path,
    dry_run: bool = False,
) -> list[str]:
    """
    Generate ``.pyi`` stubs for the Plot and SubPlot chart classes.

    Builds each chart stub, appends module-level items, validates the
    output path, and writes to disk.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.
    charts_dir
        Directory containing the chart ``.py`` source modules.
    dry_run
        If ``True``, print what would be generated without writing.

    Returns
    -------
        List of class names that were (or would be) generated.

    Raises
    ------
    FileNotFoundError
        If the resolved output path falls outside *charts_dir*.

    See Also
    --------
    generate_chart_stub : Builds an individual chart stub.
    generate : Top-level orchestrator that calls this.

    Examples
    --------
    >>> generate_chart_stubs(  # doctest: +SKIP
    ...     stubs_root=find_stubs_root(),
    ...     charts_dir=CHARTS_DIR,
    ... )
    """
    figure_stub = stubs_root / "graph_objs" / "_figure.pyi"
    if not figure_stub.exists():
        CONSOLE.print("[yellow]Skipping chart stubs: _figure.pyi not found[/yellow]")
        return []

    generated: list[str] = []

    configs = [
        ("plot.py", "Plot", "go.Figure"),
        ("subplot.py", "SubPlot", "Plot"),
    ]

    for filename, class_name, base_class in configs:
        py_path = charts_dir / filename
        pyi_path = charts_dir / f"{Path(filename).stem}.pyi"

        if not py_path.exists():
            CONSOLE.print(f"[yellow]Skipping {class_name}: {py_path} not found[/yellow]")
            continue

        if dry_run:
            CONSOLE.print(f"[cyan]Would generate {pyi_path}[/cyan]")
            generated.append(class_name)
            continue

        content = generate_chart_stub(
            py_path=py_path,
            class_name=class_name,
            base_class=base_class,
            figure_stub_path=figure_stub,
        )

        item_imports, item_stubs = parse_chart_module_items(
            py_path=py_path,
            charts_dir=charts_dir,
        )
        if item_stubs:
            content = append_module_functions(
                stub_text=content,
                func_imports=item_imports,
                func_stubs=item_stubs,
            )

        charts_dir_resolved = charts_dir.resolve()
        pyi_path_resolved = pyi_path.resolve()
        try:
            pyi_path_resolved.relative_to(charts_dir_resolved)
        except ValueError as err:
            msg = "Invalid file path"
            raise FileNotFoundError(msg) from err

        pyi_path_resolved.write_text(content)
        generated.append(class_name)
        CONSOLE.print(f"[green]Generated {pyi_path}[/green]")

    return generated


## Dev-only stubs (typings/plotly/)


def generate_basedatatypes_stub(  # noqa: C901
    *,
    stubs_root: Path,
    typings_dir: Path,
    dry_run: bool = False,
) -> bool:
    """
    Generate the patched ``basedatatypes.pyi`` with ``Self`` returns.

    Copies the upstream stub, injects ``Self`` return types for
    chaining methods, and adds ``BaseTraceType`` property stubs.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.
    typings_dir
        Project ``typings/`` directory where the stub is written.
    dry_run
        If ``True``, print what would be generated without writing.

    Returns
    -------
        ``True`` if the stub was (or would be) generated, ``False`` if
        the upstream source was not found.

    Raises
    ------
    FileNotFoundError
        If the resolved source or destination path falls outside the
        expected directory.

    See Also
    --------
    check_upstream : Warns when this stub may be obsolete.
    generate : Top-level orchestrator that calls this.

    Examples
    --------
    >>> generate_basedatatypes_stub(  # doctest: +SKIP
    ...     stubs_root=find_stubs_root(),
    ...     typings_dir=TYPINGS_DIR,
    ... )
    """
    source = stubs_root / "basedatatypes.pyi"
    stubs_root_resolved = stubs_root.resolve()
    source_resolved = source.resolve()
    try:
        source_resolved.relative_to(stubs_root_resolved)
    except ValueError as err:
        msg = "Invalid file path"
        raise FileNotFoundError(msg) from err

    if not source_resolved.exists():
        CONSOLE.print("[yellow]Skipping basedatatypes: stub not found[/yellow]")
        return False

    dest = typings_dir / "plotly" / "basedatatypes.pyi"

    if dry_run:
        CONSOLE.print(f"[cyan]Would generate {dest}[/cyan]")
        return True

    text = source_resolved.read_text()

    typing_import_match = re.search(r"^from typing import (.+)$", text, re.MULTILINE)
    if typing_import_match:
        current_imports = typing_import_match.group(1)
        if "Self" not in current_imports:
            text = text.replace(
                typing_import_match.group(0),
                f"from typing import Self, {current_imports}",
                1,
            )
    else:
        text = "from typing import Self\n" + text

    self_replacements = {
        r"(\) -> BaseFigure:)": ") -> Self:",
        r"(\) -> BasePlotlyType:)": ") -> Self:",
    }
    for pattern, replacement in self_replacements.items():
        text = re.sub(pattern, replacement, text)

    trace_type_section = text.find("class BaseTraceType")
    if trace_type_section != -1:
        init_match = re.search(
            r"(class BaseTraceType.*?def __init__\(.*?\) -> None: \.\.\.)",
            text[trace_type_section:],
            re.DOTALL,
        )
        if init_match:
            insert_pos = trace_type_section + init_match.end()
            property_lines: list[str] = []
            for prop_name, prop_type in BASETRACETYPE_PROPERTIES.items():
                property_lines.append("    @property")
                property_lines.append(f"    def {prop_name}(self) -> {prop_type}: ...")
                property_lines.append(f"    @{prop_name}.setter")
                property_lines.append(f"    def {prop_name}(self, val: {prop_type}) -> None: ...")

            property_block = "\n" + "\n".join(property_lines) + "\n"
            text = text[:insert_pos] + property_block + text[insert_pos:]

    dest.parent.mkdir(parents=True, exist_ok=True)

    typings_dir_resolved = typings_dir.resolve()
    dest_resolved = dest.resolve()
    try:
        dest_resolved.relative_to(typings_dir_resolved)
    except ValueError as err:
        msg = "Invalid file path"
        raise FileNotFoundError(msg) from err

    dest_resolved.write_text(text)
    CONSOLE.print(f"[green]Generated {dest}[/green]")
    return True


_SUBPLOTS_STUB = """\
from collections.abc import Sequence
from typing import Any, NamedTuple


class SubplotRef(NamedTuple):
    subplot_type: str
    layout_keys: tuple[str, ...]
    trace_kwargs: dict[str, Any]


class SubplotDomain(NamedTuple):
    x: tuple[float, float]
    y: tuple[float, float]


class SubplotXY(NamedTuple):
    xaxis: Any
    yaxis: Any


def _build_subplot_title_annotations(
    subplot_titles: Sequence[str],
    list_of_domains: Sequence[tuple[float, float]],
    title_edge: str = ...,
    offset: float = ...,
) -> list[dict[str, Any]]: ...
"""


_MESH3D_STUB = """\
from typing import Any

from plotly.basedatatypes import BaseTraceType


class Mesh3d(BaseTraceType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        x: Any = ...,
        y: Any = ...,
        z: Any = ...,
        i: Any = ...,
        j: Any = ...,
        k: Any = ...,
        intensity: Any = ...,
        alphahull: float = ...,
        flatshading: bool = ...,
        showscale: bool = ...,
        colorscale: Any = ...,
        cmin: float = ...,
        cmax: float = ...,
        customdata: Any = ...,
        hovertemplate: str = ...,
        meta: Any = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        scene: str | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,
    ) -> None: ...
"""


_ICICLE_STUB = """\
from typing import Any

from plotly.basedatatypes import BaseTraceType


class Icicle(BaseTraceType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        ids: Any = ...,
        labels: Any = ...,
        parents: Any = ...,
        values: Any = ...,
        branchvalues: str | None = ...,
        customdata: Any = ...,
        hovertemplate: str = ...,
        marker: Any = ...,
        meta: Any = ...,
        name: str | int | None = ...,
        opacity: float | None = ...,
        showlegend: bool | None = ...,
        visible: bool | str | None = ...,
        **kwargs: Any,
    ) -> None: ...
"""


_TEMPLATE_STUB = """\
from typing import Any

from plotly.basedatatypes import BaseLayoutHierarchyType


class Template(BaseLayoutHierarchyType):
    def __init__(
        self,
        arg: dict[str, Any] | None = ...,
        *,
        data: Any = ...,
        layout: Any = ...,
        **kwargs: Any,
    ) -> None: ...
    @property
    def data(self) -> Any: ...
    @data.setter
    def data(self, val: Any) -> None: ...
    @property
    def layout(self) -> Any: ...
    @layout.setter
    def layout(self, val: Any) -> None: ...
"""


_TEMPLATE_STUBS: dict[str, tuple[str, str]] = {
    "plotly/_subplots.pyi": (_SUBPLOTS_STUB, "_subplots stubs"),
    "plotly/graph_objs/_mesh3d.pyi": (_MESH3D_STUB, "Mesh3d stubs"),
    "plotly/graph_objs/_icicle.pyi": (_ICICLE_STUB, "Icicle stubs"),
    "plotly/graph_objs/layout/_template.pyi": (_TEMPLATE_STUB, "Template stubs"),
}


def generate_template_stubs(
    typings_dir: Path,
    /,
    *,
    dry_run: bool = False,
) -> list[str]:
    """
    Write hard-coded template stubs for missing plotly sub-components.

    Generates stubs for ``_subplots``, ``Mesh3d``, ``Icicle``, and
    ``Template`` from the inline string constants defined in this module.

    Parameters
    ----------
    typings_dir
        Project ``typings/`` directory where stubs are written.
    dry_run
        If ``True``, print what would be generated without writing.

    Returns
    -------
        List of label strings for each stub that was (or would be)
        generated.

    See Also
    --------
    generate_subcomponent_stubs : Generates stubs for discovered gaps.
    generate : Top-level orchestrator that calls this.

    Examples
    --------
    >>> generate_template_stubs(TYPINGS_DIR)  # doctest: +SKIP
    """
    generated: list[str] = []
    for rel_path, (content, label) in _TEMPLATE_STUBS.items():
        dest = typings_dir / rel_path
        if dry_run:
            CONSOLE.print(f"[cyan]Would generate {dest} ({label})[/cyan]")
            generated.append(label)
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(textwrap.dedent(content))
        generated.append(label)
        CONSOLE.print(f"[green]Generated {dest} ({label})[/green]")

    return generated


## Sub-component stub generation (scatter, layout, bar, etc.)


def find_missing_submodule_stubs(
    stubs_root: Path,
    /,
) -> dict[Path, list[str]]:
    """
    Scan plotly-stubs for imports from sub-module .pyi files that don't exist.

    Walks ``__init__.pyi`` files and checks each ``from plotly.X import Y``
    for a corresponding ``_y.pyi``.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.

    Returns
    -------
        Mapping from the ``__init__.pyi`` that does the re-export
        to a list of class names whose backing ``_<name>.pyi`` is missing.

    See Also
    --------
    generate_subcomponent_stubs : Consumer that generates the stubs.
    find_missing_subpackages : Finds missing directories instead.

    Examples
    --------
    >>> find_missing_submodule_stubs(  # doctest: +SKIP
    ...     find_stubs_root(),
    ... )
    """
    missing: dict[Path, list[str]] = {}

    for init_pyi in stubs_root.rglob("__init__.pyi"):
        text = init_pyi.read_text()
        for match in re.finditer(
            r"from\s+(plotly\.\S+)\s+import\s+(\w+)",
            text,
        ):
            module_path_str, class_name = match.groups()
            parts = module_path_str.replace("plotly.", "").replace(".", "/")
            expected_pyi = stubs_root / f"{parts}.pyi"
            if not expected_pyi.exists():
                missing.setdefault(init_pyi, []).append(class_name)

    return missing


def find_missing_subpackages(  # noqa: C901
    stubs_root: Path,
    /,
) -> dict[str, set[str]]:
    """
    Find sub-package alias imports that reference directories without stubs.

    Scans all ``__init__.pyi`` for ``import plotly.X.Y as Y`` where the
    target directory ``Y/`` has no ``__init__.pyi``.  Then scans
    ``_figure.pyi`` to infer which class names (``Marker``, ``Textfont``,
    etc.) are referenced via ``Y.ClassName``.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.

    Returns
    -------
        Mapping from dotted module path to the set of class names
        referenced from that module, e.g.
        ``{dotted_module: {ClassName, ...}}``.

    See Also
    --------
    find_missing_submodule_stubs : Finds missing individual files.
    generate_subcomponent_stubs : Consumer that generates the stubs.

    Examples
    --------
    >>> find_missing_subpackages(find_stubs_root())  # doctest: +SKIP
    """
    missing_packages: dict[str, set[str]] = {}

    for init_pyi in stubs_root.rglob("__init__.pyi"):
        text = init_pyi.read_text()
        for match in re.finditer(
            r"^import (plotly\.\S+) as (\w+)\s*",
            text,
            re.MULTILINE,
        ):
            full_module = match.group(1)
            parts = full_module.replace("plotly.", "").replace(".", "/")
            target_dir = stubs_root / parts
            if not (target_dir / "__init__.pyi").exists():
                missing_packages.setdefault(full_module, set())

    figure_stub = stubs_root / "graph_objs" / "_figure.pyi"
    if figure_stub.exists():
        figure_text = figure_stub.read_text()
        for module_path in list(missing_packages):
            alias = module_path.rsplit(".", 1)[-1]
            parent_module = module_path.rsplit(".", 1)[0].rsplit(".", 1)[-1]
            for class_match in re.finditer(
                rf"\b{parent_module}\.{alias}\.(\w+)\b",
                figure_text,
            ):
                missing_packages[module_path].add(class_match.group(1))

    for init_pyi in stubs_root.rglob("__init__.pyi"):
        text = init_pyi.read_text()
        for module_path in list(missing_packages):
            parts = module_path.replace("plotly.", "").replace(".", "/")
            if str(init_pyi.parent.relative_to(stubs_root)) != str(Path(parts).parent):
                continue
            alias = module_path.rsplit(".", 1)[-1]
            for class_match in re.finditer(
                rf"\b{alias}\.(\w+)\b",
                text,
            ):
                cls_name = class_match.group(1)
                if cls_name[0].isupper():
                    missing_packages[module_path].add(cls_name)

    return {k: v for k, v in missing_packages.items() if v}


def generate_subcomponent_stubs(
    *,
    stubs_root: Path,
    typings_dir: Path,
    dry_run: bool = False,
) -> list[str]:
    """
    Generate minimal stubs for plotly sub-component classes whose .pyi files are missing.

    Creates bare-bones class stubs for both individual missing
    sub-module files and entire missing sub-packages.

    Parameters
    ----------
    stubs_root
        Root directory of the installed ``plotly-stubs`` package.
    typings_dir
        Project ``typings/`` directory where stubs are written.
    dry_run
        If ``True``, print what would be generated without writing.

    Returns
    -------
        List of label strings for each group of stubs generated.

    See Also
    --------
    find_missing_submodule_stubs : Discovers missing individual files.
    find_missing_subpackages : Discovers missing sub-package directories.

    Examples
    --------
    >>> generate_subcomponent_stubs(  # doctest: +SKIP
    ...     stubs_root=find_stubs_root(),
    ...     typings_dir=TYPINGS_DIR,
    ... )
    """
    missing = find_missing_submodule_stubs(stubs_root)
    generated: list[str] = []

    for init_pyi, class_names in missing.items():
        rel_dir = init_pyi.parent.relative_to(stubs_root)
        dest = typings_dir / "plotly" / rel_dir / "__init__.pyi"

        original_text = init_pyi.read_text()

        new_names = [n for n in class_names if f"class {n}" not in original_text]
        if not new_names:
            continue

        label = f"{rel_dir} sub-components ({len(new_names)} classes)"

        if dry_run:
            CONSOLE.print(f"[cyan]Would generate {dest} ({label})[/cyan]")
            generated.append(label)
            continue

        is_layout = "layout" in str(rel_dir)
        base_class = "BaseLayoutHierarchyType" if is_layout else "BaseTraceHierarchyType"

        patched = original_text.rstrip() + "\n\n"
        patched += "from typing import Any\n"
        patched += f"from plotly.basedatatypes import {base_class}\n\n"

        for name in sorted(set(new_names)):
            from_line = f"from plotly.{'.'.join(rel_dir.parts)}._{name.lower()} import {name}"
            patched = patched.replace(from_line, "")
            patched += f"class {name}({base_class}):\n"
            patched += "    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...\n\n"

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(patched)
        generated.append(label)
        CONSOLE.print(f"[green]Generated {dest} ({label})[/green]")

    missing_pkgs = find_missing_subpackages(stubs_root)
    for module_path, missing_class_names in missing_pkgs.items():
        rel_path = module_path.replace("plotly.", "").replace(".", "/")
        dest = typings_dir / "plotly" / rel_path / "__init__.pyi"

        class_names = missing_class_names

        if dest.exists():
            existing = dest.read_text()
            class_names = {n for n in class_names if f"class {n}" not in existing}
            if not class_names:
                continue

        label = f"{rel_path} sub-package ({len(class_names)} classes)"

        if dry_run:
            CONSOLE.print(f"[cyan]Would generate {dest} ({label})[/cyan]")
            generated.append(label)
            continue

        lines = [
            "from typing import Any",
            "",
            "from plotly.basedatatypes import BaseTraceHierarchyType",
            "",
        ]
        for name in sorted(class_names):
            lines.append(f"class {name}(BaseTraceHierarchyType):")
            lines.append("    def __init__(self, arg: dict[str, Any] | None = ..., **kwargs: Any) -> None: ...")
            lines.append("")

        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text("\n".join(lines) + "\n")
        generated.append(label)
        CONSOLE.print(f"[green]Generated {dest} ({label})[/green]")

    return generated


## Main command


@app.command()
def generate(
    traces_dir: Path = Argument(  # noqa: B008
        TRACES_DIR,
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        writable=True,
        resolve_path=True,
        help="Directory containing the trace .py modules",
    ),
    *,
    dry_run: bool = Option(
        False,  # noqa: FBT003
        "--dry-run",
        "-n",
        help="List stubs that would be generated without writing",
    ),
) -> None:
    """
    Generate all plotly-related type stubs.

    Orchestrates trace, chart, basedatatypes, template, and
    sub-component stub generation, then runs ``ruff`` to fix and
    format the output.

    Parameters
    ----------
    traces_dir
        Directory containing the trace ``.py`` modules.
    dry_run
        If ``True``, list stubs that would be generated without
        writing any files.

    Raises
    ------
    Exit
        If no stubs were generated (or would be generated in dry-run
        mode).

    See Also
    --------
    generate_trace_stubs : Trace stub generation step.
    generate_chart_stubs : Chart stub generation step.
    generate_basedatatypes_stub : Basedatatypes stub generation step.

    Examples
    --------
    >>> generate()  # doctest: +SKIP
    """
    stubs_root = find_stubs_root()
    CONSOLE.print(f"[blue]Using plotly-stubs from {stubs_root}[/blue]")

    check_upstream(stubs_root)

    CONSOLE.print("\n[bold]Generating trace stubs...[/bold]")
    trace_results = generate_trace_stubs(
        stubs_root=stubs_root,
        traces_dir=traces_dir,
        dry_run=dry_run,
    )

    CONSOLE.print("\n[bold]Generating chart stubs...[/bold]")
    chart_results = generate_chart_stubs(
        stubs_root=stubs_root,
        charts_dir=CHARTS_DIR,
        dry_run=dry_run,
    )

    CONSOLE.print("\n[bold]Generating dev-only stubs (typings/plotly/)...[/bold]")
    basedatatypes_ok = generate_basedatatypes_stub(
        stubs_root=stubs_root,
        typings_dir=TYPINGS_DIR,
        dry_run=dry_run,
    )
    template_results = generate_template_stubs(
        TYPINGS_DIR,
        dry_run=dry_run,
    )
    subcomponent_results = generate_subcomponent_stubs(
        stubs_root=stubs_root,
        typings_dir=TYPINGS_DIR,
        dry_run=dry_run,
    )

    total = len(trace_results) + len(chart_results) + (1 if basedatatypes_ok else 0) + len(template_results) + len(subcomponent_results)
    verb = "would be " if dry_run else ""
    CONSOLE.print(f"\n[green]Done: {total} stub(s) {verb}generated.[/green]")

    if total == 0:
        raise Exit

    if not dry_run:
        fmt_targets = [str(TRACES_DIR), str(CHARTS_DIR)]
        CONSOLE.print("\n[bold]Running ruff check --fix and format...[/bold]")
        subprocess.run(  # noqa: S603
            ["ruff", "check", "--fix", "--silent", *fmt_targets],  # noqa: S607
            check=False,
        )
        subprocess.run(  # noqa: S603
            ["ruff", "format", "--silent", *fmt_targets],  # noqa: S607
            check=False,
        )


if __name__ == "__main__":
    app()
