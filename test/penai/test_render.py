import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

from penai.render import BaseSVGRenderer, ChromeSVGRenderer, ResvgRenderer


def _test_svg_renderer(
    renderer: BaseSVGRenderer,
    example_svg_path: Path,
    example_png: Path,
) -> None:
    ref_png = Image.open(example_png)
    cmp_png = renderer.render_svg_file(example_svg_path)

    assert ref_png.size == cmp_png.size

    if not renderer.SUPPORTS_ALPHA:
        ref_png = ref_png.convert("RGB")

    ref_data = np.array(ref_png) / 255.0
    cmp_data = np.array(cmp_png) / 255.0

    if ((ref_data - cmp_data) ** 2).mean() > 5e-3:
        with tempfile.TemporaryDirectory(delete=False) as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            ref_path = tmp_dir_path / "ref.png"
            cmp_path = tmp_dir_path / "cmp.png"

            ref_png.save(ref_path)
            cmp_png.save(cmp_path)

            raise AssertionError(
                f"Images do not match. Saved to  and {cmp_path} respectively for visual inspection.",
            )


class TestChromeSVGRenderer:
    def test_chrome_svg_renderer(
        self,
        example_svg_path: Path,
        example_png: Path,
    ) -> None:
        renderer = ChromeSVGRenderer()

        _test_svg_renderer(renderer, example_svg_path, example_png)

        renderer.teardown()

    def test_chrome_svg_renderer_context_manager(
        self,
        example_svg_path: Path,
        example_png: Path,
    ) -> None:
        with ChromeSVGRenderer.create_renderer() as renderer:
            _test_svg_renderer(renderer, example_svg_path, example_png)


class TestResvgRenderer:
    def test_resvg_renderer(
        self,
        example_svg_path: Path,
        example_png: Path,
    ) -> None:
        renderer = ResvgRenderer()

        _test_svg_renderer(renderer, example_svg_path, example_png)
