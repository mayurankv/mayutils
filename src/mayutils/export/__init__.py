"""
Render mayutils artefacts to external distributable formats.

Group the exporters that convert in-memory mayutils objects such as
plots, tables, notebooks and markdown definitions into distributable
artefacts including HTML documents, static images, PDF reports and
PowerPoint decks. Expose a canonical ``OUTPUT_FOLDER`` location,
anchored to the project root discovered by
:func:`mayutils.environment.filesystem.get_root`, so every exporter
writes to a consistent place on disk. Submodules are import-gated so
optional dependencies declared as package extras remain opt-in at
install time.

Attributes
----------
OUTPUT_FOLDER : pathlib.Path
    Absolute path to the ``Outputs`` directory at the repository root
    resolved via :func:`mayutils.environment.filesystem.get_root`. Used
    as the default destination for every exporter in this subpackage so
    generated files land in a predictable location.

See Also
--------
mayutils.export.html : HTML rendering backed by ``html2image`` and ``markdown``.
mayutils.export.images : Image export helpers for figures and documents.
mayutils.export.nbconvert : Multi-format notebook export via ``jupyter nbconvert``.
mayutils.export.quarto : Multi-format export delegated to the ``quarto-cli`` binary.
mayutils.environment.filesystem : Git- and path-aware filesystem utilities.

Examples
--------
>>> from mayutils.export import OUTPUT_FOLDER
>>> from mayutils.export.quarto import export
>>> OUTPUT_FOLDER.name
'Outputs'
>>> callable(export)
True
"""

from mayutils.environment.filesystem import get_root

OUTPUT_FOLDER = get_root() / "Outputs"
