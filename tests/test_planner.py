# tests/test_planner.py
import json
import pytest
from datetime import date
from unittest.mock import MagicMock, AsyncMock, patch
from service.planner import Planner, SprintPlan
from service.github.reader import RepoContext
from service.github.writer import SprintTask
from service.llm.mock import MockProvider


def make_context():
    return RepoContext(
        readme="# My App\nA web application for teams.",
        docs={},
        open_issues=[{"title": "Fix login bug", "number": 1}],
        recent_commits=[{"commit": {"message": "fix: typo in README"}}],
        open_prs=[],
        project_board_items=[],
    )


def make_planner(llm_response: str):
    config = MagicMock()
    config.sprint.duration_days = 14
    config.sprint.approval_timeout_hours = 24
    config.discord.project_channel_id = "123"
    llm = MockProvider(response=llm_response)
    reader = MagicMock()
    reader.read_context.return_value = make_context()
    writer = MagicMock()
    writer.create_issue.return_value = {"number": 1, "html_url": "https://github.com/o/r/issues/1"}
    return Planner(config=config, llm=llm, reader=reader, writer=writer), writer


def test_generate_plan_parses_tasks():
    response = json.dumps({
        "summary": "Fix auth and add tests",
        "tasks": [
            {"title": "Fix login bug", "body": "See issue #1", "assignee": "alice", "due_date": "2026-04-20"},
            {"title": "Add unit tests", "body": "Cover auth module", "assignee": None, "due_date": None},
        ],
    })
    planner, _ = make_planner(response)
    plan = planner._generate_plan(make_context())
    assert isinstance(plan, SprintPlan)
    assert plan.summary == "Fix auth and add tests"
    assert len(plan.tasks) == 2
    assert plan.tasks[0].title == "Fix login bug"
    assert plan.tasks[0].assignee == "alice"
    assert plan.tasks[0].due_date == date(2026, 4, 20)
    assert plan.tasks[1].assignee is None
    assert plan.tasks[1].due_date is None


def test_generate_plan_handles_json_wrapped_in_markdown():
    response = f"```json\n{json.dumps({'summary': 'Sprint', 'tasks': []})}\n```"
    planner, _ = make_planner(response)
    plan = planner._generate_plan(make_context())
    assert plan.summary == "Sprint"


def test_generate_plan_raises_on_invalid_json():
    planner, _ = make_planner("Here is your plan: blah blah")
    with pytest.raises(ValueError, match="LLM did not return valid JSON"):
        planner._generate_plan(make_context())


@pytest.mark.asyncio
async def test_approve_creates_issues():
    response = json.dumps({
        "summary": "Sprint",
        "tasks": [
            {"title": "Task A", "body": "body", "assignee": None, "due_date": None},
        ],
    })
    planner, writer = make_planner(response)
    bot = AsyncMock()
    plan = planner._generate_plan(make_context())
    planner._pending[99] = plan
    await planner.approve(message_id=99, bot=bot)
    writer.create_issue.assert_called_once()
    bot.confirm_plan_created.assert_called_once_with(channel_id="123", task_count=1)
    assert 99 not in planner._pending


@pytest.mark.asyncio
async def test_reject_clears_pending():
    planner, _ = make_planner(json.dumps({"summary": "s", "tasks": []}))
    bot = AsyncMock()
    planner._pending[77] = MagicMock()
    await planner.reject(message_id=77, bot=bot)
    assert 77 not in planner._pending
    bot.notify_plan_discarded.assert_called_once()


@pytest.mark.asyncio
async def test_approve_unknown_message_id_is_noop():
    planner, writer = make_planner(json.dumps({"summary": "s", "tasks": []}))
    bot = AsyncMock()
    await planner.approve(message_id=9999, bot=bot)
    writer.create_issue.assert_not_called()
