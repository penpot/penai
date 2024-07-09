import logging
from collections.abc import Iterator, Sequence
from enum import Enum, StrEnum
from pathlib import Path
from typing import Literal, Self

from sensai.util.logging import datetime_tag

from penai.config import get_config
from penai.llm.conversation import CodeSnippet, Conversation, PromptBuilder, Response
from penai.llm.llm_model import RegisteredLLM
from penai.models import PenpotColors
from penai.svg import SVG, PenpotShapeElement
from penai.types import PathLike
from penai.utils.io import ResultWriter, fn_compatible

cfg = get_config()

log = logging.getLogger(__name__)


class LLMResponseError(Exception):
    pass


class VariationInstructionSnippet(StrEnum):
    SHAPES_COLORS_POSITIONS = (
        "Modify simple shapes, foreground colors, background colors and relative positioning, "
        "but stay close to the original design. You can use techniques like scaling, rounding, "
        "mirroring, rotating, applying gradients, creating outlines, and slightly "
        "changing the stroke width. "
    )
    SPECIFIC_COLORS_SHAPES = (
        "Modify border colors, foreground and background colors as well as simple shapes. "
        "Stay close to the original design. "
    )


REVISION_PREPROMPT = (
    "Now, you are to revise the variations you have created. "
    "For each variation, consider the following revision instruction: \n"
)


class RevisionInstructionSnippet(StrEnum):
    MODIFY_SHAPES = "Modify these variations such that they all consider shape changes."
    MERGE_PATHS = (
        "Now merge all paths into one if possible while maintaining visual appearance. "
        "Otherwise, just return the svg as is. "
        "Make sure to maintain all symmetries and "
        "keep the right order of the paths such that smaller shapes are enclosed in larger ones. "
        "Give a suitable semantic id to the resulting path. "
    )
    """This revision prompt was an experiment to make filling of split-up path behave well. For now, it was superseded
    by using a better refactoring prompt. Leaving it here for reference, might come back to it."""


PROMPT_FORMAT_DESCRIPTION = (
    "For each variation, create a level 2 heading (markdown prefix `## `) that names "
    "the variation followed by the respective code snippet."
)

VARIATION_CONSTRAINT_PROMPT = (
    "Make sure to either use the original view-box or adjust the view-box accordingly. "
    "Do not add explicit width or height attributes to the <svg> tag. "
    "Round coordinates to integers if possible. Do not change fonts. "
    "Make sure to not change the semantics of the original design element (the SVG)."
    "Do not modify complex shapes defined by complicated paths "
    "unless specifically instructed to do so."
)

SVG_REFACTORING_INITIAL_LOGIC = (
    "The refactoring should not affect the visual appearance of the SVG! This is of utmost importance! \n"
    "This means that the SVG should look exactly the same before and after the refactoring. "
    "To simplify the SVG structure, follow all of the following steps!\n"
    # "When possible, replace paths by compositions that make use of svg shape tags (rect, circle, ellipse, etc.)."
    # "If a path cannot be replaced by shapes, keep it as is and don't attempt to simplify it. "
    "-) First identify the background color - it could be declared as fill or as style='background:...' in the <svg> tag. \n"
    "-) Remove any unnecessary groups that do not serve a purpose and have no attributes. "
    # "-) Remove any invisible elements, such as elements with opacity 0 or those that merge with the background. \n"
    # "-) Remove groups that do not serve a purpose and have no attributes, but keep other groups intact, e.g. those useful for separating semantically different elements.\n"
    "-) Consolidate attributes defined through 'style:...` and directly in the tag. For example, instead of "
    '\'style: "opacity:0.5;..."\' you should write `opacity:"0.5" and so on. \n'
    "-) Don't change any attributes or styles of <text> tags!\n"
    "-) Don't change the position of text elements.\n"
    # "Don't perform any changes on paths!\n"
    # "-) Format paths and add comments that identify semantic elements."
    # ". Identify enclosed shapes as cutouts.\n"
    # "Important: implement the nonzero rule for enclosed paths by adding explicit fills to the paths that resulted from the split-up. "
    # "Paths that are cutouts should be filled with the background color identified above.\n"
    "-) If any paths are split up, make sure to either define masks or "
    "to appropriately fill the enclosed shapes with the background color as follows from the "
    "svg nonzero filling rule for enclosed shapes within a single path.\n"
    "-) Don't perform any other changes on the paths.\n"
    "-) Don't merge paths! \n"
    "-) Add semantic ids to the tags where appropriate, in particular in path tags.\n"
    # "-) Lay out a plan of actions that satisfies the above points.\n"
    # "-) Revise your plan to make sure that the visual appearance of the SVG remains the same.\n"
    # "-) Finally, refactor the SVG according to your plan.\n"
    "Your answer should be an explanations of the changes you made, "
    "followed by a list of identified path elements that mentions if any of them is a cutout (enclosed path), "
    "followed by the refactored SVG inside a '```svg' code tag.\n"
    # "Your answer should only be the refactored SVG inside a '```svg' code tag and nothing else.\n"
    # "Do not merge together paths, unless they can be better represented by shapes as described above."
    # "Round coordinates to integers if possible. "
)

