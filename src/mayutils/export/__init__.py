"""Export utilities for rendering mayutils artefacts to external formats.

This subpackage groups the exporters that convert in-memory mayutils
objects (plots, tables, notebooks, markdown, slide definitions) into
distributable artefacts such as HTML documents, static images, PDF
reports and PowerPoint decks. It also exposes a canonical
``OUTPUT_FOLDER`` location, anchored to the project root discovered by
:func:`mayutils.environment.filesystem.get_root`, so that every exporter
writes to a consistent place on disk.

Submodules
----------
html
    HTML rendering backed by ``html2image`` and ``markdown`` (requires
    the ``plotting`` extra).
images
    Image export helpers for converting figures and documents to raster
    or vector images (requires the ``plotting`` or ``pdf`` extras).
nbconvert
    PDF export driven by ``jupyter nbconvert`` for notebook-based
    reports.
quarto
    Multi-format export (``pdf``, ``html``, ``docx``, ``pptx``,
    ``revealjs``) delegated to the bundled ``quarto-cli`` binary.
slides
    PowerPoint deck export powered by ``python-pptx`` (requires the
    ``microsoft`` extra).

Attributes
----------
OUTPUT_FOLDER : pathlib.Path
    Absolute path to the ``Outputs`` directory at the repository root
    resolved via :func:`mayutils.environment.filesystem.get_root`. Used
    as the default destination for every exporter in this subpackage so
    generated files land in a predictable location.
"""

from mayutils.environment.filesystem import get_root

OUTPUT_FOLDER = get_root() / "Outputs"
