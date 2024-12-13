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

class KickCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.kick_data_file = Path("e:/Programming/Discord Bot/DataBase/kick_data.json")
        self.kick_data = self.load_kick_data()

    # Load kick data from a JSON file
    def load_kick_data(self):
        if self.kick_data_file.exists():
            with open(self.kick_data_file, "r") as f:
                return json.load(f)
        return {}

    # Save kick data to a JSON file
    def save_kick_data(self):
        with open(self.kick_data_file, "w") as f:
            json.dump(self.kick_data, f, indent=4)

    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="The reason for kicking the member", image_url="An optional image URL")
    @app_commands.checks.has_permissions(kick_members=True)
    @check_if_disabled()
    async def kick(self, interaction: discord.Interaction, member: discord.Member = None, reason: str = "No reason provided", image_url: str = None):
        if member is None:
            await interaction.response.send_message("Oopsie! Please mention someone to kick! 🌸", ephemeral=True)
            return

        if member == self.bot.user:
            await interaction.response.send_message("You can't kick me, dumahh. 😔", ephemeral=True)
            return

        if member == interaction.user:
            await interaction.response.send_message("You can't kick yourself, dumahh. 😔", ephemeral=True)
            return

        if interaction.guild.owner == member:
            await interaction.response.send_message("You can't kick the server owner, dumahh. 😔", ephemeral=True)
            return

        if interaction.user.top_role <= member.top_role and interaction.user != interaction.guild.owner:
            await interaction.response.send_message(embed=self.create_embed("You can't kick someone with a higher or equal role than yours! 🌟"), ephemeral=True)
            return

        try:
            # Log the kick event in the JSON file
            self.kick_data[str(member.id)] = {
                "reason": reason,
                "kicked_by": interaction.user.name,
                "guild": interaction.guild.name,
                "kick_time": datetime.utcnow().isoformat()
            }
            self.save_kick_data()

            # Create embed to send in the server
            kick_embed = discord.Embed(
                title="🚪 Kick Notice 🚪",
                description=f"**{member.name}** has been kicked from the server. 😔",
                color=discord.Color.orange()
            )
            kick_embed.set_thumbnail(url=member.display_avatar.url)
            kick_embed.add_field(name="💬 Reason", value=reason, inline=False)
            kick_embed.add_field(name="👤 Kicked User", value=f"{member.mention} (ID: {member.id})", inline=False)
            if image_url:
                kick_embed.set_image(url=image_url)
            kick_embed.set_footer(text=f"Requested by {interaction.user.name} 💕", icon_url=interaction.user.display_avatar.url)

            # Kick the member
            await member.kick(reason=reason)
            await interaction.response.send_message(embed=kick_embed)

            # DM the kicked user with an embed
            dm_embed = discord.Embed(
                title="🌸 You've Been Kicked 🌸",
                description=f"Hi {member.name}! You've been kicked from **{interaction.guild.name}**. 😔",
                color=discord.Color.orange()
            )
            dm_embed.add_field(name="💬 Reason", value=reason, inline=False)
            if image_url:
                dm_embed.set_image(url=image_url)
            dm_embed.set_footer(text="If you have any questions, please reach out to the server admins. 💖")

            try:
                await member.send(embed=dm_embed)
            except discord.Forbidden:
                await interaction.followup.send(f"Couldn't send DM to {member.name}. 😔", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("Oh no, I don't have permission to kick this user. 🚫", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.response.send_message(f"Oopsie! An error occurred while kicking the user: {e} ❌", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

    def create_embed(self, title, description):
        return discord.Embed(title=title, description=description, color=discord.Color.red())

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(KickCog(bot))
