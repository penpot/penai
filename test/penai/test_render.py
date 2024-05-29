from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from penai.render import BaseSVGRenderer, ChromeSVGRenderer, ResvgRenderer


def _test_svg_renderer(
    renderer: BaseSVGRenderer,
    example_svg_path: Path,
    example_png: Path,
    log_dir: Path,
) -> None:
    ref_png = Image.open(example_png)
    cmp_png = renderer.render_svg_file(example_svg_path)

    assert ref_png.size == cmp_png.size

    if not renderer.SUPPORTS_ALPHA:
        ref_png = ref_png.convert("RGB")

    ref_data = np.array(ref_png) / 255.0
    cmp_data = np.array(cmp_png) / 255.0

    diff = ((ref_data - cmp_data) ** 2).mean()

    if diff > 5e-3:
        ref_path = log_dir / "ref.png"
        cmp_path = log_dir / "cmp.png"

        ref_png.save(ref_path)
        cmp_png.save(cmp_path)

        raise AssertionError(
            f"Images do not match. Saved to reference and generated image to {ref_path} and {cmp_path} for visual inspection.",
        )


class TestRenderers:
    @pytest.mark.parametrize("renderer", [ChromeSVGRenderer(), ResvgRenderer()])
    def test_rendering_works(
        self,
        renderer: BaseSVGRenderer,
        example_svg_path: Path,
        example_png: Path,
        log_dir: Path,
    ) -> None:

        _test_svg_renderer(renderer, example_svg_path, example_png, log_dir)

        renderer.teardown()

    def test_chrome_svg_renderer_context_manager(
        self,
        example_svg_path: Path,
        example_png: Path,
        log_dir: Path,
    ) -> None:
        with ChromeSVGRenderer.create_renderer() as renderer:
            _test_svg_renderer(renderer, example_svg_path, example_png, log_dir)

