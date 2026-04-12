# tests/api/test_reminders.py
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from service.llm.mock import MockProvider
from service.github.reader import RepoContext


def make_issue(title, due_date, assignee):
    labels = []
    if due_date:
        labels.append({"name": f"due:{due_date.isoformat()}"})
    assignees = [{"login": assignee}] if assignee else []
    return {"title": title, "html_url": "https://github.com/o/r/issues/1", "labels": labels, "assignees": assignees}


def make_client(bot, config, issues: list):
    from service.main import create_app
    reader = MagicMock()
    reader.read_context.return_value = RepoContext(
        readme="", docs={}, open_issues=issues, recent_commits=[], open_prs=[], project_board_items=[]
    )
    app = create_app(
        config=config, bot=bot, planner=MagicMock(),
        reader=reader, writer=MagicMock(), llm=MockProvider(),
    )
    return TestClient(app)


def test_due_today_sends_dm(mock_bot, mock_config):
    mock_config.discord.user_map = {"alice": "111"}
    issues = [make_issue("Fix login", date.today(), "alice")]
    client = make_client(mock_bot, mock_config, issues)
    client.post("/reminders/owner/repo")
    mock_bot.send_dm.assert_called_once()
    call_args = mock_bot.send_dm.call_args[0]
    assert call_args[0] == "111"
    assert "Fix login" in call_args[1]


def test_overdue_posts_to_channel(mock_bot, mock_config):
    mock_config.discord.user_map = {"bob": "222"}
    yesterday = date.today() - timedelta(days=1)
    issues = [make_issue("Add tests", yesterday, "bob")]
    client = make_client(mock_bot, mock_config, issues)
    client.post("/reminders/owner/repo")
    mock_bot.send_channel_message.assert_called_once()
    text = mock_bot.send_channel_message.call_args[0][1]
    assert "OVERDUE" in text
    assert "Add tests" in text


def test_no_due_label_skips_issue(mock_bot, mock_config):
    issues = [make_issue("Refactor DB", None, "alice")]
    client = make_client(mock_bot, mock_config, issues)
    client.post("/reminders/owner/repo")
    mock_bot.send_dm.assert_not_called()
    mock_bot.send_channel_message.assert_not_called()


def test_missing_user_map_entry_posts_warning(mock_bot, mock_config):
    mock_config.discord.user_map = {}
    issues = [make_issue("Fix bug", date.today(), "alice")]
    client = make_client(mock_bot, mock_config, issues)
    client.post("/reminders/owner/repo")
    mock_bot.send_dm.assert_not_called()
    mock_bot.send_channel_message.assert_called_once()
    text = mock_bot.send_channel_message.call_args[0][1]
    assert "alice" in text
    assert "no Discord mapping" in text
