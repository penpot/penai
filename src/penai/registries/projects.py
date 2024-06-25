import logging
import os
from dataclasses import dataclass
from enum import Enum
from functools import cache
from typing import Literal

from sensai.util.cache import pickle_cached

from penai.client import PenpotClient
from penai.config import get_config, pull_from_remote
from penai.models import PenpotPage, PenpotProject
from penai.registries.web_drivers import RegisteredWebDriver
from penai.svg import PenpotPageSVG, PenpotShapeElement
from penai.variations.svg_variations import (
    RevisionInstructionSnippet,
    VariationInstructionSnippet,
)

log = logging.getLogger(__name__)
cfg = get_config()


class ShapeType(Enum):
    BUTTON = "button"
    ICON = "icon"
    TEXT = "text"
    BUTTON_SIMPLE = "button_simple"
    BUTTON_WITH_ICONS = "button_with_icons"

    def get_default_variation_logic(self) -> str:
        match self:
            case ShapeType.BUTTON:
                return VariationInstructionSnippet.SHAPES_COLORS_POSITIONS
            case ShapeType.ICON:
                return VariationInstructionSnippet.SHAPES_COLORS_POSITIONS
            case ShapeType.TEXT:
                return VariationInstructionSnippet.SHAPES_COLORS_POSITIONS
            case _:
                raise NotImplementedError

    def get_default_revision_logic(self) -> str:
        match self:
            case ShapeType.BUTTON:
                return RevisionInstructionSnippet.MODIFY_SHAPES
            case ShapeType.ICON:
                return RevisionInstructionSnippet.MODIFY_SHAPES
            case ShapeType.TEXT:
                return RevisionInstructionSnippet.MODIFY_SHAPES
            case _:
                raise NotImplementedError


@dataclass(kw_only=True)
class ShapeMetadata:
    """Usually set manually in the context of a registry."""

    description: str
    overlayed_text: str | None = None
    subtext: str | None = None
    shape_type: ShapeType = ShapeType.ICON
    variation_logic: str | Literal["default"] = "default"
    revision_prompt: str | Literal["default"] = "default"

    def __post_init__(self) -> None:
        if self.variation_logic == "default":
            self.variation_logic = self.shape_type.get_default_variation_logic()
        if self.revision_prompt == "default":
            self.revision_prompt = self.shape_type.get_default_revision_logic()

    def to_semantics_string(self) -> str:
        result = f"of type '{self.shape_type.value}' depicting a " + self.description
        if self.overlayed_text:
            result += f" with overlayed text: '{self.overlayed_text}'"
        if self.subtext:
            result += f" with subtext: '{self.subtext}'"
        return result + "."


_MD = ShapeMetadata


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

        @pickle_cached(cfg.temp_cache_dir, load=cached)
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

        @pickle_cached(cfg.temp_cache_dir, load=cached)
        def load_main_file_typographies_css(saved_project: SavedPenpotProject) -> str:
            client = PenpotClient.create_default()
            project = saved_project.load(pull=True)
            typographies = client.get_file_typographies(
                saved_project.get_project_id(),
                project.main_file_id,
            )
            return typographies.to_css()

        return load_main_file_typographies_css(self)


@dataclass
class ShapeForExperimentation:
    name: str
    metadata: ShapeMetadata
    project: SavedPenpotProject
    page_name: str

    @staticmethod
    @cache
    def _load_page_svg(project: SavedPenpotProject, page_name: str) -> PenpotPageSVG:
        return project.load_page_svg_with_viewboxes(page_name)

    def get_shape(self) -> PenpotShapeElement:
        page_svg = self._load_page_svg(self.project, self.page_name)
        return page_svg.get_shape_by_name(self.name)


class _ShapeCollection:
    def __init__(self) -> None:
        self.shapes: list[ShapeForExperimentation] = []

    def _add(self, shape: ShapeForExperimentation) -> ShapeForExperimentation:
        self.shapes.append(shape)
        return shape

    def add_music_app_shape(self, name: str, metadata: ShapeMetadata) -> ShapeForExperimentation:
        return self._add(
            ShapeForExperimentation(
                name=name,
                metadata=metadata,
                page_name="Interactive music app",
                project=SavedPenpotProject.INTERACTIVE_MUSIC_APP,
            )
        )


class ShapeCollection:
    _collection = _ShapeCollection()

    ma_equalizer = _collection.add_music_app_shape(
        name="ic_equalizer_48px-1", metadata=_MD(description="Equalizer icon")
    )
    ma_group_5 = _collection.add_music_app_shape(
        name="Group-5", metadata=_MD(description="Home icon", subtext="Home")
    )
    ma_group_6 = _collection.add_music_app_shape(
        name="Group-6", metadata=_MD(description="Compass icon", subtext="Explore")
    )
    ma_group_7 = _collection.add_music_app_shape(
        name="Group-7",
        metadata=_MD(
            description="Music library icon",
            subtext="Library",
            variation_logic="Adjust the form of background elements while keeping the icon.",
            revision_prompt="Keep the icon but adjust the background elements while staying close to the original design.",
        ),
    )
    ma_btn_primary_1 = _collection.add_music_app_shape(
        name="btn-primary-1",
        metadata=_MD(
            description="Play button",
            shape_type=ShapeType.BUTTON,
            overlayed_text="Play",
        ),
    )
    ma_btn_secondary = _collection.add_music_app_shape(
        name="btn-secondary",
        metadata=_MD(
            description="Shuffle button",
            shape_type=ShapeType.BUTTON,
            overlayed_text="Shuffle",
        ),
    )
    ma_icsupervisor_account_48px = _collection.add_music_app_shape(
        "ic_supervisor_account_48px", metadata=_MD(description="User icon")
    )

    @classmethod
    def get_shapes(cls) -> list[ShapeForExperimentation]:
        return cls._collection.shapes
