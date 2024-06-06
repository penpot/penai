from typing import Self

from penai.config import get_config
from penai.llm.conversation import Conversation, Response
from penai.llm.llm_model import RegisteredLLM
from penai.svg import SVG, PenpotShapeElement

cfg = get_config()


class SVGVariationsResponse(Response):
    def get_variations_dict(self) -> dict:
        return self.get_code_in_sections(2)


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
        html += "<h1>Variations</h1>"
        for name, svg in self.variations_dict.items():
            html += f"<h2>{name}</h2>"
            html += svg
        html += "</div>"
        html += "</body></html>"
        return html

    def revise(self, prompt: str) -> "SVGVariations":
        conversation = self.conversation.clone()
        response = conversation.query_response(prompt)
        variations_dict = response.get_variations_dict()
        return SVGVariations(self.original_svg, variations_dict, conversation)


class SVGVariationsGenerator:
    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str,
        verbose: bool = True,
        num_variations: int = 5,
    ):
        self.conversation = SVGVariationsConversation(verbose=verbose)
        self.semantics = semantics
        self.num_variations = num_variations

        # create simplified SVG (without the bloat)
        self.svg = shape.to_svg()
        self.svg.strip_penpot_tags()

    def create_variations(self) -> SVGVariations:
        self.conversation.query(
            f"The semantics of the following SVG can be summarized using the term(s) '{self.semantics}'. "
            "Refactor the SVG to make the shapes that are being used explicit (where applicable), "
            "making use of the respective shape tags (rect, circle, ellipse, etc.) whenever possible. "
            "Be sure to maintain any cutouts that are present in the original SVG by using appropriate masks.\n\n"
            f"```{self.svg.to_string()}```",
        )

        response = self.conversation.query_response(
            f"Create {self.num_variations} variations of the SVG. "
            f"Modify shapes, foreground colors and relative positioning, but stay close to the original design. "
            "For each variation, create a level 2 heading (markdown prefix `## `) that names the variation "
            "followed by the respective code snippet.",
        )
        variations_dict = response.get_code_in_sections(2)
        return SVGVariations(self.svg, variations_dict, self.conversation)
