import discord
from discord import app_commands
from discord.ext import commands
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

class PurgeCog(commands.Cog):
    """A cog for purging messages in a channel."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="purge", description="Purge messages from the channel.")
    @app_commands.describe(amount="The number of messages to purge (or 'all' to delete all messages)")
    @app_commands.checks.has_permissions(manage_messages=True)
    @check_if_disabled()
    async def purge(self, interaction: discord.Interaction, amount: str = None):
        """Purges messages from the channel."""
        if amount is None:
            await interaction.response.send_message("Oopsie! You forgot to tell me how many messages to purge~ Type `/purge [number]` or `/purge all` if you wanna reset the whole channel! 💫", ephemeral=True)
            return

        if amount.lower() == "all":
            # Save the channel info
            old_channel = interaction.channel
            new_channel_position = old_channel.position
            new_channel_name = old_channel.name
            new_channel_category = old_channel.category

            # Delete the old channel
            await old_channel.delete()

            # Check if the channel belongs to a category
            if new_channel_category:
                # Create a new channel in the same category
                new_channel = await new_channel_category.create_text_channel(new_channel_name, position=new_channel_position)
            else:
                # Create a new channel in the guild without a category
                new_channel = await interaction.guild.create_text_channel(new_channel_name, position=new_channel_position)

            # Send a confirmation message
            await new_channel.send(f"{interaction.user.mention}, I poofed the whole channel and made it shiny and new! ✨")
            await interaction.response.send_message("Done! The channel has been refreshed.")

        else:
            try:
                amount = int(amount)
                if amount <= 0:
                    await interaction.response.send_message("Hehe, I can't delete 0 or negative messages! Try a positive number, please~ 🌸", ephemeral=True)
                    return

                # Delete the specified amount of messages
                deleted = await interaction.channel.purge(limit=amount + 1)  # +1 to include the command message
                if amount >= 2:
                    await interaction.response.send_message(f"Poof! I deleted {len(deleted) - 1} messages for you~ 🌟", delete_after=5)  # -1 to exclude the command message
                elif amount == 1:
                    await interaction.response.send_message(f"Poof! I deleted 1 message for you~ 🌟", delete_after=5)

            except ValueError:
                await interaction.response.send_message("Hmm, that doesn't look like a number... try again or type `/purge all` to start fresh! 🌈", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("Oh no, I don't have permission to delete messages in this channel. 🚫", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.response.send_message(f"Oopsie! An error occurred while purging messages: {e} ❌", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"Oops! An unexpected error occurred: {e} 😓", ephemeral=True)

# Setup function for the cog
async def setup(bot):
    """Setup function for the PurgeCog."""
    await bot.add_cog(PurgeCog(bot))
