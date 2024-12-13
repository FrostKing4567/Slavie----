import discord
from discord.ext import commands
from discord import app_commands
import yt_dlp as youtube_dl
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import json 
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

class Volume(commands.Cog):
    def __init__(self, bot, play_cog):
        self.bot = bot
        self.play_cog = play_cog  # Reference to Play cog for shared volume access

    @app_commands.command(name='volume', description="Set the volume level (0-100%).")
    @check_if_disabled()
    async def volume(self, interaction: discord.Interaction, level: int):
        if level < 0 or level > 100:
            await interaction.response.send_message("Volume level must be between 0 and 100! 🔊", ephemeral=True)
            return
        
        if interaction.guild.voice_client:
            if interaction.guild.voice_client.source:
                # Adjust the volume so that 100% is 10%
                scaled_volume = (level / 100) * 0.1
                
                # Set the volume in both the voice client and the Play cog's volume dictionary
                interaction.guild.voice_client.source.volume = scaled_volume
                self.play_cog.volume[interaction.guild.id] = scaled_volume  # Update the volume in Play cog
                
                await interaction.response.send_message(f"Volume set to {level}% 🔊 (Scaled to {scaled_volume * 100:.1f}% of max volume)")
            else:
                await interaction.response.send_message("No song is playing to adjust the volume! 😅", ephemeral=True)
        else:
            await interaction.response.send_message("Not connected to a voice channel! 🙅‍♂️", ephemeral=True)

async def setup(bot):
    # Ensure Play cog is loaded before setting up Volume cog
    play_cog = bot.get_cog("Play")
    if play_cog:
        await bot.add_cog(Volume(bot, play_cog))
    else:
        print("Play cog is not loaded. Ensure Play is added before Volume.")
