import base64
import re
from collections.abc import Callable
from copy import copy, deepcopy
from functools import cached_property
from io import BytesIO
from typing import Any, Generic, Self, TypeAlias, TypeVar, cast

import bs4
import httpx
import markdown
from bs4 import BeautifulSoup
from langchain.globals import set_llm_cache
from langchain.memory import ConversationBufferMemory
from langchain_community.cache import SQLiteCache
from langchain_core.language_models import BaseLanguageModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from PIL.Image import Image
from pydantic import BaseModel

from penai.config import get_config, pull_from_remote
from penai.llm.llm_model import RegisteredLLM, RegisteredLLMParams
from penai.llm.utils import PromptVisualizer

USE_LLM_CACHE_DEFAULT = True
cfg = get_config()
_is_cache_enabled = False


class CodeSnippet:
    def __init__(self, code_tag: bs4.element.Tag):
        code = code_tag.text
        language_match = re.match(r"(\w+)\s*", code)
        if language_match:
            language = language_match.group(1)
            code = code[len(language_match.group(0)) :]
        else:
            language = None

        self.code: str = code
        """
        the actual code snippet
        """
        self.code_tag = code_tag
        """
        the HTML code tag from the parsed LLM response in which the code snippet is embedded
        """
        self.language: str | None = language
        """
        the language that was declared in the LLM's markdown response (succeeding the triple backtick code delimiter), if any
        """

    def get_preceding_heading(self, heading_level: int) -> str | None:
        heading = self.code_tag.find_previous(f"h{heading_level}")
        if heading is None:
            return None
        else:
            return heading.text


class Response:
    def __init__(self, response_text: str):
        self.text = response_text

    @cached_property
    def html(self) -> str:
        def replace_code(m: re.Match) -> str:
            code = m.group(1)
            code = re.sub("\n\\s*\n", "\n", code)
            return "```" + code + "```"

        # TODO: Workaround for limitation in `markdown` library.
        # The library `markdown` cannot deal with empty lines in code blocks, so we remove them
        text = re.sub(r"```(.*?)```", replace_code, self.text, flags=re.DOTALL)

        return markdown.markdown(text)

    @cached_property
    def soup(self) -> BeautifulSoup:
        return BeautifulSoup(self.html, features="html.parser")

    def get_code_snippets(self) -> list[CodeSnippet]:
        """Retrieves all (multi-line) code snippets in the response.

        :return: the list of code snippets
        """
        code_snippets = []
        for code_tag in self.soup.find_all("code"):
            if "\n" not in code_tag.text:  # skip inline code snippets
                continue
            code_snippets.append(CodeSnippet(code_tag))
        return code_snippets

    def get_code_in_sections(self, heading_level: int) -> dict[str, CodeSnippet]:
        """Retrieves code snippets in the response that appear under a certain heading level.

        :param heading_level: the heading level (e.g. 2 for markdown prefix "## ")
        :return: a mapping from heading captions to code snippets
        """
        result = {}
        for code_snippet in self.get_code_snippets():
            heading = code_snippet.get_preceding_heading(heading_level)
            if heading is None:
                continue
            result[heading] = code_snippet
        return result


TResponse = TypeVar("TResponse", bound=Response)
QueryType: TypeAlias = str | HumanMessage


class Conversation(Generic[TResponse]):
    def __init__(
        self,
        model: RegisteredLLM = RegisteredLLM.GPT4O,
        verbose: bool = True,
        response_factory: Callable[[str], TResponse] = Response,  # type: ignore
        system_prompt: str | None = None,
        require_json: bool = False,
        use_cache: bool = USE_LLM_CACHE_DEFAULT,
        **model_options: RegisteredLLMParams,
    ):
        global _is_cache_enabled
        if use_cache:
            if not _is_cache_enabled:
                pull_from_remote(cfg.llm_responses_cache_path, force=True)
                cache = SQLiteCache(database_path=cfg.llm_responses_cache_path)
                set_llm_cache(cache)
                _is_cache_enabled = True
        else:
            if _is_cache_enabled:
                raise ValueError(
                    "Caching is already enabled. Since caching is enabled globally, it cannot be disabled for this conversation."
                )
        self.memory = ConversationBufferMemory()
        self.llm = model.create_model(**model_options)
        self.verbose = verbose
        self.response_factory = response_factory
        if system_prompt is not None:
            self.memory.chat_memory.add_message(
                SystemMessage(content=system_prompt),
            )

    def to_html(self, prompt_visualizer: PromptVisualizer | None = None) -> str:
        if prompt_visualizer is None:
            prompt_visualizer = PromptVisualizer()

        return prompt_visualizer.messages_to_html(self.memory.chat_memory.messages)

    def display_html(self, prompt_visualizer: PromptVisualizer | None = None) -> None:
        if prompt_visualizer is None:
            prompt_visualizer = PromptVisualizer()

        prompt_visualizer.display_messages(self.memory.chat_memory.messages)

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


class MessageBuilder:
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
                "image_url": {"url": f"data:image/png;base64,{image_data}"},
            },
        )

    def with_image_from_url(self, image_url: str) -> Self:
        image_bytes = httpx.get(image_url, follow_redirects=True).content
        assert len(image_bytes), f"Failed to download image from URL: {image_url}"
        self._add_image_from_bytes(image_bytes)
        return self

    def with_image(self, image: Image) -> Self:
        byte_buffer = BytesIO()
        image.save(byte_buffer, format="PNG")
        image_bytes = byte_buffer.getvalue()
        self._add_image_from_bytes(image_bytes)
        return self

    # NOTE: It would be _cleaner_ to use a generic type for the argument and return type here but the typing
    # system in Python does currently not seem to support TypeVars that are bound to a type that is a subclass
    # of a specific class.
    def build(self, message_type: type[BaseMessage] = HumanMessage) -> BaseMessage:
        return message_type(content=self._content)  # type: ignore

    def build_system_message(self) -> SystemMessage:
        return cast(SystemMessage, self.build(SystemMessage))

    def build_human_message(self) -> HumanMessage:
        return cast(HumanMessage, self.build(HumanMessage))

    def build_ai_message(self) -> AIMessage:
        return cast(AIMessage, self.build(AIMessage))


class PromptBuilder:
    def __init__(self, initial_prompt: str = ""):
        self._content = initial_prompt

    def with_text(self, text: str, breaks: int = 0) -> Self:
        self._content += "\n" * breaks
        self._content += text
        return self

    def with_conditional_text(self, condition: bool, text: str) -> Self:
        if condition:
            self._content += text
        return self

    def build(self) -> str:
        return self._content


class LLMBaseModel(BaseModel):
    @classmethod
    def from_llm(cls, model: BaseLanguageModel, messages: list[BaseMessage]) -> Self:
        """Try to invoke the model with structured output and fall back to non-structured output if it is not available."""
        try:
            model = model.with_structured_output(cls, method="json_mode")  # type: ignore
            response_dict = model.invoke(messages)
            response = cls.model_validate(response_dict)
        except ValueError:
            conversation_response = Response(model.invoke(messages).content)

            try:
                response_json = conversation_response.get_code_snippets()[0].code
            except IndexError:
                response_json = conversation_response.text

            response = cls.model_validate_json(response_json)

        return response
