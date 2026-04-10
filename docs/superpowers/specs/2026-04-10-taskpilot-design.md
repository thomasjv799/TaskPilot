# TaskPilot — Design Spec
**Date:** 2026-04-10  
**Status:** Approved

---

## Overview

TaskPilot is an LLM-powered project management AI for teams. It reads a GitHub repository (code, docs, issues) to understand the project, generates sprint plans, manages a GitHub Kanban board, tracks progress, and posts updates and reminders to Discord.

---

## Goals

- Automate sprint planning from repo context — no manual input required
- Keep teams accountable with weekly digests and deadline DMs
- Let any team member create tasks via Discord without touching GitHub
- Be easy to onboard: five steps from zero to running
- Be LLM-agnostic: swap providers without changing business logic

---

## Out of Scope (v1)

- GitHub App (PAT-based for now; GitHub App is a planned future phase)
- Multi-repo sprint planning (one repo per TaskPilot config)
- UI dashboard
- Billing or seat management

---

## Architecture

### Deployment Model

**FastAPI Service + GitHub Actions hybrid:**

- One Docker container runs the always-on parts: Discord bot, GitHub webhook receiver, approval flow handler, REST API
- GitHub Actions in each target repo handle all scheduled jobs (weekly digest, daily deadline check)
- GitHub Actions call the service REST API — all LLM logic stays in the service, no duplication

### Components

#### 1. FastAPI Service

| Module | Responsibility |
|--------|----------------|
| `api/webhooks.py` | Receives GitHub webhook events (push, issues, PRs). Responds `200` immediately, processes async. |
| `api/digest.py` | `POST /digest/{repo}` — triggered by GitHub Action, runs weekly analysis |
| `api/reminders.py` | `POST /reminders/{repo}` — triggered by GitHub Action, runs daily deadline check |
| `bot/discord_bot.py` | Persistent Discord bot connection. Posts to channels, sends DMs, listens for reaction approvals. |
| `bot/commands.py` | Parses ad-hoc Discord commands via LLM (e.g. "create task: add auth") |
| `llm/base.py` | `LLMProvider` interface: `complete(messages: list) -> str` |
| `llm/groq.py` | Groq implementation |
| `llm/cerebras.py` | Cerebras implementation |
| `llm/ollama.py` | Ollama (local Llama) implementation |
| `github/client.py` | PAT-based GitHub API wrapper |
| `github/reader.py` | Reads repo files, issues, PRs, commits. Read-only — never mutates. |
| `github/writer.py` | Creates issues, updates project board, sets assignees, closes tasks |
| `planner.py` | Orchestrates sprint planning: reader → LLM → Discord approval → writer |
| `config.py` | Loads `.taskpilot.yml` + env vars. Validates on startup. |

#### 2. GitHub Actions (shipped with TaskPilot, copied into target repos)

| Workflow | Schedule | Action |
|----------|----------|--------|
| `taskpilot-weekly.yml` | Every Monday 09:00 | Calls `POST /digest/{repo}` |
| `taskpilot-reminders.yml` | Daily 08:00 | Calls `POST /reminders/{repo}` |

#### 3. LLM Abstraction

- `LLMProvider` is a Python abstract base class with a single `complete(messages) -> str` method
- Provider is selected at startup from `.taskpilot.yml`
- Switching providers requires changing one line in config — no code changes
- Supported v1 providers: Groq, Cerebras, Ollama

#### 4. Config File (`.taskpilot.yml` — lives in project root)

```yaml
github:
  repo: owner/repo
  project_number: 1

discord:
  project_channel_id: "123456789"
  user_map:
    alice_gh: "discord_user_id_1"
    bob_gh: "discord_user_id_2"

llm:
  provider: groq          # groq | cerebras | ollama
  model: llama-3.1-70b-versatile

sprint:
  duration_days: 14
  approval_timeout_hours: 24
```

Secrets (tokens, API keys) are environment variables — never committed to config:
- `GITHUB_TOKEN`
- `DISCORD_BOT_TOKEN`
- `GROQ_API_KEY` / `CEREBRAS_API_KEY` (whichever provider is active)
- `TASKPILOT_SERVICE_URL` — set as a GitHub Actions repository secret so workflows know where to call the service (e.g. `https://taskpilot.myteam.com`)

---

## Core Flows

### 1. Sprint Planning

