"""
Music Player module for BronxBot
Handles audio playback, streaming, and advanced player features
"""

import nextcord
from nextcord.ext import commands
import asyncio
import yt_dlp
import logging
from typing import Optional, Dict, Any, List
import aiohttp
import re

class AudioSource:
    """Base class for audio sources"""
    def __init__(self, title: str, url: str, duration: Optional[int] = None, 
                 thumbnail: Optional[str] = None, uploader: Optional[str] = None):
        self.title = title
        self.url = url
        self.duration = duration
        self.thumbnail = thumbnail
        self.uploader = uploader

class YouTubeSource(AudioSource):
    """YouTube audio source with enhanced features"""
    
    def __init__(self, data: Dict[str, Any]):
        super().__init__(
            title=data.get('title', 'Unknown'),
            url=data.get('webpage_url', data.get('url', '')),
            duration=data.get('duration'),
            thumbnail=data.get('thumbnail'),
            uploader=data.get('uploader')
        )
        self.stream_url = data.get('url')
        self.view_count = data.get('view_count')
        self.upload_date = data.get('upload_date')
        self.description = data.get('description', '')[:200] + '...' if data.get('description') else None

class MusicPlayer(commands.Cog):
    """Advanced music player with streaming and playback features"""
    
    def __init__(self, bot):
        self.bot = bot
        # Multiple user agents to rotate through
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/121.0'
        ]
        self.current_ua_index = 0
        
        self.ytdl_options = {
            'format': 'bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best',
            'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
            'restrictfilenames': True,
            'noplaylist': True,
            'nocheckcertificate': True,
            'ignoreerrors': False,
            'logtostderr': False,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',  # Force YouTube search
            'source_address': '0.0.0.0',
            'extractaudio': False,
            'age_limit': None,
            'geo_bypass': True,
            'geo_bypass_country': 'US',
            # Anti-bot measures
            'extractor_args': {
                'youtube': {
                    'skip': ['hls', 'dash'],  # Skip problematic formats
                    'player_skip': ['js'],    # Skip JavaScript player
                }
            },
            # Headers to mimic real browser
            'http_headers': {
                'User-Agent': self.user_agents[0],
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Accept-Encoding': 'gzip,deflate',
                'Accept-Charset': 'ISO-8859-1,utf-8;q=0.7,*;q=0.7',
                'Keep-Alive': '300',
                'Connection': 'keep-alive',
            },
            # Retry and timeout options
            'retries': 5,
            'fragment_retries': 5,
            'file_access_retries': 3,
            'extractor_retries': 3,
            'socket_timeout': 30,
        }
        
        self.ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin -user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"',
            'options': '-vn -filter:a "volume=0.5" -bufsize 512k'
        }
        
        self.ytdl = yt_dlp.YoutubeDL(self.ytdl_options)
        self.current_players: Dict[int, nextcord.PCMVolumeTransformer] = {}  # guild_id -> current player
        
    async def search_youtube(self, query: str, max_results: int = 5) -> List[YouTubeSource]:
        """Search YouTube and return a list of sources with improved error handling"""
        try:
            loop = asyncio.get_event_loop()
            
            # If it's a URL, extract info directly
            if re.match(r'https?://', query):
                try:
                    data = await loop.run_in_executor(
                        None, 
                        lambda: self.ytdl.extract_info(query, download=False)
                    )
                    if 'entries' in data:
                        return [YouTubeSource(entry) for entry in data['entries'][:max_results] if entry]
                    else:
                        return [YouTubeSource(data)]
                except Exception as url_error:
                    logging.error(f"Error extracting URL {query}: {url_error}")
                    # Try as search query instead
                    query = query.split('/')[-1] if '/' in query else query
            
            # Search YouTube
            search_query = f"ytsearch{max_results}:{query}"
            logging.info(f"Searching YouTube with query: {search_query}")
            
            data = await loop.run_in_executor(
                None, 
                lambda: self.ytdl.extract_info(search_query, download=False)
            )
            
            if 'entries' in data and data['entries']:
                # Filter out None entries and create sources
                valid_entries = [entry for entry in data['entries'] if entry and entry.get('url')]
                if valid_entries:
                    return [YouTubeSource(entry) for entry in valid_entries]
                else:
                    logging.warning("No valid entries found in search results")
                    return []
            else:
                logging.warning("No entries found in search results")
                return []
                
        except Exception as e:
            logging.error(f"Error searching YouTube: {e}")
            return []
    
    async def create_audio_source(self, source: YouTubeSource, volume: float = 0.5) -> nextcord.PCMVolumeTransformer:
        """Create a Discord audio source from a YouTubeSource with retry logic"""
        try:
            loop = asyncio.get_event_loop()
            
            # Try to get fresh stream URL with retries
            max_retries = 3
            stream_url = None
            
            for attempt in range(max_retries):
                try:
                    logging.info(f"Attempting to extract stream URL (attempt {attempt + 1}/{max_retries})")
                    
                    # Get fresh stream URL (they expire)
                    data = await loop.run_in_executor(
                        None, 
                        lambda: self.ytdl.extract_info(source.url, download=False)
                    )
                    
                    # Try different URL fields
                    stream_url = data.get('url') or data.get('manifest_url') or data.get('webpage_url')
                    
                    if stream_url:
                        logging.info(f"Successfully extracted stream URL: {stream_url[:100]}...")
                        break
                    else:
                        logging.warning(f"No stream URL found in attempt {attempt + 1}")
                        
                except Exception as e:
                    logging.error(f"Attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        raise
                    await asyncio.sleep(1)  # Wait before retry
            
            if not stream_url:
                raise Exception("Could not get stream URL after retries")
            
            # Create audio source with improved error handling
            try:
                audio_source = nextcord.FFmpegPCMAudio(stream_url, **self.ffmpeg_options)
                volume_source = nextcord.PCMVolumeTransformer(audio_source, volume=volume)
                
                # Attach metadata to the source
                volume_source.title = source.title
                volume_source.url = source.url
                volume_source.duration = source.duration
                volume_source.thumbnail = source.thumbnail
                volume_source.uploader = source.uploader
                
                return volume_source
                
            except Exception as ffmpeg_error:
                logging.error(f"FFmpeg error: {ffmpeg_error}")
                # Try with simpler options as fallback
                fallback_options = {
                    'before_options': '-nostdin',
                    'options': '-vn'
                }
                audio_source = nextcord.FFmpegPCMAudio(stream_url, **fallback_options)
                volume_source = nextcord.PCMVolumeTransformer(audio_source, volume=volume)
                
                # Attach metadata
                volume_source.title = source.title
                volume_source.url = source.url
                volume_source.duration = source.duration
                volume_source.thumbnail = source.thumbnail
                volume_source.uploader = source.uploader
                
                return volume_source
            
        except Exception as e:
            logging.error(f"Error creating audio source: {e}")
            raise Exception(f"Failed to create audio source: {str(e)}")

    def play_in_guild(self, guild_id: int, source: nextcord.PCMVolumeTransformer, 
                     after_callback=None):
        """Play audio in a specific guild"""
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return False
        
        try:
            # Store current player
            self.current_players[guild_id] = source
            
            # Define the after callback
            def after_playing(error):
                if error:
                    logging.error(f"Player error in guild {guild_id}: {error}")
                
                # Remove from current players
                if guild_id in self.current_players:
                    del self.current_players[guild_id]
                
                # Call custom callback if provided
                if after_callback:
                    self.bot.loop.create_task(after_callback(error))
            
            guild.voice_client.play(source, after=after_playing)
            return True
            
        except Exception as e:
            logging.error(f"Error playing audio in guild {guild_id}: {e}")
            return False

    def get_current_player(self, guild_id: int) -> Optional[nextcord.PCMVolumeTransformer]:
        """Get the current player for a guild"""
        return self.current_players.get(guild_id)

    @commands.command(name='search')
    async def search_music(self, ctx, *, query: str):
        """Search for music and display results"""
        loading_embed = nextcord.Embed(
            description=f"🔍 Searching for: **{query}**",
            color=nextcord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)
        
        try:
            results = await self.search_youtube(query, max_results=5)
            
            if not results:
                embed = nextcord.Embed(
                    description="❌ No results found for your search.",
                    color=nextcord.Color.red()
                )
                await message.edit(embed=embed)
                return
            
            # Create search results embed
            embed = nextcord.Embed(
                title=f"🔍 Search Results for: {query}",
                color=nextcord.Color.blue()
            )
            
            description = ""
            for i, result in enumerate(results, 1):
                duration_str = f"{result.duration // 60}:{result.duration % 60:02d}" if result.duration else "Live"
                description += f"**{i}.** [{result.title}]({result.url})\n"
                description += f"    By {result.uploader} • {duration_str}\n\n"
            
            embed.description = description
            embed.set_footer(text="Use '.play <number>' to play a song from the results")
            
            # Store search results temporarily
            if not hasattr(self.bot, 'search_results'):
                self.bot.search_results = {}
            self.bot.search_results[ctx.author.id] = results
            
            # Auto-clear search results after 5 minutes
            async def clear_results():
                await asyncio.sleep(300)  # 5 minutes
                if ctx.author.id in self.bot.search_results:
                    del self.bot.search_results[ctx.author.id]
            
            asyncio.create_task(clear_results())
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logging.error(f"Error in search command: {e}")
            embed = nextcord.Embed(
                description=f"❌ An error occurred while searching: {str(e)}",
                color=nextcord.Color.red()
            )
            await message.edit(embed=embed)

    @commands.command(name='volume', aliases=['vol'])
    async def set_volume(self, ctx, volume: int):
        """Set the volume of the current player (0-100)"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if volume < 0 or volume > 100:
            embed = nextcord.Embed(
                description="❌ Volume must be between 0 and 100!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Check if user has permission to change volume
        if not ctx.author.guild_permissions.manage_messages and volume > 50:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to set volume above 50%!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Set volume
        if isinstance(ctx.voice_client.source, nextcord.PCMVolumeTransformer):
            ctx.voice_client.source.volume = volume / 100.0
            
            embed = nextcord.Embed(
                description=f"🔊 Volume set to **{volume}%**",
                color=nextcord.Color.green()
            )
            await ctx.send(embed=embed)
        else:
            embed = nextcord.Embed(
                description="❌ Cannot adjust volume for this audio source!",
                color=nextcord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='playinfo', aliases=['info'])
    async def play_info(self, ctx):
        """Show detailed information about the currently playing song"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        source = ctx.voice_client.source
        
        embed = nextcord.Embed(
            title="🎵 Currently Playing",
            color=nextcord.Color.blue()
        )
        
        if hasattr(source, 'title'):
            embed.add_field(name="Title", value=source.title, inline=False)
        
        if hasattr(source, 'uploader') and source.uploader:
            embed.add_field(name="Channel", value=source.uploader, inline=True)
        
        if hasattr(source, 'duration') and source.duration:
            embed.add_field(
                name="Duration", 
                value=f"{source.duration // 60}:{source.duration % 60:02d}", 
                inline=True
            )
        
        if hasattr(source, 'volume'):
            embed.add_field(
                name="Volume", 
                value=f"{int(source.volume * 100)}%", 
                inline=True
            )
        
        if hasattr(source, 'url') and source.url:
            embed.add_field(name="URL", value=f"[Click here]({source.url})", inline=False)
        
        if hasattr(source, 'thumbnail') and source.thumbnail:
            embed.set_thumbnail(url=source.thumbnail)
        
        # Add queue info
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_length = len(queue_cog.get_queue(ctx.guild.id))
            if queue_length > 0:
                embed.add_field(name="Queue", value=f"{queue_length} songs", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name='lyrics')
    async def get_lyrics(self, ctx, *, song_title: str = None):
        """Get lyrics for the current song or a specified song"""
        if not song_title:
            # Try to get current song title
            if ctx.voice_client and ctx.voice_client.is_playing():
                source = ctx.voice_client.source
                if hasattr(source, 'title'):
                    song_title = source.title
                else:
                    embed = nextcord.Embed(
                        description="❌ Please specify a song title or play a song first!",
                        color=nextcord.Color.red()
                    )
                    return await ctx.send(embed=embed)
            else:
                embed = nextcord.Embed(
                    description="❌ Please specify a song title or play a song first!",
                    color=nextcord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        loading_embed = nextcord.Embed(
            description=f"🔍 Searching for lyrics: **{song_title}**",
            color=nextcord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)
        
        try:
            # This is a placeholder - you would need to implement actual lyrics fetching
            # from a service like Genius API or similar
            embed = nextcord.Embed(
                title="🎵 Lyrics",
                description="Lyrics functionality is not yet implemented. This would require integration with a lyrics API service.",
                color=nextcord.Color.blue()
            )
            embed.add_field(name="Song", value=song_title, inline=False)
            embed.set_footer(text="Feature coming soon!")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logging.error(f"Error fetching lyrics: {e}")
            embed = nextcord.Embed(
                description=f"❌ An error occurred while fetching lyrics: {str(e)}",
                color=nextcord.Color.red()
            )
            await message.edit(embed=embed)

async def setup(bot):
    bot.add_cog(MusicPlayer(bot))
