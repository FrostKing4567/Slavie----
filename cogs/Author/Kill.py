import discord
from discord.ext import commands, tasks
import os
import asyncio
import traceback
from itertools import cycle
from dotenv import load_dotenv
import ctypes
import tkinter as tk
from tkinter import messagebox
import inspect
from discord import app_commands

class KysCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(aliases=["byebye", "die", "kill", "fuckingendit", "justkillyourselfforgood", "sorryman", "endit"])
    @commands.is_owner()
    async def kys(self, ctx):
        await ctx.send("Shutting down... <:AiAngry:1297320187460190208>")
        await self.bot.close()

    @kys.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Shutting down... 😴")
            await asyncio.sleep(2)
            await ctx.send("||haha jk||")

async def setup(bot):
    await bot.add_cog(KysCog(bot))
