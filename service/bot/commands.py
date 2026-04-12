from __future__ import annotations
import json
import re
from dataclasses import dataclass
from ..llm.base import LLMProvider, Message


@dataclass
class CreateTaskCommand:
    title: str
    body: str
    assignee: str | None

    async def execute(self, message, bot) -> None:
        from ..github.writer import GitHubWriter, SprintTask
        from ..github.client import GitHubClient

        client = GitHubClient.from_env()
        writer = GitHubWriter(client=client, repo=bot.config.github.repo)
        task = SprintTask(title=self.title, body=self.body, assignee=self.assignee, due_date=None)
        issue = writer.create_issue(task)
        await message.reply(f"✅ Created issue #{issue['number']}: {issue['html_url']}")


_TRIGGER_PHRASES = ("create task", "add task")

PARSE_SYSTEM = (
    'Parse the user message and return JSON: '
    '{"title": "...", "body": "...", "assignee": "github_username or null"}. '
    'If the message is not requesting task creation, return the string null.'
)


def parse_command(text: str, llm: LLMProvider) -> CreateTaskCommand | None:
    if not any(phrase in text.lower() for phrase in _TRIGGER_PHRASES):
        return None

    response = llm.complete([
        Message(role="system", content=PARSE_SYSTEM),
        Message(role="user", content=text),
    ])

    match = re.search(r"\{[\s\S]*\}", response)
    if not match:
        return None

    try:
        data = json.loads(match.group())
        return CreateTaskCommand(
            title=data["title"],
            body=data.get("body", ""),
            assignee=data.get("assignee"),
        )
    except (json.JSONDecodeError, KeyError):
        return None
