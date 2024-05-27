from pathlib import Path

from penai import utils
from penai.models import (
    Dimensions,
    PenpotComponent,
    PenpotContainer,
    PenpotFile,
    PenpotPage,
    PenpotProject,
)
from penai.schemas import PenpotFileDetailsSchema, PenpotProjectManifestSchema
from penai.svg import SVG
from penai.types import PathLike


def load_from_directory(directory: PathLike) -> PenpotProject:
    """Load a Penpot project from the given directory."""
    directory = Path(directory)

    manifest = PenpotProjectManifestSchema.model_validate(
        utils.read_json(directory / "manifest.json"),
    )

    penpot_project = PenpotProject()

    for file_id, file in manifest.files.root.items():
        file_directory = directory / str(file_id)

        assert file_directory.exists() and file_directory.is_dir()

        penpot_project.files[file_id] = load_file(
            file,
            directory / str(file_id),
        )

    return penpot_project


def load_file(file: PenpotFileDetailsSchema, file_root: Path) -> PenpotFile:
    """Load a Penpot file."""
    penpot_file = PenpotFile()

    for page_id in file.pages:
        page_info = file.pagesIndex[page_id]
        penpot_file.pages[page_id] = load_page(page_id, page_info.name, file_root)

    if file.hasComponents:
        for component in load_components(file_root):
            penpot_file.components[component.id] = component
    return penpot_file


def load_components(file_root: Path) -> list[PenpotComponent]:
    """Load all Penpot components that are children of the given file root."""
    components_path = (file_root / "components").with_suffix(".svg")
    components_svg = SVG.from_file(components_path)

    # Yes, lxml's find/xpath is not compatible with its own datatypes.
    nsmap = components_svg.dom.getroot().nsmap

    xpath_nsmap = dict(nsmap)
    xpath_nsmap[""] = xpath_nsmap.pop(None)

    component_symbols = components_svg.dom.findall(
        "./defs/symbol",
        namespaces=xpath_nsmap,
    )

    components = []

    for symbol in component_symbols:
        view_box = symbol.get("viewBox")
        dimensions = Dimensions.from_bounding_box(*map(float, view_box.split()))
        svg = SVG.from_root_element(
            symbol,
            namespace_map=nsmap,
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


def load_page(page_id: str, name: str, file_root: Path) -> PenpotPage:
    """Load a Penpot page."""
    page_path = (file_root / str(page_id)).with_suffix(".svg")
    container = PenpotContainer(svg=SVG.from_file(page_path))
    return PenpotPage(
        id=page_id,
        name=name,
        container=container,
    )
