from service.llm.base import LLMProvider, Message
from service.llm.mock import MockProvider


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
