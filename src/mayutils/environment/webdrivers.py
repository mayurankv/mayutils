"""Selenium WebDriver factories."""

from typing import Any

from mayutils.core.extras import requires_extras

with requires_extras("web"):
    from selenium.webdriver.safari.options import Options as SafariOptions
    from selenium.webdriver.safari.service import Service as SafariService
    from selenium.webdriver.safari.webdriver import WebDriver
    from selenium.webdriver.safari.webdriver import WebDriver as SafariWebDriver


def get_safari_driver(
    service_kwargs: dict[str, Any] | None = None,
    options_kwargs: dict[str, Any] | None = None,
) -> WebDriver:
    """Return a freshly-created Safari WebDriver instance with default options.

    Uses macOS's built-in ``safaridriver`` — no additional installation
    needed. Remote Automation must be enabled in Safari ▸ Develop.

    Returns
    -------
    WebDriver
        A Safari WebDriver ready to issue browser-automation commands.
    """
    return SafariWebDriver(
        service=SafariService(**(service_kwargs or {})),
        options=SafariOptions(**(options_kwargs or {})),
    )
