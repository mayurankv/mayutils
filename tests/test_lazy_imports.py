"""Test that mayutils modules import without optional extras where expected.

This test locks in which mayutils modules are importable without installing
optional dependencies. The test runs in a subprocess with optional packages
blocked, checking that only expected modules fail at import time. Modules that
fail structurally (e.g. inherit from optional-library base classes, use
import-time decorators, or have module-level instances of optional types) are
allowlisted; all other failures trigger an assertion to prevent regressions.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# The 31 modules structurally blocked by optional-library base classes,
# import-time decorators, or module-level instances that cannot be deferred.
EXPECTED_BLOCKED: frozenset[str] = frozenset(
    {
        "mayutils.export.html",  # html2image
        "mayutils.interfaces.filetypes.pptx",  # pptx (imports pptx.units / pptx.markdown)
        "mayutils.interfaces.filetypes.pptx.markdown",  # pptx
        "mayutils.interfaces.filetypes.pptx.units",  # pptx (class Length(BaseLength))
        "mayutils.interfaces.data.snowflake",  # snowflake (subclasses connection/session)
        "mayutils.mathematics.numba",  # numba, numpy (@njit at import)
        "mayutils.objects.dataframes.pandas.stylers",  # pandas (class Styler(Style))
        "mayutils.visualisation.graphs.plotly.traces.ecdf",  # plotly (imports line.py)
        "mayutils.visualisation.graphs.plotly.traces.kde",  # plotly (imports line.py)
        "mayutils.visualisation.graphs.plotly.traces.line",  # plotly.graph_objects
        "mayutils.visualisation.graphs.plotly.traces.mesh3d",  # plotly.graph_objects
        "mayutils.visualisation.graphs.plotly.traces.null",  # plotly.graph_objects
        "mayutils.objects.datetime",  # pendulum
        "mayutils.objects.datetime.constants",  # pendulum
        "mayutils.objects.datetime.datetime",  # pendulum
        "mayutils.objects.datetime.interval",  # pendulum
        "mayutils.objects.datetime.numpy",  # numpy
        "mayutils.objects.datetime.timezone",  # pendulum
        "mayutils.objects.datetime.traveller",  # pendulum
        "mayutils.visualisation.graphs.plotly.charts.plot",  # plotly.graph_objects, numpy
        "mayutils.visualisation.graphs.plotly.charts.subplot",  # plotly (imports plot/templates)
        "mayutils.visualisation.graphs.plotly.templates",  # plotly.graph_objects
        "mayutils.visualisation.graphs.plotly.traces.icicle",  # plotly.graph_objects
        "mayutils.visualisation.graphs.plotly.traces.scatter",  # plotly.graph_objects
        "mayutils.interfaces.code.tui.textual",  # textual
        "mayutils.interfaces.code.tui.tuiplot",  # textual, textual_image, rich, typer
        "mayutils.interfaces.websites.streamlit.views.forbidden",  # streamlit
        "mayutils.interfaces.websites.streamlit.views.login",  # streamlit
        "mayutils.scripts.clear_cache",  # typer
        "mayutils.scripts.generate_plotly_stubs",  # typer
        "mayutils.scripts.refresh_stubs",  # typer
    }
)

WORKER_SCRIPT: str = '''
"""Worker process to test lazy imports by blocking optional packages."""

from __future__ import annotations

import importlib
import importlib.metadata
import re
import sys
import tomllib
from pathlib import Path


def optional_import_names() -> set[str]:
    """Resolve top-level package names from pyproject optional-dependencies."""
    root = Path(sys.argv[1])
    pyproject = tomllib.loads((root / "pyproject.toml").read_text())
    dists: set[str] = set()
    for specs in pyproject["project"]["optional-dependencies"].values():
        for spec in specs:
            name = re.split(r"[\\[><=~!; ]", spec, maxsplit=1)[0].strip()
            if name and name != "mayutils":
                dists.add(name.lower())
    names: set[str] = set()
    for import_name, dist_names in importlib.metadata.packages_distributions().items():
        if any(d.lower() in dists for d in dist_names):
            names.add(import_name)
    return names - {"mayutils"}


BLOCKED = optional_import_names()


class Blocker:
    """Meta-path finder that raises ImportError for blocked packages."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: ANN001, ANN201
        """Block top-level package imports for optional extras."""
        top = fullname.split(".", 1)[0]
        if top in BLOCKED:
            raise ImportError(f"BLOCKED:{top}")
        return None


sys.meta_path.insert(0, Blocker())

root = Path(sys.argv[1])
modules: list[str] = []
for file in sorted((root / "src" / "mayutils").rglob("*.py")):
    rel = file.relative_to(root / "src")
    if "__pycache__" in rel.parts:
        continue
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    modules.append(".".join(parts))

failed: dict[str, str] = {}
for module in modules:
    try:
        importlib.import_module(module)
    except ImportError as err:
        message = str(err)
        match = re.search(r"BLOCKED:(\\w+)", message)
        failed[module] = match.group(1) if match else f"OTHER: {message[:80]}"
    except Exception as err:  # noqa: BLE001
        failed[module] = f"{type(err).__name__}: {str(err)[:80]}"

for module, cause in sorted(failed.items()):
    print(f"{module}\\t{cause}")
'''


def test_modules_import_without_extras() -> None:
    """Verify that all non-blocked modules import without optional extras.

    Runs a subprocess with optional packages blocked via meta-path finder,
    attempts to import all mayutils modules, and asserts that:
    - No new regressions (modules in blocked but not EXPECTED_BLOCKED).
    - No improvements without updating EXPECTED_BLOCKED.
    """
    repo_root = Path(__file__).parents[1]

    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", WORKER_SCRIPT, str(repo_root)],
        capture_output=True,
        text=True,
        check=True,
    )

    blocked: dict[str, str] = {}
    for line in result.stdout.strip().split("\n"):
        if line:
            module, cause = line.split("\t", 1)
            blocked[module] = cause

    # Check for regressions: modules newly hard-requiring extras.
    regressions = set(blocked) - EXPECTED_BLOCKED
    assert not regressions, (
        f"Regression: {len(regressions)} module(s) now hard-require an optional extra "
        f"at import time. Defer these imports to call time:\n"
        + "\n".join(f"  {module}: {blocked[module]}" for module in sorted(regressions))
    )

    # Check for improvements: modules now importing lazily.
    improvements = EXPECTED_BLOCKED - set(blocked)
    assert not improvements, (
        f"Improvement: {len(improvements)} module(s) now import lazily. "
        f"Remove them from EXPECTED_BLOCKED:\n" + "\n".join(f"  {module}" for module in sorted(improvements))
    )
