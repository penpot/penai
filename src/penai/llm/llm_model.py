# mypy: disable-error-code="call-arg"
# Langchain uses pydantic validators to turn args into kwargs, this confuses mypy

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
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    GEMINI_1_0_PRO = "gemini-1.0-pro"
    GEMINI_1_0_FLASH = "gemini-1.0-flash"
    GEMINI_PRO = "gemini-pro"
    """Exists but I'm not sure which model it refers to. Gives different (better?) results than GEMINI_1_5_PRO."""
    CLAUDE_3_OPUS = "claude-3-opus-20240229"
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20240620"

    def create_model(
        self,
        max_tokens: int | None = None,
        temperature: float = 0,
        require_json: bool = False,
    ) -> BaseLanguageModel:
        """:param max_tokens: the maximum number of tokens to generate in the response; set to None for no limit.
        :param temperature: the generation temperature which controls the randomness of the output. 0 is typically deterministic
            (save for equal token probabilities). Higher values increase randomness.
        :param require_json: whether to constrain the model to only (valid) JSON.
            For OpenAI models, this requires that the term "JSON" also appear in a system or user prompt.
            For other models, it is currently unsupported.
        :return:
        """

        def require_json_unsupported() -> None:
            if require_json:
                raise ValueError(f"Constraining output to JSON is not supported for {self}.")

        match self:
            case RegisteredLLM.GPT4O | RegisteredLLM.GPT4:
                model_kwargs = {}
                if require_json:
                    model_kwargs["response_format"] = {"type": "json_object"}
                return ChatOpenAI(
                    model=self.value,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=cfg.openai_api_key,
                    model_kwargs=model_kwargs,
                )
            case RegisteredLLM.GEMINI_1_5_PRO | RegisteredLLM.GEMINI_1_5_FLASH | RegisteredLLM.GEMINI_1_0_PRO | RegisteredLLM.GEMINI_1_0_FLASH | RegisteredLLM.GEMINI_PRO:
                # NOTE: In langchain-google, the changes necessary to support require_json were merged on June 10, 2024.
                # https://github.com/langchain-ai/langchain-google/pull/228
                # TODO This code should be updated to use the require_json parameter once the changes are released.
                require_json_unsupported()
                return ChatGoogleGenerativeAI(
                    model=self.value,
                    google_api_key=cfg.gemini_api_key,
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            case RegisteredLLM.CLAUDE_3_OPUS:
                require_json_unsupported()
                if max_tokens is None:
                    # Anthropic doesn't accept None for max_tokens. 4096 is the maximal allowed value.
                    max_tokens = 4096
                return ChatAnthropic(
                    model_name=self.value,
                    api_key=cfg.anthropic_api_key,
                    temperature=temperature,
                    max_tokens_to_sample=max_tokens,
                )
            case _:
                raise NotImplementedError(self)
