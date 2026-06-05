"""
Generate API reference pages for every package module at docs build time.

Walk the ``src/`` source tree, filter out private packages and
``__pycache__`` artefacts, emit a stub ``reference/<module>.md`` file for
each surviving module via ``mkdocs_gen_files`` and assemble a literate
``reference/SUMMARY.md`` navigation file. The script executes at the
``on_files`` phase of MkDocs (that is the phase at which
``mkdocs-gen-files`` invokes configured scripts) and therefore runs once
per ``mkdocs build`` or ``mkdocs serve`` invocation. All writes are
routed through ``mkdocs_gen_files.open`` so the generated pages live
only in the virtual file tree that MkDocs then treats as part of
``docs/``.

See Also
--------
mkdocs_gen_files : Runtime used to materialise the virtual pages produced here.
mkdocstrings : Renders the ``::: <dotted.path>`` directives emitted for each module.
docs.hooks.readme_to_index : Companion build hook that writes ``docs/index.md``.
docs.hooks.generate_dependency_groups : Companion build hook that refreshes the extras table.

Examples
--------
Enable ``mkdocs-gen-files`` in ``mkdocs.yml`` so this script executes on build:

>>> # mkdocs.yml
>>> # plugins:
>>> #   - gen-files:
>>> #       scripts:
>>> #         - docs/gen_ref_pages.py
>>> #   - literate-nav:
>>> #       nav_file: SUMMARY.md

Build the site from the command line and the script runs automatically:

>>> # $ mkdocs build
>>> # $ mkdocs serve  # live-reload workflow
"""  # noqa: INP001

from pathlib import Path

import mkdocs_gen_files
from mkdocs_gen_files.nav import Nav

nav = Nav()

src = Path("src")

for path in sorted(src.rglob(pattern="*.py")):
    module_path = path.relative_to(src).with_suffix(suffix="")
    doc_path = path.relative_to(src).with_suffix(suffix=".md")
    full_doc_path = Path("reference", doc_path)

    parts = tuple(module_path.parts)

    if "__pycache__" in parts:
        continue

    if any(part.startswith("_") and part != "__init__" for part in parts):
        continue

    # A file named index.py in a package collides with __init__.py → index.md mapping.
    if parts[-1] == "index" and (path.parent / "__init__.py").exists():
        continue

    if parts[-1] == "__init__":
        parts = parts[:-1]
        if not parts:
            continue
        doc_path = doc_path.with_name(name="index.md")
        full_doc_path = full_doc_path.with_name(name="index.md")

    nav[parts] = doc_path.as_posix()

    with mkdocs_gen_files.open(full_doc_path, "w") as fd:
        ident = ".".join(parts)
        fd.write(f"::: {ident}\n")

    mkdocs_gen_files.set_edit_path(full_doc_path, path)

with mkdocs_gen_files.open("reference/SUMMARY.md", "w") as nav_file:
    nav_file.writelines(nav.build_literate_nav())
