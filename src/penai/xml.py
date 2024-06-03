from functools import cached_property
from typing import TYPE_CHECKING, Any, Self, overload

from lxml import etree
from lxml.etree import ElementBase as Element
from lxml.etree import ElementTree
from overrides import override

from penai.types import PathLike

if TYPE_CHECKING:
    # Trick to get proper type hints and docstrings for lxlml etree stuff
    # It has the same api as etree, but the latter is in python and properly typed and documented,
    # whereas the former is a stub but much faster. So at type-checking time, we use the python version of etree.
    from xml import etree
    from xml.etree.ElementTree import Element, ElementTree


class CustomElement(Element):
    """Customizing the Element class to allow for custom element classes.

    The associated parser and parsing methods will produce trees with elements of this custom class.
    Therefore, for such trees all find methods will return (collections of) elements of this class.
    """

    nsmap: dict

    @classmethod
    def get_parser(cls) -> etree.XMLParser:
        parser_lookup = etree.ElementDefaultClassLookup(element=cls)
        parser = etree.XMLParser()
        parser.set_element_class_lookup(parser_lookup)
        return parser

    @classmethod
    def parse_file(cls, path: PathLike) -> ElementTree:
        """Parses an XML file into an ElementTree which contains elements of the custom element class."""
        parser = cls.get_parser()
        return etree.parse(path, parser)

    @classmethod
    def parse_string(cls, string: str) -> ElementTree:
        parser = cls.get_parser()
        return etree.ElementTree(etree.fromstring(string, parser))

    def find(self, path: str, namespaces: dict[str, str] | None = None) -> Self | None:
        return super().find(path, namespaces=namespaces)

    def findall(self, path: str, namespaces: dict[str, str] | None = None) -> list[Self]:
        return super().findall(path, namespaces=namespaces)

    def xpath(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
        **kwargs: dict[str, Any],
    ) -> list[Self]:
        return super().xpath(path, namespaces=namespaces, **kwargs)


class BetterElement(CustomElement):
    """Simplifies handling of namespaces in ElementTree."""

    @cached_property
    def query_compatible_nsmap(self) -> dict[str, str]:
        nsmap = dict(self.nsmap)
        nsmap[""] = nsmap.pop(None)
        return nsmap

    @override
    def find(self, path: str, namespaces: dict[str, str] | None = None) -> Self | None:
        return super().find(path, namespaces=namespaces or self.query_compatible_nsmap)

    @override
    def findall(self, path: str, namespaces: dict[str, str] | None = None) -> list[Self]:
        return super().findall(path, namespaces=namespaces or self.query_compatible_nsmap)

    @override
    def xpath(
        self,
        path: str,
        namespaces: dict[str, str] | None = None,
        **kwargs: dict[str, Any],
    ) -> list[Self]:
        namespaces = namespaces or self.query_compatible_nsmap

        # xpath() does not support empty namespaces (applies to both None and empty string)
        namespaces.pop("", None)

        return super().xpath(path, namespaces=namespaces, **kwargs)

    @overload
    def get_namespaced_key(self, key: str) -> str:
        ...

    @overload
    def get_namespaced_key(self, namespace: str, key: str) -> str:
        ...

    # Note: Is there a better way to handle the overload here?
    def get_namespaced_key(self, arg1: str, arg2: str | None = None) -> str:  # type: ignore[misc]
        """Returns a XML key (tag or attribute name) with the correct namespace.

        The key is returned without prefix if no namespace is provided or
        no namespace map is attached.

        Otherwise the key is returned in the format {namespace}key or a exception
        is raised if the namespace can't be found in the namespace map.
        """
        if arg2 is None:
            key = arg1
            namespace = None
        else:
            namespace, key = arg1, arg2

        if not self.nsmap and namespace is None:
            return key

        if not (namespace_uri := self.nsmap.get(namespace)):
            raise ValueError(
                f"No namespace with name {namespace}. Known namespaces are {list(self.nsmap)}",
            )
        return f"{{{namespace_uri}}}{key}"

    @cached_property
    def localname(self) -> str:
        return etree.QName(self).localname
