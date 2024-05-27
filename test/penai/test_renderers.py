from pathlib import Path
import numpy as np
from penai.render import BaseSVGRenderer, ChromeSVGRenderer
from PIL import Image


def _test_chrome_svg_renderer(
    renderer: BaseSVGRenderer, example_svg_path: Path, example_png: Path
) -> None:
    ref_png = Image.open(example_png)
    cmp_png = renderer.render(example_svg_path)

    ref_png.save("ref.png")
    cmp_png.save("cmp.png")

    assert ref_png.size == cmp_png.size

    ref_png = ref_png.convert("RGB")

    ref_data = np.array(ref_png) / 255.0
    cmp_data = np.array(cmp_png) / 255.0

    # We compare a properly _exported_ SVG against a screenshot
    # The two versions are therefore not expected to match pixel-perfectly
    assert ((ref_data - cmp_data) ** 2).mean() < 1e-3


def test_chrome_svg_renderer(example_svg_path: Path, example_png: Path) -> None:
    renderer = ChromeSVGRenderer()

    _test_chrome_svg_renderer(renderer, example_svg_path, example_png)

    renderer.teardown()


def test_chrome_svg_renderer_context_manager(example_svg_path: Path, example_png: Path) -> None:
    with ChromeSVGRenderer.create_renderer() as renderer:
        _test_chrome_svg_renderer(renderer, example_svg_path, example_png)
