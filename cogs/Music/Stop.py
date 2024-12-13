import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import spotipy
import json 
from spotipy.oauth2 import SpotifyClientCredentials
import os
import random
import asyncio
from .Music_utils import *
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["Slavie"]  # Database name
disabled_commands_col = db.disabled_commands

def load_disabled_commands():
    """Load the disabled commands from MongoDB."""
    return disabled_commands_col.find_one({"guild_id": str(os.getenv("GUILD_ID"))}) or {}

async def is_command_disabled(guild_id, command_name):
    """Check if a command is disabled for a specific guild."""
    disabled_commands = disabled_commands_col.find_one({"guild_id": str(guild_id)})
    return disabled_commands and command_name in disabled_commands.get("commands", [])

# Custom check function to disable commands
def check_if_disabled():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild.id
        command_name = interaction.command.name
        if await is_command_disabled(guild_id, command_name):
            await interaction.response.send_message(f"The command `{command_name}` is disabled in this server.", ephemeral=True)
            return False  # Prevents the slash command from executing
        return True
    return app_commands.check(predicate)

class Stop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='stop', description="Stop the music and disconnect from the voice channel.")
    @check_if_disabled()
    async def stop(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect()
            if interaction.guild.id in self.bot.get_cog('Play').queue:
                self.bot.get_cog('Play').queue[interaction.guild.id] = []
            self.bot.get_cog('Play').is_playing[interaction.guild.id] = False
            self.bot.get_cog('Play').loop_all[interaction.guild.id] = False
            self.bot.get_cog('Play').shuffle_active[interaction.guild.id] = False
            self.bot.get_cog('Play').current_song.pop(interaction.guild.id, None)
            await interaction.response.send_message("Stopped the music and disconnected! 🛑")
        else:
            await interaction.response.send_message("I'm not connected to a voice channel! 🙅‍♂️")

async def setup(bot):
    await bot.add_cog(Stop(bot))
