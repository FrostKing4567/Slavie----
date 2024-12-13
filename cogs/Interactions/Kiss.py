import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
import random  # Import random for random selection
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
TENOR_API_KEY = os.getenv("TENOR_API_KEY")
MONGODB_URI = os.getenv("MONGODB_URI")

LIMIT = 1000  # Increased limit for fetching multiple GIFs

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client["Slavie"]  # Database name

# Define collections
marriages_col = db.marriages
proposals_col = db.proposals
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

def get_kiss_gif(friendly=False):
    """Fetch a random kiss GIF from Tenor API."""
    search_term = "anime+kiss"
    if friendly:
        search_term = "anime+peck+on+cheek"  # Friendly kiss search term

    # Increase the limit to fetch multiple GIFs and allow random selection
    response = requests.get(
        f"https://tenor.googleapis.com/v2/search?q={search_term}&key={TENOR_API_KEY}&client_key=my_test_app&limit={LIMIT}"
    )
    
    if response.status_code == 200:
        gifs = response.json().get('results', [])
        if gifs:
            # Select a random GIF from the list
            return random.choice(gifs)['media_formats']['gif']['url']
    return None

class KissCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="kiss", description="Send a kiss to someone")
    @check_if_disabled()
    async def kiss_interaction(self, interaction: discord.Interaction, member: discord.Member):
        user_id = str(interaction.user.id)
        member_id = str(member.id)

        # Check if the member is valid and not a bot
        if not member or member.bot:
            await interaction.response.send_message("You cannot kiss a bot!", ephemeral=True)
            return

        # Check if the user is trying to kiss themselves
        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't kiss yourself! Kiss someone else!", ephemeral=True)
            return

        # Check if the user has proposed to someone but they haven't accepted yet
        proposal = proposals_col.find_one({"proposer_id": user_id, "recipient_id": member_id})
        if proposal:
            await interaction.response.send_message("They haven't accepted your proposal yet! Be patient.", ephemeral=True)
            return

        # Check if the user has a pending proposal to someone else
        existing_proposal = proposals_col.find_one({"proposer_id": user_id})
        if existing_proposal:
            await interaction.response.send_message("You already proposed to someone! Wait until they either accept or decline.", ephemeral=True)
            return

        # Check if the member being kissed has a pending proposal from someone else
        member_proposal = proposals_col.find_one({"recipient_id": member_id, "proposer_id": {"$ne": user_id}})
        if member_proposal:
            proposer = self.bot.get_user(int(member_proposal["proposer_id"]))
            if proposer:
                await interaction.response.send_message(f"{member.mention} has a pending proposal from {proposer.display_name}. Wait until they respond!", ephemeral=True)
            else:
                await interaction.response.send_message(f"{member.mention} has a pending proposal from someone. Wait until they respond!", ephemeral=True)
            return

        # Check if the kiss initiator is married to someone else
        marriage = marriages_col.find_one({"user_id": user_id})
        if marriage and marriage.get("married_to") != member_id:
            # Random responses for cheating message
            cheating_responses = [
                "Cheating, huh? You're already married to someone else!<a:DameDame:1297318892204462120>",
                "Caught red-handed! You're already taken.",
                "Oh no! You're already tied to someone. Watch out! <a:DameDame:1297318892204462120>",
                "Seems like you're double-dipping! You're married already. <a:DameDame:1297318892204462120>",
                "Oops, you're already committed to someone else. Careful! <a:DameDame:1297318892204462120>",
                "Sneaky sneaky, but you're already in a relationship! <a:DameDame:1297318892204462120>",
                "Stop trying to fucking cheat <:AiAngry:1297320187460190208>"
            ]
            selected_response = random.choice(cheating_responses)  # Select a random message
            await interaction.response.send_message(selected_response, ephemeral=False)
            return

        # Check if the member being kissed is married to someone else
        member_marriage = marriages_col.find_one({"user_id": member_id})
        if member_marriage and member_marriage.get("married_to") != user_id:
            await interaction.response.send_message(f"{member.mention} is married and can only be kissed by their spouse!", ephemeral=True)
            return

        # Check if the member being kissed has a pending proposal (and you're not married)
        if member_id in proposals_col.find({"recipient_id": member_id}) and not (user_id in marriages_col.find_one({"user_id": user_id}) or member_id in marriages_col.find_one({"user_id": member_id})):
            await interaction.response.send_message(f"{member.mention} has already proposed to someone else. You shouldn't kiss them right now!", ephemeral=True)
            return

        # Determine if it's a friendly kiss or romantic kiss
        if not marriage and not member_marriage:
            # Both are not married; friendly kiss
            kiss_gif = get_kiss_gif(friendly=True)
            embed = discord.Embed(
                title="💋 Friendly Kiss!",
                description=f"{interaction.user.mention} gives a friendly kiss to {member.mention}!",
                color=discord.Color.light_gray()
            )
        else:
            # Romantic kiss if married
            kiss_gif = get_kiss_gif(friendly=False)
            embed = discord.Embed(
                title="💋 Kiss!",
                description=f"{interaction.user.mention} gives a sweet kiss to {member.mention}! <:AiFreaky:1297322088251658380>",
                color=discord.Color.pink()
            )

        if kiss_gif:
            embed.set_image(url=kiss_gif)

        # Send the embed
        try:
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message("An error occurred while sending the kiss. Please try again.", ephemeral=True)
            print(f"Error in kiss command: {e}")

async def setup(bot):
    await bot.add_cog(KissCommand(bot))
