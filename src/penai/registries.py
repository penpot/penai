import logging
import os
from collections.abc import Generator
from contextlib import contextmanager, nullcontext
from enum import Enum

from selenium.webdriver.remote.webdriver import WebDriver

from penai.config import get_config, pull_from_remote
from penai.models import PenpotProject
from penai.utils.svg import temp_file_for_content
from penai.utils.web_drivers import create_chrome_web_driver

log = logging.getLogger(__name__)


class SavedPenpotProject(Enum):
    AVATAAARS = "Avataaars by Pablo Stanley"
    BLACK_AND_WHITE_MOBILE_TEMPLATES = "Black & White Mobile Templates"
    COMMUNITY_CARDS_GRID_THEME = "Community - Cards grid theme"
    INTERACTIVE_MUSIC_APP = "Interactive music app"
    MASTODON_SOCIAL_APP = "Mastodon Social App"
    MATERIAL_DESIGN_3 = "Material Design 3"
    NEXTCLOUD_DESIGN_SYSTEM = "Nextcloud design system"
    PLANTS_APP = "Plants app"
    UX_NOTES = "UX Notes"
    WIREFRAMING_KIT = "Wireframing kit"

    def get_project_name(self) -> str:
        return self.value

    def get_path(self, pull: bool = False) -> str:
        result = os.path.join(get_config().penpot_designs_basedir(), self.get_project_name())
        if pull:
            log.info(f"Pulling data for project {self.get_project_name()} to {result}")
            pull_from_remote(result)
        return result

    @classmethod
    def pull_all(cls) -> None:
        for design in cls:
            design.get_path(pull=True)

    def load(self, pull: bool = False) -> PenpotProject:
        project_path = self.get_path(pull=pull)
        return PenpotProject.from_directory(project_path)


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


# class RegisteredSVGRenderer(Enum):
#     CHROME_WEB_DRIVER = "chrome_web_driver"

#     @contextmanager
#     def create_renderer(self) -> Generator[BaseSVGRenderer, None, None]:
#         match self:
#             case self.CHROME_WEB_DRIVER:
#                 with WebDriverSVGRenderer.create_chrome_renderer() as renderer:
#                     yield renderer
#             case _:
#                 raise ValueError(f"Unsupported renderer {self}")
