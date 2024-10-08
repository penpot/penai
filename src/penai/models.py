import json
from copy import deepcopy
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Generic, Self, TypeVar
from uuid import UUID

from lxml import etree
from lxml.etree import Element
from pydantic import BaseModel, Field, parse_obj_as

from penai.errors import FontFetchError
from penai.schemas import (
    PenpotFileDetailsSchema,
    PenpotProjectManifestSchema,
    PenpotTypographiesSchema,
    PenpotTypographySchema,
)
from penai.svg import (
    SVG,
    BaseStyleSupplier,
    PenpotComponentSVG,
    PenpotPageSVG,
    PenpotShapeElement,
)
from penai.types import PathLike
from penai.utils.fonts import (
    get_css_for_penpot_font,
)
from penai.xml import BetterElement


@dataclass
class PenpotShape:
    name: str
    type: str
    node: etree.ElementBase
    children: list[Self] = field(default_factory=list)
    parent: Self | None = None


TSVG = TypeVar("TSVG", bound=SVG)


@dataclass
class PenpotComposition(Generic[TSVG]):
    svg: TSVG
    id: str
    name: str


@dataclass
class PenpotPage(PenpotComposition[PenpotPageSVG]):
    @classmethod
    def from_file(
        cls,
        path: PathLike,
        name: str,
        style_supplier: BaseStyleSupplier | None = None,
    ) -> Self:
        path = Path(path)
        svg = PenpotPageSVG.from_file(path, style_supplier=style_supplier)

        if style_supplier is not None:
            svg.inject_style(style_supplier.get_style())

        return cls(
            id=path.stem,
            name=name,
            svg=svg,
        )

    @classmethod
    def from_dir(
        cls,
        page_id: str | UUID,
        name: str,
        file_root: Path,
        style_supplier: BaseStyleSupplier | None = None,
    ) -> Self:
        page_path = (file_root / str(page_id)).with_suffix(".svg")
        return cls.from_file(page_path, name, style_supplier=style_supplier)


@dataclass
class Dimensions:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Width and height must be non-negative")

    # TODO: end the toxic non-relationship with BoundingBox
    @classmethod
    def from_bbox(cls, left: float, top: float, right: float, bottom: float) -> Self:
        return cls(
            width=right - left,
            height=bottom - top,
        )

    @classmethod
    def from_view_box_string(cls, view_box: str) -> Self:
        return cls.from_bbox(*map(float, view_box.split()))

    def to_view_box_string(self) -> str:
        return f"0 0 {self.width} {self.height}"


@dataclass
class PenpotComponent(PenpotComposition[PenpotComponentSVG]):
    dimensions: Dimensions

    def to_svg(self) -> SVG:
        # This function should eventually build an SVG from the component's
        # shape hierarchy. Since we currently represent a component by its raw
        # unprocessed SVG, we just copy the SVG DOM and place a component reference
        # to make it visible.
        svg = deepcopy(self.svg)
        svg_root = svg.dom.getroot()
        svg_root.append(
            etree.Element("use", {"href": f"#{self.id}"}),
        )
        svg_root.attrib["viewBox"] = self.dimensions.to_view_box_string()
        return svg


class PenpotComponentDict(dict[str, PenpotComponent]):
    """A dict mapping component ids to PenpotComponent objects.

    Provides some utility methods for retrieving components by name.
    """

    def get_component_names(self) -> list[str]:
        return [component.name for component in self.values()]

    def get_by_name(self, name: str) -> PenpotComponent:
        # This can definitely be implemented more efficiently but since the number
        # of components per file is typically very small, this shouldn't become
        # a bottleneck for now.
        for component in self.values():
            if component.name == name:
                return component
        raise KeyError(f"No component with name '{name}' not found")


class PenpotComponentsSVG(SVG):
    """Representing a collection of Penpot components, usually loaded from a file named `components.svg`."""

    @classmethod
    def from_penpot_file_dir(cls, file_dir: PathLike) -> Self:
        return cls.from_file(Path(file_dir) / "components.svg")

    def get_component_list(self) -> list[PenpotComponent]:
        component_symbols = self.dom.findall("./defs/symbol")

        components = []

        for symbol in component_symbols:
            view_box = symbol.get("viewBox")
            dimensions = Dimensions.from_view_box_string(view_box)
            svg = PenpotComponentSVG.from_root_element(
                symbol,
                svg_attribs=dict(
                    viewBox=view_box,
                ),
            )

            component = PenpotComponent(
                id=symbol.get("id"),
                name=symbol.find("./title").text,
                svg=svg,
                dimensions=dimensions,
            )

            components.append(component)

        return components

    # NOTE: if ever this is a bottleneck, we can avoid iterating twice
    def get_penpot_component_dict(self) -> PenpotComponentDict:
        return PenpotComponentDict(
            {component.id: component for component in self.get_component_list()},
        )


class PenpotColor(BaseModel):
    id: str | None = Field(default_factory=lambda: None)
    name: str
    color: str
    """
    The color in hex format, e.g. '#ff0000' for red.
    """
    opacity: float
    path: str


