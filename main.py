import discord
from discord import Embed
from discord.ext import commands, tasks
import os
import asyncio
import traceback
from dotenv import load_dotenv

author_id = 734521077744664588
author2_id = 1194399742516531222

# Load environment variables from .env file
load_dotenv()

# Set up bot intents
intents = discord.Intents.all()
intents.message_content = True
intents.guilds = True
intents.presences = True
bot = commands.Bot(command_prefix="`", intents=intents)

# Change this to the channel ID where you want to send logs
LOG_CHANNEL_ID = 1298320581464162387  # Updated to your specified channel ID
log_channel = None

# Track the bot's start time
start_time = None

@tasks.loop()
async def update_status():
    activity = discord.Activity(
        type=discord.ActivityType.playing, 
        name=f"/help"
    )
    await bot.change_presence(activity=activity)

@bot.event
async def on_ready():
    global log_channel, start_time
    log_channel = bot.get_channel(LOG_CHANNEL_ID)  # Get the log channel

    try:
        # Sync commands globally
        synced_commands = await bot.tree.sync(guild=None)  # `guild=None` syncs globally
        print(f"Synced {len(synced_commands)} commands globally")
    except Exception as e:
        await log_to_channel("An error with syncing application commands has occurred: " + str(e))
        print("An error with syncing application commands has occurred: ", e)

    print("-------------")
    print(f"'{bot.user.name}' is Ready!")
    print("-------------")
    
    # Create an embed
    embed = Embed(
        description=f"**Bot has successfully started!**<:AiHeart:1297412047134392370>\n\n"
                    f"**Logged In As:** {bot.user.name}\n"
                    f"**Status:** Ready!",
        color = 0xE6E6FA  # You can choose any color you like
    )

    # Set the author's name and avatar
    embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url)

    # Add additional fields for clarity
    if len(synced_commands) > 1:
        embed.add_field(name="🔄 Synced Commands", value=f"{len(synced_commands)} commands have been synced successfully", inline=False)
    elif len(synced_commands) == 1:
        embed.add_field(name="🔄 Synced Commands", value=f"{len(synced_commands)} command has been synced successfully", inline=False)
    else:
        embed.add_field(name="🔄 Synced Commands", value=f"No commands have been synced", inline=False)

    # Fetch the user by their ID
    user = await bot.fetch_user(author_id)
    
    # Add footer with user's pfp
    embed.set_footer(text=f"Bot created by mohamed_elmecky💞", icon_url=user.avatar.url)

    # Log the embed to the channel
    await log_to_channel(embed)

    # Start the status updater task
    update_status.start()

async def log_to_channel(message):
    if log_channel:
        try:
            await log_channel.send(embed=message) if isinstance(message, Embed) else await log_channel.send(message)
        except Exception as e:
            print(f"Failed to send log to channel: {e}")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        print(error)
        await ctx.send("This command does not exist..")
        return

    # Log the error to the console
    print('An error occurred:', error)
    traceback.print_exception(type(error), error, error.__traceback__)

async def load():
    # Load all cogs
    directories = ["Author", "Interactions", "Moderation", "Other", "EvilAuthorShit"]
    
    for directory in directories:
        await log_to_channel(f"Loading {directory}...")
        print(f"Loading {directory}")
        for filename in os.listdir(f"./cogs/{directory}"):
            if filename.endswith(".py") and filename != "__init__.py" and not filename.endswith("utils.py"):
                cog = f"cogs.{directory}.{filename[:-3]}"
                try:
                    module = __import__(cog, fromlist=['setup'])
                    await module.setup(bot)
                    await log_to_channel(f"Successfully loaded {cog}.")
                except Exception as e:
                    await log_to_channel(f"Failed to load {cog}: {e}")
                    print(f"Failed to load {cog}: {e}")

async def main():
    try:
        await load()  
        token = os.getenv("Token")  # Use your actual token here
        await bot.start(token)
    except Exception as e:
        print(f"An error occurred during startup: {e}")
    finally:
        await bot.close()  # Ensure the bot is closed properly

if __name__ == "__main__":
    asyncio.run(main())