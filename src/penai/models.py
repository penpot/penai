from copy import deepcopy
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Self
from uuid import UUID

from lxml import etree

from penai.schemas import PenpotFileDetailsSchema, PenpotProjectManifestSchema
from penai.svg import SVG
from penai.types import PathLike
from penai.utils import read_json


@dataclass
class PenpotShape:
    name: str
    type: str
    node: etree.ElementBase
    children: list[Self] = field(default_factory=list)
    parent: Self | None = None


@dataclass
class PenpotContainer:
    # TODO: A Penpot container is a composition of objects, i.e. shapes.
    # For the sake of simplicity, we will just represent it by its plain SVG object.
    # objects: list[PenpotShape] = field(default_factory=list)
    svg: SVG


@dataclass
class PenpotComposition:
    container: PenpotContainer
    id: str
    name: str


@dataclass
class PenpotPage(PenpotComposition):
    @classmethod
    def from_file(cls, path: PathLike, name: str) -> Self:
        path = Path(path)
        container = PenpotContainer(svg=SVG.from_file(path))
        page_id = path.stem
        return cls(
            id=page_id,
            name=name,
            container=container,
        )

    @classmethod
    def from_dir(cls, page_id: str | UUID, name: str, file_root: Path) -> Self:
        page_path = (file_root / str(page_id)).with_suffix(".svg")
        container = PenpotContainer(svg=SVG.from_file(page_path))
        return cls(
            id=str(page_id),
            name=name,
            container=container,
        )


@dataclass
class Dimensions:
    width: float
    height: float

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Width and height must be non-negative")

    @classmethod
    def from_bbox(cls, left: float, top: float, right: float, bottom: float) -> Self:
        return cls(
            width=right - left,
            height=bottom - top,
        )

    @classmethod
    def from_viewbox_string(cls, view_box: str) -> Self:
        return cls.from_bbox(*map(float, view_box.split()))


@dataclass
class PenpotComponent(PenpotComposition):
    dimensions: Dimensions

    def get_svg(self) -> SVG:
        # This function should eventually build an SVG from the component's
        # shape hierarchy. Since we currently represent a component by its raw
        # unprocessed SVG, we just copy the SVG DOM and place a component reference
        # to make it visible.
        svg = deepcopy(self.container.svg)
        svg.dom.getroot().append(
            etree.Element("use", {"href": f"#{self.id}"}),
        )
        return svg


class PenpotComponentDict(dict[str, PenpotComponent]):
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
        # Yes, lxml's find/xpath is not compatible with its own datatypes.
        nsmap = self.dom.getroot().nsmap

        xpath_nsmap = dict(nsmap)
        xpath_nsmap[""] = xpath_nsmap.pop(None)

        component_symbols = self.dom.findall(
            "./defs/symbol",
            namespaces=xpath_nsmap,
        )

        components = []

        for symbol in component_symbols:
            view_box = symbol.get("viewBox")
            dimensions = Dimensions.from_viewbox_string(view_box)
            svg = SVG.from_root_element(
                symbol,
                nsmap=nsmap,
                svg_attribs=dict(
                    viewBox=view_box,
                ),
            )

            component = PenpotComponent(
                id=symbol.get("id"),
                name=symbol.find("./title", namespaces=xpath_nsmap).text,
                container=PenpotContainer(svg=svg),
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
    pages: dict[str | UUID, PenpotPage]
    components: PenpotComponentDict

    # TODO: Implement when needed
    # colors: list[PenpotColor]
    # mediaItems: list[PenpotMediaItem]
    # typography: list[PenpotTypography]

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
    files: dict[str, PenpotFile] = field(default_factory=dict)

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

        manifest = PenpotProjectManifestSchema(**read_json(project_dir / "manifest.json"))
        files = {}

        for file_id, file_schema in manifest.files.root.items():
            files[file_id] = PenpotFile.from_schema_and_dir(
                file_schema,
                project_dir / str(file_id),
            )

        return cls(files=files)
