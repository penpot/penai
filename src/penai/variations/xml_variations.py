from enum import StrEnum
from pathlib import Path

from sensai.util.logging import datetime_tag

from penai.llm.llm_model import RegisteredLLM
from penai.llm.prompting import Conversation, Response
from penai.models import PenpotMinimalShapeXML
from penai.svg import PenpotShapeElement
from penai.types import PathLike
from penai.utils.io import ResultWriter, fn_compatible

XML_FORMAT_DESCRIPTION = """
The Penpot XML format is a custom format for the definition of vector graphics,
which is partly related to the SVG format.

A shape is defined based on a `g` element, which contains a `penpot:shape` element as well as one or more siblings
depending on the `penpot:type` attribute of the `penpot_shape` element.

For types that build on SVG, the `penpot:shape` has one sibling, an SVG `g` element. Specifically:
  * For type `path`, the `g` element must contain an SVG `path` element.
  * For type `circle` or `ellipse`, the `g` element must contain an SVG `ellipse` element.
  * For type `rect`, the `g` element must contain an SVG `rect` element.

For type `bool`, the `penpot_shape` element has a `penpot_bool` sibling with two children,
where the second is subtracted from the first.
"""


class VariationInstructionSnippet(StrEnum):
    SHAPES_COLORS_POSITIONS = (
        "Modify shapes, foreground colors and relative positioning, "
        "but stay close to the original design. "
    )


PROMPT_OUTPUT_FORMAT_DESCRIPTION = (
    "For each variation, create a level 2 heading (markdown prefix `## `) that names"
    "the variation followed by the respective code snippet."
)


class XMLVariationsResponse(Response):
    def get_variations_dict(self) -> dict[str, str]:
        return {k: code_snippet.code for k, code_snippet in self.get_code_in_sections(2).items()}


class XMLVariationsConversation(Conversation[XMLVariationsResponse]):
    def __init__(self, model: RegisteredLLM = RegisteredLLM.GPT4O, verbose: bool = True):
        super().__init__(model, verbose=verbose, response_factory=XMLVariationsResponse)


class XMLVariations:
    def __init__(
        self,
        variations_dict: dict[str, str],
        conversation: XMLVariationsConversation,
    ):
        self.variations_dict = variations_dict
        self.conversation = conversation


class XMLVariationsGenerator:
    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str,
        verbose: bool = True,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        persistence_base_dir: PathLike = Path("log") / "xml_variations",
        persistence_enabled: bool = True,
        persistence_add_timestamp: bool = True,
    ):
        """:param shape:
        :param semantics:
        :param verbose:
        :param model:
        :param persistence_base_dir: the base directory for persistence, to which subdirectories indicating the shape name
            and (optionally, if `persistence_add_timestamp` is enabled) the current time will be added
        :param persistence_enabled: whether to save the responses to disk
        :param persistence_add_timestamp: whether to use a persistence subdirectory indicating the current date and time
        """
        self.semantics = semantics
        self.pxml = PenpotMinimalShapeXML.from_shape(shape)
        self.verbose = verbose
        self.model = model
        responses_dir = Path(persistence_base_dir / fn_compatible(shape.name))
        if persistence_add_timestamp:
            responses_dir = responses_dir / datetime_tag()
        self.result_writer = ResultWriter(responses_dir, enabled=persistence_enabled)

    def _create_conversation(self) -> XMLVariationsConversation:
        return XMLVariationsConversation(verbose=self.verbose, model=self.model)

    def create_variations(
        self,
    ) -> XMLVariations:
        conversation = self._create_conversation()

        query = XML_FORMAT_DESCRIPTION
        query += (
            "Based on this format description, create 2 variations of this shape:"
            + f"\n\n```\n{self.pxml.to_string()}\n```\n"
            + PROMPT_OUTPUT_FORMAT_DESCRIPTION
        )

        variations_response = conversation.query(query)
        variations_dict = variations_response.get_variations_dict()
        return XMLVariations(variations_dict, conversation)
