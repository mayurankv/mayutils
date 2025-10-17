from importlib import metadata
import re

data = metadata.metadata(distribution_name="mayutils")

__version__ = metadata.version(distribution_name="{{ cookiecutter.package_name }}")

author = data.get(name="author")
if author is not None:
    __author__ = author

full_email = data.get("author-email")
if full_email is not None:
    match = re.search(
        pattern=r"<(.*?)>",
        string=full_email,
    )

    if match is not None:
        __email__ = match.group(1)
