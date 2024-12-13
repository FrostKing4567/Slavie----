import discord
from discord import app_commands
from discord.ext import commands
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

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Sends a ping command with the bot's latency.")
    @check_if_disabled()
    async def ping(self, interaction: discord.Interaction):
        """Sends a ping command with the bot's latency."""
        latency = round(self.bot.latency * 1000)
        ping_embed = discord.Embed(
            title='Ping',
            description='Latency in ms',
            color = 0xE6E6FA
        )
        # Use `self.bot.user.avatar.url` to get the URL of the bot's avatar
        ping_embed.set_thumbnail(url=self.bot.user.avatar.url)
        ping_embed.add_field(
            name=f"{self.bot.user.name}'s latency (ms):",
            value=f"{latency}ms",
            inline=False
        )
        # Use `interaction.user.display_avatar.url` to get the URL of the author's avatar
        ping_embed.set_footer(text=f"Requested by {interaction.user}💞", icon_url=interaction.user.avatar)
        
        # Respond to the interaction with the embed
        await interaction.response.send_message(embed=ping_embed)

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(Ping(bot))

