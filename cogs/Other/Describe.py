import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image
import io
import aiohttp
import os
from transformers import BlipProcessor, BlipForConditionalGeneration
import torch
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

class DescribeCog(commands.Cog):
    """A Cog for describing images using AI."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Load the BLIP model and processor
        model_name = "Salesforce/blip-image-captioning-large"
        try:
            self.processor = BlipProcessor.from_pretrained(model_name)
            self.model = BlipForConditionalGeneration.from_pretrained(model_name)
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model.to(self.device)
        except Exception as e:
            print(f"Failed to load the image captioning model: {e}")
            self.model = None
            self.processor = None

    @app_commands.command(name="describe", description="Describe an image using AI.")
    @app_commands.describe(
        image="The image to describe."
    )
    async def describe(self, interaction: discord.Interaction, image: discord.Attachment):
        """Generates a detailed description for the provided image."""
        await interaction.response.defer()  # Defer to allow time for processing

        if not image.content_type or not image.content_type.startswith('image/'):
            await interaction.followup.send("❌ Please provide a valid image file.", ephemeral=True)
            return

        if not self.model or not self.processor:
            await interaction.followup.send("❌ Image description service is currently unavailable.", ephemeral=True)
            return

        try:
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image.url) as resp:
                    if resp.status != 200:
                        await interaction.followup.send("❌ Failed to download the image.", ephemeral=True)
                        return
                    img_bytes = await resp.read()

            # Open the image
            image_pil = Image.open(io.BytesIO(img_bytes)).convert("RGB")

            # Preprocess the image
            inputs = self.processor(images=image_pil, return_tensors="pt").to(self.device)

            # Generate a more detailed caption
            out = self.model.generate(
                **inputs,
                max_length=150,                # Increased max_length for more detailed descriptions
                num_beams=10,                  # Increased num_beams for better quality
                no_repeat_ngram_size=3,        # Prevents repetition
                early_stopping=True
            )
            caption = self.processor.decode(out[0], skip_special_tokens=True)

            # Create an embed with the image and detailed description
            embed = discord.Embed(
                title="🖼️ Image Description",
                description=caption,
                color=discord.Color.blue()
            )
            embed.set_image(url=image.url)

            await interaction.followup.send(embed=embed)

        except Exception as e:
            print("An error occurred while describing the image.")
            await interaction.followup.send("❌ An error occurred while describing the image.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(DescribeCog(bot))
