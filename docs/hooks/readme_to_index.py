"""MkDocs hook: generate ``docs/index.md`` from ``README.md`` at build time.

Rewrites ``docs/`` link prefixes so they resolve correctly when served
from the ``docs/`` directory.
"""  # noqa: INP001

import re
from pathlib import Path
from typing import Any

from mkdocs.config.defaults import MkDocsConfig


def on_pre_build(
    config: MkDocsConfig,  # noqa: ARG001
    **_kwargs: Any,  # noqa: ANN401
) -> None:
    """Generate ``docs/index.md`` from ``README.md`` before a docs build.

    Parameters
    ----------
    config : MkDocsConfig
        MkDocs configuration object passed to the hook.
    **_kwargs : Any
        Additional keyword arguments provided by MkDocs.
    """
    readme = Path("README.md")
    index = Path("docs/index.md")

    if not readme.exists():
        return

    content = readme.read_text()

    # Rewrite relative links: ](docs/foo.md) → ](foo.md)
    content = re.sub(r"\]\(docs/", "](", content)

    index.write_text(content)
