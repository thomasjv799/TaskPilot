# TaskPilot Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastAPI + Discord bot service that reads a GitHub repo, generates LLM-powered sprint plans, manages a GitHub Kanban board, and posts updates/reminders to Discord.

**Architecture:** A single Docker container runs a FastAPI app (webhook receiver + REST API) and a persistent Discord bot in the same asyncio event loop. GitHub Actions in target repos call the service's REST API on a schedule for weekly digests and deadline reminders. All LLM logic lives behind an abstract `LLMProvider` interface — swap providers via one config line.

**Tech Stack:** Python 3.11+, FastAPI, discord.py 2.x, httpx, Pydantic v2, PyYAML, groq SDK, cerebras-cloud-sdk, pytest, pytest-asyncio

---

## File Map

```
taskpilot/
├── service/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, app.state wiring
│   ├── config.py                # Pydantic config loader from .taskpilot.yml
│   ├── planner.py               # Sprint planning orchestrator
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py              # LLMProvider ABC + Message dataclass
│   │   ├── mock.py              # MockProvider for tests
│   │   ├── groq.py              # Groq implementation
│   │   ├── cerebras.py          # Cerebras implementation
│   │   ├── ollama.py            # Ollama (local) implementation
│   │   └── factory.py           # create_provider(cfg) -> LLMProvider
│   ├── github/
│   │   ├── __init__.py
│   │   ├── client.py            # PAT-based GitHub HTTP client
│   │   ├── reader.py            # Read-only repo context fetcher
│   │   └── writer.py            # Issue/board mutator
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhooks.py          # POST /webhook/github
│   │   ├── digest.py            # POST /digest/{repo}
│   │   └── reminders.py         # POST /reminders/{repo}
│   └── bot/
│       ├── __init__.py
│       ├── discord_bot.py       # TaskPilotBot (discord.py Bot subclass)
│       └── commands.py          # Ad-hoc command parser
├── actions/
│   ├── taskpilot-weekly.yml
│   └── taskpilot-reminders.yml
├── tests/
│   ├── conftest.py
│   ├── test_config.py
│   ├── test_planner.py
│   ├── llm/
│   │   └── test_llm.py
│   ├── github/
│   │   ├── test_reader.py
│   │   └── test_writer.py
│   ├── api/
│   │   ├── test_webhooks.py
│   │   ├── test_digest.py
│   │   └── test_reminders.py
│   └── bot/
│       └── test_commands.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pytest.ini
├── .env.example
└── .taskpilot.yml.example
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `pytest.ini`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.taskpilot.yml.example`
- Create: All `__init__.py` files (empty)

- [ ] **Step 1: Create requirements.txt**

```
fastapi>=0.115.0
uvicorn[standard]>=0.30.0
discord.py>=2.4.0
httpx>=0.27.0
pydantic>=2.7.0
pyyaml>=6.0.1
groq>=0.11.0
cerebras-cloud-sdk>=1.0.0
pytest>=8.0.0
pytest-asyncio>=0.23.0
httpx>=0.27.0
```

- [ ] **Step 2: Create pytest.ini**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 3: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "service.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 4: Create docker-compose.yml**

```yaml
services:
  taskpilot:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    restart: unless-stopped
    volumes:
      - ./.taskpilot.yml:/app/.taskpilot.yml:ro
```

- [ ] **Step 5: Create .env.example**

```bash
GITHUB_TOKEN=ghp_your_token_here
DISCORD_BOT_TOKEN=your_discord_bot_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
TASKPILOT_SERVICE_URL=https://your-server.example.com

# Set one of these based on llm.provider in .taskpilot.yml
GROQ_API_KEY=gsk_your_key_here
CEREBRAS_API_KEY=your_cerebras_key_here
```

- [ ] **Step 6: Create .taskpilot.yml.example**

