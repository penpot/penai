import abc
import atexit
import io
import time
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Generator, Self, TypedDict, Unpack

from penpy.types import PathLike
from PIL import Image


class BaseSVGRenderer(abc.ABC):
    @abc.abstractmethod
    def render(self, svg: str | PathLike, width: int | None = None, height: int | None = None) -> Image.Image:
        pass


class ChromeSVGRendererParams(TypedDict):
    wait_time: float | None


class ChromeSVGRenderer(BaseSVGRenderer):
    def __init__(self, wait_time: float | None = None):
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.common.by import By
            from webdriver_manager.chrome import ChromeDriverManager
        except ImportError as e:
            raise ImportError(
                "Please install selenium and webdriver_manager to use ChromeRasterizer",
            ) from e

        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

        # The screenshot size might deviate from the actual SVG size on high-dpi devices with a device scale factor != 1.0
        chrome_options.add_argument("--force-device-scale-factor=1.0")
        chrome_options.add_argument("--high-dpi-support=1.0")

        self.driver = webdriver.Chrome(
            service=ChromeService(ChromeDriverManager().install()),
            options=chrome_options,
        )

        self.by = By

        self.wait_time = wait_time

        atexit.register(self.teardown)

    @classmethod
    @contextmanager
    def create_renderer(cls, **kwargs: Unpack[ChromeSVGRendererParams]) -> Generator[Self, None, None]:
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

    def render(self, svg: str | PathLike, width: int | None = None, height: int | None = None) -> Image.Image:
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
