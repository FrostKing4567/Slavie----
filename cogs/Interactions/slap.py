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
db = client["Slavie"]  # Use the discord_bot database

# Define collections
marriages_col = db.marriages
adoptions_col = db.adoptions
disabled_commands_col = db.disabled_commands

def get_slap_gif():
    """Fetch a random slap GIF from Tenor API."""
    search_term = "anime+slap"
    url = f"https://tenor.googleapis.com/v2/search?q={search_term}&key={TENOR_API_KEY}&limit={LIMIT}"
    response = requests.get(url)

    if response.status_code == 200:
        gifs = response.json().get('results', [])
        if gifs:
            # Randomly select a GIF from the available results
            return random.choice(gifs)['media_formats']['gif']['url']
    return None

def is_command_disabled(guild_id, command_name):
    """Check if a command is disabled for a specific guild."""
    disabled_commands = disabled_commands_col.find_one({"guild_id": str(guild_id)})
    if disabled_commands:
        return command_name in disabled_commands.get("commands", [])
    return False

# Custom check function to disable commands
def check_if_disabled():
    async def predicate(interaction: discord.Interaction) -> bool:
        guild_id = interaction.guild.id
        command_name = interaction.command.name
        if is_command_disabled(guild_id, command_name):
            await interaction.response.send_message(f"The command `{command_name}` is disabled in this server.", ephemeral=True)
            return False  # Prevents the slash command from executing
        return True
    return app_commands.check(predicate)

def load_data(collection, user_id):
    """Load data from a MongoDB collection for a given user."""
    return collection.find_one({"user_id": str(user_id)})

class SlapCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="slap", description="Slap someone")
    @check_if_disabled()
    async def slap_interaction(self, interaction: discord.Interaction, member: discord.Member):
        """Handle the slap command."""
        try:
            # Check for valid member
            if member.bot:
                await interaction.response.send_message("You cannot slap a bot!", ephemeral=True)
                return

            if member == interaction.user:
                await interaction.response.send_message("You can't slap yourself!", ephemeral=True)
                return

            # Check if the user is trying to slap their spouse
            user_marriage = load_data(marriages_col, interaction.user.id)
            if user_marriage and user_marriage.get("married_to") == str(member.id):
                await interaction.response.send_message("Don't you dare lay a finger on your spouse!", ephemeral=False)
                return

            # Check if the slapped member is an adopted child
            member_adoption = load_data(adoptions_col, member.id)
            parent1, parent2 = None, None
            if member_adoption:
                parent1_id = member_adoption.get("adopted_by")
                if parent1_id:
                    parent2_id = member_adoption.get("spouse_id")  # Fetch the spouse of the adopting parent
                    parent1 = self.bot.get_user(int(parent1_id))
                    parent2 = self.bot.get_user(int(parent2_id)) if parent2_id else None

                    # If a parent is slapping their child
                    if str(interaction.user.id) == parent1_id or (parent2_id and str(interaction.user.id) == parent2_id):
                        await interaction.response.send_message("Isn't that.... child abuse?", ephemeral=False)
                        return

            # Check if the slapped member is a parent of the user
            user_adoption = load_data(adoptions_col, interaction.user.id)
            if user_adoption:
                if (user_adoption.get("adopted_by") == str(member.id) or 
                    user_adoption.get("spouse_id") == str(member.id)):
                    await interaction.response.send_message("You cannot slap your parents! bad child..", ephemeral=False)
                    return

            # Prepare embed for the slap
            embed = discord.Embed(
                title="💥 Slap!",
                description=f"{interaction.user.mention} slaps {member.mention}!",
                color=discord.Color.red()
            )

            slap_gif = get_slap_gif()  # Get a random slap GIF
            if slap_gif:
                embed.set_image(url=slap_gif)

            # Check if the slapped member is married
            spouse = None
            member_marriage = load_data(marriages_col, member.id)
            if member_marriage:
                spouse_id = member_marriage.get("married_to")
                spouse = self.bot.get_user(int(spouse_id))

            # Set footer based on relationships
            if parent1 and parent2 and spouse:
                embed.set_footer(text=f"You're gonna get demolished by {parent1.display_name}, {parent2.display_name}, and {spouse.display_name}!")
            elif parent1 and parent2:
                embed.set_footer(text=f"{parent1.display_name} and {parent2.display_name} aren't gonna leave you on this one!")
            elif spouse:
                embed.set_footer(text=f"{spouse.display_name} is coming for you!")
            elif parent1:
                embed.set_footer(text=f"{parent1.display_name} isn't gonna leave you alone on this one!")

            # Create the slap back button view
            view = self.SlapBackButton(interaction.user, member, spouse, parent1, parent2, db)

            # Send the embed response with the slap back button
            await interaction.response.send_message(embed=embed, view=view)

        except discord.NotFound:
            await interaction.response.send_message("The member you are trying to slap cannot be found.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("I do not have permission to send messages in this channel.", ephemeral=True)
        except Exception as e:
            print(f"Error in slap_interaction: {e}")
            await interaction.response.send_message("An unexpected error occurred. Please try again later.", ephemeral=True)

    class SlapBackButton(discord.ui.View):
        def __init__(self, slapper, slapped_member, spouse, parent1, parent2, db):
            super().__init__(timeout=None)
            self.slapper = slapper
            self.slapped_member = slapped_member
            self.spouse = spouse
            self.parent1 = parent1
            self.parent2 = parent2
            self.db = db

        @discord.ui.button(label="Slap Back", style=discord.ButtonStyle.red)
        async def slap_back(self, interaction: discord.Interaction, button: discord.ui.Button):
            """Handle slap back interaction."""
            try:
                # Check if the user has permission to slap back
                allowed_users = {self.slapped_member.id}

                # Add spouse to allowed users
                if self.spouse:
                    allowed_users.add(self.spouse.id)

                # Add parents to allowed users
                if self.parent1:
                    allowed_users.add(self.parent1.id)
                if self.parent2:
                    allowed_users.add(self.parent2.id)

                # Check if the interacting user is one of the allowed users
                if interaction.user.id not in allowed_users:
                    await interaction.response.send_message("You do not have permission to do that!", ephemeral=True)
                    return

                embed = discord.Embed(
                    title="💥 Slap Back!",
                    description=f"{interaction.user.mention} just slapped back {self.slapper.mention}!",
                    color=discord.Color.red()
                )
                slap_gif = get_slap_gif()  # Get a random slap GIF
                if slap_gif:
                    embed.set_image(url=slap_gif)
                    embed.set_footer(text="Slap back successful!")

                    # Send the slap back message as a new message
                    await interaction.channel.send(embed=embed)

                    # Disable the button after it's used
                    for child in self.children:
                        child.disabled = True
                    await interaction.response.edit_message(view=self)  # Edit the original message to remove the button

            except discord.NotFound:
                await interaction.response.send_message("The message was not found. It may have been deleted.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message("I do not have permission to send messages in this channel.", ephemeral=True)
            except Exception as e:
                print(f"Error in slap_back: {e}")
                await interaction.response.send_message("An unexpected error occurred during slap back. Please try again later.", ephemeral=True)

async def setup(bot):
    """Setup the cog."""
    await bot.add_cog(SlapCommand(bot))
