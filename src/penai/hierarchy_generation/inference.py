from collections.abc import Generator, Iterable
from dataclasses import dataclass, field
from functools import cached_property
from typing import Self

from langchain_core.output_parsers import BaseOutputParser, JsonOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.pydantic_v1 import BaseModel
from tqdm import tqdm

from penai.llm.conversation import Conversation, HumanMessageBuilder, Response
from penai.llm.llm_model import RegisteredLLM
from penai.registries.web_drivers import RegisteredWebDriver
from penai.svg import BoundingBox, PenpotShapeElement
from penai.utils.vis import ShapeVisualization, ShapeVisualizer


class HierarchyInferenceElement(BaseModel):
    id: str
    description: str
    children: list[Self] | None = None

    def flatten(self) -> Generator[Self, None, None]:
        yield self

        if self.children:
            for child in self.children:
                yield from child.flatten()


@dataclass
class HierarchyElement:
    shape: PenpotShapeElement
    description: str
    parent: Self | None = None
    children: list[Self] = field(default_factory=list)

    @classmethod
    def from_hierarchy_schema(
        cls,
        label_shape_mapping: dict[str, PenpotShapeElement],
        source_element: HierarchyInferenceElement,
        parent: Self | None = None,
    ) -> Self:
        element = cls(
            shape=label_shape_mapping[source_element.id],
            description=source_element.description,
            parent=parent,
        )

        for child in source_element.children or []:
            element.children.append(cls.from_hierarchy_schema(label_shape_mapping, child, element))

        return element

    def flatten(self) -> Iterable[Self]:
        yield self

        for child in self.children:
            yield from child.flatten()

    @cached_property
    def bbox(self) -> BoundingBox:
        return BoundingBox.from_view_box_string(self.shape._lxml_element.attrib["viewBox"])


class SchemaResponse(Response):
    def __init__(self, response_text: str, parser: BaseOutputParser) -> None:
        super().__init__(response_text)
        self.parser = parser

    def parse_response(self) -> HierarchyInferenceElement:
        return self.parser.invoke(self.text)


class HierarchyInferencer:
    parser = JsonOutputParser(pydantic_object=HierarchyInferenceElement)

    prompt_template = PromptTemplate(
        template="{query}\n{format_instructions}\n",
        input_variables=["query"],
        partial_variables={"format_instructions": parser.get_format_instructions()},
    )

    def __init__(
        self,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        validate_hierarchy: bool = True,
    ) -> None:
        self.model = model
        self.validate_hierarchy = validate_hierarchy

    def build_prompt(self, visualizations: list[ShapeVisualization]) -> str:
        query = (
            "Provided are screenshots from a design document. "
            f"Each of the {len(visualizations)} design elements is depicted with its bounding box and a tooltip above with the unique element id and the element type. "
            "Provide a logical hierarchy between those elements reflecting their semantics and spatial relationships. "
            "Additionally, provide a short and meaningful description for each element in natural language as it could appear in the layer hierarchy of a design software. "
            # "The hierarchy and description should be precise enough so that a blind person can figure out the design.\n"
        )

        message = HumanMessageBuilder()
        message.with_text_message(self.prompt_template.format(query=query))

        for visualization in visualizations:
            message.with_image(visualization.image)

        return message.build()

    def infer_shape_hierarchy(
        self,
        shape: PenpotShapeElement,
        return_visualizations: bool = False,
    ) -> HierarchyElement | tuple[HierarchyElement, list[ShapeVisualization]]:
        visualizer = ShapeVisualizer(RegisteredWebDriver.CHROME)
        visualizations = list(tqdm(visualizer.visualize_bboxes_in_shape(shape)))

        prompt = self.build_prompt(visualizations)

        conversation = Conversation(response_factory=lambda text: SchemaResponse(text, self.parser))
        response = conversation.query(prompt)
        queried_hierarchy = response.parse_response()

        label_shape_mapping = {vis.label.replace("#", ""): vis.shape for vis in visualizations}

        hierarchy = HierarchyElement.from_hierarchy_schema(label_shape_mapping, queried_hierarchy)

        if return_visualizations:
            return hierarchy, visualizations

        return hierarchy
