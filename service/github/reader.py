from __future__ import annotations
import base64
from dataclasses import dataclass
from .client import GitHubClient


@dataclass
class RepoContext:
    readme: str
    docs: dict[str, str]
    open_issues: list[dict]
    recent_commits: list[dict]
    open_prs: list[dict]
    project_board_items: list[dict]


class GitHubReader:
    def __init__(self, client: GitHubClient, repo: str, project_number: int):
        self.client = client
        self.repo = repo
        self.project_number = project_number

    def read_context(self) -> RepoContext:
        return RepoContext(
            readme=self._read_file("README.md"),
            docs=self._read_docs(),
            open_issues=self._list_open_issues(),
            recent_commits=self._list_recent_commits(),
            open_prs=self._list_open_prs(),
            project_board_items=self._list_project_board_items(),
        )

    def _read_file(self, path: str) -> str:
        try:
            data = self.client.get(f"/repos/{self.repo}/contents/{path}")
            if isinstance(data, dict) and data.get("encoding") == "base64":
                return base64.b64decode(data["content"].replace("\n", "")).decode()
            return ""
        except Exception:
            return ""

    def _read_docs(self) -> dict[str, str]:
        try:
            items = self.client.get(f"/repos/{self.repo}/contents/docs")
            if not isinstance(items, list):
                return {}
            return {
                item["name"]: self._read_file(item["path"])
                for item in items
                if item.get("type") == "file" and item["name"].endswith(".md")
            }
        except Exception:
            return {}

    def _list_open_issues(self) -> list[dict]:
        try:
            return self.client.get(
                f"/repos/{self.repo}/issues",
                params={"state": "open", "per_page": 50},
            )
        except Exception:
            return []

    def _list_recent_commits(self) -> list[dict]:
        try:
            return self.client.get(
                f"/repos/{self.repo}/commits",
                params={"per_page": 20},
            )
        except Exception:
            return []

    def _list_open_prs(self) -> list[dict]:
        try:
            return self.client.get(
                f"/repos/{self.repo}/pulls",
                params={"state": "open", "per_page": 20},
            )
        except Exception:
            return []

    def _list_project_board_items(self) -> list[dict]:
        owner = self.repo.split("/")[0]
        query = """
        query($owner: String!, $number: Int!) {
          user(login: $owner) {
            projectV2(number: $number) {
              items(first: 50) {
                nodes {
                  id
                  content { ... on Issue { title number state } }
                }
              }
            }
          }
        }
        """
        try:
            data = self.client.post(
                "/graphql",
                json={"query": query, "variables": {"owner": owner, "number": self.project_number}},
            )
            return (
                data.get("data", {})
                .get("user", {})
                .get("projectV2", {})
                .get("items", {})
                .get("nodes", [])
            )
        except Exception:
            return []
