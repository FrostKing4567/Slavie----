import discord
from discord.ext import commands

class LeaveServer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="leave_server")
    async def leave_server(self, ctx):
        # Owner check
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Only the bot owner can make me leave a server!")
            return

        try:
            await ctx.send("Leaving Server...")
            await ctx.guild.leave()
        except discord.HTTPException:
            await ctx.send("Failed to leave the server due to an HTTP error!")

async def setup(bot):
    await bot.add_cog(LeaveServer(bot))
