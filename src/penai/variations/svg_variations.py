import logging
import re
import uuid
from enum import StrEnum
from pathlib import Path
from typing import Self

from sensai.util.logging import datetime_tag

from penai.config import get_config
from penai.llm.conversation import Conversation, Response
from penai.llm.llm_model import RegisteredLLM
from penai.svg import SVG, PenpotShapeElement
from penai.types import PathLike
from penai.utils.io import ResultWriter, fn_compatible

cfg = get_config()

log = logging.getLogger(__name__)


class VariationInstructionSnippet(StrEnum):
    SHAPES_COLORS_POSITIONS = (
        "Modify shapes, foreground colors and relative positioning, "
        "but stay close to the original design. "
    )


PROMPT_FORMAT_DESCRIPTION = (
    "For each variation, create a level 2 heading (markdown prefix `## `) that names"
    "the variation followed by the respective code snippet."
)


class VariationsPrompt:
    def __init__(self, text: str, _private: int):
        if _private != 42:
            raise ValueError(
                "This class should not be instantiated directly. Use VariationsPromptBuilder instead.",
            )
        self.text = text


class VariationsPromptBuilder:
    def __init__(self, num_variations: int | None):
        """:param num_variations: the number of variations to create; if None, the number is not specified and should be made explicit in
        customized variation instructions
        """
        num_variations_text = "" if num_variations is None else f"{num_variations} "
        self._prompt_1_create_variations = f"Create {num_variations_text}variations of the SVG."
        self._prompt_2_variation_instructions: str | VariationInstructionSnippet = (
            VariationInstructionSnippet.SHAPES_COLORS_POSITIONS
        )

    def with_variation_instructions(self, instructions: str | VariationInstructionSnippet) -> Self:
        """:param instructions: instructions on how to generate variations.
            If no number of variations is specified at construction, it should include specific instructions on which variations to generate.
        :return:
        """
        self._prompt_2_variation_instructions = instructions
        return self

    def build(self) -> VariationsPrompt:
        return VariationsPrompt(
            f"{self._prompt_1_create_variations}\n"
            f"{self._prompt_2_variation_instructions}\n"
            f"{PROMPT_FORMAT_DESCRIPTION}",
            42,
        )


def transform_generated_svg_code(svg_code: str) -> str:
    """Transforms SVG code generated by an LLM in order to ensure that identifiers appearing in the code are unique.

    :param svg_code: the generated SVG code
    :return: the transformed SVG code
    """
    ids = re.findall(r'id="(.*?)"', svg_code)
    for identifier in ids:
        new_id = uuid.uuid1()
        svg_code = svg_code.replace(f'id="{identifier}"', f'id="{new_id}"')
        svg_code = svg_code.replace(f"url(#{identifier})", f"url(#{new_id})")
    return svg_code


class SVGVariationsResponse(Response):
    def get_variations_dict(self) -> dict[str, str]:
        return {
            k: transform_generated_svg_code(code_snippet.code)
            for k, code_snippet in self.get_code_in_sections(2).items()
        }


class SVGVariationsConversation(Conversation[SVGVariationsResponse]):
    def __init__(self, model: RegisteredLLM = RegisteredLLM.GPT4O, verbose: bool = True):
        super().__init__(model, verbose=verbose, response_factory=SVGVariationsResponse)


class SVGVariations:
    def __init__(
        self,
        original_svg: SVG,
        variations_dict: dict[str, str],
        conversation: SVGVariationsConversation,
    ):
        """:param original_svg: the original SVG
        :param variations_dict: a mapping from variation name to SVG code
        """
        self.variations_dict = variations_dict
        self.original_svg = original_svg
        self.conversation = conversation

    def to_html(self, width_style: str = "60%") -> str:
        html = "<html><body>"
        html += f'<div style="width:{width_style}">'
        html += "<h1>Original</h1>"
        html += self.original_svg.to_string()
        html += "<h1>Variations</h1>"
        for name, svg in self.variations_dict.items():
            html += f"<h2>{name}</h2>"
            html += svg
        html += "</div>"
        html += "</body></html>"
        return html

    def revise(self, prompt: str) -> "SVGVariations":
        conversation = self.conversation.clone()
        response = conversation.query(prompt)
        variations_dict = response.get_variations_dict()
        return SVGVariations(self.original_svg, variations_dict, conversation)


class SVGVariationsGenerator:
    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str,
        verbose: bool = True,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        persistence_base_dir: PathLike = Path("log") / "svg_variations",
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

        # create simplified SVG (without the bloat)
        self.svg = shape.to_svg()
        self.svg.strip_penpot_tags()
        self.verbose = verbose
        self.model = model
        responses_dir = Path(persistence_base_dir / fn_compatible(shape.name))
        if persistence_add_timestamp:
            responses_dir = responses_dir / datetime_tag()
        self.result_writer = ResultWriter(responses_dir, enabled=persistence_enabled)

    def _create_conversation(self) -> SVGVariationsConversation:
        return SVGVariationsConversation(verbose=self.verbose, model=self.model)

    def get_svg_refactoring_prompt(self) -> str:
        return (
            f"The semantics of the following SVG can be summarized using the term(s) '{self.semantics}'. "
            "Refactor the SVG to make the shapes that are being used explicit (where applicable), "
            "making use of the respective shape tags (rect, circle, ellipse, etc.) whenever possible. "
            "Be sure to maintain any cutouts that are present in the original SVG by using appropriate masks.\n\n"
            f"```{self.svg.to_string()}```"
        )

    def create_variations_for_prompt(
        self,
        variations_prompt: VariationsPrompt,
    ) -> SVGVariations:
        conversation = self._create_conversation()
        refactoring_response = conversation.query_text(self.get_svg_refactoring_prompt())

        variations_response = conversation.query(variations_prompt.text)
        variations_dict = variations_response.get_variations_dict()
        variations = SVGVariations(self.svg, variations_dict, conversation)

        self.result_writer.write_text_file(
            "response_refactoring.md",
            refactoring_response,
            content_description="SVG refactoring response",
        )
        self.result_writer.write_text_file(
            "response_variations.md",
            variations_response.text,
            content_description="variations response",
        )
        self.result_writer.write_text_file(
            "full_conversation.txt",
            conversation.get_full_conversation_string(),
            content_description="full conversation",
        )
        self.result_writer.write_text_file(
            "response_variations.html",
            variations.to_html(),
            content_description="variations response as HTML",
        )

        return variations

    def create_variations(
        self,
        num_variations: int = 5,
        variation_logic: str
        | VariationInstructionSnippet = VariationInstructionSnippet.SHAPES_COLORS_POSITIONS,
    ) -> SVGVariations:
        prompt = (
            VariationsPromptBuilder(num_variations)
            .with_variation_instructions(variation_logic)
            .build()
        )
        return self.create_variations_for_prompt(prompt)
