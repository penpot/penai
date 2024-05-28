from copy import deepcopy
from typing import Self

from lxml import etree

from penai.types import PathLike


class SVG:
    """A simple wrapper around the lxml.etree.ElementTree class for now.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree):
        self.dom = dom

    @classmethod
    def from_root_element(
        cls,
        element: etree.Element,
        nsmap: dict | None = None,
        svg_attribs: dict[str, str] | None = None,
    ) -> Self:
        """Create an SVG object from a given root element.

        :param element: The root element of the SVG document.
        :param nsmap: A dictionary mapping namespace prefixes to URIs.
        :param svg_attribs: A dictionary of attributes to add to the `attrib` field.
        """
        nsmap = nsmap or {}

        # Add the default SVG namespace to the nsmap if it's not already there.
        nsmap = {None: "http://www.w3.org/2000/svg", **nsmap}

        # As recommended in https://lxml.de/tutorial.html, create a deep copy of the element.
        element = deepcopy(element)

        localname = etree.QName(element).localname

        if localname != "svg":
            root = etree.Element("svg", nsmap=nsmap)
            root.append(element)
        else:
            root = element

        if svg_attribs:
            root.attrib.update(svg_attribs)

        return cls(etree.ElementTree(root))

    @classmethod
    def from_file(cls, path: PathLike) -> Self:
        return cls(etree.parse(path))

    def to_file(self, path: PathLike) -> None:
        self.dom.write(path, pretty_print=True)

    def to_string(self, pretty: bool = True) -> str:
        return etree.tostring(self.dom, pretty_print=pretty).decode()
