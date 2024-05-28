import logging
import os
from enum import Enum

from penai.config import get_config, pull_from_remote
from penai.models import PenpotProject

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

    def get_project_name(self) -> str:
        return self.value

    def get_path(self, pull: bool = False) -> str:
        result = os.path.join(get_config().penpot_designs_basedir(), self.get_project_name())
        if pull:
            log.info(f"Pulling data for project {self.get_project_name()} to {result}")
            pull_from_remote(result)
        return result

    def load(self):
        return load_from_directory(self.get_path(pull=True))

    @classmethod
    def pull_all(cls) -> None:
        for design in cls:
            design.get_path(pull=True)

    def load(self, pull: bool = False) -> PenpotProject:
        project_path = self.get_path(pull=pull)
        return PenpotProject.from_directory(project_path)
