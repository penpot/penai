from collections.abc import Callable
from copy import copy, deepcopy
from typing import Generic, Self, TypeVar

import markdown
from bs4 import BeautifulSoup
from langchain.chains.conversation.base import ConversationChain
from langchain.memory import ConversationBufferMemory

from penai.llm.llm_model import RegisteredLLM


class Response:
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


TResponse = TypeVar("TResponse", bound=Response)


class Conversation(Generic[TResponse]):
    def __init__(
        self,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        verbose: bool = True,
        response_factory: Callable[[str], TResponse] = Response,  # type: ignore
    ):
        self.memory = ConversationBufferMemory()
        self.chain = ConversationChain(llm=model.create_model(), memory=self.memory)
        self.verbose = verbose
        self.response_factory = response_factory

    def query_text(self, query: str) -> str:
        response = self.chain.run(query)
        if self.verbose:
            print(response)
        return response

    def query(self, query: str) -> None:
        self.query_text(query)

    def query_response(self, query: str) -> TResponse:
        return self.response_factory(self.query_text(query))

    def clone(self) -> Self:
        clone = copy(self)
        clone.memory = deepcopy(self.memory)
        return clone
