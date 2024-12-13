import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import os
import random
import json
import asyncio
from .Music_utils import get_youtube_info, get_spotify_tracks, FFMPEG_OPTIONS
from discord import app_commands
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

class Play(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue = {}
        self.is_playing = {}
        self.current_song = {}
        self.loop = {}
        self.loop_all = {}
        self.shuffle_active = {}
        self.is_paused = {}
        self.volume = {}  # Centralized volume per guild

    async def join_channel(self, interaction: discord.Interaction):
        if interaction.user.voice is None:
            await interaction.response.send_message("You need to be in a voice channel to use this command!")
            return None
        voice_channel = interaction.user.voice.channel
        if interaction.guild.voice_client is None:
            await voice_channel.connect()
        elif interaction.guild.voice_client.channel != voice_channel:
            await interaction.guild.voice_client.move_to(voice_channel)
        return interaction.guild.voice_client

    @app_commands.command(name='play', description="Play a song from YouTube or Spotify.")
    @check_if_disabled()
    async def play(self, interaction: discord.Interaction, *, query: str):
        # Defer the response to prevent timeout
        await interaction.response.defer(thinking=True)

        voice_client = await self.join_channel(interaction)
        if voice_client is None:
            return

        if interaction.guild.id not in self.queue:
            self.queue[interaction.guild.id] = []

        if "spotify.com" in query:
            tracks = get_spotify_tracks(query)
            if not tracks:
                await interaction.followup.send("Could not find any songs from the Spotify link! 😢")
                return
            for track in tracks:
                video = get_youtube_info(track)
                if video:
                    self.queue[interaction.guild.id].append(video)
            await interaction.followup.send(f"Added {len(tracks)} songs to the queue! 🎉")
        else:
            video = get_youtube_info(query)
            if video:
                self.queue[interaction.guild.id].append(video)
                await interaction.followup.send(f"Added {video['title']} to the queue! 💖")
            else:
                await interaction.followup.send("Could not find the song! 😢")
                return

        if not interaction.guild.voice_client.is_playing() and not self.is_playing.get(interaction.guild.id, False):
            self.is_playing[interaction.guild.id] = True
            await self.play_next(interaction)

    async def play_next(self, interaction: discord.Interaction):
        if interaction.guild.id in self.queue and len(self.queue[interaction.guild.id]) > 0:
            if self.shuffle_active.get(interaction.guild.id, False):
                random.shuffle(self.queue[interaction.guild.id])

            song_info = self.queue[interaction.guild.id].pop(0)
            self.current_song[interaction.guild.id] = song_info

            if song_info:
                try:
                    # Fetch song metadata
                    song_title = song_info.get('title', 'Unknown Title')
                    song_url = song_info.get('url')
                    song_duration = song_info.get('duration', 'Unknown Duration')  # Duration info
                    thumbnail_url = song_info.get('thumbnail', '')  # Thumbnail image

                    # Volume: Get the volume from the centralized dictionary
                    current_volume = self.volume.get(interaction.guild.id, 1.0) * 100  # Volume in percentage

                    # Create an embed for the Now Playing message
                    embed = discord.Embed(
                        title="🎶 Now Playing", 
                        description=f"[{song_title}]({song_url})",
                        color=discord.Color.pink()  # You can change the color
                    )
                    
                    embed.set_thumbnail(url=thumbnail_url)  # Set the thumbnail
                    embed.add_field(name="Duration", value=song_duration, inline=True)  # Add song duration
                    embed.add_field(name="Volume", value=f"{current_volume:.0f}%", inline=True)  # Add volume info
                    embed.set_footer(text=f"Requested by {interaction.user.display_name}💕", icon_url=interaction.user.avatar.url)

                    play_buttons = self.create_play_buttons()
                    await interaction.channel.send(embed=embed, view=play_buttons)

                    # Play the audio
                    audio_source = discord.FFmpegPCMAudio(song_url, **FFMPEG_OPTIONS)
                    audio_source = discord.PCMVolumeTransformer(audio_source, volume=self.volume.get(interaction.guild.id, 1.0))

                    interaction.guild.voice_client.play(
                        audio_source,
                        after=lambda e: asyncio.run_coroutine_threadsafe(self.handle_after_play(interaction, e), self.bot.loop)
                    )

                    self.is_playing[interaction.guild.id] = True
                except Exception as e:
                    print(f"Error playing the song: {e}")
                    await interaction.channel.send("Error occurred while trying to play the next song. 😢")
                    await self.play_next(interaction)
            else:
                await interaction.channel.send("Queue is empty. 🌟")
                self.is_playing[interaction.guild.id] = False
                self.current_song.pop(interaction.guild.id, None)
        else:
            await interaction.channel.send("Queue is empty. 🌟")
            self.is_playing[interaction.guild.id] = False
            self.current_song.pop(interaction.guild.id, None)

    async def handle_after_play(self, interaction: discord.Interaction, error):
        if error:
            print(f"Playback error: {error}")
            await interaction.channel.send("An error occurred during playback. 😢")

        if self.loop_all.get(interaction.guild.id, False):
            self.queue[interaction.guild.id].append(self.current_song[interaction.guild.id])
            await self.play_next(interaction)
        elif self.loop.get(interaction.guild.id, False):
            self.queue[interaction.guild.id].insert(0, self.current_song[interaction.guild.id])
            await self.play_next(interaction)
        else:
            await self.play_next(interaction)

    def create_play_buttons(self):
        """Create buttons for music control commands."""
        buttons = discord.ui.View()
        
        # Pause Button
        pause_button = discord.ui.Button(label='Pause', style=discord.ButtonStyle.primary, custom_id='pause')
        pause_button.callback = self.pause_song
        buttons.add_item(pause_button)
        
        # Resume Button
        resume_button = discord.ui.Button(label='Resume', style=discord.ButtonStyle.success, custom_id='resume')
        resume_button.callback = self.resume_song
        buttons.add_item(resume_button)

        # Stop Button
        stop_button = discord.ui.Button(label='Stop', style=discord.ButtonStyle.danger, custom_id='stop')
        stop_button.callback = self.stop_song
        buttons.add_item(stop_button)

        # Skip Button using the exact functionality you provided
        skip_button = discord.ui.Button(label='Skip', style=discord.ButtonStyle.secondary, custom_id='skip')
        skip_button.callback = self.skip_song
        buttons.add_item(skip_button)

        # Shuffle Button
        shuffle_button = discord.ui.Button(label='Shuffle', style=discord.ButtonStyle.secondary, custom_id='shuffle')
        shuffle_button.callback = self.shuffle_song
        buttons.add_item(shuffle_button)

        # Loop Button
        loop_button = discord.ui.Button(label='Loop', style=discord.ButtonStyle.secondary, custom_id='loop')
        loop_button.callback = self.loop_song
        buttons.add_item(loop_button)

        # Loop All Button
        loop_all_button = discord.ui.Button(label='Loop All', style=discord.ButtonStyle.secondary, custom_id='loop_all')
        loop_all_button.callback = self.loop_all_songs
        buttons.add_item(loop_all_button)

        return buttons

    async def skip_song(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is None or not interaction.guild.voice_client.is_playing():
            await interaction.response.send_message("No song is currently playing! 🙅‍♂️")
            return

        # Stop the currently playing audio
        interaction.guild.voice_client.stop()
        # Wait for the current song to finish before playing the next one
        await interaction.response.send_message("Skipped the current song! 🎵 Moving to the next one...")
        await interaction.guild.voice_client.wait_for("finished_playing") 
        
        # Play the next song
        await self.bot.get_cog('Play').play_next(interaction)

    async def pause_song(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.pause()
            await interaction.response.send_message("Paused the music! ⏸️")
        else:
            await interaction.response.send_message("No music is currently playing! 🙅‍♂️")

    async def resume_song(self, interaction: discord.Interaction):
        if interaction.guild.voice_client.is_paused():
            interaction.guild.voice_client.resume()
            await interaction.response.send_message("Resumed the music! ▶️")
        else:
            await interaction.response.send_message("Music is not paused! 🥲")

    async def stop_song(self, interaction: discord.Interaction):
        if interaction.guild.voice_client is not None:
            await interaction.guild.voice_client.disconnect()
            self.queue[interaction.guild.id] = []
            self.current_song.pop(interaction.guild.id, None)
            await interaction.response.send_message("Stopped the music and disconnected! 🛑")
        else:
            await interaction.response.send_message("Not connected to a voice channel! 🙅‍♂️")

    async def shuffle_song(self, interaction: discord.Interaction):
        self.shuffle_active[interaction.guild.id] = not self.shuffle_active.get(interaction.guild.id, False)
        if self.shuffle_active[interaction.guild.id]:
            await interaction.response.send_message("Shuffle mode is now **ON**! 🔀")
        else:
            await interaction.response.send_message("Shuffle mode is now **OFF**! 🔁")

    async def loop_song(self, interaction: discord.Interaction):
        if interaction.guild.id not in self.loop:
            self.loop[interaction.guild.id] = False

        self.loop[interaction.guild.id] = not self.loop[interaction.guild.id]
        if self.loop[interaction.guild.id]:
            await interaction.response.send_message("Looping current song! 🔄")
        else:
            await interaction.response.send_message("Looping disabled! 🚫")

    async def loop_all_songs(self, interaction: discord.Interaction):
        if interaction.guild.id not in self.loop_all:
            self.loop_all[interaction.guild.id] = False

        self.loop_all[interaction.guild.id] = not self.loop_all[interaction.guild.id]
        if self.loop_all[interaction.guild.id]:
            await interaction.response.send_message("Looping all songs in queue! 🔁")
        else:
            await interaction.response.send_message("Loop all disabled! 🚫")

async def setup(bot):
    await bot.add_cog(Play(bot))
