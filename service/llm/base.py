from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[Message]) -> str:
        ...
