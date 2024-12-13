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

class HibernateCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.is_owner()
    async def hibernate(self, ctx):
        await ctx.send("Hibernate successful")
        await os.system("shutdown /h")

    @hibernate.error
    async def stop_error(self, ctx, error):
        if isinstance(error, commands.NotOwner):
            await ctx.send("Hibernate successful....")
            await asyncio.sleep(2)
            await ctx.send("||haha jk||")

async def setup(bot):
    await bot.add_cog(HibernateCog(bot))
