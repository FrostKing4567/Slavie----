import discord
from discord.ext import commands
from datetime import datetime
import json
from pathlib import Path
from .moderation_utils import handle_missing_permissions, create_embed, calculate_remaining_time
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

class DeafenCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.deafen_data_file = Path("e:/Programming/Discord Bot/DataBase/deafen_data.json")
        self.deafen_data = self.load_deafen_data()

    def load_deafen_data(self):
        """Load deafen data from the JSON file."""
        if self.deafen_data_file.exists():
            with open(self.deafen_data_file, "r") as f:
                return json.load(f)
        return {}

    def save_deafen_data(self):
        """Save deafen data to the JSON file."""
        with open(self.deafen_data_file, "w") as f:
            json.dump(self.deafen_data, f, indent=4)

    @app_commands.command(name="deafen", description="Deafen a member in the voice channel.")
    @app_commands.describe(member="The member to deafen", reason="The reason for deafening")
    @app_commands.checks.has_permissions(deafen_members=True)
    @check_if_disabled()
    async def deafen(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
        try:
            # Deafen the user
            await member.edit(deafen=True)
            await interaction.response.send_message(f"🔇 {member.name} has been deafened in the voice channel! Reason: {reason} 🌸")

            # Save the deafen event
            self.deafen_data[str(member.id)] = {
                "reason": reason,
                "deafen_time": datetime.utcnow().isoformat(),
                "deafened_by": interaction.user.name,
                "guild": interaction.guild.name
            }
            self.save_deafen_data()

            # DM the deafened user
            dm_embed = discord.Embed(
                title="🔇 Voice Channel Deafened 🔇",
                description=f"Hi {member.name}! You've been deafened in a voice channel in **{interaction.guild.name}**. 😔",
                color=discord.Color.red()
            )
            dm_embed.add_field(name="💬 Reason", value=reason, inline=False)
            dm_embed.set_footer(text="If you have any questions, please reach out to the server admins. 💖")

            try:
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(f"Couldn't send DM to {member.name}. 😔")

        except discord.Forbidden:
            await interaction.response.send_message("Oh no, I don't have permission to deafen this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Oopsie! An error occurred while deafening the user: {e} ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

    @app_commands.command(name="undeafen", description="Undeafen a member in the voice channel.")
    @app_commands.describe(member="The member to undeafen")
    @app_commands.checks.has_permissions(deafen_members=True)
    @check_if_disabled()
    async def undeafen(self, interaction: discord.Interaction, member: discord.Member):
        try:
            # Undeafen the user
            await member.edit(deafen=False)
            await interaction.response.send_message(f"🔊 {member.name} has been undeafened in the voice channel! 🌟")

            # Remove the deafen event from the JSON file
            if str(member.id) in self.deafen_data:
                del self.deafen_data[str(member.id)]
                self.save_deafen_data()

        except discord.Forbidden:
            await interaction.response.send_message("Oh no, I don't have permission to undeafen this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Oopsie! An error occurred while undeafening the user: {e} ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

    def create_embed(self, title, description):
        """Helper method to create an embed."""
        return discord.Embed(title=title, description=description, color=discord.Color.red())

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(DeafenCog(bot))
