import discord
from discord.ext import commands
from discord import app_commands
import json
import os

class ForceMarry(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.marriage_data = "e:/Programming/Discord Bot/DataBase/marriages.json"  # Path to the JSON file storing marriage data

    @app_commands.command(name="force_marry")
    async def force_marry(self, interaction: discord.Interaction, member1: discord.Member, member2: discord.Member):
        # Owner check
        if not await self.bot.is_owner(interaction.user):
            await interaction.response.send_message("Only the bot author can force a marriage!", ephemeral=True)
            return

        try:
            marriages = self.load_marriages()

            # Ensure both members are not already married
            if member1.id in marriages or member2.id in marriages:
                await interaction.response.send_message("One of these members is already married!", ephemeral=True)
                return

            # Create a marriage entry
            marriages[member1.id] = {"married_to": str(member2.id)}
            marriages[member2.id] = {"married_to": str(member1.id)}
            self.save_marriages(marriages)

            await interaction.response.send_message(f"{member1.display_name} and {member2.display_name} are now married!", ephemeral=False)

        except discord.HTTPException:
            await interaction.response.send_message("An HTTP error occurred while processing the request.", ephemeral=True)
        except json.JSONDecodeError:
            await interaction.response.send_message("There was an error reading the marriage data.", ephemeral=True)
        except FileNotFoundError:
            await interaction.response.send_message("Marriage data file not found. Creating a new one.", ephemeral=True)
            self.save_marriages({})  # Create an empty marriage file
        except Exception as e:
            await interaction.response.send_message(f"An unexpected error occurred: {str(e)}", ephemeral=True)

    def load_marriages(self):
        """Load the marriages from the JSON file."""
        if not os.path.exists(self.marriage_data):
            return {}  # Return an empty dictionary if the file doesn't exist

        with open(self.marriage_data, "r") as file:
            return json.load(file)

    def save_marriages(self, marriages):
        """Save the marriages to the JSON file."""
        with open(self.marriage_data, "w") as file:
            json.dump(marriages, file, indent=4)  # Indent added for readability

async def setup(bot):
    await bot.add_cog(ForceMarry(bot))