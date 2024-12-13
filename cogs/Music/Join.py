import discord
from discord.ext import commands
from discord import app_commands
import os
import json
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

class JoinChannel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='join', description="Join the user's voice channel.")
    @check_if_disabled()
    async def join(self, interaction: discord.Interaction):
        if interaction.user.voice is None:
            await interaction.response.send_message("You need to be in a voice channel to use this command!", ephemeral=True)
            return
        voice_channel = interaction.user.voice.channel
        if interaction.guild.voice_client is None:
            await voice_channel.connect()
        elif interaction.guild.voice_client.channel != voice_channel:
            await interaction.guild.voice_client.move_to(voice_channel)
        await interaction.response.send_message(f"Joined {voice_channel.name}!")

async def setup(bot):
    await bot.add_cog(JoinChannel(bot))
