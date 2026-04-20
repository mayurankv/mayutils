"""Selenium WebDriver factory helpers.

This module centralises construction of Selenium WebDriver instances used
elsewhere in :mod:`mayutils` for browser automation tasks such as headless
rendering, authenticated screen captures, and scripted navigation. It keeps
the heavy ``selenium`` dependency behind the optional-extras guard so the
core package remains importable without it, and exposes small factory
functions that apply sensible defaults while still allowing the caller to
override the underlying ``Service`` and ``Options`` configuration.
"""

from typing import Any

from mayutils.core.extras import may_require_extras

with may_require_extras():
    from selenium.webdriver.safari.options import Options as SafariOptions
    from selenium.webdriver.safari.service import Service as SafariService
    from selenium.webdriver.safari.webdriver import WebDriver
    from selenium.webdriver.safari.webdriver import WebDriver as SafariWebDriver


def get_safari_driver(
    *,
    service_kwargs: dict[str, Any] | None = None,
    options_kwargs: dict[str, Any] | None = None,
) -> WebDriver:
    """Construct a Safari WebDriver backed by macOS's built-in ``safaridriver``.

    The factory instantiates a fresh :class:`SafariService` and
    :class:`SafariOptions`, forwarding any user-supplied keyword arguments
    so callers can tweak executable paths, logging, port selection, or
    browser-level flags without having to import the Selenium classes
    themselves. A new WebDriver session is opened on every call; the
    caller is responsible for quitting it when finished.

    Parameters
    ----------
    service_kwargs : Mapping[str, Any] or None, optional
        Keyword arguments forwarded to :class:`SafariService`. Use this to
        override the ``safaridriver`` executable path, the service port,
        or logging destinations. ``None`` applies Selenium's defaults.
    options_kwargs : Mapping[str, Any] or None, optional
        Keyword arguments forwarded to :class:`SafariOptions`. Use this to
        set capabilities such as ``use_technology_preview`` or arbitrary
        Safari-specific flags. ``None`` applies Selenium's defaults.

    Returns
    -------
    WebDriver
        A live Safari WebDriver session ready to issue browser-automation
        commands (navigation, element queries, screenshots, etc.).

    Raises
    ------
    selenium.common.exceptions.WebDriverException
        If ``safaridriver`` cannot be launched — typically because Remote
        Automation has not been enabled under Safari's Develop menu, or
        the service is unable to bind to the requested port.

    Notes
    -----
    macOS ships ``safaridriver`` with Safari, so no separate driver
    download is required. Remote Automation must be enabled once per
    machine via Safari > Develop > Allow Remote Automation.
    """
    return SafariWebDriver(
        service=SafariService(**(service_kwargs or {})),
        options=SafariOptions(**(options_kwargs or {})),
    )
