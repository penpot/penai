import logging
from dataclasses import dataclass
from typing import Self

from penai.config import get_config
from penai.registries.shapes import ShapeReference, ShapeReferences
from penai.utils.datastruct import StaticCollection, T
from penai.variations.svg_variations import SVGVariations

log = logging.getLogger(__name__)
cfg = get_config()


class ShapeVariationTemplate:
    """Represents a template for transferring variations from one shape to another.
    It consists of (a reference to) a shape with a set of variations thereof.
    """

    def __init__(
        self, shape_ref: ShapeReference, variations: dict[str, ShapeReference] | None = None
    ) -> None:
        self.shape_ref = shape_ref
        if variations is None:
            variations = {}
        self.variations = variations

    def with_variation(self, name: str, shape_ref: ShapeReference) -> Self:
        self.variations[name] = shape_ref
        return self

    def to_svg_variations(self) -> SVGVariations:
        shape = self.shape_ref.load_shape()
        variations_dict = {}
        for name, ref in self.variations.items():
            shape_variation = ref.load_shape()
            variations_dict[name] = shape_variation.to_svg().to_string()
        return SVGVariations(shape.to_svg(), variations_dict=variations_dict)


class ShapeVariationTemplates:
    """Collection fo shape variation templates."""

    gv_button_regular = (
        ShapeVariationTemplate(ShapeReferences.gv_button_regular_1)
        .with_variation("decolorized", ShapeReferences.gv_button_regular_2)
        .with_variation("decolorized, dotted", ShapeReferences.gv_button_regular_3)
    )
    gv_button_hover = (
        ShapeVariationTemplate(ShapeReferences.gv_button_hover_1)
        .with_variation("decolorized", ShapeReferences.gv_button_hover_2)
        .with_variation("decolorized, dotted", ShapeReferences.gv_button_hover_3)
    )
    gv_input_field = (
        ShapeVariationTemplate(ShapeReferences.gv_dark_input_rest)
        .with_variation("focus", ShapeReferences.gv_dark_input_focus)
        .with_variation("disabled", ShapeReferences.gv_dark_input_disabled)
        .with_variation("error", ShapeReferences.gv_dark_input_error)
    )


@dataclass
class VariationTransferTask:
    """Represents a task for transferring variations from a shape variation template to a set of shapes."""

    shape_variation_template: ShapeVariationTemplate
    """
    shape variation template (original shape with example variations)
    """
    shapes: list[ShapeReference]
    """
    shapes to which the template shall be applied
    """


class VariationTransferTasks(StaticCollection):
    """Collection of variation transfer tasks."""

    gv_button_regular = VariationTransferTask(
        ShapeVariationTemplates.gv_button_regular,
        [
            ShapeReferences.gv_button_plus_icon,
            ShapeReferences.gv_button_icon,
            ShapeReferences.gv_button_danger,
        ],
    )
    gv_button_hover = VariationTransferTask(
        ShapeVariationTemplates.gv_button_hover,
        [
            ShapeReferences.gv_button_plus_icon,
            ShapeReferences.gv_button_icon,
            ShapeReferences.gv_button_danger,
        ],
    )
    gv_input_field = VariationTransferTask(
        ShapeVariationTemplates.gv_input_field,
        [
            ShapeReferences.gv_textarea_rest,
        ],
    )

    @classmethod
    def _item_type(cls) -> type[T]:
        return VariationTransferTask

    @classmethod
    def items(cls) -> list[VariationTransferTask]:
        return cls._items()
