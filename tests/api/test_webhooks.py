# tests/api/test_webhooks.py
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock


def make_client(bot, config):
    from service.main import create_app
    app = create_app(
        config=config,
        bot=bot,
        planner=MagicMock(),
        reader=MagicMock(),
        writer=MagicMock(),
        llm=MagicMock(),
    )
    return TestClient(app)


def test_webhook_issue_closed_returns_200(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={
            "action": "closed",
            "issue": {"title": "Fix login", "html_url": "https://github.com/o/r/issues/1"},
        },
        headers={"X-GitHub-Event": "issues"},
    )
    assert response.status_code == 200


def test_webhook_unknown_event_returns_200(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={"action": "labeled", "label": {"name": "bug"}},
        headers={"X-GitHub-Event": "label"},
    )
    assert response.status_code == 200


def test_webhook_bad_signature_returns_401(mock_bot, mock_config, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "mysecret")
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={"action": "closed"},
        headers={
            "X-GitHub-Event": "issues",
            "X-Hub-Signature-256": "sha256=badhash",
        },
    )
    assert response.status_code == 401
