import abc
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from tempfile import NamedTemporaryFile

import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.axis import Axis
from matplotlib.lines import Line2D
from PIL import Image
from tqdm import tqdm

from penai.registries.web_drivers import RegisteredWebDriver, get_web_driver
from penai.render import WebDriverSVGRenderer
from penai.svg import BoundingBox, PenpotShapeElement

ShapeLabelFactory = Callable[[int, PenpotShapeElement], str]


def _default_shape_label_factory(idx: int, shape: PenpotShapeElement) -> str:
    return "#" + str(idx + 1)


@dataclass
class ShapeVisualization:
    shape: PenpotShapeElement
    label: str
    bbox: BoundingBox
    image: Image.Image


class BaseShapeVisualizer(abc.ABC):
    @abc.abstractmethod
    def visualize_shape(
        self,
        ax: Axis,
        shape: PenpotShapeElement,
        label: str,
        bboxes: dict[str, BoundingBox],
        clip_bbox: BoundingBox | None = None,
    ) -> None:
        pass


DEFAULT_BBOX_EDGE_COLOR = "green"
DEFAULT_BBOX_FACE_COLOR = "gray"

AX_LIMITS = (-10000, 10000)


def _add_label_to_axis(ax: Axis, label: str, bbox: BoundingBox, bottom_margin: float) -> None:
    ax.text(
        bbox.x + bbox.width / 2,
        bbox.y - bottom_margin,
        label,
        horizontalalignment="center",
        verticalalignment="bottom",
        fontsize=8,
        bbox=dict(
            boxstyle="round",
            facecolor="#feffc2",
            alpha=0.8,
            edgecolor="none",
            pad=0.3,
        ),
    )


def _add_bbox_outlines_to_axis(
    ax: Axis, bbox: BoundingBox, color: str = "red", linewidth: float = 1
) -> None:
    line_kwargs = dict(color=color, linewidth=linewidth, zorder=1)

    ax.add_line(Line2D(AX_LIMITS, (bbox.y, bbox.y), **line_kwargs))  # type: ignore
    ax.add_line(
        Line2D(
            AX_LIMITS,
            (bbox.y + bbox.height, bbox.y + bbox.height),
            **line_kwargs,  # type: ignore
        )
    )

    ax.add_line(Line2D((bbox.x, bbox.x), AX_LIMITS, **line_kwargs))  # type: ignore
    ax.add_line(
        Line2D(
            (bbox.x + bbox.width, bbox.x + bbox.width),
            AX_LIMITS,
            **line_kwargs,  # type: ignore
        )
    )


def _add_bbox_to_axis(
    ax: Axis,
    bbox: BoundingBox,
    bbox_alpha: float = 0.2,
    bbox_face_color: str = "gray",
    bbox_edge_color: str = "green",
    bbox_line_width: float = 1,
) -> None:
    bounds = (
        (bbox.x, bbox.y),
        bbox.width,
        bbox.height,
    )

    if bbox_alpha:
        bbox_face = patches.Rectangle(
            *bounds,
            alpha=bbox_alpha,
            facecolor=bbox_face_color,
            snap=True,
        )
        ax.add_patch(bbox_face)

    bbox_edge = patches.Rectangle(
        *bounds,
        linewidth=bbox_line_width,
        edgecolor=bbox_edge_color,
        facecolor="none",
        snap=True,
        zorder=2,
    )
    ax.add_patch(bbox_edge)


