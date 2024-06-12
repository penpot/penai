from sensai.util import logging

from penai.models import PenpotMinimalShapeXML
from penai.registries.projects import SavedPenpotProject

if __name__ == '__main__':
    logging.configure()
    page_svg = SavedPenpotProject.INTERACTIVE_MUSIC_APP.load_page_svg_with_viewboxes("Interactive music app")
    shape = page_svg.get_shape_by_name("ic_equalizer_48px-1")

    pxml = PenpotMinimalShapeXML.from_shape(shape)
    print(pxml.to_string())
