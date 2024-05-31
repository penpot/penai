from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING, Any, Self

from lxml import etree
from pptree import print_tree
from selenium.webdriver.remote.webdriver import WebDriver

from penai.types import PathLike, RecursiveStrDict
from penai.utils.dict import apply_func_to_nested_keys
from penai.utils.svg import (
    temp_file_for_content,
    trim_namespace_from_tree,
    url_to_data_uri,
    validate_uri,
)
from penai.xml import BetterElement

_CustomElementBaseAnnotationClass: Any = object
if TYPE_CHECKING:
    # Trick to get proper type hints and docstrings for lxlml etree stuff
    # It has the same api as etree, but the latter is in python and properly typed and documented,
    # whereas the former is a stub but much faster. So at type-checking time, we use the python version of etree.
    from xml import etree
    from xml.etree.ElementTree import Element as XMLElement

    # Trick to get type hints for custom elements (wrappers with getattr) in IDEs without inheriting at runtime
    _CustomElementBaseAnnotationClass = XMLElement


class SVG:
    """A simple wrapper around an `ElementTree` that is based on `BetterElement` as nodes in the tree.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree):
        self.dom = dom

    @classmethod
    def from_root_element(
        cls,
        element: BetterElement,
        nsmap: dict | None = None,
        svg_attribs: dict[str, str] | None = None,
    ) -> Self:
        """Create an SVG object from a given root element.

        :param element: The root element of the SVG document.
        :param nsmap: A dictionary mapping namespace prefixes to URIs.
        :param svg_attribs: A dictionary of attributes to add to the `attrib` field.
        """
        if not isinstance(element, BetterElement):
            raise TypeError(f"Expected an BetterElement, got {type(element)}")

        nsmap = nsmap or dict(element.nsmap)
        nsmap = {None: "http://www.w3.org/2000/svg", **nsmap}

        # As recommended in https://lxml.de/tutorial.html, create a deep copy of the element.
        element = deepcopy(element)

        if element.localname != "svg":
            root = BetterElement("svg", nsmap=nsmap)
            root.append(element)
        else:
            root = element

        if svg_attribs:
            root.attrib.update(svg_attribs)

        return cls(etree.ElementTree(root))

    @classmethod
    def from_file(cls, path: PathLike) -> Self:
        return cls(dom=BetterElement.parse_file(path))

    @classmethod
    def from_string(cls, string: str) -> Self:
        return cls(dom=BetterElement.parse_string(string))

    def strip_penpot_tags(self) -> None:
        """Strip all Penpot-specific nodes from the SVG tree.

        Useful for debugging, reverse engineering or testing purposes.
        """
        trim_namespace_from_tree(self.dom.getroot(), "penpot")

    def inline_images(self, elem: etree.ElementBase | None = None) -> None:
        # TODO: We currently don't make use of any concurrent fetching or caching
        # which could drastically speed up the inlining process.
        if elem is None:
            elem = self.dom.getroot()

        if not elem.prefix and elem.localname == "image":
            attribs = elem.attrib

            # According to https://developer.mozilla.org/en-US/docs/Web/SVG/Attribute/xlink:href
            # xlink:href is deprecated, so we will inly check the `href` attribute here.
            # Penpot also doesn't seem to make use of xlinks.
            # uri = attribs.get(f'{{{nsmap["xlink"]}}}href')

            uri = attribs.get("href")

            if uri and validate_uri(uri):
                data_uri = url_to_data_uri(uri)

                if attribs.get("href"):
                    del attribs["href"]

                attribs["href"] = data_uri

        for child in elem:
            self.inline_images(child)

    def to_file(self, path: PathLike) -> None:
        self.dom.write(path, pretty_print=True)

    def to_string(self, pretty: bool = True) -> str:
        return etree.tostring(self.dom, pretty_print=pretty).decode()


def get_node_depth(el: etree.ElementBase, root: etree.ElementBase | None = None) -> int:
    """Get the depth of an element in the SVG tree."""
    depth = 0

    def el_is_root(el: etree.ElementBase) -> bool:
        return el == root if root is not None else el.getparent() is None

    while not el_is_root(el):
        depth += 1
        el = el.getparent()
    return depth


class PenpotShapeAttr(Enum):
    NAME = "name"
    TYPE = "type"
    TRANSFORM = "transform"
    TRANSFORM_INVERSE = "transform-inverse"


# Support for other keys will be provided when needed. For reference, the full key list is below.
# ['name',
#  'type',
#  'transform',
#  'transform-inverse',
#  'flip-x',
#  'flip-y',
#  'proportion',
#  'proportion-lock',
#  'rotation',
#  'center-x',
#  'center-y',
#  'constraints-h',
#  'constraints-v',
#  'show-content',
#  'hide-in-viewer',
#  'component-file',
#  'component-id',
#  'component-root',
#  'shape-ref']


def _el_is_penpot_shape(el: etree.ElementBase) -> bool:
    return el.prefix == "penpot" and el.localname == "shape"


def _el_is_group(el: etree.ElementBase) -> bool:
    return el.tag == el.get_namespaced_key("g")


_PenpotShapeDictEntry = dict["PenpotShapeElement", "_PenpotShapeDictEntry"]


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Width and height must be non-negative")

    @classmethod
    def from_dom_rect(cls, dom_rect: dict[str, Any]) -> Self:
        """Create a BoundingBox object from a DOMRect object.

        See See https://developer.mozilla.org/en-US/docs/Web/API/DOMRect.
        """
        return cls(
            x=dom_rect["x"],
            y=dom_rect["y"],
            width=dom_rect["width"],
            height=dom_rect["height"],
        )
class PenpotShapeTypeCategory(Enum):
    # Container shapes can contain other shapes
    CONTAINER = "container"

    # Primitive shapes directly correspond to rendered elements and cannot have children
    PRIMITIVE = "primitive"


@dataclass
class PenpotShapeTypeDescription:
    category: PenpotShapeTypeCategory
    literal: str


class PenpotShapeType(Enum):
    # Group types
    GROUP = PenpotShapeTypeDescription(PenpotShapeTypeCategory.CONTAINER, "group")
    FRAME = PenpotShapeTypeDescription(PenpotShapeTypeCategory.CONTAINER, "frame")
    BOOL = PenpotShapeTypeDescription(PenpotShapeTypeCategory.CONTAINER, "bool")

    # Primitives
    CIRCLE = PenpotShapeTypeDescription(PenpotShapeTypeCategory.PRIMITIVE, "circle")
    IMAGE = PenpotShapeTypeDescription(PenpotShapeTypeCategory.PRIMITIVE, "image")
    PATH = PenpotShapeTypeDescription(PenpotShapeTypeCategory.PRIMITIVE, "path")
    RECT = PenpotShapeTypeDescription(PenpotShapeTypeCategory.PRIMITIVE, "rect")
    TEXT = PenpotShapeTypeDescription(PenpotShapeTypeCategory.PRIMITIVE, "text")

    @classmethod
    @cache
    def get_literal_type_to_shape_type_mapping(cls) -> dict[str, Self]:
        return {member.value.literal: member for member in cls}

    @classmethod
    def get_by_type_literal(cls, type_str: str) -> Self:
        mapping = cls.get_literal_type_to_shape_type_mapping()

        if type_str not in mapping:
            raise ValueError(
                f"Unknown Penpot shape type literal: {type_str}. Valid options are: {', '.join(mapping)}.",
            )

        return mapping[type_str]


class PenpotShapeElement(_CustomElementBaseAnnotationClass):
    """An object corresponding to a <penpot:shape> element in a Penpot SVG file.

    The <penpot:shape> tag is always a child of a <g> tag, to which it is in a
    one-to-one correspondence.
    However, parent or child shapes may be arbitrarily levels above or below
    the shape tag itself. Moreover, the children of a shape tag are not
    actually its children in the SVG tree, but rather the children of the
    corresponding <g> tag.
    """

    def __init__(self, lxml_element: etree.ElementBase) -> None:
        self._lxml_element = lxml_element
        self._depth_in_svg = get_node_depth(lxml_element)
        self._depth_in_shapes = len(self.get_all_parent_shapes())

        # This can serve as an implicit sanity check whether we currently cover all shape types
        self._shape_type = PenpotShapeType.get_by_type_literal(
            self.get_penpot_attr(PenpotShapeAttr.TYPE),
        )

        # NOTE: may be too slow at init, then make lazy or remove
        self._child_shapes: list[PenpotShapeElement] = []

        self._bounding_box: BoundingBox | None = None

    def __getattr__(self, item: str) -> Any:
        return getattr(self._lxml_element, item)

    def __hash__(self) -> int:
        return hash(self._lxml_element)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PenpotShapeElement):
            return False
        return self._lxml_element == other._lxml_element

    @property
    def shape_id(self) -> str:
        # The penpot shape element itself doesn't even contain its own id.
        # We actually have to ask its parent very kindly.
        return self.get_containing_g_element().get("id")

    @property
    def depth_in_svg(self) -> int:
        return self._depth_in_svg

    @property
    def depth_in_shapes(self) -> int:
        return self._depth_in_shapes

    @property
    def child_shapes(self) -> list["PenpotShapeElement"]:
        # TODO: this might be slow, and properties shouldn't be slow, but setting at init leads to infinite recursion..
        if not self._child_shapes:
            self._child_shapes = self.get_direct_children_shapes()
        return self._child_shapes

    def get_penpot_attr(self, key: str | PenpotShapeAttr) -> str:
        key = key.value if isinstance(key, PenpotShapeAttr) else key
        return self.attrib[self.get_namespaced_key("penpot", key)]

    @property
    def name(self) -> str:
        return self.get_penpot_attr(PenpotShapeAttr.NAME)

    @property
    def type(self) -> PenpotShapeType:
        return self._shape_type

    @property
    def is_container_type(self) -> bool:
        return self._shape_type.value.category == PenpotShapeTypeCategory.CONTAINER

    @property
    def is_primitive_type(self) -> bool:
        return self._shape_type.value.category == PenpotShapeTypeCategory.PRIMITIVE

    @property
    def bounding_box(self) -> BoundingBox | None:
        return self._bounding_box

    def set_bounding_box(self, bbox: BoundingBox) -> None:
        self._bounding_box = bbox

    def get_parent_shape(self) -> Self | None:
        g_containing_par_shape_candidate = self.get_containing_g_element().getparent()
        while g_containing_par_shape_candidate is not None:
            if _el_is_group(g_containing_par_shape_candidate):
                for child in g_containing_par_shape_candidate:
                    if _el_is_penpot_shape(child):
                        return self.__class__(child)
            g_containing_par_shape_candidate = g_containing_par_shape_candidate.getparent()
        return None

    def get_all_parent_shapes(self) -> list[Self]:
        parent_shape = self.get_parent_shape()
        if parent_shape is None:
            return []
        return [parent_shape, *parent_shape.get_all_parent_shapes()]

    def get_containing_g_element(self) -> etree.ElementBase:
        """Get the parent <g> element to which this shape corresponds; child shapes will be children of it.

        See docstring of the class for more info on the relation between <g> and <penpot:shape> tags.
        """
        return self.getparent()

    def is_leave(self) -> bool:
        return not self.get_direct_children_shapes()

    def get_all_children_shapes(self) -> list["PenpotShapeElement"]:
        """Get all the children of this shape, including children of children, etc."""
        containing_group = self.get_containing_g_element()
        result = find_all_penpot_shapes(containing_group)[0]
        return [shape for shape in result if shape != self]

    # TODO: very inefficient, should be optimized if ever a bottleneck
    def get_direct_children_shapes(self) -> list["PenpotShapeElement"]:
        """Get the direct children of this shape."""
        children_shapes = self.get_all_children_shapes()
        return [shape for shape in children_shapes if shape.get_parent_shape() == self]

    def get_hierarchy_dict(self) -> dict["PenpotShapeElement", "_PenpotShapeDictEntry"]:
        result = {}
        for child in self.get_direct_children_shapes():
            result[child] = child.get_hierarchy_dict()
        return {self: result}

    def get_hierarchy_dict_for_names(self) -> RecursiveStrDict:
        hierarchy_dict = self.get_hierarchy_dict()
        return apply_func_to_nested_keys(hierarchy_dict, lambda k: k.name)

    def pprint_hierarchy(self) -> None:
        print_tree(self, childattr="child_shapes", nameattr="name")


def find_all_penpot_shapes(
    root: etree.ElementBase | PenpotShapeElement,
) -> tuple[
    list[PenpotShapeElement],
    dict[int, list[PenpotShapeElement]],
    dict[PenpotShapeElement, int],
]:
    """Find all Penpot shapes in the SVG tree starting from the given root element.

    :param root:
    :return: a tuple containing the list of PenpotShapeElement objects, a dictionary mapping depths to shape elements,
        and a dictionary mapping shape elements to their depths. All depths are relative to the root element and
        are depths in terms of the parent and child shapes, not in terms of the depths in the SVG tree.
    """
    depth_to_shape_el = defaultdict(list)
    shape_el_to_depth = {}
    penpot_shape_elements = []

    for el in root.iter():
        if _el_is_penpot_shape(el):
            shape_el = PenpotShapeElement(el)
            depth_to_shape_el[shape_el.depth_in_shapes].append(shape_el)
            shape_el_to_depth[shape_el] = shape_el.depth_in_shapes
            penpot_shape_elements.append(shape_el)

    return penpot_shape_elements, depth_to_shape_el, shape_el_to_depth


class PenpotComponentSVG(SVG):
    """Representing a Penpot component, usually loaded from elements in a file named `component.svg`."""


class PenpotPageSVG(SVG):
    def __init__(self, dom: etree.ElementTree):
        super().__init__(dom)

        shape_els, depth_to_shape_el, shape_el_to_depth = find_all_penpot_shapes(dom)
        self._depth_to_shape_el = depth_to_shape_el
        self._shape_el_to_depth = shape_el_to_depth
        if depth_to_shape_el:
            self._max_shape_depth = max(depth_to_shape_el.keys())
        else:
            self._max_shape_depth = 0
        self.penpot_shape_elements = shape_els

        # We need the bounding box of the root element as well as the per-shape bounding boxes might
        # deviate between renderers or configurations, e.g. due to dpi differences.
        # This information can be used to align them.
        self.bounding_box: BoundingBox | None = None

    @property
    def max_shape_depth(self) -> int:
        return self._max_shape_depth

    def get_shape_elements_at_depth(self, depth: int) -> list[PenpotShapeElement]:
        return self._depth_to_shape_el.get(depth, [])

    def pprint_hierarchy(self) -> None:
        for shape in self.get_shape_elements_at_depth(0):
            shape.pprint_hierarchy()

    def derive_bounding_boxes(self, web_driver: WebDriver) -> None:
        svg_string = etree.tostring(self.dom).decode()

        # Perhaps not valid html but yolo
        html_string = "<body>" + svg_string + "</body>"

        with temp_file_for_content(html_string, extension=".html") as path:
            web_driver.get(path.absolute().as_uri())

            for shape in self.penpot_shape_elements:
                shape_id = shape.shape_id

                bbox = web_driver.execute_script(
                    f"return document.getElementById('{shape_id}').getBoundingClientRect();",
                )

                assert (
                    bbox is not None
                ), f"Couldn't derive bounding box for shape with id {shape_id}"

                shape.set_bounding_box(BoundingBox.from_dom_rect(bbox))

            self.bounding_box = BoundingBox.from_dom_rect(
                web_driver.execute_script(
                    'return document.querySelector("svg").getBoundingClientRect()',
                ),
            )
