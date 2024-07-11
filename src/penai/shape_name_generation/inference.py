import threading

from penai.llm.conversation import MessageBuilder, Response
from penai.llm.llm_model import RegisteredLLM, RegisteredLLMParams
from penai.svg import PenpotShapeElement
from penai.utils.vis import DesignElementVisualizer, ShapeVisualization


class DescriptionGenerator:
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
        self.shape_visualizations = {}

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

    def generate_description(self, shape: PenpotShapeElement) -> str:
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
                #
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

        return response.text
