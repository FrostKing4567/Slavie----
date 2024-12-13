import discord
from discord.ext import commands
from discord import app_commands

class InviteGenerator(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="invite", description="Get the invite link to add the bot to your server.")
    async def generate_invite(self, interaction: discord.Interaction):
        # Make sure this command only works in DMs
        if isinstance(interaction.channel, discord.DMChannel):
            # Your bot's client ID here
            client_id = self.bot.user.id
            invite_link = f"https://discord.com/oauth2/authorize?client_id={client_id}&scope=bot&permissions=8"
            
            await interaction.response.send_message(f"Here’s my invite link! Use this to invite me to a server: {invite_link}")
        else:
            await interaction.response.send_message("This command only works in DMs.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(InviteGenerator(bot))
