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

class AddRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="add_role")
    @check_if_disabled()
    async def add_role(self, interaction: discord.Interaction, member: discord.Member, role: discord.Role):
        # Ensure the user has the Manage Roles permission
        if not interaction.user.guild_permissions.manage_roles:
            await interaction.response.send_message("You don't have permission to manage roles!", ephemeral=True)
            return

        # Ensure the bot has the correct permissions
        if not interaction.guild.me.guild_permissions.manage_roles:
            await interaction.response.send_message("I need the **Manage Roles** permission to add roles!", ephemeral=True)
            return

        # Ensure the role isn't higher than the bot's top role
        if role.position >= interaction.guild.me.top_role.position:
            await interaction.response.send_message("I cannot add this role as it is higher than my highest role!", ephemeral=True)
            return

        # Ensure the role isn't higher than the user's highest role
        if role.position >= interaction.user.top_role.position:
            await interaction.response.send_message("You cannot add a role higher or equal to your highest role!", ephemeral=True)
            return

        try:
            # Add the role to the member
            await member.add_roles(role)
            await interaction.response.send_message(f"Successfully added the {role.name} role to {member.display_name}!", ephemeral=False)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to add this role!", ephemeral=True)
        except discord.HTTPException:
            await interaction.response.send_message("Failed to add the role due to a network error.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(AddRole(bot))
