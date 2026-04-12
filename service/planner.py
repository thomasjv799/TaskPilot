# service/planner.py
from __future__ import annotations
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import date, timedelta

from .config import Config
from .github.reader import GitHubReader, RepoContext
from .github.writer import GitHubWriter, SprintTask
from .llm.base import LLMProvider, Message


@dataclass
class SprintPlan:
    summary: str
    tasks: list[SprintTask]


_PLAN_SYSTEM = (
    "You are a technical project manager. Analyse the project context and return a JSON sprint plan. "
    "Return only valid JSON with no markdown formatting."
)

_PLAN_USER_TEMPLATE = """\
Generate a sprint plan for the next {duration_days} days (sprint ends {sprint_end}).

README:
{readme}

Open Issues ({issue_count}):
{issues}

Recent Commits:
{commits}

Return JSON exactly:
{{
  "summary": "One sentence sprint goal",
  "tasks": [
    {{
      "title": "Task title",
      "body": "Detailed description",
      "assignee": "github_username or null",
      "due_date": "YYYY-MM-DD or null"
    }}
  ]
}}"""


class Planner:
    def __init__(
        self,
        config: Config,
        llm: LLMProvider,
        reader: GitHubReader,
        writer: GitHubWriter,
    ) -> None:
        self.config = config
        self.llm = llm
        self.reader = reader
        self.writer = writer
        self._pending: dict[int, SprintPlan] = {}

    async def generate_and_propose(self, bot) -> None:
        context = self.reader.read_context()
        plan = self._generate_plan(context)
        message = await bot.propose_plan(
            channel_id=self.config.discord.project_channel_id,
            plan=plan,
        )
        self._pending[message.id] = plan
        asyncio.create_task(self._timeout(message.id, bot))

    async def approve(self, message_id: int, bot) -> None:
        plan = self._pending.pop(message_id, None)
        if plan is None:
            return
        for task in plan.tasks:
            self.writer.create_issue(task)
        await bot.confirm_plan_created(
            channel_id=self.config.discord.project_channel_id,
            task_count=len(plan.tasks),
        )

    async def reject(self, message_id: int, bot) -> None:
        self._pending.pop(message_id, None)
        await bot.notify_plan_discarded(channel_id=self.config.discord.project_channel_id)

    async def _timeout(self, message_id: int, bot) -> None:
        await asyncio.sleep(self.config.sprint.approval_timeout_hours * 3600)
        if message_id in self._pending:
            self._pending.pop(message_id, None)
            await bot.notify_plan_expired(channel_id=self.config.discord.project_channel_id)

    def _generate_plan(self, context: RepoContext) -> SprintPlan:
        sprint_end = date.today() + timedelta(days=self.config.sprint.duration_days)
        prompt = _PLAN_USER_TEMPLATE.format(
            duration_days=self.config.sprint.duration_days,
            sprint_end=sprint_end,
            readme=context.readme[:3000],
            issue_count=len(context.open_issues),
            issues=json.dumps(
                [{"title": i["title"], "number": i["number"]} for i in context.open_issues[:20]],
                indent=2,
            ),
            commits=json.dumps(
                [{"message": c["commit"]["message"][:100]} for c in context.recent_commits[:10]],
                indent=2,
            ),
        )
        response = self.llm.complete([
            Message(role="system", content=_PLAN_SYSTEM),
            Message(role="user", content=prompt),
        ])
        return self._parse_response(response)

    def _parse_response(self, response: str) -> SprintPlan:
        match = re.search(r"\{[\s\S]*\}", response)
        if not match:
            raise ValueError("LLM did not return valid JSON")
        data = json.loads(match.group())
        tasks = [
            SprintTask(
                title=t["title"],
                body=t["body"],
                assignee=t.get("assignee"),
                due_date=date.fromisoformat(t["due_date"]) if t.get("due_date") else None,
            )
            for t in data.get("tasks", [])
        ]
        return SprintPlan(summary=data["summary"], tasks=tasks)
