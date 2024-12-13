import discord
from discord.ext import commands
from discord import app_commands
import os
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["Slavie"]  # Database name
disabled_commands_col = db.disabled_commands
warn_data_col = db.warn_data

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

class WarnCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def save_warn_data(self, guild_id, member_id, warn_data):
        """Save warning data to MongoDB."""
        warn_data_col.update_one(
            {"guild_id": guild_id, "member_id": member_id},
            {"$set": warn_data},
            upsert=True
        )

    def load_warn_data(self, guild_id, member_id):
        """Load warning data from MongoDB."""
        return warn_data_col.find_one({"guild_id": guild_id, "member_id": member_id}) or {
            "warn_count": 0,
            "warnings": []
        }

    @app_commands.command(name="warn", description="Warn a member in the server.")
    @app_commands.describe(member="The member to warn", reason="The reason for the warning")
    @app_commands.checks.has_permissions(kick_members=True)
    @check_if_disabled()
    async def warn_interaction(self, interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):

        if member == self.bot.user:
            await interaction.response.send_message("You can't ban me, dumahh. 😔", ephemeral=True)
            return
        if interaction.user.id == member.id:
            await interaction.response.send_message("You cannot warn yourself! 🌟", ephemeral=True)
            return
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("You do not have permission to complete this action. ❌", ephemeral=True)
            return

        if member.bot:  # Skip warnings for bots
            await interaction.response.send_message("You cannot warn bots! 🌟", ephemeral=True)
            return

        if interaction.user != interaction.guild.owner:
            if member.top_role >= interaction.user.top_role:
                await interaction.response.send_message("You can't warn someone with a higher or equal role than yours! 🌟", ephemeral=True)
                return

        guild_id = str(interaction.guild.id)
        member_id = str(member.id)

        # Load the existing warning data from MongoDB
        warn_data = self.load_warn_data(guild_id, member_id)

        # Increment the warning count for the member
        warn_data["warn_count"] += 1
        warn_count = warn_data["warn_count"]

        # Append the new warning to the member's warning history
        warn_data["warnings"].append({
            "reason": reason,
            "time": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        })

        # Save the updated warning data to MongoDB
        self.save_warn_data(guild_id, member_id, warn_data)

        # Create an embed to show the warning
        warn_embed = discord.Embed(
            title="⚠️ Warning Notice ⚠️",
            description=f"**{member.name}** has been warned. 😔",
            color=discord.Color.yellow()
        )
        warn_embed.set_thumbnail(url=member.display_avatar.url)
        warn_embed.add_field(name="💬 Reason", value=reason, inline=False)
        warn_embed.add_field(name="🚨 Warning Count", value=f"{warn_count}/3", inline=False)
        warn_embed.set_footer(text=f"Requested by {interaction.user.name} 💕", icon_url=interaction.user.display_avatar.url)

        # Acknowledge the interaction and respond with the embed
        await interaction.response.send_message(embed=warn_embed)

        # DM the warned user with an embed
        dm_embed = discord.Embed(
            title="🌸 You've Been Warned 🌸",
            description=f"Hi {member.name}! You've been warned in **{interaction.guild.name}**. 😔",
            color=discord.Color.yellow()
        )
        dm_embed.add_field(name="💬 Reason", value=reason, inline=False)
        dm_embed.add_field(name="🚨 Warning Count", value=f"{warn_count}/3", inline=False)
        dm_embed.set_footer(text="Please be mindful of the server rules. 💖")

        try:
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            await interaction.followup.send("Couldn't send DM to the member. They may have DMs disabled. 😔", ephemeral=True)
        except discord.HTTPException as e:
            await interaction.followup.send(f"An error occurred while sending DM: {str(e)}", ephemeral=True)

        # Check if the user has reached 3 warnings and kick them if so
        if warn_count >= 3:
            try:
                await member.kick(reason="Received 3 warnings")
                kick_embed = discord.Embed(
                    title="🚪 Auto-Kick 🚪",
                    description=f"**{member.name}** has been kicked from the server after receiving 3 warnings. 😔",
                    color=discord.Color.orange()
                )
                kick_embed.set_thumbnail(url=member.display_avatar.url)
                kick_embed.set_footer(text=f"Requested by {interaction.user.name} 💕", icon_url=interaction.user.display_avatar.url)
                await interaction.followup.send(embed=kick_embed)

                # Notify the user they were kicked
                dm_kick_embed = discord.Embed(
                    title="🌸 You've Been Kicked 🌸",
                    description=f"Hi {member.name}! You've been kicked from **{interaction.guild.name}** for receiving 3 warnings. 😔",
                    color=discord.Color.orange()
                )
                dm_kick_embed.set_footer(text="If you have any questions, please reach out to the server admins. 💖")

                try:
                    await member.send(embed=dm_kick_embed)
                except discord.Forbidden:
                    await interaction.followup.send("Couldn't send DM to the member about their kick. They may have DMs disabled. 😔", ephemeral=True)
                except discord.HTTPException as e:
                    await interaction.followup.send(f"An error occurred while sending DM about kick: {str(e)}", ephemeral=True)

                # Remove the user's warning data after being kicked
                warn_data_col.delete_one({"guild_id": guild_id, "member_id": member_id})

            except discord.Forbidden:
                await interaction.followup.send(f"Could not kick {member.name}. ❌", ephemeral=True)
            except discord.HTTPException as e:
                await interaction.followup.send(f"An error occurred while kicking {member.name}: {str(e)}", ephemeral=True)

    @app_commands.command(name="removewarns", description="Remove all warnings for a member.")
    @app_commands.describe(member="The member whose warnings you want to remove")
    @check_if_disabled()
    async def removewarns_interaction(self, interaction: discord.Interaction, member: discord.Member):
        if not interaction.user.guild_permissions.kick_members:
            await interaction.response.send_message("You do not have permission to complete this action. ❌", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        member_id = str(member.id)

        if warn_data_col.find_one({"guild_id": guild_id, "member_id": member_id}):
            # Remove warnings for the member from MongoDB
            warn_data_col.delete_one({"guild_id": guild_id, "member_id": member_id})
            await interaction.response.send_message(f"All warnings for **{member.name}** have been removed. 🌟", ephemeral=True)
        else:
            await interaction.response.send_message(f"**{member.name}** has no warnings to remove. 🌟", ephemeral=True)

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(WarnCog(bot))
