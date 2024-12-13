import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import json
from pymongo import MongoClient
from dotenv import load_dotenv
import os

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

class RecreateCog(commands.Cog):
    """A cog for recreating all channels in a server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="recreate", description="Recreates all channels and categories in the server.")
    @commands.has_permissions(administrator=True)
    @check_if_disabled()
    async def recreate(self, interaction: discord.Interaction):
        """Recreates all channels and categories in the server."""
        # Gather existing channels and categories
        existing_channels = interaction.guild.channels
        categories = [channel for channel in existing_channels if isinstance(channel, discord.CategoryChannel)]
        
        # Prepare to save channel information
        channel_info = {}

        # Collect information from categories and their channels
        for category in categories:
            channel_info[category.id] = {
                "name": category.name,
                "channels": [],
            }
            for channel in category.channels:
                channel_info[category.id]["channels"].append({
                    "type": "text" if isinstance(channel, discord.TextChannel) else "voice",
                    "name": channel.name,
                    "topic": getattr(channel, "topic", None),
                    "bitrate": getattr(channel, "bitrate", None),
                    "user_limit": getattr(channel, "user_limit", None),
                    "position": channel.position,
                })

        # Also handle channels that are not in any category
        for channel in existing_channels:
            if isinstance(channel, discord.TextChannel) or isinstance(channel, discord.VoiceChannel):
                if channel.category is None:  # Check if the channel is not in any category
                    channel_info[channel.id] = {
                        "name": channel.name,
                        "type": "text" if isinstance(channel, discord.TextChannel) else "voice",
                        "topic": getattr(channel, "topic", None),
                        "bitrate": getattr(channel, "bitrate", None),
                        "user_limit": getattr(channel, "user_limit", None),
                        "position": channel.position,
                    }

        # Save the channel_info to a JSON file
        with open("e:/Programming/Discord Bot/DataBase/channel_info.json", "w") as f:
            json.dump(channel_info, f, indent=4)

        # Confirm the information was saved
        await interaction.response.send_message("Hold on! I'm going to recreate all channels now... 🌟")

        # Delete all channels and categories concurrently using semaphores
        semaphore_delete = asyncio.Semaphore(5)  # Limit concurrency to 5
        async def delete_channel(channel: discord.abc.GuildChannel):
            async with semaphore_delete:
                try:
                    await channel.delete()
                except discord.Forbidden:
                    pass
                except discord.HTTPException as e:
                    pass

        # Create deletion tasks
        delete_channel_tasks = [delete_channel(channel) for channel in existing_channels]
        await asyncio.gather(*delete_channel_tasks)

        # Load the channel information from the JSON file
        with open("e:/Programming/Discord Bot/DataBase/channel_info.json", "r") as f:
            channel_info = json.load(f)

        # Semaphore to limit channel creation concurrency
        semaphore_create = asyncio.Semaphore(5)  # Limit concurrency to 5
        
        async def create_channel(info, category=None):
            async with semaphore_create:
                try:
                    if info["type"] == "text":
                        await interaction.guild.create_text_channel(
                            info["name"],
                            category=category,
                            topic=info.get("topic"),
                            position=info["position"]
                        )
                    elif info["type"] == "voice":
                        await interaction.guild.create_voice_channel(
                            info["name"],
                            category=category,
                            bitrate=info["bitrate"],
                            user_limit=info["user_limit"],
                            position=info["position"]
                        )
                except discord.Forbidden:
                    pass
                except discord.HTTPException as e:
                    pass

        # Recreate the channels from the saved information
        create_tasks = []
        for category_id, info in channel_info.items():
            if isinstance(info, dict) and "channels" in info:
                # Create the category
                new_category = await interaction.guild.create_category(info["name"])
                # Create the channels in the new category
                for channel in info["channels"]:
                    create_tasks.append(create_channel(channel, category=new_category))
            else:
                # Handle standalone channels
                create_tasks.append(create_channel(info))

        # Execute channel creation tasks concurrently
        await asyncio.gather(*create_tasks)

        # Send a confirmation message to the user via DM
        await interaction.user.send("All channels have been recreated successfully! 🎉")

# Setup function for the cog
async def setup(bot: commands.Bot):
    """Setup function for the RecreateCog."""
    await bot.add_cog(RecreateCog(bot))
