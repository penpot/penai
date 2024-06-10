from collections.abc import Callable
from copy import copy, deepcopy
from typing import Generic, Self, TypeAlias, TypeVar

import markdown
from bs4 import BeautifulSoup
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage

from penai.llm.llm_model import RegisteredLLM


class Response:
    def __init__(self, response_text: str):
        self.text = response_text
        self.html = markdown.markdown(response_text)
        self.soup = BeautifulSoup(self.html, features="html.parser")

    def get_code_in_sections(self, heading_level: int) -> dict[str, str]:
        """Retrieves code snippets in the response that appear under a certain heading level.

        :param heading_level: the heading level (e.g. 2 for markdown prefix "## ")
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
QueryType: TypeAlias = str | HumanMessage


class Conversation(Generic[TResponse]):
    def __init__(
        self,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        verbose: bool = True,
        response_factory: Callable[[str], TResponse] = Response,  # type: ignore
    ):
        self.memory = ConversationBufferMemory()
        self.llm = model.create_model()
        self.verbose = verbose
        self.response_factory = response_factory

    def get_full_conversation_string(
        self,
        messages_separator: str = "\n",
    ) -> str:
        return messages_separator.join(
            [message.pretty_repr() for message in self.memory.buffer_as_messages],
        )

    def query_text(self, query: QueryType) -> str:
        self.memory.chat_memory.add_user_message(query)
        ai_message = self.llm.invoke(self.memory.chat_memory.messages)
        self.memory.chat_memory.add_ai_message(ai_message)
        response_text = ai_message.content
        if self.verbose:
            print(response_text)
        return response_text

    def query(self, query: QueryType) -> None:
        self.query_text(query)

    def query_response(self, query: QueryType) -> TResponse:
        return self.response_factory(self.query_text(query))

    def clone(self) -> Self:
        clone = copy(self)
        clone.memory = deepcopy(self.memory)
        return clone
