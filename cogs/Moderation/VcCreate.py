import discord
from discord.ext import commands
from discord import app_commands
import json 
import os 
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

class CreateVC(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_vc")
    @check_if_disabled()
    async def create_vc(self, interaction: discord.Interaction, vc_name: str, category: discord.CategoryChannel):
        # Permission check
        if not interaction.guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message("I need the **Manage Channels** permission to create voice channels!", ephemeral=True)
            return

        try:
            await category.create_voice_channel(name=vc_name)
            await interaction.response.send_message(f"Voice Channel {vc_name} created in {category.name}!", ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to create a voice channel in this category!", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to create the voice channel due to an HTTP error!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(CreateVC(bot))