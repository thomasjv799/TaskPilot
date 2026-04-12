from .base import LLMProvider, Message


class MockProvider(LLMProvider):
    def __init__(self, response: str = "mock response"):
        self.response = response
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> str:
        self.calls.append(messages)
        return self.response
