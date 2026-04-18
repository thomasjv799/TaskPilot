# TaskPilot

An LLM-powered project manager that reads your GitHub repo, generates sprint plans, manages your Kanban board, and keeps your team accountable via Discord.

## How it works

1. **Sprint planning** — TaskPilot reads your repo (README, docs, open issues, recent commits) and generates a sprint plan using an LLM. The draft is posted to Discord for a team lead to approve (✅) before any issues are created.
2. **Weekly digest** — Every Monday, a GitHub Action triggers a summary of commits, closed issues, and open PRs — posted to your Discord project channel.
3. **Deadline reminders** — Daily, a GitHub Action checks for issues with `due:YYYY-MM-DD` labels and DMs assignees who are within 48h of their deadline. Overdue tasks get a channel alert.
4. **Ad-hoc tasks** — Any team member can create a GitHub issue by typing `create task: ...` or `add task: ...` in the Discord project channel.

## Architecture

```
┌─────────────────────────────────────┐     GitHub Actions (scheduled)
│  FastAPI Service (Docker)            │ ◄── POST /digest/{repo}   (Monday 09:00)
│                                     │ ◄── POST /reminders/{repo} (Daily 08:00)
│  ┌─────────────┐  ┌──────────────┐  │
│  │ Webhook API │  │  Discord Bot │  │
│  │  /webhook/  │  │  (persistent)│  │
│  │  github     │  └──────┬───────┘  │
│  └──────┬──────┘         │          │
│         │         ┌──────▼───────┐  │
│         └────────►│   Planner    │  │
│                   │  LLM + GitHub│  │
│                   └──────────────┘  │
└─────────────────────────────────────┘
        ▲ webhooks          ▼ API calls
   GitHub repo         GitHub API + Discord
```

- The **FastAPI service** handles GitHub webhooks and exposes REST endpoints for the Actions to call
- The **Discord bot** runs persistently in the same container, handling reactions and ad-hoc commands
- **GitHub Actions** in each target repo handle scheduling — no extra infra needed
- All LLM logic lives in the service; Actions are simple `curl` callers

## LLM providers

TaskPilot supports swappable LLM backends — change one line in config:

| Provider | Value | Env var |
|---|---|---|
| [Groq](https://groq.com) | `groq` | `GROQ_API_KEY` |
| [Cerebras](https://cerebras.ai) | `cerebras` | `CEREBRAS_API_KEY` |
| Ollama (local) | `ollama` | — |

## Setup

### 1. Configure

```bash
cp .taskpilot.yml.example .taskpilot.yml
```

```yaml
# .taskpilot.yml
github:
  repo: owner/repo
  project_number: 1          # GitHub Projects board number

discord:
  project_channel_id: "123456789012345678"
  user_map:
    alice_gh: "discord_user_id"   # GitHub username → Discord user ID

llm:
  provider: groq
  model: llama-3.1-70b-versatile

sprint:
  duration_days: 14
  approval_timeout_hours: 24
```

### 2. Set environment variables

```bash
cp .env.example .env
# Fill in:
#   GITHUB_TOKEN          — Personal access token (repo + project scopes)
#   DISCORD_BOT_TOKEN     — Discord bot token
#   GITHUB_WEBHOOK_SECRET — Secret for webhook HMAC verification (required)
#   GROQ_API_KEY          — Or CEREBRAS_API_KEY depending on provider
#   TASKPILOT_SERVICE_URL — Public URL of your deployed service
#   TASKPILOT_SECRET      — Shared secret for /digest and /reminders endpoints
```

### 3. Run

```bash
docker-compose up -d
```

### 4. Add GitHub webhook

In your repo: **Settings → Webhooks → Add webhook**

- Payload URL: `https://your-server/webhook/github`
- Content type: `application/json`
- Secret: your `GITHUB_WEBHOOK_SECRET`
- Events: Issues, Pull requests, Push

### 5. Add GitHub Actions to target repo

```bash
cp actions/taskpilot-weekly.yml    path/to/repo/.github/workflows/
cp actions/taskpilot-reminders.yml path/to/repo/.github/workflows/
```

Add `TASKPILOT_SERVICE_URL` and `TASKPILOT_SECRET` as repository secrets in the target repo.

---

That's it. TaskPilot is running.

## Usage

### Sprint planning

Type in the Discord project channel:

```
/sprint plan
```

TaskPilot reads the repo and posts a draft sprint plan. React ✅ to approve (issues are created on the board) or ❌ to discard. Plans expire after 24h with no reaction.

### Create a task

```
create task: set up CI pipeline, assign to alice
add task: write unit tests for the auth module
```

TaskPilot parses the request, creates a GitHub issue, and replies with the link.

### Weekly digest

Fires automatically every Monday at 09:00 UTC. Also triggerable manually via GitHub Actions → `workflow_dispatch`.

### Deadline reminders

Fire automatically every day at 08:00 UTC. Issues need a `due:YYYY-MM-DD` label (set automatically when TaskPilot creates sprint tasks).

## Project structure

```
taskpilot/
├── service/
│   ├── config.py          # Pydantic config loader (.taskpilot.yml)
│   ├── planner.py         # Sprint planning orchestrator
│   ├── main.py            # FastAPI app factory + production builder
│   ├── llm/               # LLMProvider ABC + Groq/Cerebras/Ollama + factory
│   ├── github/            # GitHub client, reader, writer
│   ├── api/               # Webhook, digest, reminders endpoints
│   └── bot/               # Discord bot + command parser
├── actions/               # GitHub Actions (copy into target repos)
├── tests/                 # 43 tests
├── Dockerfile
├── docker-compose.yml
└── .taskpilot.yml.example
```

## Development

```bash
pip install -r requirements.txt
python3 -m pytest -v
```

## Planned

- GitHub App (replace PAT with org-level app install)
- Multi-repo support
- Slack integration
- `organization(login:)` GraphQL support for org-owned project boards
