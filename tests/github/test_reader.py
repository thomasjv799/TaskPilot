import base64
import pytest
from unittest.mock import MagicMock
from service.github.reader import GitHubReader, RepoContext


def make_reader(get_responses: dict) -> GitHubReader:
    client = MagicMock()
    def fake_get(path, params=None):
        return get_responses.get(path, [])
    client.get.side_effect = fake_get
    client.post.return_value = {"data": {"user": {"projectV2": {"items": {"nodes": []}}}}}
    return GitHubReader(client=client, repo="owner/repo", project_number=1)


def test_read_context_returns_repo_context():
    encoded_readme = base64.b64encode(b"# My Project").decode()
    reader = make_reader({
        "/repos/owner/repo/contents/README.md": {"content": encoded_readme + "\n", "encoding": "base64"},
        "/repos/owner/repo/contents/docs": [],
        "/repos/owner/repo/issues": [{"title": "Bug #1", "number": 1, "labels": []}],
        "/repos/owner/repo/commits": [{"commit": {"message": "fix: typo"}}],
        "/repos/owner/repo/pulls": [],
    })
    ctx = reader.read_context()
    assert isinstance(ctx, RepoContext)
    assert "My Project" in ctx.readme
    assert len(ctx.open_issues) == 1
    assert ctx.open_issues[0]["title"] == "Bug #1"


def test_missing_readme_returns_empty_string():
    client = MagicMock()
    client.get.side_effect = Exception("404")
    client.post.return_value = {"data": {"user": {"projectV2": {"items": {"nodes": []}}}}}
    reader = GitHubReader(client=client, repo="owner/repo", project_number=1)
    ctx = reader.read_context()
    assert ctx.readme == ""


def test_read_context_includes_recent_commits():
    commits = [
        {"commit": {"message": f"commit {i}"}} for i in range(5)
    ]
    encoded = base64.b64encode(b"readme").decode()
    reader = make_reader({
        "/repos/owner/repo/contents/README.md": {"content": encoded, "encoding": "base64"},
        "/repos/owner/repo/contents/docs": [],
        "/repos/owner/repo/issues": [],
        "/repos/owner/repo/commits": commits,
        "/repos/owner/repo/pulls": [],
    })
    ctx = reader.read_context()
    assert len(ctx.recent_commits) == 5
