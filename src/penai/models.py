from copy import deepcopy
from dataclasses import dataclass, field
from typing import Self

from lxml import etree

from penai.svg import SVG


@dataclass
class PenpotShape:
    name: str
    type: str
    node: etree._Element
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
    pass


@dataclass
class Dimensions:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError("Width and height must be non-negative")

    @classmethod
    def from_bounding_box(cls, left: int, top: int, right: int, bottom: int) -> Self:
        return cls(
            width=right - left,
            height=bottom - top,
        )


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

    def get_by_name(self, name: str) -> PenpotComponent:
        # This can definitely be implemented more efficiently but since the number
        # of components per file is typically very small, this shouldn't become
        # a bottleneck for now.
        for component in self.values():
            if component.name == name:
                return component
        raise KeyError(f"No component with name '{name}' not found")


@dataclass
class PenpotFile:
    id: str
    name: str
    pages: dict[str, PenpotPage] = field(default_factory=dict)
    components: PenpotComponentDict = field(default_factory=PenpotComponentDict)
    # TODO: Implement when needed
    # colors: list[PenpotColor]
    # mediaItems: list[PenpotMediaItem]
    # typography: list[PenpotTypography]


@dataclass
class PenpotProject:
    files: dict[str, PenpotFile] = field(default_factory=dict)

    def __str__(self):
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
