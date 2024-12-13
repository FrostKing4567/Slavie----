import os
import discord
from discord import app_commands
from discord.ext import commands
import random
import requests
from pymongo import MongoClient
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
MONGODB_URI = os.getenv("MONGODB_URI")  # MongoDB connection string
DATABASE_NAME = "Slavie"  # As specified by the user
TENOR_API_KEY = os.getenv("TENOR_API_KEY")  # Tenor API Key
LIMIT = 1000

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Define collections
adoptions_col = db.adoptions
pending_adoptions_col = db.pending_adoptions
marriages_col = db.marriages
disabled_commands_col = db.disabled_commands

def get_gif(search_term):
    """Fetch a random GIF from the Tenor API based on a search term."""
    response = requests.get(
        f"https://tenor.googleapis.com/v2/search?q={search_term}&key={TENOR_API_KEY}&client_key=my_test_app&limit={LIMIT}"
    )
    if response.status_code == 200:
        gifs = response.json().get('results', [])
        if gifs:
            selected_gif = random.choice(gifs)
            return selected_gif['media_formats']['gif']['url']
    return None

# Custom check function to disable commands
def check_if_disabled():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = str(interaction.guild.id)
        command_name = interaction.command.name
        disabled_commands = disabled_commands_col.find_one({"guild_id": guild_id})
        if disabled_commands and command_name in disabled_commands.get("commands", []):
            await interaction.response.send_message(
                f"The command `{command_name}` is disabled in this server.", ephemeral=True
            )
            return False  # Prevents the slash command from executing
        return True
    return app_commands.check(predicate)

class AdoptionView(discord.ui.View):
    """View for handling adoption acceptance or rejection."""
    def __init__(self, adopter_id, adoptee_id):
        super().__init__(timeout=None)
        self.adopter_id = adopter_id
        self.adoptee_id = adoptee_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) == self.adoptee_id:
            await interaction.response.send_message(f"{interaction.user.mention} has accepted the adoption! 🎉")
            
            # Update adoptions
            marriage = marriages_col.find_one({"user_id": self.adopter_id})
            spouse_id = marriage["married_to"] if marriage else None

            adoption_doc = {
                "user_id": self.adoptee_id,
                "adopted_by": self.adopter_id,
                "spouse_id": spouse_id
            }
            adoptions_col.insert_one(adoption_doc)

            # Remove from pending adoptions
            pending_adoptions_col.delete_one({"adopter_id": self.adopter_id, "adoptee_id": self.adoptee_id})
        else:
            await interaction.response.send_message("This adoption proposal was not meant for you!", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) == self.adoptee_id:
            await interaction.response.send_message(f"{interaction.user.mention} has declined the adoption.")
            # Remove from pending adoptions
            pending_adoptions_col.delete_one({"adopter_id": self.adopter_id, "adoptee_id": self.adoptee_id})
        else:
            await interaction.response.send_message("This adoption proposal was not meant for you!", ephemeral=True)

