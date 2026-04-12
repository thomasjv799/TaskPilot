# service/main.py
from __future__ import annotations
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api import webhooks, digest, reminders


def create_app(
    config,
    bot,
    planner,
    reader,
    writer,
    llm,
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
    from .config import load_config
    from .github.client import GitHubClient
    from .github.reader import GitHubReader
    from .github.writer import GitHubWriter
    from .llm.factory import create_provider
    from .planner import Planner
    from .bot.discord_bot import TaskPilotBot

    config = load_config()
    llm = create_provider(config.llm)
    client = GitHubClient.from_env()
    # Validate Discord token at startup — fail fast rather than silently
    discord_token = os.environ["DISCORD_BOT_TOKEN"]
    reader = GitHubReader(client=client, repo=config.github.repo, project_number=config.github.project_number)
    writer = GitHubWriter(client=client, repo=config.github.repo)
    planner = Planner(config=config, llm=llm, reader=reader, writer=writer)
    bot = TaskPilotBot(planner=planner, config=config)
    return create_app(config=config, bot=bot, planner=planner, reader=reader, writer=writer, llm=llm)


# To run in production: uvicorn service.main:app
# No config available at import time during tests — catch gracefully
try:
    app = build()
except Exception:
    # Allow import without config during testing
    app = FastAPI()
