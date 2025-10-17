from importlib import metadata
import re

data = metadata.metadata(distribution_name="{{ cookiecutter.__package_snake }}")

__version__ = metadata.version(distribution_name="{{ cookiecutter.__package_snake }}")

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
