from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import TYPE_CHECKING, Any, Literal, Self, Union, cast, overload

from lxml import etree
from pptree import print_tree
from selenium.webdriver.remote.webdriver import WebDriver
from tqdm import tqdm

from penai.registries.web_drivers import RegisteredWebDriver, get_web_driver_for_html
from penai.types import PathLike, RecursiveStrDict
from penai.utils.dict import apply_func_to_nested_keys
from penai.utils.svg import (
    trim_namespace_from_tree,
    url_to_data_uri,
    validate_uri,
)
from penai.xml import BetterElement, Element

_CustomElementBaseAnnotationClass: Any = object
if TYPE_CHECKING:
    # Trick to get proper type hints and docstrings for lxlml etree stuff
    # It has the same api as etree, but the latter is in python and properly typed and documented,
    # whereas the former is a stub but much faster. So at type-checking time, we use the python version of etree.
    from xml import etree

    _CustomElementBaseAnnotationClass = BetterElement

_VIEW_BOX_KEY = "viewBox"


@dataclass
class BoundingBox:
    x: float
    y: float
    width: float
    height: float

    def with_margin(self, margin: float, relative: bool = False) -> "BoundingBox":
        if relative:
            longest_edge = max(self.width, self.height)

            absolute_margin = margin * longest_edge
        else:
            absolute_margin = margin

        return BoundingBox(
            x=self.x - absolute_margin,
            y=self.y - absolute_margin,
            width=self.width + 2 * absolute_margin,
            height=self.height + 2 * absolute_margin,
        )

    @classmethod
    def from_view_box_string(cls, view_box: str) -> Self:
        return cls(*map(float, view_box.split()))

    def to_view_box_string(self) -> str:
        return f"{self.x} {self.y} {self.width} {self.height}"

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Width and height must be non-negative")

    @classmethod
    def from_dom_rect(cls, dom_rect: dict[str, Any]) -> Self:
        """Create a BoundingBox object from a DOMRect object.

        See https://developer.mozilla.org/en-US/docs/Web/API/DOMRect.
        """
        return cls(
            x=dom_rect["x"],
            y=dom_rect["y"],
            width=dom_rect["width"],
            height=dom_rect["height"],
        )


