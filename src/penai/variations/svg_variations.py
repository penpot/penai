import markdown
from bs4 import BeautifulSoup
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_openai.chat_models import ChatOpenAI

from penai.config import get_config
from penai.svg import PenpotShapeElement

cfg = get_config()


class ChatGPTResponse:
    def __init__(self, response_text: str):
        self.text = response_text
        self.html = markdown.markdown(response_text)
        self.soup = BeautifulSoup(self.html, features="html.parser")

    def get_code_in_sections(self, heading_level: int) -> dict[str, str]:
        """Retrieves code snippets in the response that appear under a certain heading level.

        :param heading_level: the heading level (e.g. 2 for markdown prefix `## `)
        :return: a mapping from heading captions to code snippets
        """
        result = {}
        for code in self.soup.find_all("code"):
            heading = code.find_previous(f"h{heading_level}")
            if heading is None:
                continue
            result[heading.text] = code.text
        return result


class SVGVariationsGenerator:
    def __init__(
        self,
        shape: PenpotShapeElement,
        semantics: str,
        verbose: bool = True,
        num_variations: int = 5,
    ):
        llm = ChatOpenAI(model="gpt-4o", temperature=0, max_tokens=None, api_key=cfg.openai_api_key)  # type: ignore
        memory = ConversationBufferMemory()
        self.conversation = ConversationChain(llm=llm, memory=memory)
        self.verbose = verbose

        # create simplified SVG (without the bloat)
        svg = shape.to_svg()
        svg.strip_penpot_tags()

        self._query_text(
            f"The semantics of the following SVG can be summarized using the term(s) '{semantics}'. "
            "Refactor the SVG to make the shapes that are being used explicit (where applicable), "
            "making use of the respective shape tags (rect, circle, ellipse, etc.) whenever possible. "
            "Be sure to maintain any cutouts that are present in the original SVG by using appropriate masks.\n\n"
            f"```{svg.to_string()}```",
        )

        response = self._query_response(
            f"Create {num_variations} variations of the SVG. "
            f"Modify shapes, foreground colors and relative positioning, but stay close to the original design. "
            "For each variation, create a level 2 heading (markdown prefix `## `) that names the variation "
            "followed by the respective code snippet.",
        )
        self.variations = response.get_code_in_sections(2)

    def _query_text(self, query: str) -> str:
        response = self.conversation.run(query)
        if self.verbose:
            print(response)
        return response

    def _query_response(self, query: str) -> ChatGPTResponse:
        return ChatGPTResponse(self._query_text(query))

    def create_variations_html(self) -> str:
        html = "<html><body>"
        html += '<div style="width:60%">'
        html += "<h1>Variations</h1>"
        for name, svg in self.variations.items():
            html += f"<h2>{name}</h2>"
            html += svg
        html += "</div>"
        html += "</body></html>"
        return html
