from enum import Enum

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseLanguageModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI

from penai.config import get_config

cfg = get_config()


class RegisteredLLM(Enum):
    # keep value as the model name required by the langchain constructor
    GPT4O = "gpt-4o"
    GPT4 = "gpt-4"
    GEMINI_15_PRO = "gemini-1.5-pro"
    GEMINI_15_FLASH = "gemini-1.5-flash"
    GEMINI_10_PRO = "gemini-1.0-pro"
    GEMINI_10_FLASH = "gemini-1.0-flash"
    GEMINI_PRO = "gemini-pro"
    """Exists but I'm not sure which model it refers to. Gives different (better?) results than GEMINI_15_PRO."""
    CLAUDE3_OPUS = "claude-3-opus-20240229"

    def create_model(
        self,
        max_tokens: int | None = None,
        temperature: float = 0,
    ) -> BaseLanguageModel:
        match self:
            # NOTE: annoyingly, all models have different parameter names for the same things...
            # makes for a lot of boilerplate code
            case RegisteredLLM.GPT4O:
                return ChatOpenAI(
                    model=self.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=cfg.openai_api_key,
                )
            case RegisteredLLM.GPT4:
                return ChatOpenAI(
                    model=self.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=cfg.openai_api_key,
                )
            case RegisteredLLM.GEMINI_15_PRO:
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            case RegisteredLLM.GEMINI_15_FLASH:
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            case RegisteredLLM.GEMINI_10_PRO:
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            case RegisteredLLM.GEMINI_10_FLASH:
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            case RegisteredLLM.GEMINI_PRO:
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            case RegisteredLLM.CLAUDE3_OPUS:
                # Anthropic doesn't accept None for max_tokens. 4096 is the maximal allowed value.
                if max_tokens is None:
                    max_tokens = 4096
                return ChatAnthropic(
                    model=self.value,
                    anthropic_api_key=cfg.anthropic_api_key,
                    temperature=temperature,
                    max_tokens_to_sample=max_tokens,
                )
            case _:
                raise NotImplementedError(self)
