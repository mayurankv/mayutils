"""
Regenerate ``docs/index.md`` from the repository ``README.md`` on build.

Copy the contents of ``README.md`` into ``docs/index.md`` and rewrite
relative links that point into the ``docs/`` directory so they resolve
correctly once MkDocs serves them from within ``docs/`` itself (for
example ``](docs/guides/x.md)`` becomes ``](guides/x.md)``). The module
exposes an ``on_pre_build`` entry point that MkDocs fires before any
files are indexed, ensuring the landing page is refreshed at the start
of every ``mkdocs build`` or ``mkdocs serve`` run. The write is a
straight overwrite, so the hook acts as the canonical source of the
rendered index page.

See Also
--------
mkdocs.plugins : Defines the ``on_pre_build`` event dispatched to this hook.
docs.gen_ref_pages : Companion ``mkdocs-gen-files`` script that materialises API reference pages.
mkdocstrings : Consumer of the reference stubs generated alongside this landing page.

Examples
--------
Register the hook in ``mkdocs.yml`` so MkDocs loads it automatically:

>>> # mkdocs.yml
>>> # hooks:
>>> #   - docs/hooks/readme_to_index.py

A standard build then rewrites ``docs/index.md`` in place:

>>> # $ mkdocs build   # or: mkdocs serve
"""  # noqa: INP001

import re
from pathlib import Path

from mkdocs.config.defaults import MkDocsConfig


def on_pre_build(
    config: MkDocsConfig,  # noqa: ARG001
    **_kwargs: object,
) -> None:
    """
    Regenerate ``docs/index.md`` from ``README.md`` before a docs build.

    Resolve ``README.md`` relative to the current working directory,
    silently return when it does not exist (so the hook degrades
    gracefully outside the repo root), read its content, and rewrite
    any ``](docs/...)`` Markdown link prefixes to their in-``docs``
    equivalents. The result is written verbatim to ``docs/index.md``,
    unconditionally overwriting the previous copy. MkDocs calls this
    function at the ``on_pre_build`` phase, which runs after
    configuration is loaded but before the file collection is built,
    so the regenerated landing page participates in the same build as
    the rest of the site.

    Parameters
    ----------
    config
        Fully resolved MkDocs configuration object supplied by the
        framework; accepted for API compliance but unused by this
        hook (links are rewritten relative to the working directory).
    **_kwargs
        Additional keyword arguments that MkDocs may pass to
        ``on_pre_build`` in future releases; ignored here.

    See Also
    --------
    mkdocs.plugins : Defines the ``on_pre_build`` event contract.
    docs.gen_ref_pages : ``mkdocs-gen-files`` script that generates API reference pages.
    mkdocstrings : Renders the reference stubs produced by ``gen_ref_pages``.

    Examples
    --------
    Register the hook so MkDocs invokes ``on_pre_build`` during every build:

    >>> # mkdocs.yml
    >>> # hooks:
    >>> #   - docs/hooks/readme_to_index.py

    Execute a build from the command line to trigger the rewrite:

    >>> # $ mkdocs build    # or: mkdocs serve
    """
    readme = Path("README.md")
    index = Path("docs/index.md")

    if not readme.exists():
        return

    content = readme.read_text()

    # Rewrite relative links: ](docs/foo.md) → ](foo.md)
    content = re.sub(r"\]\(docs/", "](", content)

    index.write_text(content)