1. Triggered by a Discord command (`/sprint plan`) or manually via the service API
2. `reader.py` fetches: README, docs folder, open issues, recent commits, existing project board state
3. `planner.py` sends context to LLM → receives structured sprint plan (tasks, suggested owners, estimates)
4. Bot posts the draft plan to the Discord project channel
5. A team lead reacts ✅ to approve (or ❌ to discard)
6. On approval: `writer.py` creates GitHub issues, assigns them, and adds them to the project board
7. On timeout (default 24h with no reaction): plan is discarded; bot posts "plan expired" notice

### 2. Weekly Digest

1. GitHub Action fires every Monday
2. Calls `POST /digest/{repo}` on the service
3. Service uses `reader.py` to fetch: commits since last Monday, closed issues, open PRs, overdue tasks
4. LLM generates a natural-language summary
5. Bot posts the digest to the Discord project channel

### 3. Deadline Reminders

1. GitHub Action fires daily
2. Calls `POST /reminders/{repo}` on the service
3. Service fetches all open issues with a `due:YYYY-MM-DD` label (e.g. `due:2026-04-15`) — this is how TaskPilot tracks due dates since GitHub has no native due date field. The planner sets these labels when creating sprint tasks.
4. For issues due within 48h: bot DMs the assignee via Discord (using `user_map` in config)
5. For overdue issues: bot posts a notice to the project channel

### 4. Ad-hoc Task Creation

1. Any team member sends a message in the Discord project channel (e.g. "create task: set up CI pipeline, assign to alice")
2. Bot detects the intent via LLM command parser
3. `writer.py` creates the GitHub issue and adds it to the project board
4. Bot replies in Discord with a confirmation and link to the issue

### 5. Mark Task as Done

1. When a GitHub issue is closed (via PR merge or manual close), a webhook event fires
2. Service receives the webhook and updates the project board card to "Done"
3. Bot posts a brief "✅ Task closed: [issue title]" to the project channel

---

## Project Structure

```
taskpilot/
├── service/
│   ├── main.py
│   ├── api/
│   │   ├── webhooks.py
│   │   ├── digest.py
│   │   └── reminders.py
│   ├── bot/
│   │   ├── discord_bot.py
│   │   └── commands.py
│   ├── llm/
│   │   ├── base.py
│   │   ├── groq.py
│   │   ├── cerebras.py
│   │   └── ollama.py
│   ├── github/
│   │   ├── client.py
│   │   ├── reader.py
│   │   └── writer.py
│   ├── planner.py
│   └── config.py
├── actions/
│   ├── taskpilot-weekly.yml
│   └── taskpilot-reminders.yml
├── tests/
│   ├── test_planner.py
│   ├── test_reader.py
│   └── test_llm.py
├── docker-compose.yml
├── Dockerfile
├── .taskpilot.yml.example
└── .gitignore
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| LLM call fails | Retry up to 3x with exponential backoff. On total failure, post error to Discord project channel. |
| Approval timeout | After `approval_timeout_hours`, discard draft and post "plan expired" to project channel. |
| Missing `user_map` entry | Log warning, skip the DM, post a note in project channel: "@alice_gh has no Discord mapping." |
| GitHub PAT rate limit | Check rate limit headers; back off and retry after reset time. |
| Webhook delivery failure | GitHub retries automatically. Service responds `200` immediately and processes async. |
| Discord bot disconnects | `discord.py` handles reconnect automatically with exponential backoff. |

---

## Testing Strategy

- **Unit tests** — `planner.py`, `reader.py`, `llm/` modules. All pure functions. LLM tested via `MockProvider` that returns fixture responses.
- **Integration tests** — `writer.py` against GitHub API (uses a dedicated test repo). `discord_bot.py` tested via `discord.py` test client.
- **No mocking of GitHub API in unit tests** — reader and writer are tested against real endpoints to avoid mock/prod divergence.

---

## Onboarding a New Team (5 Steps)

```bash
# 1. Configure
cp .taskpilot.yml.example .taskpilot.yml
# edit: repo, channel IDs, user_map, llm provider

# 2. Set secrets
export GITHUB_TOKEN=...
export DISCORD_BOT_TOKEN=...
export GROQ_API_KEY=...

# 3. Run
docker-compose up -d

# 4. Add GitHub webhook
# repo Settings → Webhooks → http://your-server/webhook/github
# Events: Issues, Pull requests, Push

# 5. Copy Actions into target repo
cp actions/*.yml path/to/repo/.github/workflows/
```

---

## Future Work (Post-v1)

- **GitHub App** — replace PAT with org-level GitHub App for proper multi-team support and auto-webhook registration
- **Multi-repo support** — a single TaskPilot instance manages multiple repos from one config
- **Slack integration** — alternative to Discord
- **Web dashboard** — view sprint history, task analytics, team velocity
