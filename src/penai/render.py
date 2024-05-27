import abc
import atexit
import io
import time
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Self, TypedDict, Unpack

from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from penai.types import PathLike


class BaseSVGRenderer(abc.ABC):
    @abc.abstractmethod
    def render(
        self,
        svg: str | PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        pass


class ChromeSVGRendererParams(TypedDict, total=False):
    wait_time: float | None


class ChromeSVGRenderer(BaseSVGRenderer):
    def __init__(self, wait_time: float | None = None):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

        # The screenshot size might deviate from the actual SVG size on high-dpi devices with a device scale factor != 1.0
        chrome_options.add_argument("--force-device-scale-factor=1.0")
        chrome_options.add_argument("--high-dpi-support=1.0")

        try:
            self.driver = webdriver.Chrome(
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

        self.by = By

        self.wait_time = wait_time

        atexit.register(self.teardown)

    @classmethod
    @contextmanager
    def create_renderer(
        cls,
        **kwargs: Unpack[ChromeSVGRendererParams],
    ) -> Generator[Self, None, None]:
        """create_renderer() is the recommended way to instantiate a ChromeSVGRenderer in ensure proper teardown."""
        renderer = None
        try:
            renderer = cls(**kwargs)
            yield renderer
        finally:
            if renderer is not None:
                renderer.teardown()

    def teardown(self) -> None:
        self.driver.quit()

    def _render_svg(self, svg_path: str) -> Image.Image:
        self.driver.get(svg_path)

        # TODO: Wait until content is displayed instead of a fixed time
        # See for instance https://www.selenium.dev/documentation/webdriver/waits/

        if self.wait_time:
            time.sleep(self.wait_time)

        # Determine the size of the SVG element and set the window size accordingly
        svg_el = self.driver.find_element(self.by.TAG_NAME, "svg")
        size = svg_el.size

        self.driver.set_window_size(size["width"], size["height"])

        buffer = io.BytesIO(self.driver.get_screenshot_as_png())
        buffer.seek(0)

        return Image.open(buffer)

    def render(
        self,
        svg: str | PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        if width or height:
            raise NotImplementedError(
                "Specifying width or height is currently not supported by ChromeSVGRenderer",
            )

        if isinstance(svg, Path):
            path = Path(svg).absolute()

            if not path.exists():
                raise FileNotFoundError(f"{path} does not exist")

            return self._render_svg(path.as_uri())
        else:
            with NamedTemporaryFile(prefix="penpy_", suffix=".svg", mode="w") as file:
                file.write(svg)

                return self._render_svg(Path(file.name).as_uri())