```yaml
github:
  repo: owner/repo
  project_number: 1

discord:
  project_channel_id: "123456789012345678"
  user_map:
    alice_gh: "111222333444555666"
    bob_gh: "777888999000111222"

llm:
  provider: groq          # groq | cerebras | ollama
  model: llama-3.1-70b-versatile

sprint:
  duration_days: 14
  approval_timeout_hours: 24
```

- [ ] **Step 7: Create empty package init files**

Create the following as empty files (just `# intentionally empty`):
- `service/__init__.py`
- `service/llm/__init__.py`
- `service/github/__init__.py`
- `service/api/__init__.py`
- `service/bot/__init__.py`
- `tests/__init__.py`
- `tests/llm/__init__.py`
- `tests/github/__init__.py`
- `tests/api/__init__.py`
- `tests/bot/__init__.py`

- [ ] **Step 8: Verify Python environment**

```bash
pip install -r requirements.txt
python -c "import fastapi, discord, httpx, pydantic, yaml, groq; print('all imports ok')"
```

Expected: `all imports ok`

- [ ] **Step 9: Commit**

```bash
git add requirements.txt pytest.ini Dockerfile docker-compose.yml .env.example .taskpilot.yml.example service/ tests/
git commit -m "chore: project scaffolding and package structure"
```

---

## Task 2: Config Loader

**Files:**
- Create: `service/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config.py
import pytest
import yaml
from service.config import load_config, Config

def write_config(tmp_path, data):
    f = tmp_path / ".taskpilot.yml"
    f.write_text(yaml.dump(data))
    return str(f)

VALID = {
    "github": {"repo": "owner/repo", "project_number": 1},
    "discord": {
        "project_channel_id": "123",
        "user_map": {"alice": "456", "bob": "789"},
    },
    "llm": {"provider": "groq", "model": "llama-3.1-70b-versatile"},
    "sprint": {"duration_days": 14, "approval_timeout_hours": 24},
}

def test_load_valid_config(tmp_path):
    config = load_config(write_config(tmp_path, VALID))
    assert config.github.repo == "owner/repo"
    assert config.github.project_number == 1
    assert config.discord.project_channel_id == "123"
    assert config.discord.user_map["alice"] == "456"
    assert config.llm.provider == "groq"
    assert config.sprint.duration_days == 14

def test_sprint_defaults_when_omitted(tmp_path):
    data = {**VALID}
    del data["sprint"]
    config = load_config(write_config(tmp_path, data))
    assert config.sprint.duration_days == 14
    assert config.sprint.approval_timeout_hours == 24

def test_missing_github_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "github"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))

def test_missing_discord_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "discord"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))

def test_missing_llm_raises(tmp_path):
    data = {k: v for k, v in VALID.items() if k != "llm"}
    with pytest.raises(Exception):
        load_config(write_config(tmp_path, data))
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.config'`

- [ ] **Step 3: Implement service/config.py**

```python
# service/config.py
from __future__ import annotations
from pydantic import BaseModel
import yaml


class GithubConfig(BaseModel):
    repo: str
    project_number: int


class DiscordConfig(BaseModel):
    project_channel_id: str
    user_map: dict[str, str]


class LLMConfig(BaseModel):
    provider: str
    model: str


class SprintConfig(BaseModel):
    duration_days: int = 14
    approval_timeout_hours: int = 24


class Config(BaseModel):
    github: GithubConfig
    discord: DiscordConfig
    llm: LLMConfig
    sprint: SprintConfig = SprintConfig()


def load_config(path: str = ".taskpilot.yml") -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(**data)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add service/config.py tests/test_config.py
git commit -m "feat: config loader with pydantic validation"
```

---

## Task 3: LLM Abstraction + MockProvider

