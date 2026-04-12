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
        # No secret configured — reject all webhook requests
        # Set GITHUB_WEBHOOK_SECRET in your environment to enable webhook processing
        return False
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
