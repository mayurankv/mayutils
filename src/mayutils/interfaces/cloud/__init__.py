"""
Group cloud storage service facades for third-party providers.

Collect the high-level wrappers used by ``mayutils`` to interact with
third-party cloud storage providers. Each submodule is named after its
provider, so :mod:`mayutils.interfaces.cloud.google` houses the Google
Drive file-management facade built on top of ``googleapiclient``'s
generated Drive resource. Callers import providers directly from this
namespace to keep optional cloud dependencies isolated behind dedicated
extras. New provider integrations should follow the same one-module-per
-service convention.

See Also
--------
mayutils.interfaces.cloud.google : Google Drive file-management facade
    built on the Drive v3 REST API.
googleapiclient.discovery.build : Factory used by sibling cloud helpers
    to instantiate authenticated service clients.
mayutils.interfaces.filetypes : Sibling integration namespace covering
    local filetype authoring used alongside cloud uploads.

Examples
--------
>>> from google.oauth2.credentials import Credentials
>>> from mayutils.interfaces.cloud.google import Drive
>>> creds = Credentials(token="ya29.a0Af...")  # doctest: +SKIP
>>> drive = Drive.from_creds(creds)  # doctest: +SKIP
>>> file_id = drive.find_file_id("quarterly_report.pdf")  # doctest: +SKIP
>>> drive.upload("/tmp/report.pdf", folder_id="0APnK...")  # doctest: +SKIP
"""
