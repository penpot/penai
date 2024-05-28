import abc
import atexit
import io
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import ParamSpec, Self, TypedDict, TypeVar, Unpack, cast

import resvg_py
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

from penai import utils
from penai.svg import SVG
from penai.types import PathLike


class BaseSVGRenderer(abc.ABC):
    """Base class for SVG renderers.

    We distinguish between the representation of SVGs given by their content and as a file,
    since SVG engines could inherently work with either representation.
    """

    SUPPORTS_ALPHA: bool

    @abc.abstractmethod
    def render_svg(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        pass

    @abc.abstractmethod
    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        pass


Param = ParamSpec("Param")
RetType = TypeVar("RetType")


def _size_arguments_not_supported(
    fn: Callable[Param, RetType],
) -> Callable[Param, RetType]:
    @wraps(fn)
    def wrapper(*args: Param.args, **kwargs: Param.kwargs) -> RetType:
        if kwargs.get("width") or kwargs.get("height"):
            raise NotImplementedError(
                "Specifying width or height is currently not supported by this renderer",
            )

        return fn(*args, **kwargs)

    return wrapper


class ChromeSVGRendererParams(TypedDict, total=False):
    wait_time: float | None


class ChromeSVGRenderer(BaseSVGRenderer):
    SUPPORTS_ALPHA = False

    def __init__(self, wait_time: float | None = None):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")

        # The screenshot size might deviate from the actual SVG size on high-dpi devices with a device scale factor != 1.0
        chrome_options.add_argument("--force-device-scale-factor=1.0")
        chrome_options.add_argument("--high-dpi-support=1.0")

        # Allow CORS for file://
        chrome_options.add_argument("--allow-file-access-from-files")

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
        """`with create_renderer()` is the recommended way to instantiate this class to ensure proper teardown."""
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

        return Image.open(buffer).convert("RGB")

    @_size_arguments_not_supported
    def render_svg(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        """Render the content of an SVG file to an image.

        :param svg: The content of the SVG file to render.
        :param width: The width of the rendered image. Currently not supported.
        :param height: The height of the rendered image. Currently not supported.
        """
        with NamedTemporaryFile(prefix="penpy_", suffix=".svg", mode="w") as file:
            file.write(svg_string)
            return self._render_svg(Path(file.name).as_uri())

    @_size_arguments_not_supported
    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        """Render an SVG file to an image.

        :param svg_path: Path to the SVG file to render.
        :param width: The width of the rendered image. Currently not supported.
        :param height: The height of the rendered image. Currently not supported.
        """
        svg_path = Path(svg_path)
        path = svg_path.absolute()

        if not path.exists():
            raise FileNotFoundError(f"{path} does not exist")

        return self._render_svg(path.as_uri())


class ResvgRenderer(BaseSVGRenderer):
    SUPPORTS_ALPHA = True

    def __init__(self, inline_linked_images: bool = True):
        self.inline_linked_images = inline_linked_images

    @_size_arguments_not_supported
    def render_svg(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        if self.inline_linked_images:
            svg = SVG.from_string(svg_string)
            svg.inline_images()
            svg_string = svg.to_string()

        # resvg_py.svg_to_bytes seem to be have a wrong type hint as itr
        # returns a list of ints while it's annotated to return list[bytes]
        return utils.image_from_bytes(
            bytes(cast(list[int], resvg_py.svg_to_bytes(svg_string=svg_string))),
        )

    @_size_arguments_not_supported
    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> Image.Image:
        svg_string = Path(svg_path).read_text()
        return self.render_svg(svg_string)
