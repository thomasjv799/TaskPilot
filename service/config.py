from __future__ import annotations
from typing import Literal
from pydantic import BaseModel
import yaml


class GithubConfig(BaseModel):
    repo: str
    project_number: int


class DiscordConfig(BaseModel):
    project_channel_id: str
    user_map: dict[str, str]


class LLMConfig(BaseModel):
    provider: Literal["groq", "cerebras", "ollama"]
    model: str


class SprintConfig(BaseModel):
    duration_days: int = 14
    approval_timeout_hours: int = 24


class Config(BaseModel):
    github: GithubConfig
    discord: DiscordConfig
    llm: LLMConfig
    sprint: SprintConfig = SprintConfig()


def load_config(path: str = ".taskpilot.yml") -> Config:
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Config file not found: {path!r}") from None
    if data is None:
        raise ValueError(f"Config file is empty: {path!r}")
    return Config(**data)
