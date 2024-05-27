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
        namespace_map: dict | None = None,
        svg_attribs: dict[str, str] | None = None,
    ) -> Self:
        namespace_map = namespace_map or {}

        namespace_map = {None: "http://www.w3.org/2000/svg", **namespace_map}

        # As recommended in https://lxml.de/tutorial.html, create a deep copy of the element.
        element = deepcopy(element)

        localname = etree.QName(element).localname

        if localname != "svg":
            root = etree.Element("svg", nsmap=namespace_map)
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
