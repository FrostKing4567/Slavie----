import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
import json
import os
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

owner_id = 734521077744664588
owner2_id = 1194399742516531222

class HelpMenu(View):
    def __init__(self, interaction: discord.Interaction, pages, categories):
        super().__init__(timeout=900)  # View will timeout after 15 minutes
        self.interaction = interaction
        self.pages = pages
        self.categories = categories
        self.current_page = 0

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user == self.interaction.user  # Only the user who invoked the command can interact

    async def update_message(self):
        # Update the embed with the new page
        embed = await self.format_page()
        await self.interaction.edit_original_response(embed=embed, view=self)  # Edit the original response

    async def format_page(self):
        # Create embed for the current page
        embed = discord.Embed(
            title=f"{self.categories[self.current_page]}",
            description=f"Commands available, {self.interaction.user.mention}:",
            color=discord.Color.blue()
        )

        for command_name, command_description in self.pages[self.current_page]:
            # Set prefix based on category
            if self.categories[self.current_page] in ["Author Commands", "Evil Author Commands"]:
                prefix = "`"
            else:
                prefix = "/"
            
            embed.add_field(
                name=f"{prefix}{command_name}",
                value=command_description,
                inline=True
            )

        embed.set_footer(text=f"Page {self.current_page + 1}/{len(self.pages)}")
        return embed

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.primary)
    async def previous_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message()
        else:
            await interaction.response.send_message("You're already on the first page.", ephemeral=True)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message()
        else:
            await interaction.response.send_message("You're already on the last page.", ephemeral=True)

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="Shows a list of commands the user can use.")
    @check_if_disabled()
    async def help(self, interaction: discord.Interaction):
        """Shows a list of commands the user can use."""

        # Define your commands as pages
        moderation_commands = [
            ("ban", "Ban a user from the server."),
            ("unban", "Unban a user from the server."),
            ("kick", "Kick a user from the server."),
            ("callmute", "Mute a user in a voice channel."),
            ("callunmute", "Unmute a user in a voice channel."),
            ("deafen", "Deafen a user in a voice channel."),
            ("undeafen", "Undeafen a user in a voice channel."),
            ("enslave", "Remove someone's roles completely and time them out for specific amount of time"),
            ("unenslave", "Give someone their roles back and remove the timeout"),
            ("get_invite", "Get an invite link for the server."),
            ("disable", "Disables a certain command on a certain guild"),
            ("enable", "Enables a disabled command"),
            ("addwelcomeimage", "Add a welcome image for the guild."),
            ("showwelcomeimages", "Show the welcome images for the guild."),
            ("removewelcomeimage", "Remove a welcome image by its number."),
            ("changewelcomemessage", "Change the welcome message for the guild."),
        ]

        moderation_commands2 = [            
            ("mute", "Mute a user in the server."),
            ("unmute", "Unmute a user in the server."),
            ("nickname", "Change a user's nickname."),
            ("purge", "Purge a specified number of messages."),
            ("recreate", "Recreate all channels in the server."),
            ("add_role", "Add a role to a user."),
            ("create_role", "Create a new role in the server."),
            ("delete_role", "Delete a specified role."),
            ("remove_role", "Remove a role from a user."),
            ("rename_role", "Rename a specified role."),
            ("create_vc", "Create a new voice channel."),
            ("warn", "Warn a user for inappropriate behavior."),
            ("create_category", "Create a category."),
            ("create_channel", "Create a channel."),
            ("delete_channels", "Deletes all channels(USE WITH CAUTION)"),
            ("create_channel", "Create a channel."),
        ]

        music_commands = [
            ("ping", "Ping the bot to check its latency."),
            ("back", "Go back to the previous track."),
            ("clear", "Clear the current queue."),
            ("controller", "Access the controller for the music bot."),
            ("filter", "Apply audio filters to the track."),
            ("history", "View the playback history."),
            ("jump", "Jump to a specific track in the queue."),
            ("loop", "Loop the currently playing track."),
            ("lyrics", "Get the lyrics of the currently playing track."),
            ("nowplaying", "Display the currently playing track."),
            ("pause", "Pause the currently playing track."),
            ("play", "Play a specified track."),
            ("playnext", "Queue a track to play next."),
            ("queue", "Display the current queue."),
            ("remove", "Remove a specific track from the queue."),
            ("resume", "Resume a paused track."),
            ("save", "Save the currently playing track."),
            ("search", "Search for tracks."),
            ("seek", "Seek to a specific time in the current track."),
            ("shuffle", "Shuffle the tracks in the queue."),
            ("skip", "Skip the currently playing track."),
            ("skipto", "Skip to a specific track in the queue."),
            ("stop", "Stop the currently playing track."),
            ("syncedlyrics", "Display synced lyrics for the current track."),
            ("volume", "Set the volume for the bot."),
        ]

        interact_commands = [
            ("adopt", "Adopt a user"),
            ("cancel_adoption", "Cancel your pending adoption proposal"),
            ("abandon", "Abandon an adopted user"),
            ("kiss", "Kiss another user."),
            ("hug", "Hug another user."),
            ("slap", "Slap another user."),
            ("marry", "Propose to another user."),
            ("cancel_proposal", "Cancel your pending marriage proposal"),
            ("accept", "Accept a marriage proposal."),
            ("decline", "Decline a marriage proposal"),
            ("divorce", "Divorce your spouse."),
            ("runaway", "Run away from your parents"),
        ]

        other_commands = [
            ("ping", "Check the bot's latency."),
            ("sub", "Fetches a subreddit."),
            ("userinfo", "Get information about a user."),
            ("familyinfo", "Get information about a user's family."),
            ("guildinfo", "Get information about the server."),
            ("help", "Displays this help message"),
            ("invite", "Get an invite link for the bot (can only be used in private chat)."),
        ]

        author_commands = [
            ("change_bot_banner", "Change the bot's banner."),
            ("change_bot_pfp", "Change the bot's profile picture."),
            ("change_bot_username", "Change the bot's username."),
            ("force_marry", "Force two users to get married."),
            ("hibernate", "Hibernate the author's PC."),
            ("kill", "Stop the bot."),
            ("lock", "Lock the author's PC."),
            ("rekill", "Restart the bot."),
            ("restart", "Restart the author's PC."),
            ("leave_server", "Make the bot leave a server."),
            ("shutdown", "Shutdown the author's PC."),
            ("signout", "Sign out of the author's PC."),
            ("taskmgr", "Open Task Manager on the author's PC."),
            ("showcode", "Shows the contents of a certain file."),
            ("editcode", "Edits the contents of a certain file."),
            ("revertcode", "Undo's a change in the code."),
            ("reverserevertcode", "Redo's a change in the code."),
            ("placefile", "Moves a file or a folder to a new location."),
            ("renamefile", "Renames a specified file or folder."),
            ("showfiles", "Shows the contents of a certain file or folder."),
            ("uploadcode", "Allows the owner to upload a file and save it to a specified location."),
        ]

        evilauthor_commands = [
            ("completeraid", "Completely fucks up a server."),
        ]

        # Combine all pages into a single list
        pages = [
            moderation_commands,        # Page 1: Moderation commands
            moderation_commands2,       # Page 2: Moderation commands
            #music_commands,             # Page 3: Music Player commands
            interact_commands,          # Page 4: Interact commands
            other_commands,             # Page 5: Other commands
        ]

        # Initialize categories list
        categories = [
            "Moderation Commands",
            "Moderation Commands",
            "Music Player Commands",
            "Interact Commands",
            "Other Commands",
        ]

        # Check if the user is the bot's author
        if interaction.user.id == owner_id:
            pages.append(author_commands)           # Page 6: Author Commands
            pages.append(evilauthor_commands)       # Page 7: Evil Author Commands
            categories.append("Author Commands")
            categories.append("Evil Author Commands")
            print("Author 1 detected, Showing evil author commands...")

        if interaction.user.id == owner2_id:
            pages.append(author_commands)           # Page 6: Author Commands
            categories.append("Author Commands")
            print("Author detected, Showing author commands...")

        # Create the view with buttons
        view = HelpMenu(interaction, pages, categories)
        embed = await view.format_page()  # Get the first page to send
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Setup function for the cog
async def setup(bot):
    await bot.add_cog(HelpCog(bot))
