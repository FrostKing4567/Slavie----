import os
import discord
from discord.ext import commands
from discord import app_commands
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "Slavie"

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Define the disabled_commands collection
disabled_commands_col = db.disabled_commands

# Command categories
MUSIC_COMMANDS = [
    "join", "loop", "loopall", "move", "pause", "play", "resume",
    "shuffle", "skip", "stop", "volume"
]

MODERATION_COMMANDS = [
    "ban", "unban", "kick", "callmute", "callunmute", "deafen", "undeafen",
    "enslave", "unenslave", "get_invite", "mute", "unmute",
    "nickname", "purge", "recreate", "add_role", "create_role", "delete_role",
    "remove_role", "rename_role", "create_vc", "warn", "create_category",
    "create_channel", "delete"
]

INTERACT_COMMANDS = [
    "adopt", "cancel_adoption", "abandon", "kiss", "hug", "slap", "marry", 
    "cancel_proposal", "accept", "decline", "divorce", "runaway"
]

OTHER_COMMANDS = [
    "ping", "sub", "userinfo", "familyinfo", "guildinfo", "help"
]

class CommandManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_command_disabled(self, guild_id: int, command_name: str) -> bool:
        """Check if a command is disabled for a specific guild."""
        guild_id_str = str(guild_id)
        command_name_lower = command_name.lower()
        guild = disabled_commands_col.find_one({"guild_id": guild_id_str})
        if guild and "commands" in guild:
            return command_name_lower in guild["commands"]
        return False

    @app_commands.command(name="disable", description="Disable a command or a group of commands for this guild.")
    @app_commands.checks.has_permissions(administrator=True)
    async def disable_command(self, interaction: discord.Interaction, command_name: str):
        """Disable a command or group of commands for this guild."""
        guild_id_str = str(interaction.guild.id)
        command_name_lower = command_name.lower()

        # Determine which commands to disable
        if command_name_lower == "music":
            commands_to_disable = MUSIC_COMMANDS
        elif command_name_lower == "moderation":
            commands_to_disable = MODERATION_COMMANDS
        elif command_name_lower == "interactions":
            commands_to_disable = INTERACT_COMMANDS
        elif command_name_lower == "other":
            commands_to_disable = OTHER_COMMANDS
        else:
            commands_to_disable = [command_name_lower]

        # Fetch current disabled commands for the guild
        guild = disabled_commands_col.find_one({"guild_id": guild_id_str})
        if not guild:
            disabled_commands_col.insert_one({"guild_id": guild_id_str, "commands": []})
            guild = {"guild_id": guild_id_str, "commands": []}

        updated = False
        for cmd in commands_to_disable:
            if cmd not in guild["commands"]:
                guild["commands"].append(cmd)
                updated = True

        if updated:
            disabled_commands_col.update_one(
                {"guild_id": guild_id_str},
                {"$set": {"commands": guild["commands"]}}
            )
            if command_name_lower in ["music", "moderation", "interactions", "other"]:
                await interaction.response.send_message(f"All `{command_name_lower}` commands have been disabled.", ephemeral=False)
            else:
                await interaction.response.send_message(f"The command `{command_name_lower}` has been disabled.", ephemeral=False)
        else:
            await interaction.response.send_message(f"The command(s) `{command_name}` are already disabled.", ephemeral=False)

    @app_commands.command(name="enable", description="Enable a command or a group of commands for this guild.")
    @app_commands.checks.has_permissions(administrator=True)
    async def enable_command(self, interaction: discord.Interaction, command_name: str):
        """Enable a command or group of commands for this guild."""
        guild_id_str = str(interaction.guild.id)
        command_name_lower = command_name.lower()

        # Determine which commands to enable
        if command_name_lower == "music":
            commands_to_enable = MUSIC_COMMANDS
        elif command_name_lower == "moderation":
            commands_to_enable = MODERATION_COMMANDS
        elif command_name_lower == "interactions":
            commands_to_enable = INTERACT_COMMANDS
        elif command_name_lower == "other":
            commands_to_enable = OTHER_COMMANDS
        else:
            commands_to_enable = [command_name_lower]

        # Fetch current disabled commands for the guild
        guild = disabled_commands_col.find_one({"guild_id": guild_id_str})
        if not guild:
            await interaction.response.send_message(f"No commands are disabled in this server.", ephemeral=False)
            return

        updated = False
        for cmd in commands_to_enable:
            if cmd in guild["commands"]:
                guild["commands"].remove(cmd)
                updated = True

        if updated:
            if guild["commands"]:
                disabled_commands_col.update_one(
                    {"guild_id": guild_id_str},
                    {"$set": {"commands": guild["commands"]}}
                )
            else:
                disabled_commands_col.delete_one({"guild_id": guild_id_str})

            if command_name_lower in ["music", "moderation", "interactions", "other"]:
                await interaction.response.send_message(f"All `{command_name_lower}` commands have been enabled.", ephemeral=False)
            else:
                await interaction.response.send_message(f"The command `{command_name_lower}` has been enabled.", ephemeral=False)
        else:
            await interaction.response.send_message(f"The command(s) `{command_name}` are not disabled or don't exist.", ephemeral=False)

    @commands.Cog.listener()
    async def on_application_command(self, interaction: discord.Interaction):
        """Listener to check if a command is disabled before it is invoked."""
        command_name = interaction.command.name
        guild_id = interaction.guild.id if interaction.guild else None

        if guild_id:
            if await self.is_command_disabled(guild_id, command_name):
                await interaction.response.send_message(
                    f"The command `{command_name}` is disabled in this server.",
                    ephemeral=True
                )
                return

async def setup(bot):
    await bot.add_cog(CommandManager(bot))
