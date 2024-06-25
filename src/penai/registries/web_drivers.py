from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from enum import Enum

from selenium.webdriver.remote.webdriver import WebDriver

from penai.utils.io import temp_file_for_content
from penai.utils.web_drivers import create_chrome_web_driver


class RegisteredWebDriver(Enum):
    CHROME = "chrome"

    @contextmanager
    def create_web_driver(self) -> Generator[WebDriver, None, None]:
        match self:
            case RegisteredWebDriver.CHROME:
                with create_chrome_web_driver() as web_driver:
                    yield web_driver
            case _:
                raise ValueError(f"Unsupported driver {self}")


@contextmanager
def get_web_driver(
    web_driver: WebDriver | RegisteredWebDriver,
) -> Generator[WebDriver, None, None]:
    """Simplifies using a WebDriver instance or a RegisteredWebDriver in the same context.

    The context manager is a nullcontext if the web_driver is already a WebDriver instance.
    Typical usage is `with get_web_driver(web_driver) as driver:`.
    """
    ctxt = (
        web_driver.create_web_driver()
        if isinstance(
            web_driver,
            RegisteredWebDriver,
        )
        else nullcontext(web_driver)
    )
    with ctxt as driver:
        yield driver


@contextmanager
def get_web_driver_for_html(
    web_driver: WebDriver | RegisteredWebDriver,
    html_string: str,
) -> Generator[WebDriver, None, None]:
    """Context manager that opens a web driver with a HTML string as content."""
    with get_web_driver(web_driver) as driver, temp_file_for_content(
        html_string,
        extension=".html",
    ) as path:
        driver.get(path.absolute().as_uri())
        yield driver