class ShapeHighlighter(BaseShapeVisualizer):
    def __init__(
        self,
        *,
        show_label: bool = True,
        show_bounds: bool = True,
        show_focus_outlines: bool = True,
        annotation_font_size: int = 8,
        annotation_alpha: float = 0.8,
        annotation_pad: float = 0.3,
        annotation_bottom_margin: float = 20,
        bbox_line_width: float = 1,
        bbox_edge_color: str = DEFAULT_BBOX_EDGE_COLOR,
        bbox_face_color: str = DEFAULT_BBOX_FACE_COLOR,
        bbox_alpha: float = 0.2,
    ):
        self.show_label = show_label
        self.show_bounds = show_bounds
        self.show_focus_outlines = show_focus_outlines
        self.annotation_font_size = annotation_font_size
        self.annotation_alpha = annotation_alpha
        self.annotation_pad = annotation_pad
        self.annotation_bottom_margin = annotation_bottom_margin
        self.bbox_line_width = bbox_line_width
        self.bbox_edge_color = bbox_edge_color
        self.bbox_face_color = bbox_face_color
        self.bbox_alpha = bbox_alpha

    def visualize_shape(
        self,
        ax: Axis,
        shape: PenpotShapeElement,
        label: str,
        bboxes: dict[str, BoundingBox],
        clip_bbox: BoundingBox | None = None,
    ) -> None:
        bbox = bboxes[shape.shape_id]

        if self.show_focus_outlines:
            _add_bbox_outlines_to_axis(ax, bbox)

        if self.show_label:
            _add_label_to_axis(ax, label, bbox, self.annotation_bottom_margin)

        if self.show_bounds:
            _add_bbox_to_axis(
                ax,
                bbox,
                self.bbox_alpha,
                self.bbox_face_color,
                self.bbox_edge_color,
                self.bbox_line_width,
            )


class ShapeHierarchyVisualizer(BaseShapeVisualizer):
    def __init__(
        self,
        *,
        parents_bbox_edge_color: str = "red",
        shape_bbox_edge_color: str = "blue",
        children_bbox_edge_color: str = "green",
        bbox_edge_width: float = 1.0,
        bbox_margin: float = 0.0,
        bbox_face_alpha: float = 0.2,
        edge_width_rel_to_size: bool = True,
    ):
        self.parents_bbox_edge_color = parents_bbox_edge_color
        self.shape_bbox_edge_color = shape_bbox_edge_color
        self.children_bbox_edge_color = children_bbox_edge_color
        self.bbox_edge_width = bbox_edge_width
        self.bbox_margin = bbox_margin
        self.bbox_face_alpha = bbox_face_alpha
        self.edge_width_rel_to_size = edge_width_rel_to_size

    def visualize_shape(
        self,
        ax: Axis,
        shape: PenpotShapeElement,
        label: str,
        bboxes: dict[str, BoundingBox],
        clip_bbox: BoundingBox | None = None,
    ) -> None:
        def get_bbox(shape_id: str) -> BoundingBox:
            return bboxes[shape_id].with_margin(self.bbox_margin)

        bbox = get_bbox(shape.shape_id)

        edge_scale = 1.0

        if self.edge_width_rel_to_size:
            ax_bbox = ax.get_window_extent().transformed(ax.get_figure().dpi_scale_trans.inverted())
            ax_width, ax_height = ax_bbox.width, ax_bbox.height

            shortest_edge = min(ax_width, ax_height)
            edge_scale = shortest_edge

        for parent_shape in shape.get_all_parent_shapes():
            parent_bbox = get_bbox(parent_shape.shape_id)

            _add_bbox_to_axis(
                ax,
                parent_bbox,
                bbox_edge_color=self.parents_bbox_edge_color,
                bbox_line_width=self.bbox_edge_width * edge_scale,
                bbox_alpha=0,
            )

        for child_shape in shape.get_all_children_shapes():
            child_bbox = get_bbox(child_shape.shape_id)

            if bbox == child_bbox:
                continue

            _add_bbox_to_axis(
                ax,
                child_bbox,
                bbox_edge_color=self.children_bbox_edge_color,
                bbox_line_width=self.bbox_edge_width * edge_scale,
                bbox_alpha=0,
            )

        _add_bbox_to_axis(
            ax,
            bbox,
            bbox_edge_color=self.shape_bbox_edge_color,
            bbox_line_width=self.bbox_edge_width * edge_scale,
            bbox_alpha=self.bbox_face_alpha,
        )


