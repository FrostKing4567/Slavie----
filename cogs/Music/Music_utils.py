# Music_utils.py
import discord
import yt_dlp as youtube_dl
import spotipy
from discord import app_commands
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

# Initialize Spotify client
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_ID")

spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET
))

YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True
}

def get_youtube_info(query):
    with youtube_dl.YoutubeDL(YTDL_OPTIONS) as ydl:
        try:
            info = ydl.extract_info(f"ytsearch:{query}", download=False)
            if 'entries' in info:
                video = info['entries'][0]
            else:
                video = info
            return {'url': video['url'], 'title': video['title']}
        except Exception as e:
            print(f"Error fetching YouTube info: {e}")
            return None

def get_spotify_tracks(link):
    tracks = []
    try:
        if "track" in link:
            result = spotify.track(link)
            tracks.append(result['name'] + " " + result['artists'][0]['name'])
        elif "playlist" in link:
            results = spotify.playlist_items(link)
            for item in results['items']:
                track = item['track']
                tracks.append(track['name'] + " " + track['artists'][0]['name'])
    except Exception as e:
        print(f"Error fetching Spotify tracks: {e}")
    return tracks
