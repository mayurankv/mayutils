"""Image export path configuration for the mayutils export pipeline.

This module defines the canonical on-disk location used by mayutils export
utilities when persisting rendered image artefacts. The path is derived from
:data:`mayutils.export.OUTPUT_FOLDER` so that image outputs remain co-located
with other exported assets produced by the library (HTML, slides, PDFs).
Downstream helpers in :mod:`mayutils.export` import :data:`IMAGES_FOLDER` to
build deterministic output paths without hard-coding directory structure at
each call site.
"""

from mayutils.export import OUTPUT_FOLDER

IMAGES_FOLDER = OUTPUT_FOLDER / "Images"
