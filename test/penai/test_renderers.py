from collections.abc import Iterable
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pytest import FixtureRequest

from penai.render import BaseSVGRenderer, ResvgRenderer, WebDriverSVGRenderer
from penai.svg import SVG


@pytest.fixture()
def chrome_web_driver() -> Iterable[BaseSVGRenderer]:
    with WebDriverSVGRenderer.create_chrome_renderer() as renderer:
        yield renderer


@pytest.fixture()
def resvg_renderer() -> Iterable[BaseSVGRenderer]:
    renderer = ResvgRenderer()
    yield renderer
    renderer.teardown()


@pytest.fixture(params=["chrome_web_driver", "resvg_renderer"])
def renderer(request: FixtureRequest) -> BaseSVGRenderer:
    return request.getfixturevalue(request.param)


class TestSVGRenderers:
    def test_rendering(
        self,
        renderer: BaseSVGRenderer,
        example_svg_path: Path,
        example_png_path: Path,
        log_dir: Path,
    ) -> None:
        ref_png = Image.open(example_png_path)

        cmp_png = renderer.render_svg_file(example_svg_path).image

        assert ref_png.size == cmp_png.size

        if not renderer.SUPPORTS_ALPHA:
            ref_png = ref_png.convert("RGB")

        ref_data = np.array(ref_png) / 255.0
        cmp_data = np.array(cmp_png) / 255.0

        diff = ((ref_data - cmp_data) ** 2).mean()

        # resvg uses a different fallback font so we need to have the tolerance
        # slightly higher than for the Chrome renderer.
        # For some cases, presumbly ones with lots of text, this might break entirely.
        # In the long-term, however, the font issue will be fixed and the tolerance might
        # be lowered again.
        if diff > 5e-3:
            ref_path = log_dir / "ref.png"
            cmp_path = log_dir / "cmp.png"

            ref_png.save(ref_path)
            cmp_png.save(cmp_path)

            raise AssertionError(
                f"Images do not match. Saved to reference and generated image to {ref_path} and {cmp_path} for visual inspection.",
            )

    def test_size_inference(
        self,
        renderer: BaseSVGRenderer,
        example_svg_path: Path,
    ) -> None:
        img = renderer.render_svg_file(example_svg_path).image

        view_box = SVG.from_file(example_svg_path).get_view_box()

        assert img.size == (view_box.width, view_box.height)

    def test_explicit_size_specification(
        self,
        renderer: BaseSVGRenderer,
        example_svg_path: Path,
    ) -> None:
        orig_aspect_ratio = SVG.from_file(example_svg_path).get_view_box().aspect_ratio

        img = renderer.render_svg_file(example_svg_path, width=100, height=100).image
        assert img.size == (100, 100)

        img = renderer.render_svg_file(example_svg_path, width=100).image
        assert img.size[0] == 100
        assert (
            img.size[0] >= img.size[1] if orig_aspect_ratio > 1 else img.size[0] <= img.size[1]
        ), f"Original aspect ratio: {orig_aspect_ratio}, new size: {img.size}"

        img = renderer.render_svg_file(example_svg_path, height=100).image
        assert img.size[1] == 100
        assert (
            img.size[0] >= img.size[1] if orig_aspect_ratio > 1 else img.size[0] <= img.size[1]
        ), f"Original aspect ratio: {orig_aspect_ratio}, new size: {img.size}"
