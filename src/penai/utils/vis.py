from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import reduce

import matplotlib.pyplot as plt
from matplotlib import patches
from PIL import Image

from penai.registries.web_drivers import RegisteredWebDriver, get_web_driver
from penai.render import WebDriverSVGRenderer
from penai.svg import BoundingBox, PenpotShapeElement

ShapeLabelFactory = Callable[[int, PenpotShapeElement], str]


def _default_shape_label_factory(idx: int, shape: PenpotShapeElement):
    return "#" + str(idx + 1)


@dataclass
class ShapeVisualization:
    shape: PenpotShapeElement
    label: str
    bbox: BoundingBox
    image: Image.Image


class ShapeVisualizer:
    def __init__(
        self,
        web_driver_type: RegisteredWebDriver = RegisteredWebDriver.CHROME,
        only_primitives: bool = True,
        dpi: float = 100,
        scale: float = 4,
        ax_margin: float = 200,
        label_factory: ShapeLabelFactory | None = None,
        annotation_font_size: int = 16,
        annotation_alpha: float = 0.8,
        annotation_pad: float = 0.3,
        annotation_bottom_margin: float = 20,
        bbox_line_width: float = 2,
        bbox_edge_color: str = "green",
        bbox_face_color: str = "gray",
        bbox_alpha: float = 0.2,
    ):
        self.web_driver_type = web_driver_type
        self.only_primitives = only_primitives
        self.dpi = dpi
        self.scale = scale
        self.ax_margin = ax_margin
        self.label_factory = label_factory or _default_shape_label_factory

        self.annotation_font_size = annotation_font_size
        self.annotation_alpha = annotation_alpha
        self.annotation_pad = annotation_pad
        self.annotation_bottom_margin = annotation_bottom_margin

        self.bbox_line_width = bbox_line_width
        self.bbox_edge_color = bbox_edge_color
        self.bbox_face_color = bbox_face_color
        self.bbox_alpha = bbox_alpha

    def _get_relevant_children(self, shape: PenpotShapeElement):
        return [
            child
            for child in shape.get_all_children_shapes()
            if not self.only_primitives or child.is_primitive_type
        ]

    def _prepare_shape(self, shape: PenpotShapeElement):
        with get_web_driver(self.web_driver_type) as web_driver:
            renderer = WebDriverSVGRenderer(web_driver, infer_bounding_boxes=True)

            view_box = shape.get_default_view_box()
            result = renderer.render_svg(shape.to_svg(view_box))

            shape_bboxes = {
                shape.shape_id: result.artefacts.bounding_boxes[shape.shape_id]
                for shape in self._get_relevant_children(shape)
            }

            shape_image = result.image

        return shape_image, shape_bboxes

    def _highlight_shape(self, image, shape, label, bbox, clip_bbox=None):
        ax_bbox = bbox.with_margin(self.ax_margin)

        # if clip_bbox is not None:
        #     ax_bbox = ax_bbox.intersection(clip_bbox)

        fig, ax = plt.subplots(
            dpi=self.dpi,
            figsize=(
                self.scale * ax_bbox.aspect_ratio,
                self.scale / ax_bbox.aspect_ratio,
            ),
        )

        ax.imshow(image)
        ax.axis("off")

        ax.text(
            bbox.x + bbox.width / 2,
            bbox.y - self.annotation_bottom_margin,
            f"{label} - {shape.type.value.literal}",
            horizontalalignment="center",
            verticalalignment="bottom",
            fontsize=self.annotation_font_size,
            bbox=dict(
                boxstyle="round",
                facecolor="#feffc2",
                alpha=self.annotation_alpha,
                edgecolor="none",
                pad=self.annotation_pad,
            ),
        )

        bounds = (
            (bbox.x, bbox.y),
            bbox.width,
            bbox.height,
        )

        bbox_face = patches.Rectangle(
            *bounds,
            alpha=self.bbox_alpha,
            facecolor=self.bbox_face_color,
            snap=True,
        )
        ax.add_patch(bbox_face)

        bbox_edge = patches.Rectangle(
            *bounds,
            linewidth=self.bbox_line_width,
            edgecolor=self.bbox_edge_color,
            facecolor="none",
            snap=True,
        )
        ax.add_patch(bbox_edge)

        ax.set_xlim(ax_bbox.x, ax_bbox.x + ax_bbox.width)
        ax.set_ylim(ax_bbox.y + ax_bbox.height, ax_bbox.y)

        fig.tight_layout(pad=0)

        fig.canvas.draw()

        image = Image.frombytes(
            "RGB",
            fig.canvas.get_width_height(),
            fig.canvas.tostring_rgb(),
        )

        plt.close(fig)

        return image, label

    def visualize_bboxes_in_shape(
        self,
        shape: PenpotShapeElement,
    ) -> Iterable[ShapeVisualization]:
        shape_image, shape_bboxes = self._prepare_shape(shape)

        children = self._get_relevant_children(shape)

        largest_bbox = reduce(lambda a, b: a.union(b), shape_bboxes.values())

        for i, child in enumerate(children):
            bbox = shape_bboxes[child.shape_id].with_margin(5)
            label = self.label_factory(i, shape)
            image, label = self._highlight_shape(shape_image, child, label, bbox, largest_bbox)
            yield ShapeVisualization(child, label, bbox, image)

        return
