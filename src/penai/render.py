import abc
import io
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ParamSpec, Self, TypedDict, TypeVar, Unpack, cast

import resvg_py
from PIL import Image
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver

from penai.svg import SVG, BoundingBox
from penai.types import PathLike
from penai.utils.io import temp_file_for_content
from penai.utils.svg import image_from_bytes
from penai.utils.web_drivers import create_chrome_web_driver_cm


@dataclass
class RenderArtifacts:
    bounding_boxes: dict[str, BoundingBox] | None = None


@dataclass
class RenderResult:
    def __init__(self, image: Image.Image, **artifacts: dict[str, Any]):
        self.image = image
        self.artifacts = RenderArtifacts(**artifacts)

    image: Image.Image
    artifacts: RenderArtifacts


class BaseSVGRenderer(abc.ABC):
    """Base class for SVG renderers.

    We distinguish between the representation of SVGs given by their content and as a file,
    since SVG engines could inherently work with either representation.
    """

    SUPPORTS_ALPHA: bool
    SUPPORTS_BOUNDING_BOX_INFERENCE: bool

    @abc.abstractmethod
    def render_svg_string(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        pass

    @abc.abstractmethod
    def render_svg(
        self,
        svg: SVG,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        pass

    @abc.abstractmethod
    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        pass

    # meant to be overridden if necessary
    def teardown(self) -> None:  # noqa: B027
        pass


Param = ParamSpec("Param")
RetType = TypeVar("RetType")


class WebDriverSVGRendererParams(TypedDict, total=False):
    wait_time: float | None


class WebDriverSVGRenderer(BaseSVGRenderer):
    SUPPORTS_ALPHA = False
    SUPPORTS_BOUNDING_BOX_INFERENCE = True

    def __init__(
        self,
        webdriver: WebDriver,
        wait_time: float | None = None,
        infer_bounding_boxes: bool = False,
    ):
        self.web_driver = webdriver
        self.wait_time = wait_time
        self.infer_bounding_boxes = infer_bounding_boxes

    @classmethod
    @contextmanager
    def create_chrome_renderer(
        cls,
        **kwargs: Unpack[WebDriverSVGRendererParams],
    ) -> Iterator[Self]:
        """Instantiate an SVG renderer using a headless Chrome instance."""
        with create_chrome_web_driver_cm() as driver:
            yield cls(driver, **kwargs)

    def _get(self, url: str) -> None:
        # It's not totally clear when an explicit wait time is needed.
        # For the Chrome web driver, get() seems to be blocking until the page is loaded
        # but this might be different for other web drivers or if external resources are loaded
        # in an asynchronous fashion.
        if self.wait_time:
            time.sleep(self.wait_time)

        self.web_driver.get(url)

    def _dim_to_css(self, dim: int | float | None) -> str:
        # Note that contrary to common believe, a "px" does not necessarily correspond to a physical pixel
        # but is defined to correspond to 1/96th of an inch. However, under normal circumstances, this will
        # correspond to a physical pixel in typical desktop environments.
        if isinstance(dim, float):
            return f"{dim * 100:.2f}%"
        elif isinstance(dim, int):
            return f"{dim}px"
        elif dim is None:
            return "auto"
        else:
            raise ValueError(f"Invalid dimension: {dim}")

    def _infer_bounding_boxes(self) -> dict[str, BoundingBox]:
        bboxes_result = self.web_driver.execute_script(
            """
            return Object.fromEntries(
                Array.from(
                    document.querySelectorAll('[id]')).map(el => [
                        el.id, el.getBoundingClientRect()
                    ]
                )
            );
        """,
        )

        return {
            element_id: BoundingBox.from_dom_rect(bbox)
            for element_id, bbox in bboxes_result.items()
        }

    def _render_svg(
        self,
        svg_path: str,
        width: int | None,
        height: int | None,
    ) -> RenderResult:
        self._get(svg_path)

        # At this point, the SVG will have been rendered and have the dimensions as specified by
        # the width and height attributes of the <svg>-element or corresponding to the default
        # size of the browser window if width and height are set to "100%" or not specified.
        # Since the size of the browser window might be too small not, we have to determine the necessary
        # size and set it accordingly.

        # If `width` or/and `height` are provided, we first set the element dimensions to the provided values
        # and then resize the window to the actual size of the SVG element.
        # Otherwise we will try to infer a default size from the SVG's view box.
        # if width or height:
        style = f"width: {self._dim_to_css(width)}; height: {self._dim_to_css(height)};"
        self.web_driver.execute_script(
            f"document.querySelector('svg').setAttribute('style', '{style}');",
        )

        bbox = BoundingBox.from_dom_rect(
            self.web_driver.execute_script(
                "return document.querySelector('svg').getBoundingClientRect();",
            ),
        )

        # Set the window size to the size of the SVG element, assuming that it is placed at the origin.
        # We add a small buffer to the window size to account for margins, scrollbars, etc.
        self.web_driver.set_window_size(bbox.width + 32, bbox.height + 128)

        svg_el = self.web_driver.find_element(By.CSS_SELECTOR, "svg")

        artifacts = {}

        if self.infer_bounding_boxes:
            artifacts["bounding_boxes"] = self._infer_bounding_boxes()

        buffer = io.BytesIO(self.web_driver.get_screenshot_as_png())
        buffer.seek(0)

        image = Image.open(buffer).convert("RGB")
        image = image.crop(
            (
                svg_el.location["x"],
                svg_el.location["y"],
                svg_el.size["width"],
                svg_el.size["height"],
            )
        )

        return RenderResult(image=image, **artifacts)

    def render_svg_string(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        """Render the content of an SVG file to an image.

        :param svg_string: The content of the SVG file to render.
        :param width: The width of the rendered image. Currently not supported.
        :param height: The height of the rendered image. Currently not supported.
        """
        with temp_file_for_content(svg_string, extension=".svg") as path:
            return self._render_svg(
                path.absolute().as_uri(),
                width=width,
                height=height,
            )

    def render_svg(
        self,
        svg: SVG,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        return self.render_svg_string(svg.to_string(), width=width, height=height)

    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        """Render an SVG file to an image.

        :param svg_path: Path to the SVG file to render.
        :param width: The width of the rendered image. Currently not supported.
        :param height: The height of the rendered image. Currently not supported.
        """
        return self._render_svg(
            Path(svg_path).absolute().as_uri(),
            width=width,
            height=height,
        )


class ResvgRenderer(BaseSVGRenderer):
    SUPPORTS_ALPHA = True
    SUPPORTS_BOUNDING_BOX_INFERENCE = False

    def __init__(self, inline_linked_images: bool = True, dpi: int | None = None):
        self.inline_linked_images = inline_linked_images
        self.dpi = dpi

    def render_svg_string(
        self,
        svg_string: str,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        svg = SVG.from_string(svg_string)

        if self.inline_linked_images:
            svg.inline_images()

        if width or height:
            svg.set_dimensions(width=width, height=height)

        svg_string = svg.to_string()

        # resvg_py.svg_to_bytes seem to be have a wrong type hint as itr
        # returns a list of ints while it's annotated to return list[bytes]
        result = cast(
            list[int],
            resvg_py.svg_to_bytes(
                svg_string=svg_string,
                width=width,
                height=height,
                dpi=self.dpi,
            ),
        )

        return RenderResult(image=image_from_bytes(bytes(result)))

    def render_svg_file(
        self,
        svg_path: PathLike,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        svg_string = Path(svg_path).read_text()
        return self.render_svg_string(svg_string, width=width, height=height)

    def render_svg(
        self,
        svg: SVG,
        width: int | None = None,
        height: int | None = None,
    ) -> RenderResult:
        return self.render_svg_string(svg.to_string(), width=width, height=height)