**Files:**
- Create: `service/llm/base.py`
- Create: `service/llm/mock.py`
- Create: `tests/llm/test_llm.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/llm/test_llm.py
from service.llm.base import LLMProvider, Message
from service.llm.mock import MockProvider


def test_message_dataclass():
    m = Message(role="user", content="hello")
    assert m.role == "user"
    assert m.content == "hello"


def test_mock_provider_returns_configured_response():
    provider = MockProvider(response="sprint plan here")
    result = provider.complete([Message(role="user", content="plan my sprint")])
    assert result == "sprint plan here"


def test_mock_provider_records_all_calls():
    provider = MockProvider(response="ok")
    msgs1 = [Message(role="user", content="first")]
    msgs2 = [Message(role="user", content="second")]
    provider.complete(msgs1)
    provider.complete(msgs2)
    assert len(provider.calls) == 2
    assert provider.calls[0][0].content == "first"
    assert provider.calls[1][0].content == "second"


def test_mock_provider_default_response():
    provider = MockProvider()
    result = provider.complete([Message(role="user", content="hi")])
    assert isinstance(result, str)
    assert len(result) > 0


def test_llm_provider_is_abstract():
    import inspect
    assert inspect.isabstract(LLMProvider)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/llm/test_llm.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.llm.base'`

- [ ] **Step 3: Implement service/llm/base.py**

```python
# service/llm/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Message:
    role: str   # "system" | "user" | "assistant"
    content: str


class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[Message]) -> str:
        ...
```

- [ ] **Step 4: Implement service/llm/mock.py**

```python
# service/llm/mock.py
from .base import LLMProvider, Message


class MockProvider(LLMProvider):
    def __init__(self, response: str = "mock response"):
        self.response = response
        self.calls: list[list[Message]] = []

    def complete(self, messages: list[Message]) -> str:
        self.calls.append(messages)
        return self.response
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
pytest tests/llm/test_llm.py -v
```

Expected: `5 passed`

- [ ] **Step 6: Commit**

```bash
git add service/llm/base.py service/llm/mock.py tests/llm/test_llm.py
git commit -m "feat: LLM provider abstraction + MockProvider"
```

---

## Task 4: LLM Provider Implementations

**Files:**
- Create: `service/llm/groq.py`
- Create: `service/llm/cerebras.py`
- Create: `service/llm/ollama.py`
- Create: `service/llm/factory.py`

These hit external APIs so they are not unit tested — integration-tested manually. The factory is tested via the MockProvider path.

- [ ] **Step 1: Write factory test**

```python
# Add to tests/llm/test_llm.py

import pytest
from unittest.mock import patch
from service.llm.factory import create_provider
from service.config import LLMConfig


def test_factory_raises_on_unknown_provider():
    cfg = LLMConfig(provider="unknown", model="some-model")
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider(cfg)


def test_factory_groq_requires_env_var():
    cfg = LLMConfig(provider="groq", model="llama-3.1-70b-versatile")
    with pytest.raises(KeyError):
        with patch.dict("os.environ", {}, clear=True):
            create_provider(cfg)
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/llm/test_llm.py::test_factory_raises_on_unknown_provider tests/llm/test_llm.py::test_factory_groq_requires_env_var -v
```

Expected: `ModuleNotFoundError: No module named 'service.llm.factory'`

- [ ] **Step 3: Implement service/llm/groq.py**

```python
# service/llm/groq.py
from groq import Groq
from .base import LLMProvider, Message


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = Groq(api_key=api_key)
        self.model = model

    def complete(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return response.choices[0].message.content
```

- [ ] **Step 4: Implement service/llm/cerebras.py**

```python
# service/llm/cerebras.py
from cerebras.cloud.sdk import Cerebras
from .base import LLMProvider, Message


class CerebrasProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        self.client = Cerebras(api_key=api_key)
        self.model = model

    def complete(self, messages: list[Message]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
        )
        return response.choices[0].message.content
```

- [ ] **Step 5: Implement service/llm/ollama.py**

```python
# service/llm/ollama.py
import httpx
from .base import LLMProvider, Message


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url

    def complete(self, messages: list[Message]) -> str:
        response = httpx.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": [{"role": m.role, "content": m.content} for m in messages],
                "stream": False,
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["message"]["content"]
```

- [ ] **Step 6: Implement service/llm/factory.py**

