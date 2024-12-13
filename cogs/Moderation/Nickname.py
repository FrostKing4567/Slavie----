# cogs/nickname.py

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

class Nickname(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="nickname", description="Change a member's nickname.")
    @app_commands.describe(
        member='The member whose nickname you want to change.',
        new_nickname='The new nickname to assign.'
    )
    @app_commands.checks.has_permissions(manage_nicknames=True)
    @check_if_disabled()
    async def nickname(self, interaction: discord.Interaction, member: discord.Member, new_nickname: str):
        """
        Change the nickname of a specified member.
        Only users with the Manage Nicknames permission can use this command.
        """
        # Ensure the command is used within a guild
        if interaction.guild is None:
            await interaction.response.send_message(
                "This command can only be used within a server.", ephemeral=True
            )
            return

        # Permission check: Does the user have permission to manage nicknames?
        # Already enforced by the decorator @app_commands.checks.has_permissions(manage_nicknames=True)

        # Check role hierarchy: Can the user change the member's nickname?
        if interaction.user.top_role <= member.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ You cannot change the nickname of someone with an equal or higher role than yours.",
                ephemeral=True
            )
            return

        # Check role hierarchy: Can the bot change the member's nickname?
        if interaction.guild.me.top_role <= member.top_role and interaction.user.id != interaction.guild.owner_id:
            await interaction.response.send_message(
                "❌ I cannot change the nickname of this member as their role is equal to or higher than mine.",
                ephemeral=True
            )
            return

        # Attempt to change the nickname
        try:
            await member.edit(nick=new_nickname)
            await interaction.response.send_message(
                f"✅ Nickname for {member.mention} has been changed to `{new_nickname}`!", ephemeral=False
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I do not have permission to change this member's nickname.", ephemeral=True
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ Failed to change the nickname due to an HTTP error.", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"❌ An unexpected error occurred: {e}", ephemeral=True
            )

    @nickname.error
    async def nickname_error(self, interaction: discord.Interaction, error):
        """Handle errors for the nickname command."""
        if isinstance(error, app_commands.errors.MissingPermissions):
            await interaction.response.send_message(
                "❌ You don't have permission to manage nicknames.", ephemeral=True
            )
        elif isinstance(error, app_commands.errors.CommandOnCooldown):
            await interaction.response.send_message(
                f"⏰ This command is on cooldown. Please try again later.", ephemeral=True
            )
        elif isinstance(error, app_commands.errors.MissingRequiredArgument):
            await interaction.response.send_message(
                "❌ Missing required arguments. Please provide both the member and the new nickname.",
                ephemeral=True
            )
        elif isinstance(error, app_commands.errors.CheckFailure):
            # This handles the custom check_if_disabled
            # The message is already sent in the check, so we can pass
            pass
        else:
            # For any other errors
            await interaction.response.send_message(
                "❌ An unexpected error occurred.", ephemeral=True
            )
            # Optionally, log the error
            print(f"Error in /nickname command: {error}")

async def setup(bot):
    await bot.add_cog(Nickname(bot))
