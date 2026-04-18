# service/api/digest.py
from __future__ import annotations
import asyncio
import json
from fastapi import APIRouter, Depends, Request

from ..llm.base import Message
from ._auth import verify_taskpilot_secret

router = APIRouter()

_DIGEST_SYSTEM = (
    "You are a technical project manager writing a concise weekly digest "
    "for a software development team. Be friendly and factual. Max 300 words."
)


@router.post("/digest/{repo:path}", dependencies=[Depends(verify_taskpilot_secret)])
async def generate_digest(repo: str, request: Request) -> dict:
    reader = request.app.state.reader
    llm = request.app.state.llm
    bot = request.app.state.bot
    config = request.app.state.config

    loop = asyncio.get_running_loop()
    context = await loop.run_in_executor(None, reader.read_context)

    messages = [
        Message(role="system", content=_DIGEST_SYSTEM),
        Message(
            role="user",
            content=(
                f"Generate a weekly digest for the project '{repo}'.\n\n"
                f"Recent commits ({len(context.recent_commits)}):\n"
                + json.dumps(
                    [c["commit"]["message"][:80] for c in context.recent_commits[:10]],
                    indent=2,
                )
                + f"\n\nOpen PRs: {len(context.open_prs)}"
                f"\nOpen Issues: {len(context.open_issues)}"
                "\n\nSummarise what got done, what's in progress, and any blockers."
            ),
        ),
    ]

    summary = await loop.run_in_executor(None, llm.complete, messages)

    await bot.send_channel_message(
        config.discord.project_channel_id,
        f"**Weekly Digest**\n\n{summary}",
    )
    return {"status": "ok"}
