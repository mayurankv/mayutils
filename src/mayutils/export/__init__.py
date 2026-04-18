"""Exporters for HTML, PDF, images and PowerPoint slides.

Submodules
----------
html
    HTML rendering (``plotting`` extra: html2image + markdown).
images
    Image export helpers (``plotting``/``pdf`` extras).
nbconvert
    PDF export via ``jupyter nbconvert``.
quarto
    Multi-format (pdf/html/docx/pptx/revealjs) export via the bundled
    ``quarto-cli`` binary.
slides
    PowerPoint export (``microsoft`` extra: python-pptx).
"""

from mayutils.environment.filesystem import get_root

OUTPUT_FOLDER = get_root() / "Outputs"
