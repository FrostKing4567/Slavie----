import discord
from discord.ext import commands
import subprocess
import sys
import asyncio
from discord import app_commands

class BotControl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["rebyebye", "redie", "rekill", "arise", "reawaken", "dieandcomebackorsomethingmanplease", "botrestartnotnormalrestartbtw", "justfuckingrestart", "toomuchdebuggingandyesiamusinggptformostofit", "pleasefuckingworkicanttakethisshitanymoreman", "enditandcomebackperhaps"])
    @commands.is_owner()  # Ensure only the bot owner can use this command
    async def rekys(self, ctx):
        # Save the channel ID where we want to send the "back online" message
        self.bot.restart_channel_id = ctx.channel.id
        await ctx.send("Restarting the bot to apply updates... <:AiAngry:1297320187460190208>")

        # Close the bot
        await self.bot.close()

        # Restart the bot using subprocess
        subprocess.call([sys.executable, sys.argv[0]])

    @rekys.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Restarting the bot to apply updates...")
            await asyncio.sleep(2)
            await ctx.send("||haha jk||")

@commands.Cog.listener()
async def on_ready(self):
    # Send a message to the channel stored during restart
    if hasattr(self.bot, 'restart_channel_id'):
        channel = self.bot.get_channel(self.bot.restart_channel_id)
        if channel:
            await channel.send("I'm back online!")

async def setup(bot):
    await bot.add_cog(BotControl(bot))
