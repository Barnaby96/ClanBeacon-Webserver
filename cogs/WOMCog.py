import asyncio

from discord.ext import commands, tasks

from utils import database, wom_tracking


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

    @tasks.loop(minutes=5)
    async def wom_poll(self):
        try:
            result = await asyncio.to_thread(
                wom_tracking.process_wom_competition
            )
        except Exception as error:
            print(
                "Unexpected error while processing WOM:",
                error
            )
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
