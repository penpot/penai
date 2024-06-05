from copy import deepcopy
from dataclasses import dataclass, field
from functools import cache, cached_property
from pathlib import Path
from typing import Generic, Self, TypeVar
from uuid import UUID

from lxml import etree

from penai.schemas import PenpotFileDetailsSchema, PenpotProjectManifestSchema
from penai.svg import SVG, PenpotComponentSVG, PenpotPageSVG
from penai.types import PathLike


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
    def from_file(cls, path: PathLike, name: str) -> Self:
        path = Path(path)
        return cls(
            id=path.stem,
            name=name,
            svg=PenpotPageSVG.from_file(path),
        )

    @classmethod
    def from_dir(cls, page_id: str | UUID, name: str, file_root: Path) -> Self:
        page_path = (file_root / str(page_id)).with_suffix(".svg")
        return cls.from_file(page_path, name)


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

    @cache
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


@dataclass
class PenpotFile:
    id: str
    name: str
    pages: dict[str, PenpotPage]
    """Maps page ids to PenpotPage objects.
    A page is in one to one correspondence to an svg file, and the page id is
    the filename without the '.svg' extension."""
    components: PenpotComponentDict

    # TODO: Implement when needed
    # colors: list[PenpotColor]
    # mediaItems: list[PenpotMediaItem]
    # typography: list[PenpotTypography]

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
    def from_schema_and_dir(cls, schema: PenpotFileDetailsSchema, file_dir: PathLike) -> Self:
        file_dir = Path(file_dir)
        if not file_dir.is_dir():
            raise ValueError(f"{file_dir=} is not a valid directory.")

        pages = {}
        components = PenpotComponentDict()

        for page_id in schema.pages:
            page_info = schema.pagesIndex[page_id]
            pages[page_id] = PenpotPage.from_dir(page_id, page_info.name, file_dir)

        if schema.hasComponents:
            components_svg = PenpotComponentsSVG.from_penpot_file_dir(file_dir)
            components = components_svg.get_penpot_component_dict()
        return cls(id=file_dir.stem, name=schema.name, pages=pages, components=components)


@dataclass
class PenpotProject:
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

        return cls(files=files, main_file_id=manifest.fileId)
