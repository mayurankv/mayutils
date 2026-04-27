"""
Wrap the Google Docs REST API as ergonomic Python objects.

Provide the scaffolding for helpers around the Google Docs v1 REST API
that pair a decoded ``Document`` response with a live
``googleapiclient.discovery.Resource`` service, mirroring the ergonomics
of the :mod:`mayutils.interfaces.filetypes.sheets` and
:mod:`mayutils.interfaces.filetypes.slides` modules. The intent is to
expose document-level mutations (inserting text, styling ranges,
appending tables) through ``batchUpdate`` requests while caching the
decoded payload locally so callers never hand-build request bodies.
Document lookups and creation from templates delegate to
:class:`mayutils.interfaces.cloud.google.Drive`, which resolves files by
name and handles uploads that exceed the inline payload size limit.

See Also
--------
mayutils.interfaces.cloud.google.Drive : Drive wrapper used for file lookup and uploads.
mayutils.interfaces.filetypes.sheets : Sibling helper wrapping Google Sheets.
mayutils.interfaces.filetypes.slides : Sibling helper wrapping Google Slides.
googleapiclient.discovery.Resource : Underlying service client used for ``batchUpdate`` calls.

Examples
--------
>>> from google.oauth2.credentials import Credentials
>>> from mayutils.interfaces.cloud.google import Drive
>>> creds = Credentials(token="ya29.a0Af...")  # doctest: +SKIP
>>> drive = Drive.from_creds(creds)  # doctest: +SKIP
>>> isinstance(drive, Drive)  # doctest: +SKIP
True
"""
