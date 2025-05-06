from selenium import webdriver
from selenium.webdriver.safari.options import Options as SafariOptions
from selenium.webdriver.safari.service import Service as SafariService
from selenium.webdriver.safari.webdriver import WebDriver


def get_driver() -> WebDriver:
    options = SafariOptions()

    driver = webdriver.Safari(
        service=SafariService(),
        options=options,
    )

    return driver
