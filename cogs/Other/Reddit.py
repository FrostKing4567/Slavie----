import discord
from discord.ext import commands
import random
import asyncpraw as praw
from discord import app_commands
import os
import json
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

# Reddit API credentials
CID = os.getenv("Reddit_Client_ID")
cs = os.getenv("Reddit_Client_Secret")
ru = os.getenv("Reddit_Username")

class Reddit(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.reddit = praw.Reddit(client_id=CID, client_secret=cs,
                                  user_agent=f"script:discord:v1.0 (by {ru})")

    @app_commands.command(name='sub', description="Get a random post from a subreddit.")
    @app_commands.describe(subreddit="The name of the subreddit to fetch a post from.")
    @check_if_disabled()
    async def sub(self, interaction: discord.Interaction, *, subreddit: str):
        if subreddit is None:
            await interaction.response.send_message("Uh oh. You need to specify a subreddit! Please try again with a valid subreddit name. 🌸")
            return

        try:
            subreddit_instance = await self.reddit.subreddit(subreddit)
            posts_list = []

            async for post in subreddit_instance.top(limit=100):  # Limit added to avoid too many requests
                if not post.over_18 and post.author is not None and any(
                    post.url.endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif"]):
                    author_name = post.author.name
                    posts_list.append((post.url, author_name))
                elif post.over_18:
                    await interaction.response.send_message("Sorry, I can't fetch posts from that subreddit. 😞")
                    return

            if posts_list:
                random_post = random.choice(posts_list)

                meme_embed = discord.Embed(
                    title=f"Here's a random post from r/{subreddit_instance.display_name}! 🌟",
                    description=f"Created by {random_post[1]}.",
                    color=discord.Color.green()
                )
                meme_embed.set_image(url=random_post[0])
                meme_embed.set_footer(text=f"Requested by {interaction.user.display_name} 💞", icon_url=interaction.user.avatar.url)
                await interaction.response.send_message(embed=meme_embed)
            else:
                await interaction.response.send_message("Oopsie! I couldn't find any posts from that subreddit. Please try again later. 😔")
        except praw.exceptions.RedditAPIException as e:
            await interaction.response.send_message(f"Reddit API error: {str(e)} 😓")
        except Exception as e:
            await interaction.response.send_message(f"Oops! Something went wrong: {str(e)} 😓")

    def cog_unload(self):
        # Clean up and close Reddit connection
        self.bot.loop.create_task(self.reddit.close())
        print(f"\n\n{self.bot.name} is unloaded and session closed. 👋")

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(Reddit(bot))
