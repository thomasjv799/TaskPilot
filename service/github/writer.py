from __future__ import annotations
from dataclasses import dataclass
from datetime import date
from .client import GitHubClient


@dataclass
class SprintTask:
    title: str
    body: str
    assignee: str | None
    due_date: date | None


class GitHubWriter:
    def __init__(self, client: GitHubClient, repo: str):
        self.client = client
        self.repo = repo

    def create_issue(self, task: SprintTask) -> dict:
        labels = []
        if task.due_date:
            label = f"due:{task.due_date.isoformat()}"
            self.ensure_label_exists(label, color="e4e669")
            labels.append(label)

        payload: dict = {
            "title": task.title,
            "body": task.body,
            "labels": labels,
        }
        if task.assignee:
            payload["assignees"] = [task.assignee]

        return self.client.post(f"/repos/{self.repo}/issues", json=payload)

    def close_issue(self, issue_number: int) -> dict:
        return self.client.patch(
            f"/repos/{self.repo}/issues/{issue_number}",
            json={"state": "closed"},
        )

    def ensure_label_exists(self, name: str, color: str = "0075ca") -> None:
        try:
            self.client.post(
                f"/repos/{self.repo}/labels",
                json={"name": name, "color": color},
            )
        except Exception:
            pass  # label already exists — 422 is expected
