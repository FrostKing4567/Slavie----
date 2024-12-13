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

class Loop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='loop', description="Toggle looping for the current song.")
    @check_if_disabled()
    async def loop(self, interaction: discord.Interaction):
        play_cog = self.bot.get_cog('Play')
        if interaction.guild.id not in play_cog.loop:
            play_cog.loop[interaction.guild.id] = False

        play_cog.loop[interaction.guild.id] = not play_cog.loop[interaction.guild.id]
        if play_cog.loop[interaction.guild.id]:
            await interaction.response.send_message("Looping current song! 🔄")
        else:
            await interaction.response.send_message("Looping disabled! 🚫")

async def setup(bot):
    await bot.add_cog(Loop(bot))
