from enum import Enum

from langchain_core.language_models import BaseLanguageModel
from langchain_openai import ChatOpenAI

from penai.config import get_config

cfg = get_config()


class RegisteredLLM(Enum):
    GPT4O = "gpt-4o"

    def create_model(
        self,
        max_tokens: int | None = None,
        temperature: float = 0,
    ) -> BaseLanguageModel:
        match self:
            case RegisteredLLM.GPT4O:
                return ChatOpenAI(
                    model="gpt-4o",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=cfg.openai_api_key,
                )
            case _:
                raise NotImplementedError(self)
