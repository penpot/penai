import logging
import re
import uuid
from collections.abc import Sequence
from enum import Enum, StrEnum
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
        "but stay close to the original design."
    )
    SPECIFIC_COLORS_SHAPES = (
        "Modify border colors, foreground and background colors as well as shapes. "
        "Stay close to the original design. "
    )


PROMPT_FORMAT_DESCRIPTION = (
    "For each variation, create a level 2 heading (markdown prefix `## `) that names"
    "the variation followed by the respective code snippet."
)


class VariationDescriptionSequence(Enum):
    UI_ELEMENT_STATES = (
        "adapted for UI state 'active'",
        "adapted for UI state 'disabled'",
        "adapted for UI state 'error'",
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
    def __init__(
        self,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        verbose: bool = True,
        system_prompt: str | None = None,
    ):
        super().__init__(
            model,
            verbose=verbose,
            response_factory=SVGVariationsResponse,
            system_prompt=system_prompt,
        )


class SVGVariations:
    def __init__(
        self,
        original_svg: SVG,
        variations_dict: dict[str, str],
        conversation: SVGVariationsConversation | None = None,
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
        if self.conversation is None:
            raise ValueError("Cannot revise without a conversation")
        conversation = self.conversation.clone()
        response = conversation.query(prompt)
        variations_dict = response.get_variations_dict()
        return SVGVariations(self.original_svg, variations_dict, conversation)

    def write_results(self, result_writer: ResultWriter) -> None:
        if self.conversation is not None:
            result_writer.write_text_file(
                "full_conversation.txt",
                self.conversation.get_full_conversation_string(),
                content_description="full conversation",
            )
        result_writer.write_text_file(
            "variations.html",
            self.to_html(),
            content_description="variations response as HTML",
        )
        for i, (name, svg_text) in enumerate(self.variations_dict.items(), start=1):
            result_writer.write_text_file(
                f"variation_{i}.svg",
                svg_text,
                content_description=f"variation '{name}' as SVG",
            )


class SVGVariationsGenerator:
    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str,
        verbose: bool = True,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        persistence_base_dir: PathLike = Path(cfg.results_dir()) / "svg_variations",
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

    def _create_conversation(self, system_prompt: str | None = None) -> SVGVariationsConversation:
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
        conversation.query_text(self.get_svg_refactoring_prompt())

        variations_response = conversation.query(variations_prompt.text)
        variations_dict = variations_response.get_variations_dict()
        variations = SVGVariations(self.svg, variations_dict, conversation)

        variations.write_results(self.result_writer)
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

    def create_variations_sequentially(
        self,
        variation_scope: VariationInstructionSnippet
        | str = VariationInstructionSnippet.SPECIFIC_COLORS_SHAPES,
        variation_description_sequence: VariationDescriptionSequence
        | Sequence[str] = VariationDescriptionSequence.UI_ELEMENT_STATES,
    ) -> SVGVariations:
        """Generates variations sequentially, one at a time, accounting for limitations in response token count
        (~4K for GPT-4o, which is not enough for multiple variations at once).

        :param variation_scope: describes the scope of variations to apply in generation
        :param variation_description_sequence: a sequence of instructions describing what to do for each variation
        :return: the variations
        """
        conversation = self._create_conversation()
        conversation.query(self.get_svg_refactoring_prompt())

        variation_scope_prompt = str(variation_scope)

        initial_variation_query = (
            "In the following, your task is to create variations of the SVG, one variation at a time. "
            "Whenever you output a variation, prefix it with a level 2 title (markdown prefix `## `) that names the variation, "
            "followed by the respective code snippet.\n"
            "In general, you may do the following: " + variation_scope_prompt + "\n\n"
            "Here are the instructions for the first variation:\n"
        )

        variation_prompt_template = 'Create a variation corresponding to the description "%s".'

        variation_descriptions: Sequence[str]
        if isinstance(variation_description_sequence, VariationDescriptionSequence):
            variation_descriptions = variation_description_sequence.value
        else:
            assert isinstance(variation_description_sequence, list)
            variation_descriptions = variation_description_sequence

        all_variations_dict = {}
        for i, instruction in enumerate(variation_descriptions):
            prompt = initial_variation_query if i == 0 else ""
            prompt += variation_prompt_template % instruction
            response = conversation.query(prompt)
            variations_dict = response.get_variations_dict()
            all_variations_dict.update(variations_dict)

        variations = SVGVariations(self.svg, all_variations_dict, conversation)
        variations.write_results(self.result_writer)
        return variations

    def create_variations_sequentially_from_example(
        self,
        example_variations: SVGVariations,
        write_results: bool = True,
    ) -> SVGVariations:
        """Generates variations sequentially, one at a time, based on an example set of variations
        that are presented to the model at once.

        :param example_variations: the example variations to use as a basis
        :return: the variations
        """
        system_prompt = (
            "You are a design assistant tasked with creating variations of an SVG. "
            "You will be presented with examples of variations of a UI element, and your task is to apply the same variation "
            "principles to another UI element. "
            "In each response you are to return a single variation. "
        )

        conversation = self._create_conversation(system_prompt=system_prompt)

        example_prompt = (
            "Here is an example of a UI element with variations:\n\n"
            f"Original design:\n```{example_variations.original_svg.to_string()}```\n\n"
        )
        for name, svg in example_variations.variations_dict.items():
            example_prompt += f"Variation '{name}':\n```{svg}```\n\n"

        initial_instruction_prompt = (
            example_prompt
            + f"This is the SVG for which are now to generate variations:\n\n```{self.svg.to_string()}```\n\n"
            "Here are the instructions for the first variation:\n"
        )

        variations_dict = {}
        for i, name in enumerate(example_variations.variations_dict.keys()):
            prompt = initial_instruction_prompt if i == 0 else ""
            prompt += f"Based on the example, create the variation '{name}'."
            response = conversation.query(prompt)
            code_snippets = response.get_code_snippets()
            if len(code_snippets) > 1:
                log.warning("Received more than one code snippet in response; using the first one")
            variations_dict[name] = code_snippets[0].code

        variations = SVGVariations(self.svg, variations_dict, conversation)
        if write_results:
            variations.write_results(self.result_writer)
        return variations

    def create_variations_sequentially_from_example_1by1(
        self,
        example_variations: SVGVariations,
    ) -> SVGVariations:
        # This applies the function create_variations_sequentially_from_example multiple times
        # such that the model is presented with only a single example in each conversation
        all_variations_dict = {}
        example_variations_dict = example_variations.variations_dict
        for name in example_variations_dict:
            single_example_variations_dict = {name: example_variations_dict[name]}
            single_example_variations = SVGVariations(
                example_variations.original_svg, single_example_variations_dict
            )
            variations = self.create_variations_sequentially_from_example(
                single_example_variations, write_results=False
            )
            all_variations_dict.update(variations.variations_dict)
        return SVGVariations(self.svg, all_variations_dict)

    def create_variations_from_example(
        self,
        example_variations: SVGVariations,
    ) -> SVGVariations:
        # This is a dedicated solution for the "from example" use case, where the model is to generate
        # one variation at a time based on a single example

        system_prompt = (
            "You are a design assistant tasked with creating a variation of an SVG. "
            "You will be presented with an example, i.e. an original design and a variation thereof. "
            "Your task is analyze the way in which the variation differs from the original "
            "and then apply the same mechanisms to another UI element. "
        )

        variations_dict = {}
        for _i, (name, svg_text) in enumerate(example_variations.variations_dict.items()):
            conversation = self._create_conversation(system_prompt=system_prompt)
            prompt = (
                "Here is the example pair (original and variation):\n\n"
                f"This is the original design:\n```{example_variations.original_svg.to_string()}```\n\n"
                f"This is the variation '{name}':\n```{svg_text}```\n\n"
                f"Based on this example, apply the same type of variation to this design:```{self.svg.to_string()}```\n"
            )
            response = conversation.query(prompt)
            code_snippets = response.get_code_snippets()
            if len(code_snippets) == 0:
                log.warning(f"Received no code snippets for '{name}'")
                continue
            if len(code_snippets) > 1:
                log.warning("Received more than one code snippet in response; using the first one")
            variations_dict[name] = code_snippets[0].code

        variations = SVGVariations(self.svg, variations_dict)
        variations.write_results(self.result_writer)
        return variations