SVG_REFACTORING_REFINEMENT_LOGIC = (
    "Now further refactor the SVG.\n"
    "Make the shapes that are being expressed as paths explicit (where applicable) by "
    "making use of the respective shape tags (rect, circle, ellipse, etc.) whenever possible.\n"
    "Maintain any cutouts that are present in the original SVG by using appropriate masks and fills.\n"
    "If shapes cannot be made explicit, keep them as paths but split paths separated by ZZZZ up, and fill enclosed shapes correctly "
    "(by using the overall background color or the prior element's color).\n"
    "Give any newly created tags appropriate names and IDs.\n"
    "Make sure that all tags are in the correct order and that the visual appearance remains "
    "the same as before.\n"
    # "Your answer should only be the refactored SVG and nothing else.\n"
    # "Make sure to take care of setting fill='none' for shape tags that should not be filled.\n"
    # "The elements may overlap, but make absolutely sure that the visual appearance of the SVG remains the same. "
    # "If none of the above can be done, do nothing and keep it as is. "
)

SVG_REFACTORING_FINAL_COMPARISON_LOGIC = (
    "Have a final look at the refactored SVG and compare it to the original given at the very beginning. "
    "Can any paths be simplified? If yes, simplify them. "
    "Is the order of the tags correct? Remember that contained (smaller) "
    "paths should come after the containing (larger) paths that enclose them. "
    "Paths contained within a larger path should not have the same color as the containing one, otherwise they are invisible. "
    # "This does not hold for non-overlapping or partially overlapping paths though. "
    "You will have to identify which paths are contained within each other to determine the correct fills. "
    "You should also not adjust stroke related attributes. "
    "Are any remaining paths equivalent to simple shapes? "
    "If yes, simplify them, in replacing all circles by <circle>, all rectangles by <rect>, etc. "
    "Otherwise, keep the paths as they are. "
    "If any elements after the refactoring are not needed or invisible, remove them. "
    "Your answer should contain an analysis of which elements are contained within each other, "
    "how this influences the logic of fills (see above), "
    "as well as an analysis of which paths are equivalent to simple shapes. "
    "Finally, your response should contain the final version of the refactored SVG."
)


def get_initial_refactoring_prompt(svg_str: str, semantics: str | None = None) -> str:
    """Generates a prompt for an initial refactoring of an SVG."""
    prompt = ""
    if semantics is not None:
        prompt += (
            f"The semantics of the following SVG can be summarized using the term(s): {semantics.rstrip('.')}. "
            "Refactor the SVG."
        )
    else:
        prompt += "Refactor the following SVG."
    prompt += f"\n\n{SVG_REFACTORING_INITIAL_LOGIC}"
    prompt += f"```\n{svg_str}\n```"
    return prompt


def get_refactoring_comparison_prompt(svg_str_reference: str, svg_str_refactored: str) -> str:
    """Generates a prompt for comparing a reference SVG with the refactored SVG."""
    return (
        f"{SVG_REFACTORING_FINAL_COMPARISON_LOGIC}\n"
        # "Here is the reference SVG:\n"
        # f"```{svg_str_reference}```\n"
        # "Here is the refactored SVG:\n"
        # f"```{svg_str_refactored}```\n"
    )


class VariationDescriptionSequence(Enum):
    UI_ELEMENT_STATES = (
        "adapted for UI state 'active'",
        "adapted for UI state 'disabled'",
        "adapted for UI state 'error'",
    )


class VariationInstructions:
    """Represents instructions (text prompt) for the generation of variations."""

    def __init__(self, text: str, _private: int):
        if _private != 42:
            raise ValueError(
                "This class should not be instantiated directly. Use VariationsInstructionsBuilder instead.",
            )
        self.text = text


