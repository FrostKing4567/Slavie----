# cogs/marry_command.py

import os
import discord
from discord.ext import commands
from discord import app_commands
import random
import requests
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Retrieve environment variables
MONGODB_URI = os.getenv("MONGODB_URI")
DATABASE_NAME = "Slavie"
TENOR_API_KEY = os.getenv("TENOR_API_KEY")

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Define collections
marriages_col = db.marriages
proposals_col = db.proposals
adoptions_col = db.adoptions
disabled_commands_col = db.disabled_commands

# Ensure unique constraints
marriages_col.create_index("user_id", unique=True)
proposals_col.create_index(
    [("proposer_id", ASCENDING), ("recipient_id", ASCENDING)],
    unique=True
)
proposals_col.create_index("recipient_id", unique=True, partialFilterExpression={"recipient_id": {"$exists": True}})

LIMIT = 1000

def get_propose_gif():
    search_term = "anime+proposal"
    response = requests.get(
        f"https://tenor.googleapis.com/v2/search?q={search_term}&key={TENOR_API_KEY}&client_key=my_test_app&limit={LIMIT}"
    )
    if response.status_code == 200:
        gifs = response.json().get('results', [])
        if gifs:
            selected_gif = random.choice(gifs)
            return selected_gif['media_formats']['gif']['url']
    return None

def are_siblings(user1_id, user2_id):
    adoptions1 = adoptions_col.find_one({"user_id": str(user1_id)})
    adoptions2 = adoptions_col.find_one({"user_id": str(user2_id)})
    if adoptions1 and adoptions2:
        return adoptions1.get("siblings") == adoptions2.get("siblings")
    return False

def are_related(user1_id, user2_id):
    adoptions1 = adoptions_col.find_one({"user_id": str(user1_id)})
    adoptions2 = adoptions_col.find_one({"user_id": str(user2_id)})

    if adoptions1 and adoptions2:
        # Check for sibling relationship
        if are_siblings(user1_id, user2_id):
            return True
        # Check for parent-child relationship
        if adoptions1.get("children") == adoptions2.get("children"):
            return True
        # Check for parent relationship
        if adoptions1.get("parents") == adoptions2.get("parents"):
            return True
        # Check for grandparent relationship
        if adoptions1.get("grandparents") == adoptions2.get("grandparents"):
            return True
        # Check for aunts/uncles relationship
        if adoptions1.get("aunts_uncles") == adoptions2.get("aunts_uncles"):
            return True
    return False

def check_if_disabled():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = str(interaction.guild.id)
        command_name = interaction.command.name
        disabled_commands = disabled_commands_col.find_one({"guild_id": guild_id})
        if disabled_commands and command_name in disabled_commands.get("commands", []):
            await interaction.response.send_message(
                f"The command `{command_name}` is disabled in this server.", ephemeral=True
            )
            return False
        return True
    return app_commands.check(predicate)

class ProposalView(discord.ui.View):
    def __init__(self, proposer_id, recipient_id):
        super().__init__(timeout=None)
        self.proposer_id = proposer_id
        self.recipient_id = recipient_id

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) == self.recipient_id:
            proposer_id = self.proposer_id
            await interaction.response.send_message(
                f"{interaction.user.mention} has accepted the proposal from <@{proposer_id}>! 💍"
            )
            try:
                # Create marriages
                marriages_col.insert_one({
                    "user_id": str(interaction.user.id),
                    "married_to": str(proposer_id)
                })
                marriages_col.insert_one({
                    "user_id": str(proposer_id),
                    "married_to": str(interaction.user.id)
                })
                # Remove proposal
                proposals_col.delete_one({
                    "proposer_id": str(proposer_id),
                    "recipient_id": str(interaction.user.id)
                })
            except Exception as e:
                await interaction.followup.send(
                    "An error occurred while processing the marriage. Please try again.",
                    ephemeral=True
                )
                print(f"Error in accept_button: {e}")
        else:
            await interaction.response.send_message("This proposal was not meant for you!", ephemeral=True)

    @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger)
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) == self.recipient_id:
            proposer_id = self.proposer_id
            await interaction.response.send_message(
                f"{interaction.user.mention} has declined the proposal from <@{proposer_id}>."
            )
            try:
                # Remove proposal
                proposals_col.delete_one({
                    "proposer_id": str(proposer_id),
                    "recipient_id": str(interaction.user.id)
                })
            except Exception as e:
                await interaction.followup.send(
                    "An error occurred while declining the proposal. Please try again.",
                    ephemeral=True
                )
                print(f"Error in decline_button: {e}")
        else:
            await interaction.response.send_message("This proposal was not meant for you!", ephemeral=True)

class MarryCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="marry", description="Propose marriage to someone")
    @check_if_disabled()
    async def marry_interaction(self, interaction: discord.Interaction, member: discord.Member):
        if not member or member.bot:
            await interaction.response.send_message("You cannot propose to a bot!", ephemeral=True)
            return

        if member.id == interaction.user.id:
            await interaction.response.send_message("You can't propose to yourself!", ephemeral=True)
            return

        # Check if the proposer is already married
        if marriages_col.find_one({"user_id": str(interaction.user.id)}):
            await interaction.response.send_message("You are already married!", ephemeral=False)
            return

        # Check if the recipient is already married
        if marriages_col.find_one({"user_id": str(member.id)}):
            await interaction.response.send_message("This person is already married!", ephemeral=False)
            return

        # Check for related relationships (sibling, parent, grandparent, aunt, uncle, child)
        if are_related(interaction.user.id, member.id):
            await interaction.response.send_message("You cannot marry your relative!", ephemeral=False)
            return

        # Check if the proposer has any pending proposals
        existing_proposal = proposals_col.find_one({"proposer_id": str(interaction.user.id)})
        if existing_proposal:
            await interaction.response.send_message(
                "You already have a pending proposal! Wait for it to be accepted or declined before proposing again.",
                ephemeral=False
            )
            return

        # Check if the recipient has any pending proposals
        recipient_proposal = proposals_col.find_one({"recipient_id": str(member.id)})
        if recipient_proposal:
            await interaction.response.send_message(
                f"{member.mention} already has a pending proposal! Wait for it to be accepted or declined.",
                ephemeral=False
            )
            return

        try:
            propose_gif = get_propose_gif()
            embed = discord.Embed(
                title="💍 Proposal!",
                description=f"{interaction.user.mention} has proposed to {member.mention}! Will they accept?",
                color=discord.Color.pink()
            )
            if propose_gif:
                embed.set_image(url=propose_gif)

            view = ProposalView(proposer_id=str(interaction.user.id), recipient_id=str(member.id))
            await interaction.response.send_message(embed=embed, view=view)

            # Store the proposal
            proposals_col.insert_one({
                "proposer_id": str(interaction.user.id),
                "recipient_id": str(member.id)
            })
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while proposing marriage. Please try again.", ephemeral=True
            )
            print(f"Error in marry command: {e}")

    @app_commands.command(name="accept", description="Accept a marriage proposal")
    @check_if_disabled()
    async def accept_interaction(self, interaction: discord.Interaction):
        try:
            # Find the proposal where recipient_id is the user
            proposal = proposals_col.find_one({"recipient_id": str(interaction.user.id)})
            if proposal:
                proposer_id = proposal.get("proposer_id")
                if proposer_id:
                    # Create marriages
                    marriages_col.insert_one({
                        "user_id": str(interaction.user.id),
                        "married_to": str(proposer_id)
                    })
                    marriages_col.insert_one({
                        "user_id": str(proposer_id),
                        "married_to": str(interaction.user.id)
                    })
                    # Remove proposal
                    proposals_col.delete_one({
                        "proposer_id": str(proposer_id),
                        "recipient_id": str(interaction.user.id)
                    })
                    await interaction.response.send_message(
                        f"{interaction.user.mention} and <@{proposer_id}> are now married! 💍"
                    )
            else:
                await interaction.response.send_message("No one has proposed to you!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while accepting the proposal. Please try again.", ephemeral=True
            )
            print(f"Error in accept command: {e}")

    @app_commands.command(name="decline", description="Decline a marriage proposal")
    @check_if_disabled()
    async def decline_interaction(self, interaction: discord.Interaction):
        try:
            # Find the proposal where recipient_id is the user
            proposal = proposals_col.find_one({"recipient_id": str(interaction.user.id)})
            if proposal:
                proposer_id = proposal.get("proposer_id")
                if proposer_id:
                    # Remove proposal
                    proposals_col.delete_one({
                        "proposer_id": str(proposer_id),
                        "recipient_id": str(interaction.user.id)
                    })
                    await interaction.response.send_message(
                        f"{interaction.user.mention} has rejected <@{proposer_id}>'s marriage proposal."
                    )
            else:
                await interaction.response.send_message("No marriage proposals to decline.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while declining the proposal. Please try again.", ephemeral=True
            )
            print(f"Error in decline command: {e}")

    @app_commands.command(name="divorce", description="Divorce your spouse")
    @check_if_disabled()
    async def divorce_interaction(self, interaction: discord.Interaction):
        try:
            marriage = marriages_col.find_one({"user_id": str(interaction.user.id)})
            if marriage and marriage.get("married_to"):
                spouse_id = marriage["married_to"]
                # Remove both marriage entries
                marriages_col.delete_one({"user_id": str(interaction.user.id)})
                marriages_col.delete_one({"user_id": str(spouse_id)})
                await interaction.response.send_message(
                    f"{interaction.user.mention} has divorced their spouse."
                )
            else:
                await interaction.response.send_message("You are not married.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while processing the divorce. Please try again.", ephemeral=True
            )
            print(f"Error in divorce command: {e}")

    @app_commands.command(name="cancel_proposal", description="Cancel your pending proposal")
    @check_if_disabled()
    async def cancel_proposal_interaction(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)

        try:
            # Find proposals initiated by the user
            proposals = list(proposals_col.find({"proposer_id": user_id}))
            if proposals:
                for proposal in proposals:
                    recipient_id = proposal.get("recipient_id")
                    # Remove the proposal
                    proposals_col.delete_one({
                        "proposer_id": user_id,
                        "recipient_id": recipient_id
                    })
                await interaction.response.send_message(
                    "Your proposal has been successfully canceled.", ephemeral=False
                )
            else:
                await interaction.response.send_message(
                    "You have no pending proposals to cancel.", ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(
                "An error occurred while canceling the proposal. Please try again.", ephemeral=True
            )
            print(f"Error in cancel_proposal command: {e}")

async def setup(bot):
    await bot.add_cog(MarryCommand(bot))
