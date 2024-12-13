import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import os
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
GUILD_ID = os.getenv("GUILD_ID")  # Ensure GUILD_ID is set in your .env

client = MongoClient(MONGODB_URI)
db = client["Slavie"]  # Database name
disabled_commands_col = db.disabled_commands
enslaved_members_col = db.enslaved_members  # New collection for enslaved members

def load_disabled_commands():
    """Load the disabled commands from MongoDB."""
    return disabled_commands_col.find_one({"guild_id": str(GUILD_ID)}) or {}

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
            await interaction.response.send_message(
                f"The command `{command_name}` is disabled in this server.", ephemeral=True
            )
            return False  # Prevents the slash command from executing
        return True
    return app_commands.check(predicate)

class EnslaveCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.slave_role = None  # Initialize as None

        # Start the background task to check for unenslaving
        self.check_unenslave.start()

    async def create_slave_role(self):
        """Create the Slave role with brown color if it doesn't exist."""
        guild = self.bot.get_guild(int(GUILD_ID))  # Use the specific guild ID
        if not guild:
            print(f"Guild with ID {GUILD_ID} not found.")
            return

        self.slave_role = discord.utils.get(guild.roles, name='Slave')

        if not self.slave_role:
            try:
                self.slave_role = await guild.create_role(
                    name='Slave', color=discord.Color(0x8B4513)  # Brown color
                )
                print("Created 'Slave' role.")
            except discord.Forbidden:
                print("Failed to create 'Slave' role due to insufficient permissions.")
            except Exception as e:
                print(f"An error occurred while creating 'Slave' role: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        """Event that runs when the bot is ready."""
        await self.create_slave_role()
        print(f"EnslaveCog is ready and connected to guild ID {GUILD_ID}.")

    @tasks.loop(minutes=1)  # Check every minute
    async def check_unenslave(self):
        """Check for members who need to be unenslaved across all guilds."""
        current_time = datetime.utcnow()

        try:
            # Find all enslaved members whose timeout_end_time is <= current_time
            expired_members = enslaved_members_col.find({
                "timeout_end_time": {"$lte": current_time}
            })

            for record in expired_members:
                guild_id = int(record["guild_id"])
                member_id = int(record["member_id"])
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    print(f"Guild with ID {guild_id} not found.")
                    continue

                member = guild.get_member(member_id)
                if not member:
                    print(f"Member with ID {member_id} not found in guild {guild_id}.")
                    # Optionally, remove the record if the member no longer exists
                    enslaved_members_col.delete_one({"guild_id": str(guild_id), "member_id": str(member_id)})
                    continue

                # Check if the member still has the Slave role
                slave_role = discord.utils.get(guild.roles, name='Slave')
                if slave_role and slave_role in member.roles:
                    await self.unenslave_member(member, guild)
        except Exception as e:
            print(f"An error occurred while checking for unenslave: {e}")

    async def unenslave_member(self, member: discord.Member, guild: discord.Guild):
        """Unenslave the member and restore their roles."""
        record = enslaved_members_col.find_one({"guild_id": str(guild.id), "member_id": str(member.id)})
        if not record:
            print(f"{member} is not enslaved.")
            return

        roles = record.get("roles", [])
        try:
            # Restore roles
            roles_to_add = [guild.get_role(role_id) for role_id in roles]
            roles_to_add = [role for role in roles_to_add if role is not None]  # Filter out any None roles

            await member.edit(roles=roles_to_add)

            # Remove Slave role if exists
            slave_role = discord.utils.get(guild.roles, name='Slave')
            if slave_role and slave_role in member.roles:
                await member.remove_roles(slave_role)

            # Remove timeout
            await member.timeout(None)
            print(f"{member} has been automatically unenslaved and roles restored.")

            # Remove the member's record from the database
            enslaved_members_col.delete_one({"guild_id": str(guild.id), "member_id": str(member.id)})
        except discord.Forbidden:
            print(f"Failed to unenslave {member} due to insufficient permissions.")
        except discord.HTTPException as e:
            print(f"Failed to unenslave {member}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred while unenslaving {member}: {e}")

    @app_commands.command(name='enslave', description="Removes someone's roles completely and times them out")
    @app_commands.describe(
        member='The member to enslave', 
        duration='Duration to enslave (e.g., 1d, 2h, 30m, 15s)'
    )
    @app_commands.checks.has_permissions(moderate_members=True, manage_roles=True)
    @check_if_disabled()
    async def enslave(self, interaction: discord.Interaction, member: discord.Member, duration: str):
        """Timeout a member and remove their roles."""
        # Parse duration
        time_units = {'d': 86400, 'h': 3600, 'm': 60, 's': 1}  # Seconds in each unit
        total_seconds = 0

        try:
            for part in duration.split(','):
                part = part.strip()
                if part and part[-1] in time_units:
                    amount = int(part[:-1])
                    total_seconds += amount * time_units[part[-1]]
                else:
                    await interaction.response.send_message(
                        "Invalid duration format. Use d, h, m, or s separated by commas (e.g., 1d,2h).", 
                        ephemeral=True
                    )
                    return

            if total_seconds <= 0:
                await interaction.response.send_message(
                    "Duration must be a positive value.", 
                    ephemeral=True
                )
                return

            # Save current roles excluding @everyone
            temp_roles = [role.id for role in member.roles if role != interaction.guild.default_role]

            # Calculate timeout end time
            timeout_end_time = datetime.utcnow() + timedelta(seconds=total_seconds)

            # Remove all roles and add the Slave role
            await member.edit(roles=[interaction.guild.default_role, self.slave_role])

            # Timeout the member
            await member.timeout(timeout_end_time)

            # Upsert the member's record in MongoDB
            enslaved_members_col.update_one(
                {"guild_id": str(interaction.guild.id), "member_id": str(member.id)},
                {"$set": {
                    "roles": temp_roles,
                    "timeout_end_time": timeout_end_time
                }},
                upsert=True
            )

            # Format the duration for the response
            formatted_duration = self.format_duration(total_seconds)
            await interaction.response.send_message(
                f"{member.mention} has been enslaved for {formatted_duration}.", 
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to modify this member's roles or timeout them.", 
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to enslave {member.mention}: {e}", 
                ephemeral=True
            )
        except ValueError:
            await interaction.response.send_message(
                "Invalid duration value. Make sure to use a positive integer.", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An unexpected error occurred: {e}", 
                ephemeral=True
            )

    @app_commands.command(name='unenslave', description='Removes timeout and restores all roles to a member.')
    @app_commands.describe(member='The member to unenslave')
    @app_commands.checks.has_permissions(moderate_members=True, manage_roles=True)
    @check_if_disabled()
    async def unenslave(self, interaction: discord.Interaction, member: discord.Member):
        """Remove timeout and restore roles."""
        try:
            record = enslaved_members_col.find_one({"guild_id": str(interaction.guild.id), "member_id": str(member.id)})

            if not record:
                await interaction.response.send_message(
                    f"{member.mention} is not enslaved.", 
                    ephemeral=True
                )
                return

            # Restore roles
            roles = record.get("roles", [])
            roles_to_add = [interaction.guild.get_role(role_id) for role_id in roles]
            roles_to_add = [role for role in roles_to_add if role is not None]  # Filter out any None roles

            await member.edit(roles=roles_to_add)

            # Remove Slave role if exists
            slave_role = discord.utils.get(interaction.guild.roles, name='Slave')
            if slave_role and slave_role in member.roles:
                await member.remove_roles(slave_role)

            # Remove timeout
            await member.timeout(None)

            # Remove the member's record from the database
            enslaved_members_col.delete_one({"guild_id": str(interaction.guild.id), "member_id": str(member.id)})

            await interaction.response.send_message(
                f"{member.mention} has been unenslaved and roles restored.", 
                ephemeral=False
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "I do not have permission to modify this member's roles or remove their timeout.", 
                ephemeral=True
            )
        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"Failed to unenslave {member.mention}: {e}", 
                ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An unexpected error occurred: {e}", 
                ephemeral=True
            )

    def format_duration(self, total_seconds: int) -> str:
        """Format the duration into a human-readable string."""
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)

        parts = []
        if days > 0:
            parts.append(f"{days} day{'s' if days != 1 else ''}")
        if hours > 0:
            parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
        if minutes > 0:
            parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
        if seconds > 0:
            parts.append(f"{seconds} second{'s' if seconds != 1 else ''}")

        return ', '.join(parts) if parts else "0 seconds"

async def setup(bot):
    await bot.add_cog(EnslaveCog(bot))
