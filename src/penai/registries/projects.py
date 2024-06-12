import logging
import os
from enum import Enum

from sensai.util.cache import pickle_cached

from penai.config import get_config, pull_from_remote
from penai.models import PenpotPage, PenpotProject
from penai.registries.web_drivers import RegisteredWebDriver
from penai.svg import PenpotPageSVG

log = logging.getLogger(__name__)


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

        @pickle_cached(os.path.join("temp", "cache"), load=cached)
        def load_page_svg_text(project: SavedPenpotProject, page_name: str) -> str:
            page = project._load_page_with_viewboxes(page_name)
            return page.svg.to_string()

        return PenpotPageSVG.from_string(load_page_svg_text(self, page_name))
