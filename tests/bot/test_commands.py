import json
import pytest
from service.bot.commands import parse_command, CreateTaskCommand
from service.llm.mock import MockProvider


def test_parse_create_task_returns_command():
    mock_response = json.dumps({
        "title": "Set up CI pipeline",
        "body": "Add GitHub Actions for automated tests",
        "assignee": "alice",
    })
    llm = MockProvider(response=mock_response)
    cmd = parse_command("create task: set up CI pipeline, assign to alice", llm)
    assert isinstance(cmd, CreateTaskCommand)
    assert cmd.title == "Set up CI pipeline"
    assert cmd.assignee == "alice"


def test_parse_non_task_message_returns_none():
    llm = MockProvider(response="null")
    cmd = parse_command("hey team, great work today!", llm)
    assert cmd is None


def test_parse_add_task_variant():
    mock_response = json.dumps({
        "title": "Write unit tests",
        "body": "Cover the auth module",
        "assignee": None,
    })
    llm = MockProvider(response=mock_response)
    cmd = parse_command("add task: write unit tests for auth", llm)
    assert isinstance(cmd, CreateTaskCommand)
    assert cmd.assignee is None


def test_parse_handles_malformed_llm_response():
    llm = MockProvider(response="I cannot parse this")
    cmd = parse_command("create task: something", llm)
    assert cmd is None
