import asyncio
from datetime import datetime, timezone

from discord.ext import commands, tasks

from utils import database, wom_tracking
from utils.wom_poll_schedule import get_due_wom_poll_slot


class WOMCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def cog_unload(self):
        if self.wom_poll.is_running():
            self.wom_poll.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        if not self.wom_poll.is_running():
            self.wom_poll.start()

    @tasks.loop(seconds=30)
    async def wom_poll(self):
        # Scheduler checks use the local database.
        # WOM is contacted only after a scheduled slot
        # has been successfully claimed.
        try:
            timing = await asyncio.to_thread(
                database.get_wom_competition_timing
            )

            if timing is None:
                return

            competition_id = await asyncio.to_thread(
                database.get_wom_competition_id
            )

            if competition_id is None:
                return

            slot = get_due_wom_poll_slot(
                timing["starts_at"],
                timing["ends_at"],
                datetime.now(timezone.utc),
            )

            if slot is None:
                return

            scheduled_slot = (
                competition_id,
                timing["starts_at"],
                timing["ends_at"],
                slot,
            )

        except Exception as error:
            print(
                "Unable to determine WOM polling eligibility:",
                error
            )
            return

        # A successfully claimed slot may make WOM requests.
        # The existing processing and audit behaviour remains.
        try:
            result = await asyncio.to_thread(
                wom_tracking.try_process_wom_competition,
                scheduled_slot=scheduled_slot,
            )
        except Exception as error:
            print(
                "Unexpected error while processing WOM:",
                error
            )
            return

        if result is None:
            # Lock unavailable or polling slot already claimed.
            # Neither outcome represents a completed refresh.
            return

        if result["competition_id"] is not None:
            try:
                await asyncio.to_thread(
                    database.record_wom_refresh_audit,
                    requested_by_user_id=None,
                    requested_by_username="Background WOM Poll",
                    result=result
                )
            except Exception as error:
                print(
                    "Unexpected error while recording WOM poll audit:",
                    error
                )

        if result["errors"]:
            print(
                "WOM processing errors:",
                result["errors"]
            )

        if result["tiles_completed"]:
            print(
                "WOM completed tiles:",
                result["tiles_completed"]
            )

    @wom_poll.before_loop
    async def before_wom_poll(self):
        await self.bot.wait_until_ready()
