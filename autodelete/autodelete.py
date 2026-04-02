import asyncio
import logging

import discord
from redbot.core import Config, commands
from redbot.core.bot import Red

log = logging.getLogger("red.jokaca.autodelete")


class AutoDelete(commands.Cog):
    """Auto-delete bot messages after the guild delete_delay."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(
            self, identifier=0x4A4F4B414144, force_registration=True
        )
        self.config.register_guild(excluded_channels=[])
        self._pending_tasks: set[asyncio.Task] = set()

    def cog_unload(self):
        for task in self._pending_tasks:
            task.cancel()
        log.info(
            "AutoDelete unloaded — cancelled %d pending deletion tasks.",
            len(self._pending_tasks),
        )
        self._pending_tasks.clear()

    async def _get_delete_delay(self, guild: discord.Guild) -> int:
        """Read the guild delete_delay from Red core config. Returns -1 if disabled or on error."""
        # bot._config is a private API — no public interface exists for reading
        # guild delete_delay. Tested on Red 3.5.24 / discord.py 2.7.1.
        try:
            delay = await self.bot._config.guild(guild).delete_delay()
        except Exception:
            log.error(
                "AutoDelete: failed to read delete_delay for guild %s (%s). Skipping.",
                guild.name,
                guild.id,
                exc_info=True,
            )
            return -1

        if not isinstance(delay, (int, float)) or delay < 0:
            if delay == -1:
                return -1
            log.warning(
                "AutoDelete: unexpected delete_delay value %r for guild %s (%s). Skipping.",
                delay,
                guild.name,
                guild.id,
            )
            return -1

        return int(delay)

    async def _delete_after(self, message: discord.Message, delay: int):
        """Sleep then delete a message. Designed to be wrapped in a tracked task."""
        try:
            await asyncio.sleep(delay)
            try:
                await message.delete()
            except discord.NotFound:
                pass
            except discord.Forbidden:
                log.warning(
                    "AutoDelete: missing permissions to delete message %s in #%s (%s), guild %s.",
                    message.id,
                    message.channel.name,
                    message.channel.id,
                    message.guild.name,
                )
            except discord.HTTPException:
                log.warning(
                    "AutoDelete: failed to delete message %s in #%s (%s), guild %s.",
                    message.id,
                    message.channel.name,
                    message.channel.id,
                    message.guild.name,
                    exc_info=True,
                )
        except asyncio.CancelledError:
            pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        try:
            if message.author.id != self.bot.user.id:
                return
            if not message.guild:
                return
            if message.type not in (
                discord.MessageType.default,
                discord.MessageType.reply,
            ):
                return

            delay = await self._get_delete_delay(message.guild)
            if delay <= 0:
                return

            try:
                excluded = await self.config.guild(message.guild).excluded_channels()
            except Exception:
                log.error(
                    "AutoDelete: failed to read excluded_channels for guild %s (%s). "
                    "Skipping deletion for safety.",
                    message.guild.name,
                    message.guild.id,
                    exc_info=True,
                )
                return

            if message.channel.id in excluded:
                return

            if len(self._pending_tasks) > 1000:
                log.warning("AutoDelete: pending task ceiling (1000) reached, skipping.")
                return

            task = asyncio.create_task(self._delete_after(message, delay))
            self._pending_tasks.add(task)
            task.add_done_callback(self._pending_tasks.discard)

        except Exception:
            log.error(
                "AutoDelete: unexpected error processing message %s in guild %s.",
                message.id,
                getattr(message.guild, "id", "DM"),
                exc_info=True,
            )

    @commands.group()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    async def autodelete(self, ctx: commands.Context):
        """Configure AutoDelete settings."""

    @autodelete.command(name="exclude")
    async def autodelete_exclude(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Exclude a channel from auto-deletion."""
        async with self.config.guild(ctx.guild).excluded_channels() as excluded:
            if channel.id in excluded:
                await ctx.send(f"#{channel.name} is already excluded.")
                return
            excluded.append(channel.id)
        await ctx.send(f"#{channel.name} is now excluded from auto-delete.")

    @autodelete.command(name="include")
    async def autodelete_include(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Re-include a previously excluded channel."""
        async with self.config.guild(ctx.guild).excluded_channels() as excluded:
            if channel.id not in excluded:
                await ctx.send(f"#{channel.name} is not currently excluded.")
                return
            excluded.remove(channel.id)
        await ctx.send(f"#{channel.name} is now re-included for auto-delete.")

    @autodelete.command(name="list")
    async def autodelete_list(self, ctx: commands.Context):
        """List excluded channels."""
        excluded = await self.config.guild(ctx.guild).excluded_channels()
        if not excluded:
            await ctx.send("No channels excluded.")
            return
        lines = []
        for cid in excluded:
            ch = ctx.guild.get_channel(cid)
            if ch:
                lines.append(f"<#{cid}> ({ch.name})")
            else:
                lines.append(f"`{cid}` (deleted channel)")
        await ctx.send("Excluded channels:\n" + "\n".join(lines))

    @autodelete.command(name="prune")
    async def autodelete_prune(self, ctx: commands.Context):
        """Remove deleted channels from the exclusion list."""
        removed = 0
        async with self.config.guild(ctx.guild).excluded_channels() as excluded:
            to_remove = [cid for cid in excluded if not ctx.guild.get_channel(cid)]
            for cid in to_remove:
                excluded.remove(cid)
                removed += 1
        if removed:
            await ctx.send(f"Pruned {removed} stale channel(s) from exclusion list.")
        else:
            await ctx.send("No stale channels found.")
