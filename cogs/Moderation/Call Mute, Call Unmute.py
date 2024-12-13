import discord
from discord.ext import commands
from datetime import datetime
import json
from pathlib import Path
from .moderation_utils import *  
from discord import app_commands
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

class CallMuteCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.mute_data_file = Path("e:/Programming/Discord Bot/DataBase/mute_data.json")
        self.mute_data = self.load_mute_data()

    def load_mute_data(self):
        """Load mute data from the JSON file."""
        if self.mute_data_file.exists():
            with open(self.mute_data_file, "r") as f:
                return json.load(f)
        return {}

    def save_mute_data(self):
        """Save mute data to the JSON file."""
        with open(self.mute_data_file, "w") as f:
            json.dump(self.mute_data, f, indent=4, default=str)

    @app_commands.command(name="callmute", description="Mute a member in the voice channel.")
    @app_commands.describe(member="The member to mute", reason="The reason for muting")
    @check_if_disabled()
    @app_commands.checks.has_permissions(mute_members=True)
    async def callmute(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        if member is None:
            await interaction.response.send_message("Oopsie! Please mention someone to mute in the voice channel! 🎙️", ephemeral=True)
            return

        try:
            # Mute the user
            await member.edit(mute=True)
            await interaction.response.send_message(f"🔇 {member.mention} has been muted in the voice channel! Reason: {reason} 🌸")

            # Save the mute event
            self.mute_data[str(member.id)] = {
                "reason": reason,
                "mute_time": datetime.utcnow().isoformat(),
                "muted_by": interaction.user.name,
                "guild": interaction.guild.name
            }
            self.save_mute_data()

            # DM the muted user
            dm_embed = discord.Embed(
                title="🔇 You've Been Muted 🔇",
                description=f"You have been voice chat muted in **{interaction.guild.name}**. Reason: {reason} 🌸",
                color=discord.Color.red()
            )
            await member.send(embed=dm_embed)

        except discord.Forbidden:
            await interaction.response.send_message("Oh no, I don't have permission to mute this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Oopsie! An error occurred while muting the user: {e} ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

    @app_commands.command(name="callunmute", description="Unmute a member in the voice channel.")
    @app_commands.describe(member="The member to unmute")
    @check_if_disabled()
    @app_commands.checks.has_permissions(mute_members=True)
    async def callunmute(self, interaction: discord.Interaction, member: discord.Member):
        if member is None:
            await interaction.response.send_message("Oopsie! Please mention someone to unmute in the voice channel! 🎙️", ephemeral=True)
            return

        try:
            # Unmute the user
            await member.edit(mute=False)
            await interaction.response.send_message(f"🔊 {member.mention} has been unmuted in the voice channel! 🌟")

            # Remove the mute event from the JSON file
            if str(member.id) in self.mute_data:
                del self.mute_data[str(member.id)]
                self.save_mute_data()

        except discord.Forbidden:
            await interaction.response.send_message("Oh no, I don't have permission to unmute this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Oopsie! An error occurred while unmuting the user: {e} ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

    async def send_unmute_dm(self, member, guild_name):
        dm_embed = discord.Embed(
            title="🔊 You've Been Unmuted 🔊",
            description=f"Hi {member.name}! You've been unmuted in **{guild_name}**. 🎉",
            color=discord.Color.green()
        )
        dm_embed.set_footer(text="If you have any questions, please reach out to the server admins. 💖")
        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # Do nothing if the DM fails

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(CallMuteCog(bot))