```python
# service/llm/factory.py
import os
from .base import LLMProvider
from .groq import GroqProvider
from .cerebras import CerebrasProvider
from .ollama import OllamaProvider
from ..config import LLMConfig


def create_provider(cfg: LLMConfig) -> LLMProvider:
    if cfg.provider == "groq":
        return GroqProvider(api_key=os.environ["GROQ_API_KEY"], model=cfg.model)
    elif cfg.provider == "cerebras":
        return CerebrasProvider(api_key=os.environ["CEREBRAS_API_KEY"], model=cfg.model)
    elif cfg.provider == "ollama":
        return OllamaProvider(model=cfg.model)
    else:
        raise ValueError(f"Unknown LLM provider: {cfg.provider!r}")
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/llm/ -v
```

Expected: `7 passed`

- [ ] **Step 8: Commit**

```bash
git add service/llm/groq.py service/llm/cerebras.py service/llm/ollama.py service/llm/factory.py tests/llm/test_llm.py
git commit -m "feat: Groq, Cerebras, Ollama provider implementations + factory"
```

---

## Task 5: GitHub Client

**Files:**
- Create: `service/github/client.py`
- Create: `tests/github/test_reader.py` (client behaviour tested via reader tests)

- [ ] **Step 1: Implement service/github/client.py**

