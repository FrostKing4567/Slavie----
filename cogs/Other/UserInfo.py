import discord
from discord.ext import commands
from discord import app_commands
import os
import requests
from io import BytesIO
from colorthief import ColorThief
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")

client = MongoClient(MONGODB_URI)
db = client["Slavie"]  # Database name
disabled_commands_col = db.disabled_commands
marriages_col = db.marriages
adoptions_col = db.adoptions

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

class UserInfoCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def get_avatar_color(self, avatar_url):
        """Get the dominant color from the user's avatar."""
        try:
            response = requests.get(avatar_url)
            image_data = BytesIO(response.content)
            color_thief = ColorThief(image_data)
            # Get the dominant color
            dominant_color = color_thief.get_color(quality=1)
            return discord.Color.from_rgb(*dominant_color)
        except Exception as e:
            print(f"Error fetching color from avatar: {e}")
            return discord.Color.random()  # Fallback to a random color

    @app_commands.command(name='userinfo', description='Get user information')
    @check_if_disabled()
    async def userinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user

        # Fetch member to get the most updated status
        try:
            member = await interaction.guild.fetch_member(member.id)
        except discord.NotFound:
            await interaction.response.send_message("User not found.", ephemeral=True)
            return

        avatar_color = self.get_avatar_color(member.avatar.url)
        embedded_msg = discord.Embed(title='✨ User Information ✨', color=avatar_color)
        embedded_msg.set_thumbnail(url=member.avatar.url)

        # Adjusted status fetching
        status_map = {
            discord.Status.online: "💚 Online",
            discord.Status.idle: "💛 Idle",
            discord.Status.dnd: "❤️ Do Not Disturb",
            discord.Status.offline: "⚪ Offline",
        }
        status = status_map.get(member.status, "⚪ Unknown")

        embedded_msg.add_field(name='Username:', value=f"**{member.name}**", inline=False)
        embedded_msg.add_field(name='Nickname:', value=member.nick if member.nick else 'None', inline=False)
        embedded_msg.add_field(name='User ID:', value=f"**{member.id}**", inline=False)
        embedded_msg.add_field(name='Account Created On:', value=f"🌟 {member.created_at.strftime('%Y-%m-%d')}", inline=False)
        embedded_msg.add_field(name='Joined Server On:', value=f"🌼 {member.joined_at.strftime('%Y-%m-%d')}", inline=False)
        embedded_msg.add_field(name='Status:', value=status, inline=False)

        roles = [role.mention for role in member.roles if role.name != '@everyone']
        embedded_msg.add_field(name='Roles:', value=', '.join(roles) if roles else 'No roles', inline=False)

        embedded_msg.set_footer(text=f"Requested by {interaction.user} 💞", icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=embedded_msg)

    @app_commands.command(name='familyinfo', description='Get family information')
    @check_if_disabled()
    async def familyinfo(self, interaction: discord.Interaction, member: discord.Member = None):
        if member is None:
            member = interaction.user

        # Fetch member to get the most updated status
        try:
            member = await interaction.guild.fetch_member(member.id)
        except discord.NotFound:
            await interaction.response.send_message("User not found.", ephemeral=True)
            return

        avatar_color = self.get_avatar_color(member.avatar.url)
        embedded_msg = discord.Embed(title='👨‍👩‍👦 Family Information 👨‍👩‍👦', color=avatar_color)
        embedded_msg.set_thumbnail(url=member.avatar.url)

        spouse_data = marriages_col.find_one({"user_id": str(member.id)})
        children_data = adoptions_col.find({"adopted_by": str(member.id)})
        adoption_data = adoptions_col.find_one({"user_id": str(member.id)})

        spouse_id = spouse_data.get("married_to") if spouse_data else None
        children_mentions = []
        parents_mentions = []

        if spouse_id:
            spouse = interaction.guild.get_member(int(spouse_id))
            if spouse:
                embedded_msg.add_field(name='Spouse:', value=f"{spouse.mention} 💍", inline=False)
            else:
                try:
                    spouse = await self.bot.fetch_user(int(spouse_id))
                    embedded_msg.add_field(name='Spouse:', value=f"{spouse.display_name} 💍", inline=False)
                except discord.NotFound:
                    embedded_msg.add_field(name='Spouse:', value="Spouse not found.", inline=False)
        else:
            embedded_msg.add_field(name='Spouse:', value="Not married", inline=False)

        children = [child for child in children_data]
        if children:
            for child in children:
                child_id = child["user_id"]
                child_member = interaction.guild.get_member(int(child_id))
                if child_member:
                    children_mentions.append(child_member.mention)
                else:
                    try:
                        child_user = await self.bot.fetch_user(int(child_id))
                        children_mentions.append(child_user.display_name)
                    except discord.NotFound:
                        children_mentions.append("Child not found.")
            embedded_msg.add_field(name='Children:', value=', '.join(children_mentions) + " 👶", inline=False)
        else:
            embedded_msg.add_field(name='Children:', value="No children adopted", inline=False)

        if adoption_data:
            parent1_id = adoption_data.get("adopted_by")
            parent2_id = adoption_data.get("spouse_id")

            if parent1_id:
                parent1 = interaction.guild.get_member(int(parent1_id))
                if parent1:
                    parents_mentions.append(parent1.mention)
                else:
                    try:
                        parent1_user = await self.bot.fetch_user(int(parent1_id))
                        parents_mentions.append(parent1_user.display_name)
                    except discord.NotFound:
                        parents_mentions.append("Parent not found.")

            if parent2_id:
                parent2 = interaction.guild.get_member(int(parent2_id))
                if parent2:
                    parents_mentions.append(parent2.mention)
                else:
                    try:
                        parent2_user = await self.bot.fetch_user(int(parent2_id))
                        parents_mentions.append(parent2_user.display_name)
                    except discord.NotFound:
                        parents_mentions.append("Parent not found.")

            if parents_mentions:
                embedded_msg.add_field(name='Parents:', value=', '.join(parents_mentions) + " 👪", inline=False)
            else:
                embedded_msg.add_field(name='Parents:', value="No parents found", inline=False)
        else:
            embedded_msg.add_field(name='Parents:', value="Not adopted", inline=False)

        embedded_msg.set_footer(text=f"Requested by {interaction.user} 💞", icon_url=interaction.user.avatar.url)
        await interaction.response.send_message(embed=embedded_msg)

async def setup(bot):
    await bot.add_cog(UserInfoCog(bot))