class VariationsInstructionsBuilder:
    def __init__(self, num_variations: int | None):
        """:param num_variations: the number of variations to create; if None, the number is not specified and should be made explicit in
        customized variation instructions
        """
        num_variations_text = "" if num_variations is None else f"{num_variations} "
        self._prompt_1_create_variations = f"Create {num_variations_text}variations of the SVG."
        self._prompt_2_variation_constraints: str = VARIATION_CONSTRAINT_PROMPT
        self._prompt_3_variation_instructions: str | VariationInstructionSnippet = (
            VariationInstructionSnippet.SHAPES_COLORS_POSITIONS
        )
        self._colors = None

    def with_variation_instructions(self, instructions: str | VariationInstructionSnippet) -> Self:
        """:param instructions: instructions on how to generate variations.
            If no number of variations is specified at construction, it should include specific instructions on which variations to generate.
        :return:
        """
        self._prompt_3_variation_instructions = instructions
        return self

    def with_colors(self, colors: PenpotColors | None) -> Self:
        self._colors = colors
        return self

    def build(self) -> VariationInstructions:
        prompt_text = (
            DesignPromptBuilder(
                f"{self._prompt_1_create_variations}\n"
                f"{self._prompt_2_variation_constraints}\n"
                f"{self._prompt_3_variation_instructions}\n"
                f"{PROMPT_FORMAT_DESCRIPTION}"
            )
            .with_colors(self._colors)
            .build()
        )
        return VariationInstructions(
            prompt_text,
            42,
        )


class SVGVariationsResponse(Response):
    def get_variations_dict(self) -> dict[str, str]:
        variations_dict = {
            k: code_snippet.code for k, code_snippet in self.get_code_in_sections(2).items()
        }
        return variations_dict


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
        refactored_svg_snippets: list[CodeSnippet] | None = None,
        conversation: SVGVariationsConversation | list[SVGVariationsConversation] | None = None,
    ):
        """:param original_svg: the original SVG
        :param variations_dict: a mapping from variation name to SVG code
        """
        self.variations_dict = variations_dict
        self.original_svg = original_svg
        if conversation is None:
            conversation = []
        elif isinstance(conversation, SVGVariationsConversation):
            conversation = [conversation]
        self._conversations = conversation
        self.refactored_svg_snippets = refactored_svg_snippets or []

    @property
    def conversation(self) -> SVGVariationsConversation | None:
        """Returns the main conversation (if there is only one).

        :return: the main conversation
        """
        if len(self._conversations) == 1:
            return self._conversations[0]
        else:
            return None

    def conversations(self) -> list[SVGVariationsConversation]:
        """:return: the list of all conversations (may be empty)"""
        return self._conversations

    def iter_variations_name_svg(self) -> Iterator[tuple[str, SVG]]:
        for name, svg_text in self.variations_dict.items():
            yield name, SVG.from_string(svg_text)

    def to_html(
        self,
        width_style: str = "60%",
        add_width_height: bool = True,
        scale_to_width: float | None = 400,
    ) -> str:
        # NOTE: When rendering several inlined SVGs together on an HTML page,
        #       we must ensure that all identifiers are unique.
        html = "<html><body>"
        html += f'<div style="width:{width_style}">'
        html += "<h1>Original</h1>"
        html += self.original_svg.to_string(
            unique_ids=True, add_width_height=add_width_height, scale_to_width=scale_to_width
        )
        for i, refactored_svg_snippet in enumerate(self.refactored_svg_snippets, 1):
            html += f"<h1>Refactored: {i}</h1>"
            html += SVG.from_string(refactored_svg_snippet.code).to_string(
                unique_ids=True, add_width_height=add_width_height, scale_to_width=scale_to_width
            )
        html += "<h1>Variations</h1>"
        for name, svg in self.iter_variations_name_svg():
            html += f"<h2>{name}</h2>"
            html += svg.to_string(
                unique_ids=True, add_width_height=add_width_height, scale_to_width=scale_to_width
            )
        html += "</div>"
        html += "</body></html>"
        return html

    def revise(
        self,
        revision_logic: str | RevisionInstructionSnippet = RevisionInstructionSnippet.MODIFY_SHAPES,
        preprompt: str = REVISION_PREPROMPT,
    ) -> "SVGVariations":
        if self.conversation is None:
            raise ValueError("Cannot revise without a (single main) conversation")
        conversation = self.conversation.clone()
        revision_prompt = preprompt + revision_logic
        response = conversation.query(revision_prompt)
        variations_dict = response.get_variations_dict()
        return SVGVariations(self.original_svg, variations_dict, conversation=conversation)

    def write_results(self, result_writer: ResultWriter, file_prefix: str = "") -> None:
        if self.conversation is not None:
            result_writer.write_text_file(
                f"{file_prefix}variations_conversation.md",
                "# Full conversation for variations\n"
                + self.conversation.get_full_conversation_string(),
                content_description="full conversation",
            )
        elif len(self._conversations) > 1:
            for i, conversation in enumerate(self._conversations, start=1):
                result_writer.write_text_file(
                    f"{file_prefix}conversation_{i}.md",
                    conversation.get_full_conversation_string(),
                    content_description=f"conversation {i}",
                )
        result_writer.write_text_file(
            f"{file_prefix}variations.html",
            self.to_html(),
            content_description="variations response as HTML",
        )
        for i, (name, svg_text) in enumerate(self.variations_dict.items(), start=1):
            result_writer.write_text_file(
                f"{file_prefix}variation_{i}.svg",
                svg_text,
                content_description=f"variation '{name}' as SVG",
            )


