"""
Provide Selenium WebDriver factory helpers for browser automation.

Centralise construction of Selenium WebDriver instances used elsewhere in
:mod:`mayutils` for browser automation tasks such as headless rendering,
authenticated screen captures, and scripted navigation. Keep the heavy
``selenium`` dependency behind the optional-extras guard so the core package
remains importable without it. Expose small factory functions that apply
sensible defaults while still allowing callers to override the underlying
``Service`` and ``Options`` configuration at call sites.

See Also
--------
selenium.webdriver : Top-level Selenium WebDriver package providing the
    browser automation interfaces consumed here.
playwright.sync_api : Alternative synchronous browser automation library
    that can replace Selenium when broader cross-browser support is needed.
chromedriver_autoinstaller : Helper package that auto-downloads the
    matching ``chromedriver`` binary when building Chromium-backed drivers.
get_safari_driver : Sibling factory in this module that constructs a Safari
    WebDriver session using the system ``safaridriver`` binary.

Examples
--------
>>> from mayutils.environment.webdrivers import get_safari_driver
>>> driver = get_safari_driver()  # doctest: +SKIP
>>> driver.get("https://example.com")  # doctest: +SKIP
>>> driver.title  # doctest: +SKIP
'Example Domain'
>>> driver.quit()  # doctest: +SKIP
"""

from collections.abc import Mapping
from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from selenium.webdriver.safari.options import Options as SafariOptions
    from selenium.webdriver.safari.service import Service as SafariService
    from selenium.webdriver.safari.webdriver import WebDriver
    from selenium.webdriver.safari.webdriver import WebDriver as SafariWebDriver


def get_safari_driver(
    *,
    service_kwargs: Mapping[str, Any] | None = None,
    options_kwargs: Mapping[str, Any] | None = None,
) -> WebDriver:
    """
    Construct a Safari WebDriver backed by the built-in ``safaridriver`` binary.

    Instantiate a fresh :class:`SafariService` and :class:`SafariOptions`,
    forwarding any user-supplied keyword arguments so callers can tweak
    executable paths, logging destinations, port selection, and browser-level
    flags without having to import the Selenium classes themselves. Open a
    brand-new WebDriver session on every invocation so state does not leak
    across calls; the caller owns the lifecycle and must invoke ``driver.quit``
    when finished to release the underlying ``safaridriver`` process and any
    automation window it opened. Safari does not expose a true headless mode,
    so expect a visible browser window unless the caller is running on a
    virtualised display. User-agent spoofing must be applied at the page level
    (for example, via ``driver.execute_script``) because Safari rejects most
    ``Options``-level user-agent overrides. Default timeouts fall back to
    Selenium's implicit waits; configure ``driver.set_page_load_timeout`` or
    ``WebDriverWait`` explicitly after construction when deterministic wait
    semantics are required.

    Parameters
    ----------
    service_kwargs
        Keyword arguments forwarded verbatim to :class:`SafariService`. Use
        this to override the ``safaridriver`` executable path, the service
        port, or the logging destination. ``None`` applies Selenium's
        built-in defaults, which resolve ``safaridriver`` on ``PATH`` and
        let the service pick a free ephemeral port.
    options_kwargs
        Keyword arguments forwarded verbatim to :class:`SafariOptions`. Use
        this to toggle capabilities such as ``use_technology_preview`` or to
        apply arbitrary Safari-specific flags. ``None`` applies Selenium's
        built-in defaults, which enable the stable Safari channel without
        any extra capabilities set.

    Returns
    -------
        A live Safari WebDriver session ready to issue browser-automation
        commands such as navigation, element queries, JavaScript execution,
        and viewport screenshots. The session is active until
        ``driver.quit`` is called by the caller.

    See Also
    --------
    selenium.webdriver.safari.webdriver.WebDriver : The concrete WebDriver
        class constructed and returned by this factory.
    selenium.webdriver.safari.options.Options : Options container whose
        keyword arguments flow through ``options_kwargs``.
    selenium.webdriver.safari.service.Service : Service container whose
        keyword arguments flow through ``service_kwargs``.
    playwright.sync_api.sync_playwright : Playwright's synchronous entry
        point, used when Safari's automation surface is insufficient.
    chromedriver_autoinstaller.install : Equivalent convenience helper for
        Chromium-based WebDriver sessions on non-macOS platforms.

    Notes
    -----
    macOS ships ``safaridriver`` with Safari, so no separate driver download
    is required. Remote Automation must be enabled once per machine via
    Safari > Develop > Allow Remote Automation before the factory can
    successfully launch a session.

    Examples
    --------
    Launch a default Safari session, navigate, and quit:

    >>> from mayutils.environment.webdrivers import get_safari_driver
    >>> driver = get_safari_driver()  # doctest: +SKIP
    >>> driver.set_page_load_timeout(30)  # doctest: +SKIP
    >>> driver.get("https://example.com")  # doctest: +SKIP
    >>> driver.save_screenshot("/tmp/example.png")  # doctest: +SKIP
    >>> driver.quit()  # doctest: +SKIP

    Launch Safari Technology Preview instead:

    >>> driver = get_safari_driver(  # doctest: +SKIP
    ...     options_kwargs={"use_technology_preview": True},
    ... )  # doctest: +SKIP
    >>> driver.quit()  # doctest: +SKIP
    """
    return SafariWebDriver(
        service=SafariService(**(service_kwargs or {})),
        options=SafariOptions(**(options_kwargs or {})),
    )
