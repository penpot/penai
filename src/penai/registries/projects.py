import logging
import os
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum, StrEnum

from sensai.util.cache import pickle_cached

from penai.client import PenpotClient
from penai.config import get_config, pull_from_remote
from penai.models import PenpotPage, PenpotProject, PenpotShape
from penai.registries.web_drivers import RegisteredWebDriver
from penai.svg import PenpotPageSVG

log = logging.getLogger(__name__)
cfg = get_config()


class ShapeType(StrEnum):
    BUTTON = "button"
    ICON = "icon"
    TEXT = "text"


@dataclass(kw_only=True)
class ManualShapeMetadata:
    description: str | None = None
    subtext: str | None = None
    shape_type: ShapeType = ShapeType.ICON


_MD = ManualShapeMetadata


class SavedPenpotProject(Enum):
    AVATAAARS = "Avataaars by Pablo Stanley"
    BLACK_AND_WHITE_MOBILE_TEMPLATES = "Black & White Mobile Templates"
    COMMUNITY_CARDS_GRID_THEME = "Community - Cards grid theme"
    INTERACTIVE_MUSIC_APP = "Interactive music app"
    MASTODON_SOCIAL_APP = "Mastodon Social App"
    MATERIAL_DESIGN_3 = "Material Design 3"
    NEXTCLOUD_DESIGN_SYSTEM = "Nextcloud design system"
    PLANTS_APP = "Plants app"
    UX_NOTES = "UX Notes"
    WIREFRAMING_KIT = "Wireframing kit"
    GENERATIVE_VARIATIONS = "Generative variations"

    def get_project_name(self) -> str:
        return self.value

    def get_project_id(self) -> str:
        """:return: the project's UUID on the default server (design.penpot.app)"""
        match self:
            case SavedPenpotProject.INTERACTIVE_MUSIC_APP:
                return "15586d98-a20a-8145-8004-69dd979da070"
            case _:
                raise NotImplementedError

    def get_path(self, pull: bool = False) -> str:
        """:param pull: whether to (force) pull the project from the remote storage."""
        result = os.path.join(
            get_config().penpot_designs_basedir(),
            self.get_project_name(),
        )
        if pull:
            log.info(f"Pulling data for project {self.get_project_name()} to {result}")
            pull_from_remote(result, force=True)
        return result

    @classmethod
    def pull_all(cls) -> None:
        for design in cls:
            design.get_path(pull=True)

    def load(self, pull: bool = False) -> PenpotProject:
        project_path = self.get_path(pull=pull)
        return PenpotProject.from_directory(project_path)

    def _load_page_with_viewboxes(self, page_name: str) -> PenpotPage:
        penpot_project = self.load(pull=True)
        main_file = penpot_project.get_main_file()
        page = main_file.get_page_by_name(page_name)
        page.svg.retrieve_and_set_view_boxes_for_shape_elements(RegisteredWebDriver.CHROME)
        return page

    def load_page_svg_with_viewboxes(self, page_name: str, cached: bool = True) -> PenpotPageSVG:
        """Loads the given project page's SVG.

        :param page_name:
        :param cached: whether to use a previously cached result; if False, the cache will
            not be read, but it will be updated
        :return: the page's SVG
        """

        @pickle_cached(cfg.cache_dir, load=cached)
        def load_page_svg_text(project: SavedPenpotProject, page_name: str) -> str:
            page = project._load_page_with_viewboxes(page_name)
            return page.svg.to_string()

        return PenpotPageSVG.from_string(load_page_svg_text(self, page_name))

    def load_typographies_css(self, cached: bool = True) -> str:
        """Loads the typography CSS for the project's main file.

        :param cached: whether to use a previously cached result; if False, the cache will
            not be read, but it will be updated
        :return: the CSS content
        """

        @pickle_cached(cfg.cache_dir, load=cached)
        def load_main_file_typographies_css(saved_project: SavedPenpotProject) -> str:
            client = PenpotClient.create_default()
            project = saved_project.load(pull=True)
            typographies = client.get_file_typographies(
                saved_project.get_project_id(),
                project.main_file_id,
            )
            return typographies.to_css()

        return load_main_file_typographies_css(self)

    def _get_selected_pages_to_shapes_dict(self) -> dict[str, dict[str, ManualShapeMetadata]]:
        """Returns the selected shapes for experiments for the project."""
        match self:
            case SavedPenpotProject.INTERACTIVE_MUSIC_APP:
                return {
                    "Interactive music app": {
                        "ic_equalizer_48px-1": _MD(description="Equalizer icon"),
                        "Group-5": _MD(description="Home icon", subtext="Home"),
                        "Group-6": _MD(description="Compass icon", subtext="Explore"),
                        "Group-7": _MD(description="Music library icon", subtext="Music library"),
                        "btn-primary-1": _MD(
                            description="Play button", shape_type=ShapeType.BUTTON
                        ),
                    },
                }
            case _:
                log.debug(f"No selected shapes for experiments for project {self.value}")
                return {}

    def get_selected_shapes_for_experiments(
        self,
    ) -> Iterable[tuple[PenpotShape, ManualShapeMetadata]]:
        """Returns all shapes and their metadata that are selected for experiments in the selected project."""
        for page_name, shape_name_to_metadata in self._get_selected_pages_to_shapes_dict().items():
            page = self.load_page_svg_with_viewboxes(page_name)
            for shape_name, metadata in shape_name_to_metadata.items():
                yield page.get_shape_by_name(shape_name), metadata

    @classmethod
    def get_all_selected_shapes_for_experiments(
        cls,
    ) -> Iterable[tuple[PenpotShape, ManualShapeMetadata]]:
        """Iterates over the whole registry and retrieves all shapes and their metadata that are selected for experiments."""
        for project in cls:
            yield from project.get_selected_shapes_for_experiments()
