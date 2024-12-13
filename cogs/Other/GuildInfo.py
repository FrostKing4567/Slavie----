import discord
from discord.ext import commands
import os
import json
import requests
from io import BytesIO
from colorthief import ColorThief
from discord import app_commands
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

class GuildInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_guild_icon_color(self, icon_url):
        """Get the dominant color from the guild's icon."""
        try:
            response = requests.get(icon_url)
            image_data = BytesIO(response.content)
            color_thief = ColorThief(image_data)
            # Get the dominant color
            dominant_color = color_thief.get_color(quality=1)
            return discord.Color.from_rgb(*dominant_color)
        except Exception as e:
            print(f"Error fetching color from guild icon: {e}")
            return discord.Color.random()  # Fallback to a random color

    @app_commands.command(name='guildinfo', description="Get information about the guild.")
    @check_if_disabled()
    async def guildinfo(self, interaction: discord.Interaction):
        guild = interaction.guild

        # Get the dominant color from the guild's icon
        icon_color = self.get_guild_icon_color(guild.icon.url) if guild.icon else discord.Color.random()

        embedded_msg = discord.Embed(title='🌟 Guild Information 🌟', color=icon_color)
        embedded_msg.set_thumbnail(url=guild.icon.url if guild.icon else discord.Embed.Empty)

        embedded_msg.add_field(name='Server Name:', value=f"**{guild.name}**", inline=False)
        embedded_msg.add_field(name='Server ID:', value=f"📜 {guild.id}", inline=False)
        embedded_msg.add_field(name='Total Members:', value=f"{guild.member_count} members", inline=False)
        online_count = len([m for m in guild.members if m.status != discord.Status.offline])
        embedded_msg.add_field(name='Online Members:', value=f"🌼 {online_count} online", inline=False)
        embedded_msg.add_field(name='Created On:', value=f"🎉 {guild.created_at.strftime('%Y-%m-%d')}", inline=False)

        embedded_msg.add_field(name='Text Channels:', value=f"📚 {len(guild.text_channels)} channels", inline=False)
        embedded_msg.add_field(name='Voice Channels:', value=f"🔊 {len(guild.voice_channels)} channels", inline=False)

        embedded_msg.set_footer(text=f"Requested by {interaction.user} 💞", icon_url=interaction.user.avatar.url)
        
        await interaction.response.send_message(embed=embedded_msg)

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(GuildInfoCog(bot))
