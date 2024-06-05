from langchain_openai.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

from penai.config import get_config
from penai.svg import PenpotShapeElement

cfg = get_config()


class SVGVariationsGenerator:

    def __init__(self, shape: PenpotShapeElement, semantics: str, verbose: bool = True, num_variations: int = 5):
        llm = ChatOpenAI(mode="gpt-4o", temperature=0, max_tokens=None)  # type: ignore
        memory = ConversationBufferMemory()
        self.conversation = ConversationChain(llm=llm, memory=memory)
        self.verbose = verbose

        # create simplified SVG (without the bloat)
        svg = shape.to_svg()
        svg.strip_penpot_tags()

        self._query(
            f"The semantics of the following SVG can be summarized using the term(s) '{semantics}'. "  
            "Refactor the SVG to make the shapes that are being used explicit (where applicable), "
            "making use of the respective shape tags (rect, circle, ellipse, etc.) whenever possible. "
            "Be sure to maintain any cutouts that are present in the original SVG by using appropriate masks.\n\n"
            f"```{svg.to_string()}```")

        self._query(
            f"Create {num_variations} variations of the SVG. "
            f"Modify shapes, foreground colors and relative positioning, but stay close to the original design. "
            "For each variation, create a level 2 heading (using `.h2`) that names the variation "
            "followed by the respective code snippet.")

    def _query(self, query):
        response = self.conversation.run(query)
        if self.verbose:
            print(response)
        return response