No unit test for the raw HTTP client (it's a thin wrapper). It is tested indirectly via reader/writer tests that mock httpx.

```python
# service/github/client.py
from __future__ import annotations
import os
import time
import httpx


class GitHubClient:
    BASE = "https://api.github.com"

    def __init__(self, token: str):
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @classmethod
    def from_env(cls) -> GitHubClient:
        return cls(token=os.environ["GITHUB_TOKEN"])

    def get(self, path: str, params: dict | None = None) -> dict | list:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> dict | list:
        return self._request("POST", path, json=json)

    def patch(self, path: str, json: dict | None = None) -> dict | list:
        return self._request("PATCH", path, json=json)

    def _request(self, method: str, path: str, **kwargs) -> dict | list:
        url = f"{self.BASE}{path}"
        response = httpx.request(method, url, headers=self._headers, **kwargs)
        self._handle_rate_limit(response)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        return response.json()

    def _handle_rate_limit(self, response: httpx.Response) -> None:
        remaining = int(response.headers.get("x-ratelimit-remaining", 1))
        if remaining == 0:
            reset_at = int(response.headers.get("x-ratelimit-reset", time.time() + 60))
            wait = max(0, reset_at - time.time()) + 1
            time.sleep(wait)
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from service.github.client import GitHubClient; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add service/github/client.py
git commit -m "feat: GitHub PAT HTTP client with rate-limit handling"
```

---

## Task 6: GitHub Reader

**Files:**
- Create: `service/github/reader.py`
- Create: `tests/github/test_reader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/github/test_reader.py
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/github/test_reader.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.github.reader'`

- [ ] **Step 3: Implement service/github/reader.py**

```python
# service/github/reader.py
from __future__ import annotations
import base64
from dataclasses import dataclass, field
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/github/test_reader.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add service/github/reader.py tests/github/test_reader.py
git commit -m "feat: GitHub reader — reads repo context (readme, issues, commits, PRs, board)"
```

---

## Task 7: GitHub Writer

**Files:**
- Create: `service/github/writer.py`
- Create: `tests/github/test_writer.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/github/test_writer.py
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
    client.post.assert_called_once_with(
        "/repos/owner/repo/issues",
        json={
            "title": "Fix login",
            "body": "See issue #1",
            "assignees": ["alice"],
            "labels": ["due:2026-04-20"],
        },
    )


def test_create_issue_without_assignee_or_due_date():
    writer, client = make_writer()
    task = SprintTask(title="Refactor DB", body="Clean up models", assignee=None, due_date=None)
    writer.create_issue(task)
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/github/test_writer.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.github.writer'`

- [ ] **Step 3: Implement service/github/writer.py**

```python
# service/github/writer.py
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/github/test_writer.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add service/github/writer.py tests/github/test_writer.py
git commit -m "feat: GitHub writer — creates/closes issues with due-date labels"
```

---

## Task 8: Discord Bot + Command Parser

**Files:**
- Create: `service/bot/discord_bot.py`
- Create: `service/bot/commands.py`
- Create: `tests/bot/test_commands.py`

- [ ] **Step 1: Write failing tests for command parser**

```python
# tests/bot/test_commands.py
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/bot/test_commands.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.bot.commands'`

- [ ] **Step 3: Implement service/bot/commands.py**

```python
# service/bot/commands.py
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/bot/test_commands.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Implement service/bot/discord_bot.py**

```python
# service/bot/discord_bot.py
from __future__ import annotations
import discord
from discord.ext import commands
from .commands import parse_command


class TaskPilotBot(commands.Bot):
    def __init__(self, planner, config, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.reactions = True
        super().__init__(command_prefix="!", intents=intents, **kwargs)
        self.planner = planner
        self.config = config

    async def on_ready(self) -> None:
        print(f"TaskPilot bot ready as {self.user}")

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        if payload.user_id == self.user.id:
            return
        emoji = str(payload.emoji)
        if emoji == "✅":
            await self.planner.approve(payload.message_id, self)
        elif emoji == "❌":
            await self.planner.reject(payload.message_id, self)

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user:
            return
        if str(message.channel.id) == self.config.discord.project_channel_id:
            cmd = parse_command(message.content, self.planner.llm)
            if cmd:
                await cmd.execute(message, self)
        await self.process_commands(message)

    async def propose_plan(self, channel_id: str, plan) -> discord.Message:
        channel = self.get_channel(int(channel_id))
        lines = [f"**Sprint Plan**\n\n{plan.summary}\n"]
        for i, task in enumerate(plan.tasks, 1):
            assignee = f" → @{task.assignee}" if task.assignee else ""
            due = f" (due {task.due_date})" if task.due_date else ""
            lines.append(f"{i}. **{task.title}**{assignee}{due}")
        lines.append("\nReact ✅ to approve or ❌ to discard.")
        msg = await channel.send("\n".join(lines))
        await msg.add_reaction("✅")
        await msg.add_reaction("❌")
        return msg

    async def confirm_plan_created(self, channel_id: str, task_count: int) -> None:
        await self.send_channel_message(
            channel_id,
            f"✅ Sprint plan approved. Created {task_count} issues on the GitHub board.",
        )

    async def notify_plan_discarded(self, channel_id: str) -> None:
        await self.send_channel_message(channel_id, "❌ Sprint plan discarded.")

    async def notify_plan_expired(self, channel_id: str) -> None:
        await self.send_channel_message(
            channel_id,
            "⏰ Sprint plan expired with no approval. Use `/sprint plan` to regenerate.",
        )

    async def send_dm(self, discord_user_id: str, text: str) -> None:
        user = await self.fetch_user(int(discord_user_id))
        await user.send(text)

    async def send_channel_message(self, channel_id: str, text: str) -> None:
        channel = self.get_channel(int(channel_id))
        await channel.send(text)
```

- [ ] **Step 6: Verify import**

```bash
python -c "from service.bot.discord_bot import TaskPilotBot; print('ok')"
```

Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add service/bot/discord_bot.py service/bot/commands.py tests/bot/test_commands.py
git commit -m "feat: Discord bot + ad-hoc command parser"
```

---

## Task 9: Sprint Planner

**Files:**
- Create: `service/planner.py`
- Create: `tests/test_planner.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_planner.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.planner'`

- [ ] **Step 3: Implement service/planner.py**

```python
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
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_planner.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add service/planner.py tests/test_planner.py
git commit -m "feat: sprint planner — LLM-powered plan generation with Discord approval flow"
```

---

## Task 10: FastAPI App + Webhook Endpoint

**Files:**
- Create: `service/main.py`
- Create: `service/api/webhooks.py`
- Create: `tests/api/test_webhooks.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_bot():
    bot = AsyncMock()
    bot.user = MagicMock()
    bot.user.id = 1
    return bot


@pytest.fixture
def mock_config():
    config = MagicMock()
    config.discord.project_channel_id = "123456"
    config.discord.user_map = {"alice": "111", "bob": "222"}
    config.github.repo = "owner/repo"
    return config
```

```python
# tests/api/test_webhooks.py
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


def test_webhook_issue_closed_returns_200(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={
            "action": "closed",
            "issue": {"title": "Fix login", "html_url": "https://github.com/o/r/issues/1"},
        },
        headers={"X-GitHub-Event": "issues"},
    )
    assert response.status_code == 200


def test_webhook_unknown_event_returns_200(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post(
        "/webhook/github",
        json={"action": "labeled", "label": {"name": "bug"}},
        headers={"X-GitHub-Event": "label"},
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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_webhooks.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.main'`

- [ ] **Step 3: Implement service/api/webhooks.py**

```python
# service/api/webhooks.py
from __future__ import annotations
import hashlib
import hmac
import os

from fastapi import APIRouter, BackgroundTasks, Request, Response

router = APIRouter()


def _verify_signature(payload: bytes, signature: str) -> bool:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return True
    expected = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


async def _handle_issue_closed(payload: dict, bot, config) -> None:
    issue = payload["issue"]
    await bot.send_channel_message(
        config.discord.project_channel_id,
        f"✅ Task closed: [{issue['title']}]({issue['html_url']})",
    )


@router.post("/webhook/github")
async def github_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_signature(body, signature):
        return Response(status_code=401)

    event = request.headers.get("X-GitHub-Event", "")
    payload = await request.json()
    bot = request.app.state.bot
    config = request.app.state.config

    if event == "issues" and payload.get("action") == "closed":
        background_tasks.add_task(_handle_issue_closed, payload, bot, config)

    return Response(status_code=200)
```

- [ ] **Step 4: Implement service/main.py**

```python
# service/main.py
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import Config, load_config
from .github.client import GitHubClient
from .github.reader import GitHubReader
from .github.writer import GitHubWriter
from .llm.base import LLMProvider
from .llm.factory import create_provider
from .planner import Planner
from .bot.discord_bot import TaskPilotBot
from .api import webhooks, digest, reminders


def create_app(
    config: Config,
    bot: TaskPilotBot,
    planner: Planner,
    reader: GitHubReader,
    writer: GitHubWriter,
    llm: LLMProvider,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(bot.start(os.environ["DISCORD_BOT_TOKEN"]))
        yield
        task.cancel()

    app = FastAPI(lifespan=lifespan)
    app.include_router(webhooks.router)
    app.include_router(digest.router)
    app.include_router(reminders.router)

    app.state.config = config
    app.state.bot = bot
    app.state.planner = planner
    app.state.reader = reader
    app.state.writer = writer
    app.state.llm = llm

    return app


def build() -> FastAPI:
    config = load_config()
    llm = create_provider(config.llm)
    client = GitHubClient.from_env()
    reader = GitHubReader(client=client, repo=config.github.repo, project_number=config.github.project_number)
    writer = GitHubWriter(client=client, repo=config.github.repo)
    planner = Planner(config=config, llm=llm, reader=reader, writer=writer)
    bot = TaskPilotBot(planner=planner, config=config)
    return create_app(config=config, bot=bot, planner=planner, reader=reader, writer=writer, llm=llm)


app = build()
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/api/test_webhooks.py -v
```

Expected: `3 passed`

- [ ] **Step 6: Commit**

```bash
git add service/main.py service/api/webhooks.py tests/api/test_webhooks.py tests/conftest.py
git commit -m "feat: FastAPI app entrypoint + GitHub webhook receiver"
```

---

## Task 11: Digest Endpoint

**Files:**
- Create: `service/api/digest.py`
- Create: `tests/api/test_digest.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_digest.py
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from service.llm.mock import MockProvider
from service.github.reader import RepoContext


def make_context():
    return RepoContext(
        readme="# App",
        docs={},
        open_issues=[{"title": "Bug"}],
        recent_commits=[{"commit": {"message": "feat: add login"}}],
        open_prs=[],
        project_board_items=[],
    )


def make_client(bot, config, llm_response="Weekly summary here."):
    from service.main import create_app
    reader = MagicMock()
    reader.read_context.return_value = make_context()
    app = create_app(
        config=config,
        bot=bot,
        planner=MagicMock(),
        reader=reader,
        writer=MagicMock(),
        llm=MockProvider(response=llm_response),
    )
    return TestClient(app)


def test_digest_posts_to_discord(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config)
    response = client.post("/digest/owner/repo")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    mock_bot.send_channel_message.assert_called_once()
    # call_args[0] is positional args tuple: (channel_id, text)
    call_text = mock_bot.send_channel_message.call_args[0][1]
    assert "Weekly Digest" in call_text


def test_digest_includes_llm_summary(mock_bot, mock_config):
    client = make_client(mock_bot, mock_config, llm_response="Great week! Two features shipped.")
    client.post("/digest/owner/repo")
    call_text = mock_bot.send_channel_message.call_args[0][1]
    assert "Great week! Two features shipped." in call_text
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_digest.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.api.digest'`

- [ ] **Step 3: Implement service/api/digest.py**

```python
# service/api/digest.py
from __future__ import annotations
import json
from fastapi import APIRouter, Request

from ..llm.base import Message

router = APIRouter()

_DIGEST_SYSTEM = (
    "You are a technical project manager writing a concise weekly digest "
    "for a software development team. Be friendly and factual. Max 300 words."
)


@router.post("/digest/{repo:path}")
async def generate_digest(repo: str, request: Request) -> dict:
    reader = request.app.state.reader
    llm = request.app.state.llm
    bot = request.app.state.bot
    config = request.app.state.config

    context = reader.read_context()

    prompt = (
        f"Generate a weekly digest for the project '{repo}'.\n\n"
        f"Recent commits ({len(context.recent_commits)}):\n"
        + json.dumps([c["commit"]["message"][:80] for c in context.recent_commits[:10]], indent=2)
        + f"\n\nOpen PRs: {len(context.open_prs)}"
        f"\nOpen Issues: {len(context.open_issues)}"
        "\n\nSummarise what got done, what's in progress, and any blockers."
    )

    summary = llm.complete([
        Message(role="system", content=_DIGEST_SYSTEM),
        Message(role="user", content=prompt),
    ])

    await bot.send_channel_message(
        config.discord.project_channel_id,
        f"**Weekly Digest**\n\n{summary}",
    )
    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/api/test_digest.py -v
```

Expected: `2 passed`

- [ ] **Step 5: Commit**

```bash
git add service/api/digest.py tests/api/test_digest.py
git commit -m "feat: weekly digest endpoint — LLM summary posted to Discord"
```

---

## Task 12: Reminders Endpoint

**Files:**
- Create: `service/api/reminders.py`
- Create: `tests/api/test_reminders.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/api/test_reminders.py
import pytest
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient
from service.llm.mock import MockProvider
from service.github.reader import RepoContext


def make_issue(title, due_date: date | None, assignee: str | None):
    labels = []
    if due_date:
        labels.append({"name": f"due:{due_date.isoformat()}"})
    assignees = [{"login": assignee}] if assignee else []
    return {"title": title, "html_url": f"https://github.com/o/r/issues/1", "labels": labels, "assignees": assignees}


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
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/api/test_reminders.py -v
```

Expected: `ModuleNotFoundError: No module named 'service.api.reminders'`

- [ ] **Step 3: Implement service/api/reminders.py**

```python
# service/api/reminders.py
from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Request

router = APIRouter()


@router.post("/reminders/{repo:path}")
async def check_reminders(repo: str, request: Request) -> dict:
    reader = request.app.state.reader
    bot = request.app.state.bot
    config = request.app.state.config

    today = date.today()
    issues = reader.read_context().open_issues

    for issue in issues:
        due_label = next(
            (l["name"] for l in issue.get("labels", []) if l["name"].startswith("due:")),
            None,
        )
        if not due_label:
            continue

        due_date = date.fromisoformat(due_label.removeprefix("due:"))
        days_until = (due_date - today).days

        for assignee_info in issue.get("assignees", []):
            gh_username = assignee_info["login"]
            discord_id = config.discord.user_map.get(gh_username)

            if days_until < 0:
                await bot.send_channel_message(
                    config.discord.project_channel_id,
                    f"🚨 OVERDUE: **{issue['title']}** was due {due_date} "
                    f"({abs(days_until)} days ago). Assigned to: {gh_username}",
                )
            elif 0 <= days_until <= 2:
                if discord_id:
                    await bot.send_dm(
                        discord_id,
                        f"⏰ Reminder: **{issue['title']}** is due on {due_date}. "
                        f"({issue['html_url']})",
                    )
                else:
                    await bot.send_channel_message(
                        config.discord.project_channel_id,
                        f"⚠️ {gh_username} has no Discord mapping — "
                        f"cannot DM deadline reminder for: **{issue['title']}**",
                    )

    return {"status": "ok"}
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/api/test_reminders.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Run the full test suite**

```bash
pytest -v
```

Expected: All tests pass (no failures).

- [ ] **Step 6: Commit**

```bash
git add service/api/reminders.py tests/api/test_reminders.py
git commit -m "feat: reminders endpoint — deadline DMs and overdue channel alerts"
```

---

## Task 13: GitHub Actions + Deployment Verification

**Files:**
- Create: `actions/taskpilot-weekly.yml`
- Create: `actions/taskpilot-reminders.yml`

- [ ] **Step 1: Create actions/taskpilot-weekly.yml**

```yaml
# actions/taskpilot-weekly.yml
name: TaskPilot Weekly Digest

on:
  schedule:
    - cron: '0 9 * * 1'   # Every Monday at 09:00 UTC
  workflow_dispatch:       # Allow manual trigger

jobs:
  digest:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger weekly digest
        run: |
          curl -X POST \
            "${{ secrets.TASKPILOT_SERVICE_URL }}/digest/${{ github.repository }}" \
            -H "Content-Type: application/json" \
            --fail \
            --silent \
            --show-error
```

- [ ] **Step 2: Create actions/taskpilot-reminders.yml**

```yaml
# actions/taskpilot-reminders.yml
name: TaskPilot Deadline Reminders

on:
  schedule:
    - cron: '0 8 * * *'   # Every day at 08:00 UTC
  workflow_dispatch:       # Allow manual trigger

jobs:
  reminders:
    runs-on: ubuntu-latest
    steps:
      - name: Check deadline reminders
        run: |
          curl -X POST \
            "${{ secrets.TASKPILOT_SERVICE_URL }}/reminders/${{ github.repository }}" \
            -H "Content-Type: application/json" \
            --fail \
            --silent \
            --show-error
```

- [ ] **Step 3: Verify Docker build**

```bash
docker build -t taskpilot:dev .
```

Expected: Image builds successfully with no errors.

- [ ] **Step 4: Run full test suite one final time**

```bash
pytest -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 5: Final commit**

```bash
git add actions/ 
git commit -m "feat: GitHub Actions for weekly digest and daily reminders"
```

---

## Implementation Complete

After Task 13, TaskPilot is fully implemented. To onboard a team:

```bash
cp .taskpilot.yml.example .taskpilot.yml   # edit with real values
cp .env.example .env                        # fill in tokens
docker-compose up -d
# Add GitHub webhook → http://your-server/webhook/github
# Copy actions/*.yml into target repo's .github/workflows/
```
