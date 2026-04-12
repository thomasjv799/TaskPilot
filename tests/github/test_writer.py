import pytest
from datetime import date
from unittest.mock import MagicMock, call
from service.github.writer import GitHubWriter, SprintTask


def make_writer():
    client = MagicMock()
    client.post.return_value = {"number": 42, "html_url": "https://github.com/owner/repo/issues/42"}
    client.patch.return_value = {"number": 42, "state": "closed"}
    return GitHubWriter(client=client, repo="owner/repo"), client


def test_create_issue_with_due_date():
    writer, client = make_writer()
    task = SprintTask(
        title="Fix login",
        body="See issue #1",
        assignee="alice",
        due_date=date(2026, 4, 20),
    )
    result = writer.create_issue(task)
    assert result["number"] == 42
    # ensure_label_exists is called first, then create_issue
    # The create call should have the due label and assignee
    create_call = [c for c in client.post.call_args_list if "issues" in c[0][0] and "labels" not in c[0][0]][0]
    assert create_call[1]["json"]["title"] == "Fix login"
    assert create_call[1]["json"]["assignees"] == ["alice"]
    assert "due:2026-04-20" in create_call[1]["json"]["labels"]


def test_create_issue_without_assignee_or_due_date():
    writer, client = make_writer()
    task = SprintTask(title="Refactor DB", body="Clean up models", assignee=None, due_date=None)
    writer.create_issue(task)
    # Only one post call (no label creation)
    assert client.post.call_count == 1
    call_kwargs = client.post.call_args[1]["json"]
    assert "assignees" not in call_kwargs
    assert call_kwargs["labels"] == []


def test_close_issue():
    writer, client = make_writer()
    writer.close_issue(42)
    client.patch.assert_called_once_with(
        "/repos/owner/repo/issues/42",
        json={"state": "closed"},
    )


def test_ensure_label_exists_swallows_conflict():
    writer, client = make_writer()
    client.post.side_effect = Exception("422 Unprocessable Entity")
    writer.ensure_label_exists("due:2026-04-20")  # should not raise
