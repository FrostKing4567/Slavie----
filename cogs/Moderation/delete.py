import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from typing import Optional


def is_guild_owner():
    """
    Custom check to ensure that the command is only used by the server owner.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False  # Command not used within a guild
        return interaction.user.id == interaction.guild.owner_id
    return app_commands.check(predicate)


class ChannelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    class ConfirmDeletionView(discord.ui.View):
        def __init__(self, timeout: float = 60.0):
            super().__init__(timeout=timeout)
            self.confirmed = False

        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
        async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.confirmed = True
            await interaction.response.edit_message(content="🔨 Deleting all channels...", view=None)
            self.stop()

        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.edit_message(content="❌ Channel deletion has been canceled.", view=None)
            self.stop()

    @app_commands.command(
        name="delete_channels",
        description="Deletes all channels in the server. **Use with caution!**"
    )
    @is_guild_owner()
    async def delete_channels(self, interaction: discord.Interaction):
        """
        Slash command to delete all channels in the server. Only the server owner can use this command.
        """
        # Check if the command is used within a guild
        if not interaction.guild:
            await interaction.response.send_message("This command can only be used within a server.", ephemeral=True)
            return

        # Defer the response as the operation might take time
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Confirmation step to prevent accidental deletions
        view = self.ConfirmDeletionView()
        await interaction.followup.send(
            "⚠️ **Are you sure you want to delete all channels in this server? This action cannot be undone.**",
            view=view,
            ephemeral=True
        )

        # Wait for the user to confirm or cancel
        await view.wait()

        if view.confirmed:
            guild = interaction.guild
            channels = guild.channels
            semaphore_delete = asyncio.Semaphore(5)  # Limit concurrency to 5

            async def delete_channel(channel: discord.abc.GuildChannel):
                async with semaphore_delete:
                    try:
                        await channel.delete()
                    except discord.HTTPException as e:
                        pass

            # Create deletion tasks
            delete_channel_tasks = [delete_channel(channel) for channel in channels]

            # Execute deletion tasks concurrently
            await asyncio.gather(*delete_channel_tasks)

            await interaction.followup.send(f"✅ All channels have been deleted in **{guild.name}**.", ephemeral=True)

    @delete_channels.error
    async def delete_channels_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.errors.CheckFailure):
            await interaction.response.send_message("❌ Only the server owner can use this command.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelManager(bot))