class SVG:
    """A simple wrapper around an `ElementTree` that is based on `BetterElement` as nodes in the tree.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree):
        self.dom = dom

    def to_html_string(self) -> str:
        return f"<html><body>{self.to_string()}</body></html>"

    def retrieve_default_view_box(
        self,
        web_driver: WebDriver | RegisteredWebDriver,
    ) -> "BoundingBox":
        with get_web_driver_for_html(web_driver, self.to_html_string()) as driver:
            retrieved_bbox_dom_rect = driver.execute_script(
                'return document.querySelector("svg").getBBox()',
            )

        if retrieved_bbox_dom_rect is None:
            raise ValueError(
                f"Could not find the bbox for svg using {web_driver=}. "
                "This is likely caused by an invalid SVG, problems with the WebDriver "
                "or an actual bug in PenAI.",
            )
        return BoundingBox.from_dom_rect(retrieved_bbox_dom_rect)

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
            root = BetterElement.create(tag="svg", nsmap=nsmap)
            root.append(element)
        else:
            root = element

        if svg_attribs:
            root.attrib.update(svg_attribs)

        return cls(etree.ElementTree(root))

    def set_view_box(self, view_box: BoundingBox) -> None:
        self.dom.getroot().attrib["viewBox"] = view_box.to_view_box_string()

    def set_default_view_box_from_web_driver(self, web_driver: WebDriver) -> None:
        self.set_view_box(self.retrieve_default_view_box(web_driver))

    def get_view_box(self) -> "BoundingBox":
        view_box_str = self.dom.getroot().attrib.get("viewBox")
        if view_box_str is None:
            raise ValueError("No view box set.")
        return BoundingBox(*map(float, view_box_str.split()))

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


def _el_is_penpot_shape(el: Element) -> bool:
    return el.prefix == "penpot" and el.localname == "shape"


def _el_is_group(el: Element) -> bool:
    return el.tag == el.get_namespaced_key("g")


_PenpotShapeDictEntry = dict["PenpotShapeElement", "_PenpotShapeDictEntry"]


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
        # NOTE: The PenpotShapeElement is a shallow wrapper around an lxml element.
        # Equality, hash and other things are all bound to the lxml element itself
        # This means that essentially no attributes should be saved in the instances
        # of ShapeElement directly, as it would break this pattern.
        # Instead, everything concerning the true state should "forwarded" to
        # the _lxml_element. See the property _default_view_box for an example

        self._lxml_element = lxml_element
        self._depth_in_svg = get_node_depth(lxml_element)
        self._depth_in_shapes = len(self.get_all_parent_shapes())

        # This can serve as an implicit sanity check whether we currently cover all shape types
        self._shape_type = PenpotShapeType.get_by_type_literal(
            self.get_penpot_attr(PenpotShapeAttr.TYPE),
        )

        self._child_shapes: list[PenpotShapeElement] = []

    def get_root_element(self) -> BetterElement:
        return cast(BetterElement, self._lxml_element.getroottree().getroot())

    @property
    def _default_view_box(self) -> BoundingBox | None:
        view_box_string = self._lxml_element.attrib.get(_VIEW_BOX_KEY)
        if view_box_string:
            return BoundingBox.from_view_box_string(view_box_string)
        return None

    @_default_view_box.setter
    def _default_view_box(self, view_box: BoundingBox) -> None:
        view_box_string = view_box.to_view_box_string()
        self._lxml_element.attrib[_VIEW_BOX_KEY] = view_box_string

    def __getattr__(self, item: str) -> Any:
        return getattr(self._lxml_element, item)

    def __hash__(self) -> int:
        return hash(self._lxml_element)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, PenpotShapeElement):
            return False
        return self._lxml_element == other._lxml_element

    def to_svg(self, view_box: BoundingBox | Literal["default"] | None = "default") -> SVG:
        """Convert the shape to an SVG object.

        :param view_box: The view box to set for the SVG. The "default" setting will use the view-box that just fits
            the shape. If None, the containing SVG's root-element's view box will be used.
            If the shape came from a Penpot page, the root element is the SVG element of the page,
            and the view box will be set to the default view box of the page.
        """
        svg_root_attribs = deepcopy(self._lxml_element.getroottree().getroot().attrib)
        if view_box == "default":
            view_box = self.get_default_view_box()
        if view_box is not None:
            svg_root_attribs["viewBox"] = view_box.to_view_box_string()
        svg_root_attribs["preserveAspectRatio"] = "xMinYMin meet"
        return SVG.from_root_element(self.get_containing_g_element(), svg_attribs=svg_root_attribs)

    def set_default_view_box(
        self,
        bbox: BoundingBox | None = None,
        web_driver: Union[WebDriver, "RegisteredWebDriver"] = None,
    ) -> None:
        if bbox is not None:
            self._default_view_box = bbox
            return

        if web_driver is None:
            raise ValueError(
                "since bbox was not provided, a renderer must be provided to derive the default view box "
                "from the dom.",
            )
        self._default_view_box = self.to_svg(view_box=None).retrieve_default_view_box(web_driver)

    def get_default_view_box(
        self,
        web_driver: Union[WebDriver, "RegisteredWebDriver"] | None = None,
    ) -> BoundingBox:
        if self._default_view_box is not None:
            return self._default_view_box

        if web_driver is None:
            raise ValueError(
                "Default view box was not yet set, a renderer must be provided to derive the default view box.",
            )
        self.set_default_view_box(web_driver=web_driver)
        return cast(BoundingBox, self._default_view_box)

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

    def get_containing_g_element(self) -> BetterElement:
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

    def pprint_hierarchy(self, horizontal: bool = True) -> None:
        print_tree(self, childattr="child_shapes", nameattr="name", horizontal=horizontal)


def find_all_penpot_shapes(
    root: Element | PenpotShapeElement,
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

    @overload
    def _get_shapes_by_attr(
        self,
        attr_name: str,
        attr_value: Any,
        should_be_unique: Literal[True],
    ) -> PenpotShapeElement:
        ...

    @overload
    def _get_shapes_by_attr(
        self,
        attr_name: str,
        attr_value: Any,
        should_be_unique: Literal[False],
    ) -> list[PenpotShapeElement]:
        ...

    @cache
    def _get_shapes_by_attr(
        self,
        attr_name: str,
        attr_value: Any,
        should_be_unique: bool = False,
    ) -> PenpotShapeElement | list[PenpotShapeElement]:
        matched_shapes = [
            shape for shape in self.penpot_shape_elements if getattr(shape, attr_name) == attr_value
        ]
        if not should_be_unique:
            return matched_shapes

        if len(matched_shapes) == 0:
            raise KeyError(f"No shape with '{attr_name=}' and '{attr_value=}' found")
        if len(matched_shapes) > 1:
            raise RuntimeError(
                f"Multiple shapes {len(matched_shapes)=} with '{attr_name=}' and '{attr_value=}' found. "
                "This should not happen and could be caused by an implementation error or by a malformed SVG file.",
            )
        return matched_shapes[0]

    def get_shape_by_name(self, name: str) -> PenpotShapeElement:
        return self._get_shapes_by_attr("name", name, should_be_unique=True)

    def get_shape_by_id(self, shape_id: str) -> PenpotShapeElement:
        return self._get_shapes_by_attr("shape_id", shape_id, should_be_unique=True)

    @property
    def max_shape_depth(self) -> int:
        return self._max_shape_depth

    def get_shape_elements_at_depth(self, depth: int) -> list[PenpotShapeElement]:
        return self._depth_to_shape_el.get(depth, [])

    def pprint_hierarchy(self, horizontal: bool = True) -> None:
        for shape in self.get_shape_elements_at_depth(0):
            shape.pprint_hierarchy(horizontal=horizontal)

    def retrieve_and_set_view_boxes_for_shape_elements(
        self,
        web_driver: WebDriver | RegisteredWebDriver,
        selected_shape_elements: Iterable[PenpotShapeElement] | None = None,
        show_progress: bool = True,
    ) -> None:
        """Retrieve the default view boxes for all shapes in the SVG and set them on the shapes.
        This is more efficient than setting them one by one, as
        this way only a single html (corresponding to the whole page) needs to be rendered
        instead of one for each shape.

        :param web_driver:
        :param selected_shape_elements: if None, all shapes in a page will be processed.
            Otherwise, a subset of the page's shapes can be passed.
        :param show_progress: Whether to show a progress bar.
        :return:
        """
        if selected_shape_elements is None:
            selected_shape_elements = self.penpot_shape_elements
        else:
            if non_contained_shape_ids := {s.shape_id for s in selected_shape_elements}.difference(
                {s.shape_id for s in self.penpot_shape_elements},
            ):
                raise ValueError(
                    f"The provided shapes are not a subset of the pages' shape. {non_contained_shape_ids=}",
                )
        if show_progress:
            selected_shape_elements = cast(
                Iterable[PenpotShapeElement],
                tqdm(selected_shape_elements, desc="Setting view boxes"),
            )

        with get_web_driver_for_html(web_driver, self.to_html_string()) as driver:
            for shape_el in selected_shape_elements:
                view_box_dom_rect = driver.execute_script(
                    f"return document.getElementById('{shape_el.shape_id}').getBBox();",
                )
                shape_bbox = BoundingBox.from_dom_rect(view_box_dom_rect)
                shape_el.set_default_view_box(bbox=shape_bbox)
