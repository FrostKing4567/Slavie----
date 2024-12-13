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

class ShutdownCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def shutdown(self, ctx):
        await ctx.send("Shutdown successful....")
        await os.system("shutdown /s /t 0")

    @shutdown.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Shutdown successful....")
            await asyncio.sleep(2)
            await ctx.send("||haha jk||")

async def setup(bot):
    await bot.add_cog(ShutdownCog(bot))
