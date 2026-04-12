import pytest
from unittest.mock import patch, MagicMock
from service.llm.base import LLMProvider, Message
from service.llm.mock import MockProvider
from service.llm.factory import create_provider
from service.config import LLMConfig


def test_message_dataclass():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_mock_provider_returns_configured_response():
    provider = MockProvider(response="sprint plan here")
    result = provider.complete([Message(role="user", content="plan my sprint")])
    assert result == "sprint plan here"


def test_mock_provider_records_all_calls():
    provider = MockProvider(response="ok")
    msgs1 = [Message(role="user", content="first")]
    msgs2 = [Message(role="user", content="second")]
    provider.complete(msgs1)
    provider.complete(msgs2)
    assert len(provider.calls) == 2
    assert provider.calls[0][0].content == "first"
    assert provider.calls[1][0].content == "second"


def test_mock_provider_default_response():
    provider = MockProvider()
    result = provider.complete([Message(role="user", content="hi")])
    assert isinstance(result, str)
    assert len(result) > 0


def test_llm_provider_is_abstract():
    import inspect
    assert inspect.isabstract(LLMProvider)


# Factory tests


def test_factory_creates_groq_provider():
    cfg = LLMConfig(provider="groq", model="llama-3.1-70b-versatile")
    with patch("service.llm.factory.GroqProvider") as MockGroq:
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            create_provider(cfg)
            MockGroq.assert_called_once_with(api_key="test-key", model="llama-3.1-70b-versatile")


def test_factory_creates_cerebras_provider():
    cfg = LLMConfig(provider="cerebras", model="llama3.1-70b")
    with patch("service.llm.factory.CerebrasProvider") as MockCerebras:
        with patch.dict("os.environ", {"CEREBRAS_API_KEY": "test-key"}):
            create_provider(cfg)
            MockCerebras.assert_called_once_with(api_key="test-key", model="llama3.1-70b")


def test_factory_creates_ollama_provider():
    cfg = LLMConfig(provider="ollama", model="llama3")
    with patch("service.llm.factory.OllamaProvider") as MockOllama:
        create_provider(cfg)
        MockOllama.assert_called_once_with(model="llama3")


def test_factory_groq_requires_env_var():
    cfg = LLMConfig(provider="groq", model="llama-3.1-70b-versatile")
    with pytest.raises(KeyError):
        with patch.dict("os.environ", {}, clear=True):
            create_provider(cfg)
