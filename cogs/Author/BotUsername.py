import discord
from discord.ext import commands

class ChangeBotUsername(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # This will be a normal command now
    @commands.command(name="change_bot_username")
    @commands.is_owner()
    async def change_bot_username(self, ctx, new_username: str):
        # Owner check
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Only the bot owner can change the bot's username!")
            return

        try:
            await self.bot.user.edit(username=new_username)
            await ctx.send("Bot username changed!")
        except discord.HTTPException:
            await ctx.send("Failed to change the username due to an HTTP error!")

async def setup(bot):
    await bot.add_cog(ChangeBotUsername(bot))