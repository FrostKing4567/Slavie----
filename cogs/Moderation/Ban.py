import discord
from discord.ext import commands
from datetime import datetime, timedelta
import re
import json
from pathlib import Path
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

class BanCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.ban_data = {}  # Dictionary to store ban data with unban times
        self.ban_data_file = Path("e:/Programming/Discord Bot/DataBase/ban_data.json")
        self.load_ban_data()  # Load ban data from file

    def load_ban_data(self):
        """Load ban data from the JSON file."""
        if self.ban_data_file.exists():
            with open(self.ban_data_file, "r") as f:
                self.ban_data = json.load(f)
        else:
            self.ban_data = {}

    def save_ban_data(self):
        """Save ban data to the JSON file."""
        with open(self.ban_data_file, "w") as f:
            json.dump(self.ban_data, f, indent=4, default=str)  # Convert datetime to string

    def parse_time(self, time_str):
        """Parses a time string like '1d', '2w', etc., into seconds."""
        match = re.match(r'(\d+)([dwm])', time_str.lower())
        if not match:
            return None

        value, unit = match.groups()
        value = int(value)

        if unit == 'd':
            return value * 86400  # Days to seconds
        elif unit == 'w':
            return value * 604800  # Weeks to seconds
        elif unit == 'm':
            return value * 2592000  # Months to seconds
        else:
            return None

    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="The member to ban", reason="The reason for the ban", time="Duration of the ban (e.g., '1d', '2w', '1m')")
    @check_if_disabled()
    @app_commands.checks.has_permissions(ban_members=True)
    async def ban(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", time: str = "forever"):
        try:
            if member == self.bot.user:
                await interaction.response.send_message("You can't ban me, dumahh. 😔", ephemeral=True)
                return

            if member == interaction.user:
                await interaction.response.send_message("You can't ban yourself, dumahh. 😔", ephemeral=True)
                return

            if interaction.guild.owner == member:
                await interaction.response.send_message("You can't ban the server owner, dumahh. 😔", ephemeral=True)
                return

            if interaction.user.top_role <= member.top_role and interaction.user != interaction.guild.owner:
                await interaction.response.send_message("You can't ban someone with a higher or equal role than yours! 🌟", ephemeral=True)
                return

            if time.lower() != "forever":
                seconds = self.parse_time(time)
                if seconds is None:
                    await interaction.response.send_message("Oops! Please provide a valid ban duration (e.g., '1d', '1w', '1m')! ⏳", ephemeral=True)
                    return
                unban_time = datetime.utcnow() + timedelta(seconds=seconds)
                self.ban_data[str(member.id)] = {
                    "reason": reason,
                    "ban_time": datetime.utcnow().isoformat(),
                    "unban_time": unban_time.isoformat(),
                    "banner": interaction.user.name
                }
            else:
                unban_time = None
                self.ban_data.pop(str(member.id), None)  # Remove any existing ban duration

            self.save_ban_data()  # Save ban data to the file

            ban_embed = discord.Embed(
                title="⛔ Ban Notice ⛔",
                description=f"**{member.name}** has been banned from the server. 😔",
                color=discord.Color.red()
            )
            ban_embed.add_field(name="💬 Reason", value=reason, inline=False)
            ban_embed.add_field(name="⏰ Duration", value=f"{time}" if time.lower() != "forever" else "Forever", inline=False)
            ban_embed.add_field(name="👤 Banned User", value=f"{member.mention} (ID: {member.id})", inline=False)

            await member.ban(reason=reason)
            await interaction.response.send_message(embed=ban_embed)

            # DM the banned user with an embed
            dm_embed = discord.Embed(
                title="🌸 You've Been Banned 🌸",
                description=f"Hi {member.name}! You've been banned from **{interaction.guild.name}**. 😔",
                color=discord.Color.red()
            )
            dm_embed.add_field(name="💬 Reason", value=reason, inline=False)
            dm_embed.add_field(name="⏰ Duration", value=f"{time}" if time.lower() != "forever" else "Forever", inline=False)

            try:
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(f"Couldn't send DM to {member.name}. 😔", ephemeral=True)

            if unban_time:
                await discord.utils.sleep_until(unban_time)
                await interaction.guild.unban(member, reason="Temporary ban duration expired.")
                await self.send_unban_dm(member, interaction.guild.name)

        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to ban this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to ban the user: {e}. ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}. 😓", ephemeral=True)

    @app_commands.command(name="unban", description="Unban a user from the server.")
    @app_commands.describe(user_id="The ID of the user to unban")
    @check_if_disabled()
    @app_commands.checks.has_permissions(ban_members=True)
    async def unban(self, interaction: discord.Interaction, user_id: str):
        try:
            # Validate the user ID
            if not user_id.isdigit():
                await interaction.response.send_message("Please provide a valid user ID. ❌", ephemeral=True)
                return

            # Attempt to fetch the user object using the user ID
            user = await self.bot.fetch_user(user_id)

            # Check if the user is actually banned
            bans = await interaction.guild.bans()
            banned_users = [ban_entry.user.id for ban_entry in bans]
            if int(user_id) not in banned_users:
                await interaction.response.send_message(f"No banned user found with ID {user_id}. 🤔", ephemeral=True)
                return

            # Unban the user from the guild
            await interaction.guild.unban(user, reason=f"Unbanned by {interaction.user}.")

            # Confirm the unban action with a message
            await interaction.response.send_message(f"Successfully unbanned {user.name}! 🎉", ephemeral=False)

            # Remove the user from the ban_data JSON file
            if str(user_id) in self.ban_data:
                del self.ban_data[str(user_id)]
                self.save_ban_data()

        except discord.NotFound:
            await interaction.response.send_message(f"No user found with ID {user_id}. 🤔", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to unban this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Failed to unban the user: {e}. ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {e}. 😓", ephemeral=True)

    async def send_unban_dm(self, member, guild_name):
        dm_embed = discord.Embed(
            title="🌟 You've Been Unbanned! 🌟",
            description=f"Hi {member.name}! You've been unbanned from **{guild_name}**. 🎉",
            color=discord.Color.green()
        )
        dm_embed.set_footer(text="If you have any questions, please reach out to the server admins. 💖")
        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass  # Do nothing if the DM fails

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(BanCog(bot))
