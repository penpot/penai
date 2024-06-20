import logging
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.remote.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

log = logging.getLogger(__name__)


@contextmanager
def create_chrome_web_driver(headless: bool = True) -> Generator[WebDriver, Any, Any]:
    """Helper function to instantiate a Chrome WebDriver instance with all options we need."""
    driver = None
    log.info("Starting Chrome WebDriver")

    try:
        chrome_options = Options()

        if headless:
            chrome_options.add_argument("--headless")

        chrome_options.add_argument("--disable-gpu")

        # The screenshot size might deviate from the actual SVG size on high-dpi devices with a device scale factor != 1.0
        chrome_options.add_argument("--force-device-scale-factor=1.0")
        chrome_options.add_argument("--high-dpi-support=1.0")

        # Allow CORS for file://
        chrome_options.add_argument("--allow-file-access-from-files")

        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=chrome_options,
            )
        except Exception as e:
            raise Exception(
                "Failed to start Chrome. "
                "Make sure you have Chrome installed and the chromedriver executable in your PATH. "
                "On Ubuntu, you can install the required packages e.g., by following the instructions in "
                "https://skolo.online/documents/webscrapping/#pre-requisites. "
                "You can also directly download and install chrome and chromedriver from "
                "https://googlechromelabs.github.io/chrome-for-testing/#stable",
            ) from e

        yield driver
    finally:
        if driver is not None:
            log.info("Quitting Chrome WebDriver")
            driver.quit()
