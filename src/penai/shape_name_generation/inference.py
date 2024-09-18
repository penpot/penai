import abc
import threading
from typing import NamedTuple

from langchain_core.messages import BaseMessage
from PIL.Image import Image
from pydantic import BaseModel

from penai.llm.conversation import MessageBuilder, Response
from penai.llm.llm_model import RegisteredLLM, RegisteredLLMParams
from penai.render import BaseSVGRenderer
from penai.svg import PenpotShapeElement
from penai.utils.misc import format_bbox
from penai.utils.vis import DesignElementVisualizer, ShapeVisualization


class BaseShapeNameGenerator(abc.ABC):
    @abc.abstractmethod
    def generate_name(self, shape: PenpotShapeElement) -> str:
        pass

    def generate_names_multiple(self, shapes: list[PenpotShapeElement]) -> list[str]:
        return [self.generate_name(shape) for shape in shapes]


class AnnotationBasedShapeNameGeneratorOutput(NamedTuple):
    name: str
    shape_vis: ShapeVisualization
    messages: list[BaseMessage]


class AnnotationBasedShapeNameGenerator(BaseShapeNameGenerator):
    def __init__(
        self,
        visualizer: DesignElementVisualizer,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        validate_result: bool = True,
        **model_options: RegisteredLLMParams,
    ) -> None:
        self.visualizer = visualizer
        self.model = model
        self.model_options = model_options
        self.validate_result = validate_result
        self.lock = threading.Lock()
        self.shape_visualizations: dict[PenpotShapeElement, ShapeVisualization] = {}

    def add_shape_to_message(
        self, message_builder: MessageBuilder, shape_vis: ShapeVisualization
    ) -> None:
        message_builder.with_text_message(
            f"Element ID: {shape_vis.label} (type: {shape_vis.shape.type.value})"
        )
        message_builder.with_image(shape_vis.image)
        message_builder.with_text_message("\n\n")

    def _get_shape_visualization(self, shape: PenpotShapeElement) -> ShapeVisualization:
        with self.lock:
            if shape in self.shape_visualizations:
                return self.shape_visualizations[shape]

            parent_frames = shape.get_containing_frame_elements()

            if parent_frames:
                top_level_frame = parent_frames[-1]
            else:
                parents = shape.get_all_parent_shapes()
                top_level_frame = parents[-1] if parents else shape

            top_level_frame = shape.get_top_level_frame()

            visualizations = list(
                self.visualizer.visualize_bboxes_in_shape(top_level_frame)
            )

            for vis in visualizations:
                self.shape_visualizations[vis.shape] = vis

            shape_vis = self.shape_visualizations.get(shape)

            assert (
                shape_vis is not None
            ), "Could not find visualization for shape in newly generated visualizations."

            return vis

    def generate_name_impl(
        self, shape: PenpotShapeElement
    ) -> AnnotationBasedShapeNameGeneratorOutput:
        shape_vis = self._get_shape_visualization(shape)

        system_message = (
            MessageBuilder()
            .with_text_message(
                "Provided is a screenshot from a design document. "
                "Name the design shape in the blue bounding box. "
                "The children of this element within the layer hierarchy are provided in green bounding boxes, the parents in red for context. "
                f'This elements has type "{shape.type.value.literal}". '
                "Keep in mind that elements may be occluded in some cases."
                "The type of element and relation to the other elements in the hierarchy should be reflected in the name. "
                "Only provide the suggested name, no explanation required."
                "\n"
                "Example names:\n"
                "- Car Button Icon\n"
                "- User Profile Picture\n"
                "- Navigation Bar Container"
            )
            .build_system_message()
        )

        human_message = (
            MessageBuilder()
            .with_text_message("Screenshot: ")
            .with_image(shape_vis.image)
            .build_human_message()
        )

        model = self.model.create_model(**self.model_options)

        response = Response(model.invoke([system_message, human_message]).content)

        return AnnotationBasedShapeNameGeneratorOutput(
            name=response.text,
            shape_vis=shape_vis,
            messages=[system_message, human_message],
        )

    def generate_name(self, shape: PenpotShapeElement) -> str:
        return self.generate_name_impl(shape).name


