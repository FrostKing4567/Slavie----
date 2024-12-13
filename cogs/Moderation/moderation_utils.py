# /bot/cogs/Moderation/moderation_utils.py
import discord
from discord.ext import commands
from discord import app_commands


# Error handler function
async def handle_missing_permissions(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        missing_permissions = ', '.join(error.missing_permissions)
        await ctx.send(f"Oops! You don't have permission to do that. You need the `{missing_permissions}` permission(s) to run this command. 🚫")
    else:
        raise error  # Re-raise the error if it's not handled here

# Function to create an embed
def create_embed(title, description, color=discord.Color.default(), thumbnail_url=None):
    embed = discord.Embed(title=title, description=description, color=color)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)
    return embed

# Placeholder function to calculate remaining time for a ban
async def calculate_remaining_time(ban_entry):
    # You can implement the logic based on your ban data structure
    return "1 day"
