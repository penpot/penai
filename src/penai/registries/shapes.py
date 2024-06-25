import logging
from functools import cache

from penai.config import get_config
from penai.registries.projects import SavedPenpotProject
from penai.svg import PenpotPageSVG, PenpotShapeElement

log = logging.getLogger(__name__)
cfg = get_config()


class ShapeReference:
    def __init__(self, shape_name: str, project: SavedPenpotProject, page_name: str) -> None:
        self.shape_name = shape_name
        self.project = project
        self.page_name = page_name

    @staticmethod
    @cache
    def _load_page_svg(project: SavedPenpotProject, page_name: str) -> PenpotPageSVG:
        return project.load_page_svg_with_viewboxes(page_name)

    def load_shape(self) -> PenpotShapeElement:
        page_svg = self._load_page_svg(self.project, self.page_name)
        return page_svg.get_shape_by_name(self.shape_name, require_unique=False)


class ShapeReferenceGenerativeVariations(ShapeReference):
    """Reference to a shape in the 'Generative Variations' project."""

    def __init__(self, shape_name: str):
        super().__init__(
            shape_name=shape_name,
            project=SavedPenpotProject.GENERATIVE_VARIATIONS,
            page_name="examples",
        )


class ShapeReferences:
    # from project "Generative Variations" (gv)
    gv_button_regular_1 = ShapeReferenceGenerativeVariations("Buttons / Regular / btn-primary-lg")
    gv_button_regular_2 = ShapeReferenceGenerativeVariations("Buttons / Regular / btn-default-lg")
    gv_button_regular_3 = ShapeReferenceGenerativeVariations("Buttons / Regular / btn-dashed-lg")
    gv_button_hover_1 = ShapeReferenceGenerativeVariations(
        "Buttons / Regular / btn-primary-hover-lg"
    )
    gv_button_hover_2 = ShapeReferenceGenerativeVariations(
        "Buttons / Regular / btn-default-hover-lg"
    )
    gv_button_hover_3 = ShapeReferenceGenerativeVariations(
        "Buttons / Regular / btn-dashed-hover-lg"
    )
    gv_button_plus_icon = ShapeReferenceGenerativeVariations(
        "Buttons / + Icon / btn-primary-icon-lg"
    )
    gv_button_icon = ShapeReferenceGenerativeVariations("Buttons / Icon / btn-primary-nolabel-lg")
    gv_button_danger = ShapeReferenceGenerativeVariations("Buttons / Danger / btn-danger-lg")
    gv_dark_input_rest = ShapeReferenceGenerativeVariations("Dark / Input / Rest")
    gv_dark_input_focus = ShapeReferenceGenerativeVariations("Dark / Input / Focus")
    gv_dark_input_disabled = ShapeReferenceGenerativeVariations("Dark / Input / Disabled")
    gv_dark_input_error = ShapeReferenceGenerativeVariations("Dark / Input / Error")
    gv_textarea_rest = ShapeReferenceGenerativeVariations("Dark / Text area / Rest")
