from sensai.util import logging

from penai.models import PenpotMinimalShapeXML
from penai.registries.projects import SavedPenpotProject
from zmq import log

if __name__ == "__main__":
    logging.configure(level=logging.DEBUG)
    page_svg = SavedPenpotProject.INTERACTIVE_MUSIC_APP.load_page_svg_with_viewboxes(
        "Interactive music app"
    )
    shape_name = "ic_equalizer_48px-1"
    shape = page_svg.get_shape_by_name(shape_name)

    pxml = PenpotMinimalShapeXML.from_shape(shape)
    print(
        f"Below is the minimal penpot-importable XML representation of the shape {shape_name}:",
        "\n------------------\n",
    )
    print(pxml.to_string())
