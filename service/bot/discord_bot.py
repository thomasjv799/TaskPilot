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
        if str(payload.channel_id) != self.config.discord.project_channel_id:
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
