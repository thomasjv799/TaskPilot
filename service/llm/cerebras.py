from cerebras.cloud.sdk import Cerebras
from .base import LLMProvider, Message


class CerebrasProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = Cerebras(api_key=api_key)
        self.model = model

    def complete(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return response.choices[0].message.content
