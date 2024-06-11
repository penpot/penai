import base64
from collections.abc import Callable
from copy import copy, deepcopy
from functools import cached_property
from io import BytesIO
from typing import Any, Generic, Self, TypeAlias, TypeVar

import httpx
import markdown
from bs4 import BeautifulSoup
from langchain.memory import ConversationBufferMemory
from langchain_core.messages import HumanMessage
from PIL.Image import Image

from penai.llm.llm_model import RegisteredLLM


class Response:
    def __init__(self, response_text: str):
        self.text = response_text

    @cached_property
    def html(self) -> str:
        return markdown.markdown(self.text)

    @cached_property
    def soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.html, features="html.parser")

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
        """Issues the given query and returns the model's text response.

        :param query: the query
        :return: the response text
        """
        self.memory.chat_memory.add_user_message(query)
        ai_message = self.llm.invoke(self.memory.chat_memory.messages)
        self.memory.chat_memory.add_ai_message(ai_message)
        response_text = ai_message.content
        if self.verbose:
            print(response_text)
        return response_text

    def query(self, query: QueryType) -> TResponse:
        return self.response_factory(self.query_text(query))

    def clone(self) -> Self:
        clone = copy(self)
        clone.memory = deepcopy(self.memory)
        return clone


class HumanMessageBuilder:
    def __init__(self, text_message: str | None = None):
        self._content: list[dict[str, Any]] = []
        if text_message is not None:
            self._add_text_message(text_message)

    def _add_text_message(self, msg: str) -> None:
        self._content.append({"type": "text", "text": msg})

    def with_text_message(self, text_message: str) -> Self:
        self._add_text_message(text_message)
        return self

    def _add_image_from_bytes(self, image_bytes: bytes) -> None:
        image_data = base64.b64encode(image_bytes).decode("utf-8")
        self._content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        )

    def with_image_from_url(self, image_url: str) -> Self:
        image_bytes = httpx.get(image_url).content
        self._add_image_from_bytes(image_bytes)
        return self

    def with_image(self, image: Image) -> Self:
        byte_buffer = BytesIO()
        image.save(byte_buffer, format="PNG")
        image_bytes = byte_buffer.getvalue()
        self._add_image_from_bytes(image_bytes)
        return self

    def build(self) -> HumanMessage:
        return HumanMessage(content=self._content)  # type: ignore
