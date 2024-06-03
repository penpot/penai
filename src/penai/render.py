import abc
import io
import time
from collections.abc import Callable, Generator
from contextlib import contextmanager
from functools import wraps
from pathlib import Path
from typing import ParamSpec, Self, TypedDict, TypeVar, Unpack, cast

import resvg_py
from PIL import Image
from selenium.webdriver.remote.webdriver import WebDriver

from penai.svg import SVG, BoundingBox
from penai.types import PathLike
from penai.utils.svg import image_from_bytes, temp_file_for_content
from penai.utils.web_drivers import create_chrome_web_driver


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

    # meant to be overridden if necessary
    def teardown(self) -> None:  # noqa: B027
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


class WebDriverSVGRendererParams(TypedDict, total=False):
    wait_time: float | None


class WebDriverSVGRenderer(BaseSVGRenderer):
    SUPPORTS_ALPHA = False

    def __init__(self, webdriver: WebDriver, wait_time: float | None = None):
        self.web_driver = webdriver
        self.wait_time = wait_time

    @classmethod
    @contextmanager
    def create_chrome_renderer(
        cls,
        **kwargs: Unpack[WebDriverSVGRendererParams],
    ) -> Generator[Self, None, None]:
        """Instantiate an SVG renderer using a headless Chrome instance."""
        with create_chrome_web_driver() as driver:
            yield cls(driver, **kwargs)

    def _open_svg(self, svg_path: str) -> None:
        self.web_driver.get(svg_path)

        # TODO: Wait until content is displayed instead of a fixed time
        # See for instance https://www.selenium.dev/documentation/webdriver/waits/

        if self.wait_time:
            time.sleep(self.wait_time)

        # Determine the size of the SVG element and set the window size accordingly
        bbox = BoundingBox.from_dom_rect(
            self.web_driver.execute_script(
                "return document.querySelector('svg').getBoundingClientRect();",
            ),
        )

        assert (
            bbox.x >= 0 and bbox.y >= 0
        ), f"Bounding box origin should be non-negative, got ({bbox.x}, {bbox.y})"

        self.web_driver.set_window_size(bbox.x + bbox.width, bbox.y + bbox.height)

        if self.wait_time:
            time.sleep(self.wait_time)

        self.web_driver.get(svg_path)

    def _render_svg(self, svg_path: str) -> Image.Image:
        self._open_svg(svg_path)

        buffer = io.BytesIO(self.web_driver.get_screenshot_as_png())
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

        :param svg_string: The content of the SVG file to render.
        :param width: The width of the rendered image. Currently not supported.
        :param height: The height of the rendered image. Currently not supported.
        """
        # The svg element needs to be wrapped in a <body> element.
        # Otherwise the SVG element bounding box will take on the size of the whole screen,
        # but only within the web driver and not a *normal* Chrome instance for some yet unknown reason.
        # And yes, the <HTML> tag can be omitted.
        # See https://html.spec.whatwg.org/multipage/syntax.html#syntax-tag-omission
        content = '<body style="margin: 0;">' + svg_string + "</body>"

        with temp_file_for_content(content, extension=".html") as path:
            return self._render_svg(path.absolute().as_uri())

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
        return self.render_svg(Path(svg_path).read_text())


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
        return image_from_bytes(
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
