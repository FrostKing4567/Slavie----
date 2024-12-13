import discord
from discord.ext import commands
from discord import app_commands
import os
import json 
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

class InviteManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="get_invite", description="Creates a new invite or retrieves an existing custom one.")
    @app_commands.describe(days="Number of days the invite should last (optional).")
    @commands.guild_only()  # Makes sure the command is used in a server, not in DMs
    @check_if_disabled()
    async def get_invite(self, interaction: discord.Interaction, days: int = None):
        """
        Creates a new invite or retrieves an existing custom one.
        If a number is provided, it creates an invite lasting that many days.
        """
        # Check if the bot has permission to create an invite
        if not interaction.guild.me.guild_permissions.create_instant_invite:
            return await interaction.response.send_message("I don't have permission to create invites.", ephemeral=True)

        # Get existing invites for the guild
        invites = await interaction.guild.invites()

        # Check if there is already a custom invite link
        custom_invite = None
        for invite in invites:
            if invite.inviter == interaction.guild.owner:  # Assuming the owner made a custom invite
                custom_invite = invite
                break
        
        if custom_invite:
            # Send the existing custom invite
            await interaction.response.send_message(f"Here is the custom invite: {custom_invite.url}")
        else:
            # If no custom invite, create a new one
            if days:
                # Create an invite lasting for 'days' (if specified)
                new_invite = await interaction.channel.create_invite(max_age=days*86400, max_uses=0)  # 86400 seconds in a day
                await interaction.response.send_message(f"Here is your invite for {days} day(s): {new_invite.url}")
            else:
                # Create a permanent invite (no expiration)
                new_invite = await interaction.channel.create_invite(max_age=0, max_uses=0)  # Permanent
                await interaction.response.send_message(f"Here is your permanent invite: {new_invite.url}")

async def setup(bot):
    await bot.add_cog(InviteManager(bot))