class PenpotColors:
    def __init__(self, colors_json_path: PathLike | None = None):
        """:param colors_json_path: the path to an existing `colors.json` file containing the colors or None of no colors are available."""
        self._colors_json_path = colors_json_path
        self._colors: list[PenpotColor] | None = None

    def get_colors(self) -> list[PenpotColor]:
        """:return: the list of colors, which may be empty if no colors are defined"""
        if self._colors is None:
            self._colors = []
            if self._colors_json_path is not None:
                with open(self._colors_json_path) as f:
                    colors_json = json.load(f)
                color_map = parse_obj_as(dict[str, PenpotColor], colors_json)
                for uuid, color in color_map.items():
                    color.id = uuid
                    self._colors.append(color)
        return self._colors


@dataclass
class PenpotTypography(BaseStyleSupplier):
    name: str
    font_family: str
    font_variant_id: str

    @classmethod
    def from_schema(cls, schema: PenpotTypographySchema) -> Self:
        return cls(
            name=schema.name,
            font_family=schema.fontFamily,
            font_variant_id=schema.fontVariantId,
        )

    def get_style(self) -> str | None:
        return get_css_for_penpot_font(self.font_family, self.font_variant_id)


class PenpotTypographyDict(dict[str, PenpotTypography], BaseStyleSupplier):
    def get_style(self, raise_errors: bool = True) -> str:
        css = []

        for typography in self.values():
            try:
                if (style := typography.get_style()) is not None:
                    css.append(style)
            except FontFetchError as e:
                if raise_errors:
                    raise e

                print(f"Error fetching font {typography.font_family}:", e)

        return "\n".join(css)


@dataclass
class PenpotFile(BaseStyleSupplier):
    id: str
    name: str
    pages: dict[str, PenpotPage]
    """Maps page ids to PenpotPage objects.
    A page is in one to one correspondence to an svg file, and the page id is
    the filename without the '.svg' extension."""
    components: PenpotComponentDict
    typographies: PenpotTypographyDict
    colors: PenpotColors

    # TODO: Implement when needed
    # mediaItems: list[PenpotMediaItem]

    @cached_property
    def page_names(self) -> list[str]:
        return list(self._name_to_page.keys())

    @cached_property
    def _name_to_page(self) -> dict[str, PenpotPage]:
        return {page.name: page for page in self.pages.values()}

    def get_page_by_name(self, name: str) -> PenpotPage:
        try:
            return self._name_to_page[name]
        except KeyError as e:
            raise KeyError(
                f"No page with '{name=}' found in file '{self.name}'. Valid page names are: {self.page_names}",
            ) from e

    @classmethod
    def from_schema_and_dir(
        cls,
        schema: PenpotFileDetailsSchema,
        file_dir: PathLike,
    ) -> Self:
        file_dir = Path(file_dir)
        if not file_dir.is_dir():
            raise ValueError(f"{file_dir=} is not a valid directory.")

        colors_json_path = Path(file_dir) / "colors.json"

        penpot_file = cls(
            id=file_dir.stem,
            name=schema.name,
            pages={},
            components=PenpotComponentDict(),
            typographies=PenpotTypographyDict(),
            colors=PenpotColors(colors_json_path if colors_json_path.exists() else None),
        )

        if schema.hasComponents:
            components_svg = PenpotComponentsSVG.from_penpot_file_dir(file_dir)
            penpot_file.components.update(components_svg.get_penpot_component_dict())

        if schema.hasTypographies:
            typographies_def = PenpotTypographiesSchema.from_typographies_file(
                file_dir / "typographies.json",
            )

            for typ_id, typ_schema in typographies_def.root.items():
                penpot_file.typographies[typ_id] = PenpotTypography.from_schema(
                    typ_schema,
                )

        for page_id in schema.pages:
            page_info = schema.pagesIndex[page_id]
            penpot_file.pages[page_id] = PenpotPage.from_dir(
                page_id,
                page_info.name,
                file_dir,
                style_supplier=penpot_file,
            )

        return penpot_file

    def get_style(self) -> str | None:
        if not self.typographies:
            return None

        return self.typographies.get_style(raise_errors=False)


@dataclass
class PenpotProject:
    name: str
    main_file_id: str
    files: dict[str, PenpotFile]

    def get_main_file(self) -> PenpotFile:
        return self.files[self.main_file_id]

    def __str__(self) -> str:
        lines = []
        lines += ["Files: (name, id)"]

        for file in self.files.values():
            lines += [f"- {file.name} ({file.id})"]
            lines += ["  Pages: (name, id)"]
            for page in file.pages.values():
                lines += [f"  - {page.name} ({page.id})"]

            lines += ["  Components: (name, id)"]
            for component in file.components.values():
                lines += [f"  - {component.name} ({component.id})"]

            lines += ["  Typographies: (name, id)"]
            for typography_id, typography in file.typographies.items():
                lines += [f"  - {typography.name} ({typography_id})"]

        return "\n".join(lines)

    @classmethod
    def from_directory(cls, project_dir: PathLike) -> Self:
        project_dir = Path(project_dir)

        manifest = PenpotProjectManifestSchema.from_project_dir(project_dir)
        files = {}

        for file_id, file_schema in manifest.files.items():
            files[file_id] = PenpotFile.from_schema_and_dir(
                file_schema,
                project_dir / str(file_id),
            )

        return cls(name=project_dir.stem, files=files, main_file_id=manifest.fileId)


