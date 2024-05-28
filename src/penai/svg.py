from copy import deepcopy
from functools import cached_property
from typing import Any, Self

from lxml import etree

from penai import utils
from penai.types import PathLike


class BetterElement(etree.ElementBase):
    @cached_property
    def query_compatible_nsmap(self):
        nsmap = dict(self.nsmap)
        nsmap[""] = nsmap.pop(None)
        return nsmap

    def find(self, path, namespaces=None) -> Any:
        return super().find(path, namespaces=namespaces or self.query_compatible_nsmap)

    def findall(self, path, namespaces=None) -> Any:
        return super().findall(path, namespaces=namespaces or self.query_compatible_nsmap)

    def xpath(self, path, namespaces=None, **kwargs) -> Any:
        return super().xpath(path, namespaces=namespaces or self.query_compatible_nsmap, **kwargs)

    @cached_property
    def localname(self):
        return etree.QName(self).localname


class SVG:
    """A simple wrapper around the lxml.etree.ElementTree class for now.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree):
        self.dom = dom

    @classmethod
    def from_root_element(
        cls,
        element: BetterElement,
        namespace_map: dict | None = None,
        svg_attribs: dict[str, str] | None = None,
    ) -> Self:
        if not isinstance(element, BetterElement):
            raise TypeError(f"Expected an BetterElement, got {type(element)}")

        namespace_map = namespace_map or dict(element.nsmap)
        namespace_map = {None: "http://www.w3.org/2000/svg", **namespace_map}

        # As recommended in https://lxml.de/tutorial.html, create a deep copy of the element.
        element = deepcopy(element)

        if element.localname != "svg":
            root = BetterElement("svg", nsmap=namespace_map)
            root.append(element)
        else:
            root = element

        if svg_attribs:
            root.attrib.update(svg_attribs)

        return cls(etree.ElementTree(root))

    @staticmethod
    def get_parser():
        parser_lookup = etree.ElementDefaultClassLookup(element=BetterElement)
        parser = etree.XMLParser()
        parser.set_element_class_lookup(parser_lookup)
        return parser

    @classmethod
    def from_file(cls, path: PathLike) -> Self:
        parser = cls.get_parser()
        return cls(etree.parse(path, parser))

    @classmethod
    def from_string(cls, string: str) -> Self:
        parser = cls.get_parser()
        return cls(etree.ElementTree(etree.fromstring(string, parser)))

    def inline_images(self, elem: etree.ElementBase | None = None):
        # TODO: We currently don't make use of any concurrent fetching or caching
        # which could drastically speed up image inlining.
        if elem is None:
            elem = self.dom.getroot()

        if not elem.prefix and elem.localname == 'image':
            attribs = elem.attrib

            # According to https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/xlink:href
            # xlink:href is deprecated, so we will inly check the `href` attribute here.
            # Penpot also doesn't seem to make use of xlinks.
            # uri = attribs.get(f'{{{nsmap["xlink"]}}}href')

            uri = attribs.get('href')

            if uri and utils.validate_uri(uri):
                data_uri = utils.url_to_data_uri(uri)

                if attribs.get('href'):
                    del attribs['href']

                attribs['href'] = data_uri

        for child in elem:
            self.inline_images(child)

    def to_file(self, path: PathLike) -> None:
        self.dom.write(path, pretty_print=True)

    def to_string(self, pretty: bool = True) -> str:
        return etree.tostring(self.dom, pretty_print=pretty).decode()
