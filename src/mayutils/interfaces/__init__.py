"""
Provide adapters for third-party services, document formats, and runtimes.

Group the integration layers that connect ``mayutils`` to systems it
does not own: filetype-specific document authoring, cloud storage
clients, and Streamlit applications. Each submodule is guarded by an
optional dependency extra so installing the library stays lightweight.
The full mapping of submodule to extra is documented in
``docs/guides/dependency-groups.md``. The ``cloud`` namespace exposes
service facades such as Google Drive, ``filetypes`` covers ``markdown``,
``pptx``, ``pdf``, ``sheets``, ``slides``, ``docx``, and ``xlsx``, while
``streamlit`` provides helpers for dashboard authoring.

See Also
--------
mayutils.interfaces.filetypes : Filetype-dependent authoring and rendering helpers.
mayutils.interfaces.cloud : Cloud storage service facades such as Google Drive.
mayutils.interfaces.streamlit : Utilities for building Streamlit dashboards.

Examples
--------
>>> from mayutils.interfaces.filetypes.xlsx import Xlsx
>>> from mayutils.interfaces.cloud.google import Drive
>>> Xlsx.__name__, Drive.__name__
('Xlsx', 'Drive')
"""
