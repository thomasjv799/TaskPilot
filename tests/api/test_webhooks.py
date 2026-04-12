# tests/api/test_webhooks.py
import hashlib
import hmac
import json as json_module
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


def make_signed_request(client, payload_dict, event):
    """Helper: make a properly signed webhook request."""
    secret = "test-secret"
    body = json_module.dumps(payload_dict).encode()
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhook/github",
        content=body,
        headers={
            "X-GitHub-Event": event,
            "X-Hub-Signature-256": sig,
            "Content-Type": "application/json",
        },
    )


def test_webhook_issue_closed_returns_200(mock_bot, mock_config, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    client = make_client(mock_bot, mock_config)
    response = make_signed_request(
        client,
        {"action": "closed", "issue": {"title": "Fix login", "html_url": "https://github.com/o/r/issues/1"}},
        "issues"
    )
    assert response.status_code == 200


def test_webhook_unknown_event_returns_200(mock_bot, mock_config, monkeypatch):
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", "test-secret")
    client = make_client(mock_bot, mock_config)
    response = make_signed_request(
        client,
        {"action": "labeled", "label": {"name": "bug"}},
        "label"
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


def test_webhook_no_secret_configured_returns_401(mock_bot, mock_config, monkeypatch):
    monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={"action": "closed"},
        headers={"X-GitHub-Event": "issues"},
    )
    assert response.status_code == 401