class DesignPromptBuilder(PromptBuilder):
    def with_colors(self, colors: PenpotColors | None, breaks: int = 2) -> Self:
        """Adds information on the given colors (if any)."""
        if colors is None:
            return self
        colors = colors.get_colors()
        if len(colors) > 0:
            prompt = "The design uses the following colors:\n"
            for color in colors:
                prompt += f"{color.name}: {color.color}\n"
            prompt += (
                "In the outputs you create, use these colors where applicable "
                "and make sure that any additional colors fit well with the existing color scheme."
            )
            self.with_text(prompt, breaks=breaks)
        return self


class SVGVariationsGenerator:
    FILENAME_VARIATION_TRANSFER_EXAMPLE_PRESENTED = "example_presented.html"

    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str | None = None,
        verbose: bool = True,
        svg_refactoring_model: RegisteredLLM = RegisteredLLM.GPT4O,
        svg_variations_model: RegisteredLLM = RegisteredLLM.CLAUDE_3_5_SONNET,
        persistence_base_dir: PathLike = Path(cfg.results_dir()) / "svg_variations",
        persistence_enabled: bool = True,
        num_refactoring_steps: Literal[0, 1, 2, 3] = 1,
    ):
        """:param shape:
        :param semantics:
        :param verbose:
        :param svg_refactoring_model:
        :param persistence_base_dir: the base directory for persistence, to which subdirectories indicating the shape name
            and (optionally, if `persistence_add_timestamp` is enabled) the current time will be added
        :param persistence_enabled: whether to save the responses to disk
        """
        self.semantics = semantics

        # create simplified SVG (without the bloat)
        self.svg = shape.to_svg().with_shortened_ids()
        self.svg.strip_penpot_tags()
        self.verbose = verbose
        self.refactoring_model = svg_refactoring_model
        self.variations_model = svg_variations_model
        persistence_base_dir = Path(persistence_base_dir)

        results_basedir = datetime_tag()[4:]  # Strip off the year digits
        if num_refactoring_steps > 0 and svg_refactoring_model != svg_variations_model:
            results_basedir += f"_{svg_refactoring_model.value}"
        results_basedir += f"_{svg_variations_model.value}"

        result_dir = persistence_base_dir / fn_compatible(shape.name) / results_basedir
        self.result_writer = ResultWriter(result_dir, enabled=persistence_enabled)
        self.num_refactoring_steps = num_refactoring_steps

    @property
    def persistence_dir(self) -> Path:
        return Path(self.result_writer.result_dir).absolute()

    def _create_refactoring_conversation(
        self, system_prompt: str | None = None
    ) -> SVGVariationsConversation:
        return SVGVariationsConversation(
            verbose=self.verbose, model=self.refactoring_model, system_prompt=system_prompt
        )

    def _create_variations_conversation(
        self, system_prompt: str | None = None
    ) -> SVGVariationsConversation:
        return SVGVariationsConversation(
            verbose=self.verbose, model=self.variations_model, system_prompt=system_prompt
        )

    def get_refactoring_conversation_and_code_snippets(
        self,
    ) -> tuple[SVGVariationsConversation, list[CodeSnippet]]:
        conversation = self._create_refactoring_conversation()
        initial_refactoring_prompt = get_initial_refactoring_prompt(
            self.svg.to_string(), self.semantics
        )

        initial_response = conversation.query(initial_refactoring_prompt)
        refactored_snippets = initial_response.get_code_snippets()
        if len(refactored_snippets) != 1:
            raise LLMResponseError(
                f"Expected the initial response to contain exactly one code snippet but got:\n{initial_response.text}"
            )
        if self.num_refactoring_steps == 1:
            return conversation, refactored_snippets

        refinement_response = conversation.query(SVG_REFACTORING_REFINEMENT_LOGIC)
        refactored_snippets += refinement_response.get_code_snippets()
        if self.num_refactoring_steps == 2:
            return conversation, refactored_snippets

        # the initial refactored SVG is usually good enough to serve as reference
        reference_svg_str = refactored_snippets[0].code
        last_refactored_svg_str = refactored_snippets[-1].code
        comparison_prompt = get_refactoring_comparison_prompt(
            reference_svg_str, last_refactored_svg_str
        )
        comparison_response = conversation.query(comparison_prompt)
        refactored_snippets += comparison_response.get_code_snippets()
        return conversation, refactored_snippets

    def _prepare_for_variations(self) -> tuple[str, list[CodeSnippet]]:
        """Performs refactoring to specified degree, saves refactoring conversation as str,
        and returns the refactored snippets and the svg for variations.
        """
        refactored_snippets: list[CodeSnippet] = []
        if self.num_refactoring_steps > 0:
            (
                refactoring_conversation,
                refactored_snippets,
            ) = self.get_refactoring_conversation_and_code_snippets()

            self.result_writer.write_text_file(
                "refactoring_conversation.md",
                "# Refactoring the SVG \n"
                + refactoring_conversation.get_full_conversation_string(),
            )
            svg_for_variations = refactored_snippets[-1].code
        else:
            svg_for_variations = self.svg.to_string()

        return svg_for_variations, refactored_snippets

    def create_variations_for_instructions(
        self,
        variation_instructions: VariationInstructions,
    ) -> SVGVariations:
        svg_for_variations, refactored_snippets = self._prepare_for_variations()
        variations_conversation = self._create_variations_conversation()
        if self.semantics is not None:
            semantics_prompt = f"The semantics of the following SVG can be summarized using the term(s): {self.semantics.rstrip('.')}. "
        else:
            semantics_prompt = "Below is an SVG that contains a design element."

        variations_conversation.query_text(
            semantics_prompt
            + f"```{svg_for_variations}```. In the following, you are to create variations of this SVG. "
            f"If not needed for the variation, do not adjust the svg path. "
            f"You should also not adjust the view-box. Don't create any variations yet and wait for my instructions."
        )
        # Now actually create the variations
        variations_response = variations_conversation.query(variation_instructions.text)
        variations_dict = variations_response.get_variations_dict()
        variations = SVGVariations(
            self.svg,
            variations_dict,
            refactored_svg_snippets=refactored_snippets,
            conversation=variations_conversation,
        )

        variations.write_results(self.result_writer)
        return variations

    def create_variations(
        self,
        num_variations: int = 5,
        variation_logic: (
            str | VariationInstructionSnippet
        ) = VariationInstructionSnippet.SHAPES_COLORS_POSITIONS,
        colors: PenpotColors | None = None,
    ) -> SVGVariations:
        prompt = (
            VariationsInstructionsBuilder(num_variations)
            .with_variation_instructions(variation_logic)
            .with_colors(colors)
            .build()
        )
        return self.create_variations_for_instructions(prompt)

    def revise_variations(
        self,
        variations: SVGVariations,
        revision_prompt: str
        | RevisionInstructionSnippet = RevisionInstructionSnippet.MODIFY_SHAPES,
    ) -> SVGVariations:
        """Generates revised variations based on the given variations. If persistence is enabled, the saved files will
        have the prefix `revised_`.
        """
        revised_variations = variations.revise(revision_prompt)
        revised_variations.write_results(self.result_writer, file_prefix="revised_")
        return revised_variations

    @classmethod
    def _create_variation_scope_prompt(
        cls, variation_scope: VariationInstructionSnippet | str, colors: PenpotColors | None = None
    ) -> str:
        return DesignPromptBuilder(str(variation_scope)).with_colors(colors).build()

    def create_variations_sequentially(
        self,
        variation_scope: (
            VariationInstructionSnippet | str
        ) = VariationInstructionSnippet.SPECIFIC_COLORS_SHAPES,
        variation_description_sequence: (
            VariationDescriptionSequence | Sequence[str]
        ) = VariationDescriptionSequence.UI_ELEMENT_STATES,
        colors: PenpotColors | None = None,
    ) -> SVGVariations:
        """Generates variations sequentially, one at a time, accounting for limitations in response token count
        (~4K for GPT-4o, which is not enough for multiple variations at once).

        :param variation_scope: describes the scope of variations to apply in generation
        :param variation_description_sequence: a sequence of instructions describing what to do for each variation
        :param colors: the colors used in the design, which shall be considered in the generation process
        :return: the variations
        """
        svg_for_variation, refactored_snippets = self._prepare_for_variations()
        conversation = self._create_variations_conversation()

        variation_scope_prompt = self._create_variation_scope_prompt(variation_scope, colors)

        initial_variation_query = (
            "In the following, your task is to create variations of the SVG, one variation at a time. "
            "Whenever you output a variation, prefix it with a level 2 title "
            "(markdown prefix `## `) that names the variation, "
            "followed by the respective code snippet.\n"
            "In general, you may do the following: " + variation_scope_prompt + "\n\n"
            "Here are the instructions for the first variation:\n"
        )

        variation_prompt_template = 'Create a variation corresponding to the description: "%s".'

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

        variations = SVGVariations(
            self.svg,
            all_variations_dict,
            refactored_svg_snippets=refactored_snippets,
            conversation=conversation,
        )
        variations.write_results(self.result_writer)
        return variations

    def create_variations_from_example_present_at_once(
        self,
        example_variations: SVGVariations,
        colors: PenpotColors | None = None,
    ) -> SVGVariations:
        """Generates variations based on an example set of variations that are presented to the model initially.
        Given the example variations (original, (variation_1, variation_2, ...)), the model is asked to generate,
        the same kinds of variations for another UI element - one at atime, but in a single conversation.

        :param example_variations: the example variations
        :param colors: the colors used in the design, which shall be considered in the generation process
        :return: the variations
        """
        system_prompt = (
            DesignPromptBuilder(
                "You are a design assistant tasked with creating variations of an SVG. "
                "You will be presented with examples of variations of a UI element, "
                "and your task is to apply the same variation "
                "principles to another UI element. "
                "In each response you are to return a single variation. "
            )
            .with_colors(colors)
            .build()
        )

        conversation = self._create_refactoring_conversation(system_prompt=system_prompt)

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

        variations = SVGVariations(self.svg, variations_dict, conversation=conversation)
        variations.write_results(self.result_writer)
        self.result_writer.write_text_file(
            self.FILENAME_VARIATION_TRANSFER_EXAMPLE_PRESENTED, example_variations.to_html()
        )
        return variations

    def create_variations_from_example(
        self,
        example_variations: SVGVariations,
        colors: PenpotColors | None = None,
    ) -> SVGVariations:
        """Generates variations based on an example set of variations that are presented to the model one
        at a time, i.e. in each conversation, the model is given one example (original, variation) and is
        asked to create the same type of variation for another UI element.

        :param example_variations: the example variations; if there are multiple variations, then there
            will be a separate conversation for each variation asking the model to create that kind of variation
        :param colors: the colors used in the design, which shall be considered in the generation process
        :return: the variations
        """
        system_prompt = (
            DesignPromptBuilder(
                "You are a design assistant tasked with creating a variation of an SVG. "
                "You will be presented with an example, i.e. an original design and a variation thereof. "
                "Your task is analyze the way in which the variation differs from the original "
                "and then apply the same mechanisms to another UI element. "
            )
            .with_colors(colors)
            .build()
        )

        variations_dict = {}
        conversations = []
        for _i, (name, svg_text) in enumerate(example_variations.variations_dict.items()):
            conversation = self._create_refactoring_conversation(system_prompt=system_prompt)
            prompt = (
                "Here is the example pair (original and variation):\n\n"
                f"This is the original design:\n```{example_variations.original_svg.to_string()}```\n\n"
                f"This is the variation '{name}':\n```{svg_text}```\n\n"
                f"Based on this example, apply the same type of variation to this design:\n```{self.svg.to_string()}```\n"
            )
            response = conversation.query(prompt)
            code_snippets = response.get_code_snippets()
            if len(code_snippets) == 0:
                log.warning(f"Received no code snippets for '{name}'")
                continue
            if len(code_snippets) > 1:
                log.warning("Received more than one code snippet in response; using the first one")
            variations_dict[name] = code_snippets[0].code
            conversations.append(conversation)

        variations = SVGVariations(self.svg, variations_dict, conversations)
        variations.write_results(self.result_writer)
        self.result_writer.write_text_file("example_presented.html", example_variations.to_html())
        return variations
