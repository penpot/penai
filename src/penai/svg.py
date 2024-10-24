import abc
import logging
import re
import webbrowser
from collections import defaultdict
from collections.abc import Iterable
from copy import deepcopy
from enum import Enum
from functools import cache
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Any, Literal, Self, Union, cast, overload

import matplotlib.transforms as mpl_transforms
import randomname
import shortuuid
from lxml import etree
from PIL.Image import Image
from pptree import print_tree
from pydantic import NonNegativeFloat
from pydantic.dataclasses import dataclass
from selenium.webdriver.remote.webdriver import WebDriver
from tqdm import tqdm

import penai.utils.misc as utils
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
log = logging.getLogger(__name__)


class BaseStyleSupplier(abc.ABC):
    @abc.abstractmethod
    def get_style(self) -> str | None:
        pass


@dataclass
class BoundingBox:
    x: float
    y: float
    width: NonNegativeFloat
    height: NonNegativeFloat

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

    def intersection(self, other: Self) -> "BoundingBox":
        return BoundingBox(
            x=min(self.x + self.width, other.x + other.width) - max(self.x, other.x),
            y=min(self.y + self.height, other.y + other.height) - max(self.y, other.y),
            width=min(self.x + self.width, other.x + other.width) - max(self.x, other.x),
            height=min(self.y + self.height, other.y + other.height) - max(self.y, other.y),
        )

    def union(self, other: Self) -> "BoundingBox":
        return BoundingBox(
            x=min(self.x, other.x),
            y=min(self.y, other.y),
            width=max(self.x + self.width, other.x + other.width) - min(self.x, other.x),
            height=max(self.y + self.height, other.y + other.height) - min(self.y, other.y),
        )

    @property
    def aspect_ratio(self) -> NonNegativeFloat:
        return self.width / self.height

    @classmethod
    def from_view_box_string(cls, view_box: str) -> Self:
        return cls(*map(float, view_box.split()))

    def to_view_box_string(self) -> str:
        return f"{self.x} {self.y} {self.width} {self.height}"

    def to_view_box_tuple(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_svg_attribs(self) -> dict[str, str]:
        return {
            "x": str(self.x),
            "y": str(self.y),
            "width": str(self.width),
            "height": str(self.height),
        }

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

    @classmethod
    def from_clip_rect(cls, clip_rect_el: Element) -> Self:
        """Create a BoundingBox object from a clipPath rect SVG element."""
        return cls(
            *[float(clip_rect_el.get(attr)) for attr in ("x", "y", "width", "height")],
        )

    def crop_image(self, image: Image) -> Image:
        """Utility method to crop an PIL image to the bounding box."""
        box = cast(
            tuple[int, int, int, int],
            tuple(map(round, (self.x, self.y, self.x + self.width, self.y + self.height))),
        )
        return image.crop(box)

    def intersects(self, other: Self) -> bool:
        # Check if one rectangle is to the left of the other
        if self.x + self.width < other.x or other.x + other.width < self.x:
            return False
        # Check if one rectangle is above the other
        if self.y + self.height < other.y or other.y + other.height < self.y:
            return False
        return True

    def format_as_string(self) -> str:
        """Format a bounding box as a string."""
        bbox_tuple = self.to_view_box_tuple()
        bbox_values = [str(round(value)) for value in bbox_tuple]
        bbox_str = "[" + ", ".join(bbox_values) + "]"
        return bbox_str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BoundingBox):
            return False

        return (
            self.x == other.x
            and self.y == other.y
            and self.width == other.width
            and self.height == other.height
        )

    @classmethod
    def from_corner_points(
        cls,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> Self:
        if x0 > x1:
            x0, x1 = x1, x0
        if y0 > y1:
            y0, y1 = y1, y0
        return cls(x0, y0, x1 - x0, y1 - y0)

    @classmethod
    def from_mpl_bbox(cls, bbox: mpl_transforms.Bbox) -> Self:
        return cls.from_corner_points(bbox.x0, bbox.y0, bbox.x1, bbox.y1)


class SVG:
    """A simple wrapper around an `ElementTree` that is based on `BetterElement` as nodes in the tree.

    In the long-term (lol never), we might extend this a full-fledged SVG implementation.
    """

    def __init__(self, dom: etree.ElementTree, remove_unwanted_elements: bool = True):
        if remove_unwanted_elements:
            dom = deepcopy(dom)
            self._remove_unwanted_elements(dom)
        self.dom = dom

    NSMAP = {
        "svg": "http://www.w3.org/2000/svg",
        "penpot": "https://penpot.app/xmlns",
    }

    # NOTE: very similar to MinimalPenpotXML logic
    UNWANTED_ATTR_KEY_VALS = {
        "transform": "matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)",
        "transform-inverse": "matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)",
        "rotation": "0",
        "rx": "0",
        "ry": "0",
    }

    @classmethod
    def _attr_qual_name(cls, name: str, namespace: str) -> str:
        return "{" + cls.NSMAP[namespace] + "}" + name

    @classmethod
    def possible_attr_qual_names(cls, name: str) -> list[str]:
        return [name] + [cls._attr_qual_name(name, ns) for ns in cls.NSMAP]

    @classmethod
    @cache
    def _unwanted_attr_qual_name_values(cls) -> list[tuple[str, str]]:
        result = []
        for attr_name, value in cls.UNWANTED_ATTR_KEY_VALS.items():
            for attr_qual_name in cls.possible_attr_qual_names(attr_name):
                result.append((attr_qual_name, value))
        return result

    @classmethod
    def _remove_unwanted_elements(cls, tree: BetterElement) -> None:
        for element in tree.iter():
            for attr_qual_name, value in cls._unwanted_attr_qual_name_values():
                if element.attrib.get(attr_qual_name, None) == value:
                    del element.attrib[attr_qual_name]

    def to_html_string(
        self, width_override: str | None = None, height_override: str | None = None
    ) -> str:
        try:
            view_box = self.get_view_box()
            w, h = f"{int(view_box.width)}px", f"{int(view_box.height)}px"
        except AttributeError as e:
            log.debug(str(e))
            w = ""
            h = ""

        # handle user-provided scaling infosw
        # note that if the user provides only one, we should set the other value to
        # auto even if it's set previously from the viewBox
        # Note: width_override=None is not the same as width_override=""
        if width_override is not None:
            w = width_override
            if height_override is not None:
                h = "auto"
        if height_override is not None:
            h = height_override
            if width_override is not None:
                w = "auto"

        style_tag = f'style="width: {w}; height: {h};"'
        return f"<html><body><div {style_tag}>{self.to_string()}</div></body></html>"

    def compute_view_box_with_web_driver(
        self,
        web_driver: WebDriver | RegisteredWebDriver,
    ) -> "BoundingBox":
        """Computes the view box of the SVG by rendering it in a browser and querying the BBox.

        Should only be used if the viewBox attribute of the SVG is not yet set. Otherwise, the
        method `get_view_box` should be preferred, since rendering is slow. Recommended to use
        this method only if you know what you are doing.
        """
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
        """Sets the viewBox attribute of the SVG."""
        self.dom.getroot().attrib["viewBox"] = view_box.to_view_box_string()

    def get_view_box(self) -> BoundingBox:
        """Retrieves the SVG's view box by either using the viewBox attribute or by using width and height as fallback.

        If neither viewBox nor width and height are present will raise an `AttributeError`
        """
        root = self.dom.getroot()
        view_box_str = root.attrib.get("viewBox")
        if view_box_str is None:
            # If a view box is not explicitly set, we can try to derive it from the width and height attributes.
            # This seems to the default behavior of Chrome.
            width = root.get("width")
            height = root.get("height")

            if width and height:
                return BoundingBox(0, 0, float(width), float(height))

            raise AttributeError(
                f"No viewBox and no width and height attributes set in SVG:\n"
                f"{self.to_string(pretty=True)[:200]}..."
            )
        return BoundingBox(*map(float, view_box_str.split()))

    def set_dimensions(
        self,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Sets the width and height attributes in the SVG.

        Some renderers may make use of them, especially if the viewBox attribute is not set.
        """
        if not width and not height:
            raise ValueError("At least one of width or height must be provided.")

        aspect_ratio = self.get_view_box().aspect_ratio

        root = self.dom.getroot()

        if width is not None:
            root.attrib["width"] = str(width)
        elif height is not None:
            root.attrib["width"] = str(round(height * aspect_ratio))

        if height is not None:
            root.attrib["height"] = str(height)
        elif width is not None:
            root.attrib["height"] = str(round(width / aspect_ratio))

    @classmethod
    # type: ignore
    def from_file(cls, path: PathLike, **kwargs) -> Self:
        return cls(dom=BetterElement.parse_file(path), **kwargs)

    @classmethod
    # type: ignore
    def from_string(cls, string: str, **kwargs) -> Self:
        return cls(dom=BetterElement.parse_string(string), **kwargs)

    def strip_penpot_tags(self) -> None:
        """Strip all Penpot-specific nodes from the SVG tree.

        Useful for debugging, reverse engineering or testing purposes.
        """
        trim_namespace_from_tree(self.dom.getroot(), "penpot")

    def strip_foreign_tags(self) -> None:
        """Removes all non-native SVG tags from the SVG tree.

        Currently only implemented for SVGs extracted from penpot and thus incomplete.
        Will be completed as needed.
        """
        self.strip_penpot_tags()

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

    def inject_style(self, style: str) -> None:
        style_el = etree.Element("style")
        style_el.text = style
        self.dom.getroot().insert(0, style_el)

    def to_file(self, path: PathLike, pretty: bool = False) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.dom.write(path, pretty_print=pretty)

    def to_string(
        self,
        pretty: bool = True,
        replace_ids_by_short_ids: bool = False,
        unique_ids: bool = False,
        add_width_height: bool = False,
        scale_to_width: int | None = None,
    ) -> str:
        """:param pretty:
        :param replace_ids_by_short_ids:
        :param unique_ids: whether to replace all ids with unique ids
            (in order to avoid id conflicts when combining multiple SVGs)
        :param add_width_height: whether to add width and height attributes to the SVG element
            (as indicated by the viewBox)
        :param scale_to_width: only has an effect if add_width_height is True; if set, the width
            and height attributes will be set to the corresponding values of the viewBox, scaled
            to the given width.
        :return: string representation of the entire <svg> element
        """
        if unique_ids and replace_ids_by_short_ids:
            raise ValueError("Cannot set both unique_ids and replace_ids_by_short_ids to True.")

        dom = self.dom

        if add_width_height:
            dom = deepcopy(dom)

            # read viewbox dimensions from root and add corresponding width and height attributes
            view_box = dom.getroot().attrib.get("viewBox")
            if view_box:
                x, y, width, height = map(float, view_box.split())

                if scale_to_width is not None:
                    scale_factor = scale_to_width / width
                    width *= scale_factor
                    height *= scale_factor

                dom.getroot().attrib["width"] = str(width)
                dom.getroot().attrib["height"] = str(height)

            else:
                log.warning("No viewBox found; could not set width and height")

        result = etree.tostring(dom, pretty_print=pretty).decode()

        if replace_ids_by_short_ids:
            all_ids = set()
            for el in dom.iter():
                if "id" in el.attrib:
                    all_ids.add(el.attrib["id"])

            for i, el_id in enumerate(sorted(all_ids)):
                result = result.replace(el_id, f"{i}")

        if unique_ids:
            result = ensure_unique_ids_in_svg_code(result)

        return result

    def open_in_browser(self) -> None:
        with NamedTemporaryFile(suffix=".html", delete=False) as f:
            self.to_file(f.name)
            webbrowser.open("file://" + f.name)

    def with_shortened_ids(self) -> Self:
        return self.from_string(self.to_string(replace_ids_by_short_ids=True, unique_ids=False))


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


def _el_has_visible_content(el: Element) -> bool:
    children = el.getchildren()

    # Note: Not sure if this is really true
    # A <g> might have a class set that will set some fill / bg color and thus make it visible
    if not children:
        return False

    if len(children) == 1 and children[0].tag == el.get_namespaced_key(
        "path",
    ):
        css_parser = utils.get_css_parser()

        path = children[0]
        path_style = css_parser.parseStyle(path.get("style", ""))

        if path_style.getPropertyValue("opacity") == "0":
            return False

        if not path.getchildren() and (
            path.get("fill") == "none" or path_style.getPropertyValue("fill") in ["none"]
        ):
            return False

    return True


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

    def __init__(
        self,
        lxml_element: etree.ElementBase,
        style_supplier: BaseStyleSupplier | None = None,
    ) -> None:
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
        self._style_supplier = style_supplier

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

    def to_svg(
        self,
        view_box: BoundingBox | Literal["default"] | None = "default",
    ) -> SVG:
        """Convert the shape to an SVG object.

        :param view_box: The view box to set for the SVG. The "default" setting will use the view-box that just fits
            the shape. If None, the containing SVG's root-element's view box will be used.
            If the shape came from a Penpot page, the root element is the SVG element of the page,
            and the view box will be set to the default view box of the page.
        """
        svg_root_attribs = deepcopy(self._lxml_element.getroottree().getroot().attrib)
        style_string = svg_root_attribs.get("style", "")
        style_string = re.sub(r"width:.*?;", "", style_string)
        style_string = re.sub(r"height:.*?;", "", style_string)
        style_string = re.sub(r"fill:.*?;", "", style_string)
        if style_string:
            svg_root_attribs["style"] = style_string

        svg_root_attribs.pop("fill", None)
        svg_root_attribs.pop("width", None)
        svg_root_attribs.pop("height", None)

        if isinstance(view_box, str) and view_box == "default":
            view_box = self.get_default_view_box()
        if view_box is not None:
            svg_root_attribs["viewBox"] = view_box.to_view_box_string()
        svg_root_attribs["preserveAspectRatio"] = "xMinYMin meet"
        svg = SVG.from_root_element(
            self.get_containing_g_element(),
            svg_attribs=svg_root_attribs,
        )

        if self._style_supplier is not None:
            style = self._style_supplier.get_style()
            if style is not None:
                svg.inject_style(style)

        return svg

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
                "since bbox was not provided, a web_driver must be provided to derive the default view box "
                "from the dom.",
            )
        self._default_view_box = self.to_svg(view_box=None).compute_view_box_with_web_driver(
            web_driver,
        )

    def get_clip_rect(self) -> BoundingBox | None:
        """Objects (maybe only groups?) in SVG can have a `clip-path` attribute that sets the clip mask.

        For Penpot shapes, this attribute will typically be set on the main group element of the shape
        and reference a <clipPath> element that contains a <rect>-element, defining the clip mask, defined
        in the <defs>-section of that shape.

        This method retrieves the bounding box of the clip mask rect if it exists.

        Note, that for now we only support simple clip masks that are defined by a <rect> element and will
        throw an error if no such element can be found.
        """
        parent_group = self.get_containing_g_element()
        if (child_group := parent_group.find("g")) is not None and (
            clip_path := child_group.get("clip-path")
        ) is not None:
            if (clip_path_match := re.match(r"url\(#(.*)\)", clip_path)) is not None:
                clip_path_id = clip_path_match.group(1)
            else:
                raise AssertionError(
                    f"Expected clip-path to be in the format 'url(#id)', but got '{clip_path}'",
                )

            defs = parent_group.find("./defs")

            # Note: <clipPath> defines the clip _mask_ which can be a rect in the simplest case but potentially
            # also more complex compositions.
            # For the sake of sanity, we assume that the clip-path is a simple rect for now and will throw an error
            # if a <rect>-element or path with x, y, width and height attributes can't be found within the <clipPath>.
            for tag in ["rect", "path"]:
                clip_el = defs.find(
                    f'./clipPath[@id="{clip_path_id}"]/{tag}',
                )

                if clip_el is None:
                    continue

                assert set(clip_el.keys()) >= {
                    "x",
                    "y",
                    "width",
                    "height",
                }, f"Expected clip element to have attributes 'x', 'y', 'width', 'height', but got {clip_el.keys()}"

                return BoundingBox.from_clip_rect(clip_el)

            raise AssertionError(
                f"Expected to find <clipPath> with containing <rect> or <path> element with id {clip_path_id} as it was "
                "referenced in the element's main group element, but didn't, which is, you know, like unexpected.",
            )
        return None

    def get_default_view_box(
        self,
        web_driver: Union[WebDriver, "RegisteredWebDriver"] | None = None,
    ) -> BoundingBox:
        if self._default_view_box is not None:
            return self._default_view_box

        if web_driver is None:
            raise ValueError(
                "Default view box was not yet set, a web_driver must be provided to derive the default view box.",
            )
        self.set_default_view_box(web_driver=web_driver)
        return cast(BoundingBox, self._default_view_box)

    @property
    def shape_id(self) -> str:
        # The penpot shape element itself doesn't even contain its own id.
        # We actually have to ask its parent very kindly.
        return self.get_containing_g_element().get("id")

    @property
    def id(self) -> str:
        """:return: the shape's UUID"""
        shape_id = self.shape_id
        prefix = "shape-"
        assert shape_id.startswith(prefix)
        return shape_id[len(prefix) :]

    @property
    def depth_in_svg(self) -> int:
        return self._depth_in_svg

    @property
    def depth_in_shapes(self) -> int:
        return self._depth_in_shapes

    def get_shape_height(self) -> int:
        children = list(self.get_direct_children_shapes())

        if not children:
            return 0

        return 1 + max(child.get_shape_height() for child in children)

    def iter_children_at_depth(self, depth: int) -> Iterable[Self]:
        if depth:
            for child in self.get_direct_children_shapes():
                yield from child.iter_children_at_depth(depth - 1)
        else:
            yield self

    @property
    def child_shapes(self) -> list["PenpotShapeElement"]:
        # TODO: this might be slow, and properties shouldn't be slow, but setting at init leads to infinite recursion..
        if not self._child_shapes:
            self._child_shapes = self.get_direct_children_shapes()
        return self._child_shapes

    def get_penpot_attr(self, key: str | PenpotShapeAttr) -> str:
        key = key.value if isinstance(key, PenpotShapeAttr) else key
        return self.attrib[self.get_namespaced_key("penpot", key)]

    def set_penpot_attr(self, key: str | PenpotShapeAttr, value: str) -> None:
        key = key.value if isinstance(key, PenpotShapeAttr) else key
        self.attrib[self.get_namespaced_key("penpot", key)] = value

    @property
    def name(self) -> str:
        return self.get_penpot_attr(PenpotShapeAttr.NAME)

    @name.setter
    def name(self, value: str) -> None:
        self.set_penpot_attr(PenpotShapeAttr.NAME, value)

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
    def is_visible(self) -> bool:
        return self.get_containing_g_element().attrib.get("visibility") != "hidden"

    def check_for_visible_content(self) -> bool:
        if self.type == PenpotShapeType.GROUP:
            return any(child.check_for_visible_content() for child in self.child_shapes)

        inner_groups = self.get_inner_g_elements()

        if not inner_groups:
            return False

        assert len(inner_groups), (
            f"Found no inner <g>-elements (i.e. content elements) for shape with id {self.shape_id} while expecting at least one such element. "
            f"Tree: {etree.tostring(self.get_containing_g_element(), pretty_print=True)}"
        )

        return any(_el_has_visible_content(group) for group in inner_groups)

    def get_top_level_frame(self) -> Self:
        parent_frames = self.get_containing_frame_elements()

        if parent_frames:
            top_level_frame = parent_frames[-1]
        else:
            parents = self.get_all_parent_shapes()
            top_level_frame = parents[-1] if parents else self

        return top_level_frame

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

    def get_containing_frame_element(self) -> Self | None:
        parent_shape = self.get_parent_shape()
        if parent_shape is None:
            return None
        if parent_shape.type == PenpotShapeType.FRAME:
            return parent_shape
        return parent_shape.get_containing_frame_element()

    def get_containing_frame_elements(self) -> list[Self]:
        parent_frame = self.get_containing_frame_element()
        if parent_frame is None:
            return []
        return [parent_frame, *parent_frame.get_containing_frame_elements()]

    def get_containing_g_element(self) -> BetterElement:
        """Get the parent <g> element to which this shape corresponds; child shapes will be children of it.

        See docstring of the class for more info on the relation between <g> and <penpot:shape> tags.
        """
        return self.getparent()

    def get_inner_g_elements(self) -> list[BetterElement]:
        return self.get_containing_g_element().xpath(
            "default:g[not(starts-with(@id, 'shape-'))]",
            empty_namespace_name="svg",
        )

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

    def remove_clip_paths(self) -> bool:
        groups = self.get_inner_g_elements()
        return any(group.attrib.pop("clip-path", None) is not None for group in groups)

    def pprint_hierarchy(self, horizontal: bool = True) -> None:
        print_tree(
            self,
            childattr="child_shapes",
            nameattr="name",
            horizontal=horizontal,
        )

    def set_visibility(self, visibility: bool) -> None:
        g_elem = self.get_containing_g_element()

        if visibility:
            g_elem.attrib.pop("visibility", None)
        else:
            g_elem.attrib["visibility"] = "hidden"

    def remove(self) -> None:
        """Removes the shape from the SVG tree."""
        container_g = self.get_containing_g_element()
        container_g.getparent().remove(container_g)


def find_all_penpot_shapes(
    root: Element | PenpotShapeElement,
    style_supplier: BaseStyleSupplier | None = None,
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
            shape_el = PenpotShapeElement(el, style_supplier=style_supplier)
            depth_to_shape_el[shape_el.depth_in_shapes].append(shape_el)
            shape_el_to_depth[shape_el] = shape_el.depth_in_shapes
            penpot_shape_elements.append(shape_el)

    return penpot_shape_elements, depth_to_shape_el, shape_el_to_depth


class PenpotComponentSVG(SVG):
    """Representing a Penpot component, usually loaded from elements in a file named `component.svg`."""


class PenpotPageSVG(SVG):
    def __init__(
        self,
        dom: etree.ElementTree,
        style_supplier: BaseStyleSupplier | None = None,
    ):
        super().__init__(dom)
        (
            self._shape_elements,
            self._depth_to_shape_el,
            self._shape_el_to_depth,
        ) = find_all_penpot_shapes(self.dom, style_supplier=style_supplier)

        self._style_supplier = style_supplier

    def _reset_state(self) -> None:
        (
            self._shape_elements,
            self._depth_to_shape_el,
            self._shape_el_to_depth,
        ) = find_all_penpot_shapes(self.dom, style_supplier=self._style_supplier)

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
        should_be_unique: Literal[False] = False,
    ) -> list[PenpotShapeElement]:
        ...

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

    def get_shape_by_name(
        self,
        name: str,
        require_unique: bool = True,
    ) -> PenpotShapeElement:
        result = self._get_shapes_by_attr("name", name, should_be_unique=require_unique)  # type: ignore
        if not require_unique and isinstance(result, list):
            return result[0]
        else:
            return result

    def get_shape_by_id(self, shape_id: str) -> PenpotShapeElement:
        return self._get_shapes_by_attr("shape_id", shape_id, should_be_unique=True)

    @property
    def penpot_shape_elements(self) -> list[PenpotShapeElement]:
        return self._shape_elements

    @property
    def max_shape_depth(self) -> int:
        if self._depth_to_shape_el:
            return max(self._depth_to_shape_el.keys())
        else:
            return 0

    def get_shape_elements_at_depth(self, depth: int) -> list[PenpotShapeElement]:
        return self._depth_to_shape_el.get(depth, [])

    def pprint_hierarchy(self, horizontal: bool = True) -> None:
        for shape in self.get_shape_elements_at_depth(0):
            shape.pprint_hierarchy(horizontal=horizontal)

    def _remove_shape_from_tree(self, shape_id: str) -> None:
        shape = self.get_shape_by_id(shape_id)

        container_g = shape.get_containing_g_element()
        container_g.getparent().remove(container_g)

    def remove_shape(self, shape_id: str) -> None:
        """Removes a shape (and its sub-shapes) given by its ID from the SVG tree.

        The state of the PenpotPageSVG object is reset after the shape is removed, i.e.
        the shape elements are re-extracted from the tree.
        """
        self._remove_shape_from_tree(shape_id)
        self._reset_state()

        try:
            self.get_shape_by_id(shape_id)
        except KeyError:
            return

        raise AssertionError(f"Shape with id {shape_id} was not removed correctly.")

    def remove_elements_with_no_visible_content(self) -> None:
        # Sort the shapes by descending depth in the shape hierarchy, so that we start with the deepest shapes.
        # Otherwise we may delete a parent shape before its children, thus decouple the children from the tree
        # which will lead to weird behavior (i.e. lxml will assign arbitrary namespace names) and errors.
        # We could, of course, also detect these relationships and only remove invisible parents,
        # but just sorting the shapes is easier and should be fine for now.
        shapes = sorted(
            self.penpot_shape_elements,
            key=lambda shape: shape.depth_in_shapes,
            reverse=True,
        )

        removed_ids = []

        for shape in shapes:
            if not shape.check_for_visible_content():
                self._remove_shape_from_tree(shape.shape_id)
                removed_ids.append(shape.shape_id)

        self._reset_state()

        for shape_id in removed_ids:
            try:
                self.get_shape_by_id(shape_id)
            except KeyError:
                continue

            raise AssertionError(f"Shape with id {shape_id} was not removed correctly.")

    def retrieve_and_set_view_boxes_for_shape_elements(
        self,
        web_driver: WebDriver | RegisteredWebDriver = RegisteredWebDriver.CHROME,
        selected_shape_elements: Iterable[PenpotShapeElement] | None = None,
        respect_clip_masks: bool = True,
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
                # Frames will typically have a clip-path that defines the clip mask.
                if (
                    respect_clip_masks
                    and shape_el.type is PenpotShapeType.FRAME
                    and (clip_rect := shape_el.get_clip_rect()) is not None
                ):
                    shape_bbox = clip_rect
                else:
                    view_box_dom_rect = driver.execute_script(
                        f"return document.getElementById('{shape_el.shape_id}').getBBox();",
                    )
                    shape_bbox = BoundingBox.from_dom_rect(view_box_dom_rect)
                shape_el.set_default_view_box(bbox=shape_bbox)


def ensure_unique_ids_in_svg_code(svg_code: str) -> str:
    """Transforms SVG code generated by an LLM in order to ensure that identifiers appearing in the code are unique.

    :param svg_code: the generated SVG code
    :return: the transformed SVG code
    """
    ids = re.findall(r'id="(.*?)"', svg_code)
    for identifier in ids:
        new_id = f"{identifier}_{shortuuid.uuid()}"
        svg_code = svg_code.replace(f'id="{identifier}"', f'id="{new_id}"')
        svg_code = svg_code.replace(f"url(#{identifier})", f"url(#{new_id})")
        svg_code = svg_code.replace(f"url('#{identifier}')", f"url('#{new_id})'")
        svg_code = svg_code.replace(f'href="#{identifier}"', f'href="#{new_id}"')
    return svg_code


def randomize_penpot_shape_names(element: PenpotShapeElement | PenpotPageSVG) -> None:
    """Randomize the names of all shapes in the given PenpotShapeElement or PenpotPageSVG."""
    if isinstance(element, PenpotShapeElement):
        shapes = [element]
    elif isinstance(element, PenpotPageSVG):
        shapes = element.get_shape_elements_at_depth(0)
    else:
        raise TypeError(f"Unsupported element type: {type(element)}")

    for shape in shapes:
        shape.name = randomname.get_name()

        for child in shape.get_direct_children_shapes():
            randomize_penpot_shape_names(child)
