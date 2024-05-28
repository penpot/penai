from collections import defaultdict
from copy import deepcopy
from enum import Enum
from typing import TYPE_CHECKING, Any, Self

from lxml import etree
from pptree import print_tree

from penai.types import PathLike, RecursiveStrDict
from penai.utils.dict import apply_func_to_nested_keys

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
    """A simple wrapper around the `ElementTree` class for now.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree):
        self.dom = dom

    @classmethod
    def from_root_element(
        cls,
        element: etree.ElementBase,
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


def get_node_depth(el: etree.ElementBase, root: etree.ElementBase | None = None) -> int:
    """Get the depth of an element in the SVG tree."""
    depth = 0

    def el_is_root(el: etree.ElementBase) -> bool:
        return el == root if root is not None else el.getparent() is None

    while not el_is_root(el):
        depth += 1
        el = el.getparent()
    return depth


def _get_penpot_svg_key(
    key: str,
    nsmap_prefix: str | None = "{https://penpot.app/xmlns}",
    nsmap: dict | None = None,
) -> str:
    if nsmap_prefix is not None and nsmap is not None:
        raise ValueError(f"Exactly one of {nsmap_prefix=} and {nsmap=} should be provided")
    if nsmap is not None:
        nsmap_prefix = "{" + nsmap["penpot"] + "}"
    if nsmap_prefix is None:
        raise ValueError(f"Exactly one of {nsmap_prefix=} and {nsmap=} should be provided")
    return nsmap_prefix + key


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
    return el.tag == _get_penpot_svg_key("shape")


def _el_is_group(el: etree.ElementBase) -> bool:
    return el.tag == "{http://www.w3.org/2000/svg}g"


_PenpotShapeDictEntry = dict["PenpotShapeElement", "_PenpotShapeDictEntry"]


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

        # NOTE: may be too slow at init, then make lazy or remove
        self._child_shapes: list[PenpotShapeElement] = []

    def __getattr__(self, item: str) -> Any:
        return getattr(self._lxml_element, item)

    def __hash__(self) -> int:
        return hash(self._lxml_element)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PenpotShapeElement):
            return False
        return self._lxml_element == other._lxml_element

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
        return self.attrib[_get_penpot_svg_key(key)]

    @property
    def name(self) -> str:
        return self.get_penpot_attr(PenpotShapeAttr.NAME)

    @property
    def type(self) -> str:
        return self.get_penpot_attr(PenpotShapeAttr.TYPE)

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


class PenpotPageSVG(SVG):
    def __init__(self, dom: etree.ElementTree):
        super().__init__(dom)

        shape_els, depth_to_shape_el, shape_el_to_depth = find_all_penpot_shapes(dom)
        self._depth_to_shape_el = depth_to_shape_el
        self._shape_el_to_depth = shape_el_to_depth
        self._max_shape_depth = max(depth_to_shape_el.keys())
        self.penpot_shape_elements = shape_els

    @property
    def max_shape_depth(self) -> int:
        return self._max_shape_depth

    def get_shape_elements_at_depth(self, depth: int) -> list[PenpotShapeElement]:
        return self._depth_to_shape_el.get(depth, [])

    def pprint_hierarchy(self) -> None:
        for shape in self.get_shape_elements_at_depth(0):
            shape.pprint_hierarchy()
