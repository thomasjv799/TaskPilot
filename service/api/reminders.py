# service/api/reminders.py
from __future__ import annotations
import asyncio
from datetime import date
from fastapi import APIRouter, Depends, Request

from ._auth import verify_taskpilot_secret

router = APIRouter()


@router.post("/reminders/{repo:path}", dependencies=[Depends(verify_taskpilot_secret)])
async def check_reminders(repo: str, request: Request) -> dict:
    reader = request.app.state.reader
    bot = request.app.state.bot
    config = request.app.state.config

    loop = asyncio.get_running_loop()
    today = date.today()
    context = await loop.run_in_executor(None, reader.read_context)
    issues = context.open_issues

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