class AdoptionCommand(commands.Cog):
    """Cog for managing adoptions."""
    def __init__(self, bot):
        self.bot = bot

    def get_spouse_id(self, user_id):
        """Get the spouse ID of a user."""
        marriage = marriages_col.find_one({"user_id": user_id})
        return marriage["married_to"] if marriage else None

    def is_family(self, user1_id, user2_id):
        """Check if two users are related (parent-child, siblings, etc.)."""
        # Parent-child relationship
        adoption1 = adoptions_col.find_one({"user_id": user1_id})
        adoption2 = adoptions_col.find_one({"user_id": user2_id})
        if adoption1 and adoption1["adopted_by"] == user2_id:
            return True
        if adoption2 and adoption2["adopted_by"] == user1_id:
            return True

        # Sibling relationship (adopted by the same parent)
        if adoption1 and adoption2 and adoption1["adopted_by"] == adoption2["adopted_by"]:
            return True

        # Check for grandparent or uncle/aunt relationship
        if adoption1 and adoption2:
            adopter1 = adoption1.get("adopted_by")
            adopter2 = adoption2.get("adopted_by")
            if adopter1 and adopter2:
                grandparent1 = adoptions_col.find_one({"user_id": adopter1})
                grandparent2 = adoptions_col.find_one({"user_id": adopter2})
                if grandparent1 and grandparent2:
                    return True  # Assuming they share a grandparent
                if adopter1 == adopter2:
                    return True  # Uncle/aunt and niece/nephew
        return False

    @app_commands.command(name="adopt", description="Propose adoption to someone")
    @check_if_disabled()
    async def adopt_interaction(self, interaction: discord.Interaction, member: discord.Member):
        if not member or member.bot:
            await interaction.response.send_message("You cannot adopt a bot!", ephemeral=True)
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't adopt yourself!", ephemeral=True)
            return

        # Check if the adopter is trying to adopt their spouse
        adopter_spouse_id = self.get_spouse_id(str(interaction.user.id))
        if adopter_spouse_id and adopter_spouse_id == str(member.id):
            await interaction.response.send_message("You can't adopt your spouse!", ephemeral=True)
            return

        # Check if the adopter is trying to adopt their child's spouse
        adopted_children = adoptions_col.find({"adopted_by": str(interaction.user.id)})
        for child in adopted_children:
            child_spouse_id = self.get_spouse_id(child["user_id"])
            if child_spouse_id == str(member.id):
                await interaction.response.send_message("You can't adopt your child's spouse!", ephemeral=True)
                return

        # Check for family relationship restrictions (parents, grandparents, aunts, uncles, etc.)
        if self.is_family(str(interaction.user.id), str(member.id)):
            await interaction.response.send_message(
                "You cannot adopt someone who is already your family (parents, siblings, grandparents, etc.).",
                ephemeral=True
            )
            return

        # Check if the adopter has a pending proposal to the same member
        pending = pending_adoptions_col.find_one({
            "adopter_id": str(interaction.user.id),
            "adoptee_id": str(member.id)
        })
        if pending:
            await interaction.response.send_message(
                "You already proposed to adopt this person! Wait for their response.",
                ephemeral=False
            )
            return

        try:
            adopt_gif = get_gif("anime+adoption")
            embed = discord.Embed(
                title="👶 Adoption Proposal!",
                description=f"{interaction.user.mention} has proposed to adopt {member.mention}! Will they accept?",
                color=discord.Color.blue()
            )
            if adopt_gif:
                embed.set_image(url=adopt_gif)

            view = AdoptionView(adopter_id=str(interaction.user.id), adoptee_id=str(member.id))
            await interaction.response.send_message(embed=embed, view=view)

            # Store the pending adoption proposal
            pending_adoptions_col.insert_one({
                "adopter_id": str(interaction.user.id),
                "adoptee_id": str(member.id)
            })
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while proposing adoption. Please try again.",
                ephemeral=True
            )
            print(f"Error in adopt command: {e}")

    @app_commands.command(name="cancel_adoption", description="Cancel your pending adoption proposal")
    @check_if_disabled()
    async def cancel_adoption_interaction(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        pending = pending_adoptions_col.find_one({"adopter_id": user_id})
        if not pending:
            await interaction.response.send_message("You have no pending adoptions to cancel.", ephemeral=True)
            return

        pending_adoptions_col.delete_one({"adopter_id": user_id})
        pending_adoptions_col.delete_one({"adoptee_id": user_id})  # Remove reciprocal entry if any

        await interaction.response.send_message(
            "Your adoption proposal has been successfully canceled.",
            ephemeral=False
        )

    @app_commands.command(name="abandon", description="Abandon your child")
    @check_if_disabled()
    async def abandon_interaction(self, interaction: discord.Interaction, member: discord.Member):
        """Command for a parent to disown a child."""
        user_id = str(interaction.user.id)
        member_id = str(member.id)

        # Check if the member is adopted by the user
        adoption = adoptions_col.find_one({"user_id": member_id, "adopted_by": user_id})
        if adoption:
            adoptions_col.delete_one({"_id": adoption["_id"]})
            
            # Fetch a kick GIF
            abandon_gif = get_gif("anime+kick")
            embed = discord.Embed(
                title="👋 Disowned!",
                description=f"You have disowned {member.mention}.",
                color=discord.Color.red()
            )
            if abandon_gif:
                embed.set_image(url=abandon_gif)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(f"{member.mention} is not your adopted child.", ephemeral=True)

    @app_commands.command(name="runaway", description="Run away from your parents")
    @check_if_disabled()
    async def runaway_interaction(self, interaction: discord.Interaction):
        """Command for a child to run away from their parents."""
        user_id = str(interaction.user.id)

        # Check if the user is adopted
        adoption = adoptions_col.find_one({"user_id": user_id})
        if adoption:
            adoptions_col.delete_one({"_id": adoption["_id"]})
            
            # Fetch a runaway GIF
            runaway_gif = get_gif("anime+runaway")
            embed = discord.Embed(
                title="🏃 Runaway!",
                description="You have successfully run away from your parents.",
                color=discord.Color.orange()
            )
            if runaway_gif:
                embed.set_image(url=runaway_gif)
            
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("You are not adopted.", ephemeral=True)

async def setup(bot):
    """Setup function to add the AdoptionCommand cog to the bot."""
    await bot.add_cog(AdoptionCommand(bot))
