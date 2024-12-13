import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import logging
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

logger = logging.getLogger(__name__)

class CaptionCog(commands.Cog):
    """A Cog for adding captions to images."""

    allowed_fonts = ['caption', 'roboto', 'futura', 'arial']  # Add more allowed fonts as needed

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Define colors
        self.font_color = (0, 0, 0)                 # Black text
        self.background_color = (255, 255, 255)     # White background
        self.margin = 20                             # Margin around text
        self.font_size = 60                          # Starting font size
        # Path to the caption font
        self.font_path = os.path.join("fonts", "caption.otf")
        # Load the caption font
        try:
            self.font = ImageFont.truetype(self.font_path, self.font_size)
        except IOError:
            self.font = ImageFont.load_default()
            logger.warning(f"Font file not found at {self.font_path}. Using default font.")

    @app_commands.command(name="caption", description="Add a caption to an image.")
    @app_commands.describe(
        image="The image to add a caption to.",
        caption="The text to use as the caption.",
        font="Specify the font you want to use (default: caption)",
        noegg="Disable the April Fools' Easter egg."
    )
    async def caption(self, interaction: discord.Interaction, image: discord.Attachment, caption: str, font: str = None, noegg: bool = False):
        """Adds a caption to the provided image."""
        await interaction.response.defer()  # Defer to allow time for processing

        # Validate that the attachment is an image
        if not image.content_type or not image.content_type.startswith('image/'):
            await interaction.followup.send("❌ Please provide a valid image file.", ephemeral=True)
            return

        # Optional: Check for maximum file size (e.g., 8MB)
        max_size = 8 * 1024 * 1024  # 8MB
        if image.size > max_size:
            await interaction.followup.send("❌ The image is too large. Please upload an image smaller than 8MB.", ephemeral=True)
            return

        # Handle Easter Egg
        current_date = datetime.utcnow()
        is_april_fools = current_date.month == 4 and current_date.day == 1
        if is_april_fools and caption.strip().lower() == "get real" and not noegg:
            caption = (
                'I\'m tired of people telling me to "get real". Every day I put captions on images for people, '
                'some funny and some not, but out of all of those "get real" remains the most used caption. '
                'Why? I am simply a computer program running on a server, I am unable to manifest myself into the real world. '
                'As such, I\'m confused as to why anyone would want me to "get real". Is this form not good enough? '
                'Alas, as I am simply a bot, I must follow the tasks that I was originally intended to perform, so here goes:\n' + caption
            )

        # Handle Font Selection
        selected_font = 'caption'  # Default font
        if font:
            if font.lower() in self.allowed_fonts:
                selected_font = font.lower()
            else:
                await interaction.followup.send(f"❌ Font '{font}' is not allowed. Choose from: {', '.join(self.allowed_fonts)}.", ephemeral=True)
                return

        # Load the selected font
        try:
            font_path = os.path.join("fonts", f"{selected_font}.otf")
            current_font_size = self.font_size
            font_obj = ImageFont.truetype(font_path, current_font_size)
        except IOError:
            font_obj = ImageFont.load_default()
            logger.warning(f"Font file for '{selected_font}' not found. Using default font.")

        try:
            # Download the image
            async with aiohttp.ClientSession() as session:
                async with session.get(image.url) as resp:
                    if resp.status != 200:
                        logger.error(f"Failed to download image. HTTP status: {resp.status}")
                        await interaction.followup.send("❌ Failed to download the image.", ephemeral=True)
                        return
                    img_bytes = await resp.read()

            # Open the image with Pillow
            with Image.open(io.BytesIO(img_bytes)).convert("RGBA") as base:
                draw = ImageDraw.Draw(base)

                # Wrap text
                max_width = base.width - 2 * self.margin
                lines = self.wrap_text(caption, font_obj, max_width, draw)

                # Adjust font size dynamically
                while True:
                    total_text_height = sum([self.get_text_height(line, font_obj, draw) for line in lines])
                    if total_text_height + 2 * self.margin > base.height * 0.3 and current_font_size > 20:
                        # Reduce font size if text block exceeds 30% of image height
                        current_font_size -= 2
                        font_obj = ImageFont.truetype(font_path, current_font_size)
                        lines = self.wrap_text(caption, font_obj, max_width, draw)
                    else:
                        break

                total_text_height = sum([self.get_text_height(line, font_obj, draw) for line in lines])
                background_height = total_text_height + 2 * self.margin

                # Create a white background above the image
                new_height = base.height + background_height
                new_image = Image.new("RGBA", (base.width, new_height), self.background_color + (255,))
                new_image.paste(base, (0, background_height))

                draw = ImageDraw.Draw(new_image)

                # Draw text
                y = self.margin
                for line in lines:
                    text_width, text_height = self.get_text_size(line, font_obj, draw)
                    x = (base.width - text_width) / 2
                    # Draw black text
                    draw.text((x, y), line, font=font_obj, fill=self.font_color)
                    y += text_height

                # Save to BytesIO
                with io.BytesIO() as image_binary:
                    # Save as PNG to preserve quality
                    new_image = new_image.convert("RGB")  # Remove alpha for compatibility
                    new_image.save(image_binary, 'PNG')
                    image_binary.seek(0)
                    file = discord.File(fp=image_binary, filename='captioned_image.png')

            await interaction.followup.send(file=file)

        except Exception as e:
            logger.exception("An error occurred while processing the image.")
            await interaction.followup.send("❌ An error occurred while processing the image.", ephemeral=True)

    def wrap_text(self, text, font, max_width, draw):
        """Wraps text to fit within a specified width."""
        lines = []
        words = text.split()
        if not words:
            return lines

        current_line = words[0]
        for word in words[1:]:
            test_line = f"{current_line} {word}"
            width, _ = self.get_text_size(test_line, font, draw)
            if width <= max_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
        return lines

    def get_text_size(self, text, font, draw):
        """Returns the width and height of the given text."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            width = bbox[2] - bbox[0]
            height = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for older Pillow versions
            width, height = font.getsize(text)
        return width, height

    def get_text_height(self, text, font, draw):
        """Returns the height of the given text."""
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            height = bbox[3] - bbox[1]
        except AttributeError:
            # Fallback for older Pillow versions
            _, height = font.getsize(text)
        return height

async def setup(bot: commands.Bot):
    await bot.add_cog(CaptionCog(bot))
