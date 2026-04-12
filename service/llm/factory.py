import os
from .base import LLMProvider
from .groq import GroqProvider
from .cerebras import CerebrasProvider
from .ollama import OllamaProvider
from ..config import LLMConfig


def create_provider(cfg: LLMConfig) -> LLMProvider:
    if cfg.provider == "groq":
        return GroqProvider(api_key=os.environ["GROQ_API_KEY"], model=cfg.model)
    elif cfg.provider == "cerebras":
        return CerebrasProvider(api_key=os.environ["CEREBRAS_API_KEY"], model=cfg.model)
    elif cfg.provider == "ollama":
        return OllamaProvider(model=cfg.model)
    else:
        raise ValueError(f"Unknown LLM provider: {cfg.provider!r}")
