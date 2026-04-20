"""Google Workspace service facades for Drive, Sheets, and Slides.

This package groups the high-level wrappers used by ``mayutils`` to interact
with Google Workspace APIs. It re-exports the :class:`Drive` file-management
facade, the :class:`Sheet` and :class:`Sheets` spreadsheet accessors, and the
:class:`Slides` presentation facade so that downstream modules can import
them from a single, stable namespace without reaching into submodules.
"""

from mayutils.interfaces.google.drive import Drive
from mayutils.interfaces.google.sheets import Sheet, Sheets
from mayutils.interfaces.google.slides import Slides

__all__ = [
    "Drive",
    "Sheet",
    "Sheets",
    "Slides",
]
