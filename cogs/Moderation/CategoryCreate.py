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

class CreateCategory(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="create_category", description="Create a new category in the server.")
    @app_commands.describe(category_name="The name of the category to create")
    @check_if_disabled()
    @app_commands.checks.has_permissions(manage_channels=True)
    async def create_category(self, interaction: discord.Interaction, category_name: str):
        """Creates a new category channel in the server."""
        # Validate category_name
        if not category_name.strip():
            await interaction.response.send_message("Please provide a valid category name. ❌", ephemeral=True)
            return

        # Check if the bot has the required permissions
        if not interaction.guild.me.guild_permissions.manage_channels:
            await interaction.response.send_message("I need the **Manage Channels** permission to create categories!", ephemeral=True)
            return
        # Create the category
        category = await interaction.guild.create_category_channel(name=category_name)
        await interaction.response.send_message(f"🎉 Category `{category_name}` has been created successfully! ✅", ephemeral=False)

async def setup(bot):
    await bot.add_cog(CreateCategory(bot))