class DesignElementVisualizer:
    def __init__(
        self,
        shape_visualizer: BaseShapeVisualizer,
        web_driver_type: RegisteredWebDriver = RegisteredWebDriver.CHROME,
        only_primitives: bool = True,
        dpi: float = 100,
        scale: float = 4,
        ax_margin: float = 200,
        label_factory: ShapeLabelFactory = _default_shape_label_factory,
    ) -> None:
        self.shape_visualizer = shape_visualizer
        self.web_driver_type = web_driver_type
        self.only_primitives = only_primitives
        self.dpi = dpi
        self.scale = scale
        self.ax_margin = ax_margin
        self.label_factory = (
            label_factory if label_factory is not None else _default_shape_label_factory
        )

    def _get_relevant_children(self, shape: PenpotShapeElement) -> list[PenpotShapeElement]:
        return [
            child
            for child in shape.get_all_children_shapes()
            if not self.only_primitives or child.is_primitive_type
        ]

    def _prepare_shape(
        self,
        shape: PenpotShapeElement,
    ) -> tuple[Image.Image, dict[str, BoundingBox]]:
        with get_web_driver(self.web_driver_type) as web_driver:
            renderer = WebDriverSVGRenderer(web_driver, infer_bounding_boxes=True)

            view_box = shape.get_default_view_box()
            result = renderer.render_svg(shape.to_svg(view_box))

            shape_bboxes = {
                shape.shape_id: result.artefacts.bounding_boxes[shape.shape_id]
                for shape in [shape, *shape.get_all_children_shapes()]
            }

            shape_image = result.image

        return shape_image, shape_bboxes

    def _prepare_plt_context(self, img: Image.Image, bbox: BoundingBox) -> tuple[plt.Figure, Axis]:
        fig, ax = plt.subplots(
            dpi=self.dpi,
            figsize=(
                self.scale * bbox.aspect_ratio,
                self.scale / bbox.aspect_ratio,
            ),
        )

        ax.imshow(img)
        ax.axis("off")

        ax.set_xlim(bbox.x, bbox.x + bbox.width)
        ax.set_ylim(bbox.y + bbox.height, bbox.y)

        return fig, ax

    def _figure_to_image(self, fig: plt.Figure) -> Image.Image:
        fig.tight_layout(pad=0)

        with NamedTemporaryFile(suffix=".png") as f:
            fig.savefig(f.name, format="png", bbox_inches="tight", pad_inches=0)
            return Image.open(f.name).copy()

    def _visualize_single_shape(
        self, super_image, shape, bbox, label, all_shape_bboxes
    ) -> ShapeVisualization:
        ax_bbox = bbox.with_margin(self.ax_margin)

        fig, ax = self._prepare_plt_context(super_image, ax_bbox)

        self.shape_visualizer.visualize_shape(ax, shape, label, all_shape_bboxes, clip_bbox=ax_bbox)

        image = self._figure_to_image(fig)

        result = ShapeVisualization(shape, label, bbox, image)

        plt.close(fig)

        return result

    def visualize_bboxes_in_shape(
        self,
        shape: PenpotShapeElement,
        return_artifacts: bool = False,
        show_progress: bool = False,
    ) -> (
        list[ShapeVisualization]
        | tuple[list[ShapeVisualization], Image.Image, dict[str, BoundingBox]]
    ):
        super_image, shape_bboxes = self._prepare_shape(shape)

        children = self._get_relevant_children(shape)

        # largest_bbox = reduce(lambda a, b: a.union(b), shape_bboxes.values())

        results = []

        if show_progress:
            children = tqdm(children, desc="Visualizing shapes", leave=False)

        futures = []

        with ThreadPoolExecutor() as executor:
            for i, child in enumerate([*children, shape]):
                bbox = shape_bboxes[child.shape_id].with_margin(5)

                label = self.label_factory(i, shape)

                futures.append(
                    executor.submit(
                        self._visualize_single_shape,
                        super_image,
                        child,
                        bbox,
                        label,
                        shape_bboxes,
                    )
                )

        results = [future.result() for future in as_completed(futures)]

        if return_artifacts:
            return results, super_image, shape_bboxes

        return results