class PenpotMinimalShapeXML:
    """(Minimal) XML representation of a Penpot shape (as contained in SVGs exported by Penpot)."""

    NSMAP = {
        "svg": "http://www.w3.org/2000/svg",
        "penpot": "https://penpot.app/xmlns",
    }

    def __init__(self, element: Element):
        """:param element: the root element, which must be a <g> element.
        The element is assumed not to contain any redundant, non-penpot elements.
        If your starting point is a PenpotShapeElement, use PenpotXML.from_shape instead.
        """
        self.root = element

    @classmethod
    def from_shape(cls, shape: PenpotShapeElement) -> Self:
        root = cls._remove_unwanted_elements(shape.get_containing_g_element())
        return cls(root)

    @classmethod
    def _is_penpot_element(self, element: etree.Element) -> bool:
        return element.tag.startswith("{" + self.NSMAP["penpot"] + "}")

    @classmethod
    def _has_penpot_child(cls, el: BetterElement) -> bool:
        return any(cls._is_penpot_element(child) for child in el.getchildren())

    @classmethod
    def _element_to_string(cls, element: etree.Element) -> str:
        return etree.tostring(element, encoding="unicode")

    @classmethod
    def _find_g_sibling(cls, el: BetterElement) -> BetterElement | None:
        sibling = el.getnext()
        while sibling is not None:
            if sibling.tag == cls._name("g", "svg"):
                return sibling
            sibling = sibling.getnext()
        return None

    DEFAULT_PENPOT_ATTRIBUTES = {
        "transform": "matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)",
        "transform-inverse": "matrix(1.000000, 0.000000, 0.000000, 1.000000, 0.000000, 0.000000)",
        "proportion": "1",
        "proportion-lock": "false",
        "rotation": "0",
        "constraints-h": "scale",
        "constraints-v": "scale",
    }

    # Note: there is some duplication with a similar mechanism in the SVG class
    @classmethod
    def _remove_unwanted_elements(cls, tree: BetterElement) -> BetterElement:
        root = deepcopy(tree)

        removed_elements = []
        retained_element_set = set()

        # traverse the elements of the tree, collecting the ones to remove
        for element in root.iter():
            # if the element is already marked as retained, we don't need to check it
            if element in retained_element_set:
                continue

            is_penpot_element = cls._is_penpot_element(element)

            if is_penpot_element:
                # For penpot:shapes, we need to retain the subsequent <g> sibling and all its descendants if
                #   - the <g> sibling has no subsequent penpot sibling AND
                #   - the <g> sibling has no penpot child.
                # Note that if the <g> sibling has a penpot child, we may need to clean its children recursively
                # and the logic below applies.
                if element.tag == cls._name("shape", "penpot"):
                    g_sibling = cls._find_g_sibling(element)
                    if g_sibling is not None:
                        subsequent_sibling = g_sibling.getnext()
                        has_subsequent_penpot_sibling = (
                            subsequent_sibling is not None
                            and cls._is_penpot_element(subsequent_sibling)
                        )
                        if not has_subsequent_penpot_sibling and not cls._has_penpot_child(
                            g_sibling,
                        ):
                            retained_element_set.update(g_sibling.iter())

            # decide whether to keep or remove the current element:
            # We keep penpot elements and <g> elements that have at least one penpot element as a child
            keep = is_penpot_element
            if not keep and element.tag == cls._name("g", "svg"):
                if cls._has_penpot_child(element):
                    keep = True
            if not keep:
                removed_elements.append(element)

        # apply the actual removal of the elements
        for element in removed_elements:
            element.getparent().remove(element)

        # remove default attributes
        for element in root.iter():
            for attr_name, value in cls.DEFAULT_PENPOT_ATTRIBUTES.items():
                attr_qual_name = cls._name(attr_name, "penpot")
                if attr_qual_name in element.attrib and element.attrib[attr_qual_name] == value:
                    del element.attrib[attr_qual_name]

        return root

    @classmethod
    def _name(cls, name: str, namespace: str) -> str:
        return "{" + cls.NSMAP[namespace] + "}" + name

    @classmethod
    def _nsmap_with_default(cls, default_ns: str) -> dict[str | None, str]:
        return {None if k == default_ns else k: v for k, v in cls.NSMAP.items()}

    def to_svg_root(self) -> etree.Element:
        nsmap = self._nsmap_with_default("svg")
        root = etree.Element(self._name("svg", namespace="svg"), nsmap=nsmap)
        root.append(self.root)
        return root

    def to_string(self) -> str:
        root = self.to_svg_root()
        return etree.tostring(root, encoding="unicode")
