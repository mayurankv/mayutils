"""
Collect shared testing utilities for the ``mayutils`` library.

Group reusable fixtures, assertion helpers, and harness primitives that
keep the project's ``pytest`` suite consistent, reproducible and easy to
extend. Modules in this package are intended to be imported from test
files across the codebase so that numerical comparisons, temporary
resource management and environment scaffolding follow the same
conventions everywhere. Keeping the utilities in a dedicated namespace
avoids duplicating boilerplate across ``tests/`` directories and makes
it straightforward to share the helpers with downstream projects that
extend ``mayutils``.

See Also
--------
pytest : Third-party framework that consumes the fixtures and helpers
    exposed by this package.
unittest : Standard library test framework whose ``mock`` module pairs
    naturally with the harness utilities gathered here.
numpy.testing : Numeric assertion helpers (``assert_allclose`` and
    friends) preferred over ``pytest.approx`` by project convention.
mayutils.environment.logging : Logging configuration re-used when
    tests need deterministic log capture.

Examples
--------
>>> import mayutils.testing as mt
>>> hasattr(mt, "__doc__")
True
"""