class SimplifiedShapeNameGeneratorOutput(NamedTuple):
    name: str
    top_frame_image: Image
    shape_image: Image
    messages: list[BaseMessage]


class SimplifiedShapeNameGeneratorResponseSchema(BaseModel):
    name: str


class SimplifiedShapeNameGenerator(BaseShapeNameGenerator):
    def __init__(
        self,
        svg_renderer: BaseSVGRenderer,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        provide_isolated_shape: bool = False,
        use_json_mode: bool = True,
        include_coordinates: bool = False,
        **model_options: RegisteredLLMParams,
    ) -> None:
        if provide_isolated_shape:
            assert (
                svg_renderer.SUPPORTS_BOUNDING_BOX_INFERENCE
            ), "Renderer must support bounding box inference."

        self.renderer = svg_renderer
        self.model = model
        self.provide_isolated_shape = provide_isolated_shape
        self.use_json_mode = use_json_mode
        self.include_coordinates = include_coordinates
        self.model_options = model_options

    def generate_name_impl(
        self, shape: PenpotShapeElement
    ) -> SimplifiedShapeNameGeneratorOutput:
        assert shape.is_visible, "Shape must be visible to generate a name."

        top_frame = shape.get_top_level_frame()
        result = self.renderer.render_svg(top_frame.to_svg(), width=2000)

        bbox = result.artifacts.bounding_boxes[shape.shape_id]

        cropped_shape = result.image.crop(
            (bbox.x, bbox.y, bbox.x + bbox.width, bbox.y + bbox.height)
        )

        shape_type_literal = shape.type.value.literal

        message_builder = (
            MessageBuilder()
            .with_text_message(
                "Find a short and descriptive name for the design element below as it could "
                "appear in the layer hierarchy of a design program:"
                "\n"
            )
            .with_image(cropped_shape)
            .with_text_message(
                "Examples are:"
                "\n"
                "\n"
                "- Car Button Icon"
                "- User Profile Picture"
                "- Navigation Bar Container"
                "\n"
                "\n"
                f'The type of the element is "{shape_type_literal}".'
            )
        )

        if self.include_coordinates:
            frame_bbox = result.artifacts.bounding_boxes[top_frame.shape_id]

            message_builder.with_text_message(
                f"The bounding box (x1, y1, x2, y2) of the design document is {format_bbox(frame_bbox)} while the "
                f"design element is located at {format_bbox(bbox)}."
            )

        message_builder.with_text_message(
            "Use the following design document into context in which the design element is contained:\n"
        ).with_image(result.image).with_text_message(
            'Provide the name as JSON object in the format `{"name": "<element-name>"}`. Do not provide any other output or explanation except for the JSON.'
        )

        messages = [message_builder.build_human_message()]

        model = self.model.create_model(**self.model_options)

        if self.use_json_mode:
            model = model.with_structured_output(
                SimplifiedShapeNameGeneratorResponseSchema, method="json_mode"
            )
            response_dict = model.invoke(messages)
            response = SimplifiedShapeNameGeneratorResponseSchema.model_validate(
                response_dict
            )
        else:
            response = Response(model.invoke(messages).content)

            try:
                response_json = response.get_code_snippets()[0].code
            except IndexError:
                response_json = response.text

            response = SimplifiedShapeNameGeneratorResponseSchema.model_validate_json(
                response_json
            )

        return SimplifiedShapeNameGeneratorOutput(
            name=response.name,
            top_frame_image=result.image,
            shape_image=cropped_shape,
            messages=messages,
        )

    def generate_name(self, shape: PenpotShapeElement) -> str:
        return self.generate_name_impl(shape).name
