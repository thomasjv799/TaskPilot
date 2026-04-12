from __future__ import annotations
from pydantic import BaseModel
import yaml


class GithubConfig(BaseModel):
    repo: str
    project_number: int


class DiscordConfig(BaseModel):
    project_channel_id: str
    user_map: dict[str, str]


class LLMConfig(BaseModel):
    provider: str
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
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(**data)
