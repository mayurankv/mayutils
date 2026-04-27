"""
Expose shared package-level constants used across :mod:`mayutils`.

Centralises singleton instances and literal values that need to stay
identical across subpackages, so lookups and comparisons remain
consistent regardless of which feature module first imports them. The
module is kept intentionally dependency-light and free of optional
extras, which makes it safe to import from any bootstrap path without
pulling in heavier runtimes. Heavier shared singletons whose creation
depends on third-party libraries live in the feature-specific submodules
behind their own optional-dependency groups and are never re-exported
from here.

See Also
--------
mayutils.core.extras : Companion module that resolves which optional
    extras ship a given import and formats actionable install hints.
mayutils : Top-level package whose subpackages consume the constants
    defined here to keep identifier values in lockstep.

Examples
--------
>>> from mayutils.core import constants
>>> constants.__name__
'mayutils.core.constants'
"""
