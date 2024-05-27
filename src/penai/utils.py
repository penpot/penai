import json
from pathlib import Path

from lxml import etree

from penai.svg import SVG
from penai.types import PathLike


def read_json(path: PathLike) -> dict:
    """Read a JSON file from the given path."""
    return json.loads(Path(path).read_text())


def strip_penpot_from_tree(node: etree.Element) -> None:
    """Strip all Penpot-specific nodes from a given SVG DOM.

    Useful for debugging, reverse engineering or testing purposes.
    """
    children = list(node)

    for child in children:
        if child.prefix and child.prefix == "penpot":
            node.remove(child)
        else:
            strip_penpot_from_tree(child)


def strip_penpot_from_svg(svg: SVG) -> None:
    """Strip all Penpot-specific nodes from a given SVG object.

    Useful for debugging, reverse engineering or testing purposes.
    """
    strip_penpot_from_tree(svg.dom.getroot())
