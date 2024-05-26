import numpy as np
from penpy.render import ChromeSVGRenderer
from PIL import Image


def test_chrome_svg_renderer(example_svg_path, example_png):
    ref_png = Image.open(example_png)
    cmp_png = ChromeSVGRenderer().render(example_svg_path)
    
    ref_png.save("ref.png")
    cmp_png.save("cmp.png")
    
    assert ref_png.size == cmp_png.size
    
    ref_png = ref_png.convert("RGB")

    ref_data = np.array(ref_png) / 255.0
    cmp_data = np.array(cmp_png) / 255.0
    
    # We compare a properly _exported_ SVG against a screenshot
    # The two versions are therefore not expected to match pixel-perfectly
    assert ((ref_data - cmp_data) ** 2).mean() < 1e-3
