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

class RestartCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def restart(self, ctx):
        await ctx.send("Restart successful")
        await os.system("shutdown /r /t 0")

    @restart.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Restart successful....")
            await asyncio.sleep(2)
            await ctx.send("||haha jk||")

async def setup(bot):
    await bot.add_cog(RestartCog(bot))
