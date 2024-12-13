import discord
from discord.ext import commands
import aiohttp

class ChangeBotPFP(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # This is now a normal command
    @commands.command(name="change_bot_pfp")
    @commands.is_owner()
    async def change_bot_pfp(self, ctx, image_url: str = None):
        # Owner check
        if not await self.bot.is_owner(ctx.author):
            await ctx.send("Only the bot owner can change the bot's profile picture!")
            return

        try:
            avatar_bytes = None

            # Check if an image is attached
            if ctx.message.attachments:
                # Use the attached image
                attachment = ctx.message.attachments[0]
                if attachment.content_type and 'image' in attachment.content_type:
                    avatar_bytes = await attachment.read()
                else:
                    await ctx.send("The attached file is not an image!")
                    return

            elif image_url:
                # Use the image from the provided URL
                avatar_bytes = await self.fetch_image(image_url)

            # If neither an attachment nor a valid URL is provided
            if not avatar_bytes:
                await ctx.send("Please provide a valid image URL or attach an image.")
                return

            # Update the bot's avatar
            await self.bot.user.edit(avatar=avatar_bytes)
            await ctx.send("Bot profile picture changed successfully!")

        except discord.HTTPException as e:
            await ctx.send(f"Failed to change the profile picture due to an HTTP error: {e}")
        except ValueError as e:
            await ctx.send(f"Error: {e}")

    async def fetch_image(self, url):
        # Fetch the image as bytes using aiohttp
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200:
                    raise ValueError("Failed to fetch the image. Make sure the URL is correct.")
                return await response.read()  # Return the image content in bytes

async def setup(bot):
    await bot.add_cog(ChangeBotPFP(bot))