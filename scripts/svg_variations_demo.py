from sensai.util import logging

from penai.registries.projects import SavedPenpotProject
from penai.variations.svg_variations import SVGVariationsGenerator

if __name__ == "__main__":
    logging.configure(level=logging.INFO)

    page_svg = SavedPenpotProject.INTERACTIVE_MUSIC_APP.load_page_svg_with_viewboxes(
        "Interactive music app"
    )
    shape = page_svg.get_shape_by_name("ic_equalizer_48px-1")

    var_gen = SVGVariationsGenerator(shape=shape, semantics="equalizer")
    variations = var_gen.create_variations()
    variations_revised = var_gen.revise_variations(variations)
