# tests/api/test_digest.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from service.llm.mock import MockProvider
from service.github.reader import RepoContext


def make_context():
    return RepoContext(
        readme="# App",
        docs={},
        open_issues=[{"title": "Bug"}],
        recent_commits=[{"commit": {"message": "feat: add login"}}],
        open_prs=[],
        project_board_items=[],
    )


def make_client(bot, config, llm_response="Weekly summary here."):
    from service.main import create_app
    reader = MagicMock()
    reader.read_context.return_value = make_context()
    app = create_app(
        config=config,
        bot=bot,
        planner=MagicMock(),
        reader=reader,
        writer=MagicMock(),
        llm=MockProvider(response=llm_response),
    )
    return TestClient(app)


def test_digest_posts_to_discord(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post("/digest/owner/repo")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_bot.send_channel_message.assert_called_once()
    # call_args[0] is positional args tuple: (channel_id, text)
    call_text = mock_bot.send_channel_message.call_args[0][1]
    assert "Weekly Digest" in call_text


def test_digest_includes_llm_summary(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config, llm_response="Great week! Two features shipped.")
    client.post("/digest/owner/repo")
    call_text = mock_bot.send_channel_message.call_args[0][1]
    assert "Great week! Two features shipped." in call_text
