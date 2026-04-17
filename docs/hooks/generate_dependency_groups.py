"""MkDocs hook: regenerate the optional-extras table in the dependency-groups guide.

Reads ``[project.optional-dependencies]`` from ``pyproject.toml`` and
splices an up-to-date table into ``docs/guides/dependency-groups.md``
between two sentinel comments.
"""  # noqa: INP001

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from mkdocs.config.defaults import MkDocsConfig

MARKER_START = "<!-- BEGIN AUTO-GENERATED GROUPS TABLE -->"
MARKER_END = "<!-- END AUTO-GENERATED GROUPS TABLE -->"


def _render_table(
    pyproject: Path,
) -> str:
    data = tomllib.loads(pyproject.read_text())
    optional: dict[str, list[str]] = data.get("project", {}).get("optional-dependencies", {}) or {}

    lines = ["| Extra | Install | Distributions |", "| ----- | ------- | ------------- |"]
    for name in sorted(optional):
        dists = optional[name]
        rendered_dists = ", ".join(_format_distribution(spec=spec) for spec in dists)
        install = f'`uv add "mayutils[{name}]"`'
        lines.append(f"| `{name}` | {install} | {rendered_dists} |")

    return "\n".join(lines)


def _format_distribution(
    spec: str,
) -> str:
    without_marker = spec.split(";", maxsplit=1)[0].strip()
    head = (
        without_marker.split("[", maxsplit=1)[0]
        .split(">", maxsplit=1)[0]
        .split("<", maxsplit=1)[0]
        .split("=", maxsplit=1)[0]
        .split("!", maxsplit=1)[0]
        .split("~", maxsplit=1)[0]
        .strip()
    )
    dist_key = head.replace("_", "-").lower()

    if dist_key == "mayutils" and "[" in without_marker:
        sub_extras = without_marker.split("[", maxsplit=1)[1].rsplit("]", maxsplit=1)[0]
        parts = [f"`{extra.strip()}`" for extra in sub_extras.split(",") if extra.strip()]
        return "meta: " + " + ".join(parts)

    return f"`{head}`"


def on_pre_build(
    config: MkDocsConfig,
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """Regenerate the optional-extras table before the docs build.

    Parameters
    ----------
    config : MkDocsConfig
        MkDocs configuration object.
    **_kwargs : Any
        Additional keyword arguments provided by MkDocs.
    """
    doc = Path(config["docs_dir"]) / "guides" / "dependency-groups.md"  # pyright: ignore[reportUnknownArgumentType]
    pyproject = Path(config["docs_dir"]).parent / "pyproject.toml"  # pyright: ignore[reportUnknownArgumentType]
    if not doc.is_file() or not pyproject.is_file():
        return

    content = doc.read_text()
    if MARKER_START not in content or MARKER_END not in content:
        return

    before, _, tail = content.partition(MARKER_START)
    _, _, after = tail.partition(MARKER_END)

    table = _render_table(pyproject=pyproject)
    new_content = before + MARKER_START + "\n\n" + table + "\n\n" + MARKER_END + after

    if new_content != content:
        doc.write_text(new_content)
