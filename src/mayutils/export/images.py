"""
Configure the canonical on-disk image export location for mayutils.

Derive the :data:`IMAGES_FOLDER` path from :data:`mayutils.export.OUTPUT_FOLDER`
so rendered image artefacts sit alongside HTML, slide, and PDF exports produced
elsewhere in :mod:`mayutils.export`. Centralising the path here lets downstream
helpers that rely on ``PIL.Image``, ``html2image``, ``kaleido``, or
``dataframe_image`` write PNG, JPEG, SVG, or WebP outputs (honouring DPI,
pixel-size scaling, and alpha transparency) to a deterministic folder without
hard-coding directory structure at each call site.

See Also
--------
mayutils.export.OUTPUT_FOLDER : Root export directory that this module extends.
PIL.Image : Pillow image objects frequently persisted into ``IMAGES_FOLDER``.
html2image : HTML-to-PNG renderer that writes into ``IMAGES_FOLDER``.
kaleido : Static figure renderer used by Plotly exports writing PNG/SVG files.
dataframe_image : Library for exporting styled pandas tables as images.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from mayutils.export.images import IMAGES_FOLDER
>>> from PIL import Image
>>> IMAGES_FOLDER.name
'Images'
>>> with tempfile.TemporaryDirectory() as _tmp:
...     _out = Path(_tmp) / "transparent_banner.png"
...     img = Image.new("RGBA", (16, 9), (255, 255, 255, 0))
...     img.save(_out, dpi=(300, 300))
...     _out.exists()
True
"""

from mayutils.export import OUTPUT_FOLDER

IMAGES_FOLDER = OUTPUT_FOLDER / "Images"
