"""
Alternative Music Player with multiple fallback methods
Handles YouTube bot detection by using multiple strategies
"""

import nextcord
from nextcord.ext import commands
import asyncio
import yt_dlp
import logging
from typing import Optional, Dict, Any, List
import aiohttp
import re
import json
import random

class AlternativeMusicPlayer(commands.Cog):
    """Alternative music player with multiple YouTube access methods"""
    
    def __init__(self, bot):
        self.bot = bot
        self.session = aiohttp.ClientSession()
        
        # Multiple yt-dlp instances with different configurations
        self.ytdl_configs = [
            # Configuration 1: Basic with rotation
            {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'default_search': 'ytsearch',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                },
            },
            # Configuration 2: Alternative method
            {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'default_search': 'ytsearch',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android'],
                    }
                },
                'http_headers': {
                    'User-Agent': 'com.google.android.youtube/17.31.35 (Linux; U; Android 11) gzip'
                },
            },
            # Configuration 3: Invidious fallback
            {
                'format': 'bestaudio/best',
                'quiet': True,
                'no_warnings': True,
                'extractaudio': False,
                'default_search': 'ytsearch',
                'extractor_args': {
                    'youtube': {
                        'player_client': ['web'],
                    }
                },
            }
        ]
        
        self.ytdl_instances = [yt_dlp.YoutubeDL(config) for config in self.ytdl_configs]
        self.current_instance = 0
        
        # Invidious instances for fallback
        self.invidious_instances = [
            'https://invidious.io',
            'https://invidious.snopyta.org',
            'https://invidious.xyz',
            'https://yewtu.be',
            'https://invidious.zapashcanon.fr',
            'https://invidious.kavin.rocks'
        ]
    
    def get_next_ytdl(self):
        """Get the next yt-dlp instance in rotation"""
        ytdl = self.ytdl_instances[self.current_instance]
        self.current_instance = (self.current_instance + 1) % len(self.ytdl_instances)
        return ytdl
    
    async def search_with_invidious(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search using Invidious API as fallback"""
        for instance in self.invidious_instances:
            try:
                url = f"{instance}/api/v1/search"
                params = {
                    'q': query,
                    'type': 'video',
                    'max_results': max_results
                }
                
                async with self.session.get(url, params=params, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = []
                        
                        for item in data[:max_results]:
                            if 'videoId' in item:
                                results.append({
                                    'title': item.get('title', 'Unknown'),
                                    'url': f"https://www.youtube.com/watch?v={item['videoId']}",
                                    'duration': item.get('lengthSeconds'),
                                    'thumbnail': f"https://img.youtube.com/vi/{item['videoId']}/maxresdefault.jpg",
                                    'uploader': item.get('author', 'Unknown')
                                })
                        
                        if results:
                            logging.info(f"Found {len(results)} results using Invidious")
                            return results
                            
            except Exception as e:
                logging.warning(f"Invidious instance {instance} failed: {e}")
                continue
        
        return []
    
    async def search_youtube_multi(self, query: str, max_results: int = 5) -> List[Dict]:
        """Search YouTube using multiple methods"""
        
        # Method 1: Try each yt-dlp configuration
        for i, ytdl in enumerate(self.ytdl_instances):
            try:
                logging.info(f"Trying yt-dlp configuration {i+1}")
                
                loop = asyncio.get_event_loop()
                search_query = f"ytsearch{max_results}:{query}"
                
                data = await loop.run_in_executor(
                    None, 
                    lambda: ytdl.extract_info(search_query, download=False)
                )
                
                if 'entries' in data and data['entries']:
                    valid_entries = [entry for entry in data['entries'] if entry and entry.get('url')]
                    if valid_entries:
                        logging.info(f"Success with yt-dlp config {i+1}")
                        return valid_entries
                        
            except Exception as e:
                logging.warning(f"yt-dlp config {i+1} failed: {e}")
                continue
        
        # Method 2: Try Invidious as fallback
        logging.info("Trying Invidious fallback...")
        invidious_results = await self.search_with_invidious(query, max_results)
        if invidious_results:
            return invidious_results
        
        # Method 3: Simple web search fallback (YouTube search page scraping)
        try:
            logging.info("Trying web search fallback...")
            return await self.search_youtube_web(query, max_results)
        except Exception as e:
            logging.error(f"Web search fallback failed: {e}")
        
        return []
    
    async def search_youtube_web(self, query: str, max_results: int = 5) -> List[Dict]:
        """Fallback web search method"""
        try:
            # Simple YouTube search URL
            search_url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            
            async with self.session.get(search_url, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    
                    # Basic regex to find video IDs (this is a simplified approach)
                    video_ids = re.findall(r'"videoId":"([^"]+)"', html)
                    titles = re.findall(r'"title":"([^"]+)"', html)
                    
                    results = []
                    for i, (video_id, title) in enumerate(zip(video_ids[:max_results], titles[:max_results])):
                        results.append({
                            'title': title,
                            'url': f"https://www.youtube.com/watch?v={video_id}",
                            'thumbnail': f"https://img.youtube.com/vi/{video_id}/maxresdefault.jpg",
                            'uploader': 'Unknown'
                        })
                    
                    return results
                    
        except Exception as e:
            logging.error(f"Web search error: {e}")
        
        return []
    
    async def create_audio_source_safe(self, video_url: str, title: str = "Unknown") -> nextcord.PCMVolumeTransformer:
        """Create audio source with multiple fallback methods"""
        
        # Try each yt-dlp instance to get stream URL
        for i, ytdl in enumerate(self.ytdl_instances):
            try:
                logging.info(f"Trying to extract stream with config {i+1}")
                
                loop = asyncio.get_event_loop()
                data = await loop.run_in_executor(
                    None, 
                    lambda: ytdl.extract_info(video_url, download=False)
                )
                
                stream_url = data.get('url')
                if not stream_url:
                    continue
                
                # Try to create FFmpeg source
                ffmpeg_options = {
                    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
                    'options': '-vn -filter:a "volume=0.5"'
                }
                
                try:
                    audio_source = nextcord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
                    volume_source = nextcord.PCMVolumeTransformer(audio_source, volume=0.5)
                    
                    # Attach metadata with proper title handling
                    extracted_title = data.get('title', title)
                    # Ensure we use the original title if extraction gives us a generic one
                    if extracted_title and extracted_title != 'videoplayback' and not extracted_title.startswith('https://'):
                        volume_source.title = extracted_title
                    else:
                        volume_source.title = title
                    
                    volume_source.url = video_url
                    volume_source.duration = data.get('duration')
                    volume_source.thumbnail = data.get('thumbnail')
                    volume_source.uploader = data.get('uploader', 'Unknown')
                    
                    logging.info(f"Successfully created audio source with config {i+1}")
                    return volume_source
                    
                except Exception as ffmpeg_error:
                    logging.warning(f"FFmpeg failed with config {i+1}: {ffmpeg_error}")
                    
                    # Try with minimal options
                    try:
                        audio_source = nextcord.FFmpegPCMAudio(stream_url, before_options='-nostdin', options='-vn')
                        volume_source = nextcord.PCMVolumeTransformer(audio_source, volume=0.5)
                        
                        # Handle title properly for minimal options too
                        extracted_title = data.get('title', title)
                        if extracted_title and extracted_title != 'videoplayback' and not extracted_title.startswith('https://'):
                            volume_source.title = extracted_title
                        else:
                            volume_source.title = title
                        
                        volume_source.url = video_url
                        volume_source.duration = data.get('duration')
                        volume_source.thumbnail = data.get('thumbnail')
                        volume_source.uploader = data.get('uploader', 'Unknown')
                        
                        logging.info(f"Created audio source with minimal options")
                        return volume_source
                        
                    except Exception as minimal_error:
                        logging.error(f"Even minimal FFmpeg options failed: {minimal_error}")
                        continue
                        
            except Exception as e:
                logging.warning(f"Config {i+1} completely failed: {e}")
                continue
        
        raise Exception("All methods failed to create audio source")
    
    @commands.command(name='search2', aliases=['asearch', 'find2'])
    async def alternative_search(self, ctx, *, query: str):
        """Advanced search using multiple methods (alternative to basic search)"""
        loading_embed = nextcord.Embed(
            description=f"🔍 Searching with multiple methods: **{query}**",
            color=nextcord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)
        
        try:
            results = await self.search_youtube_multi(query, max_results=5)
            
            if not results:
                embed = nextcord.Embed(
                    description="❌ No results found with any method.",
                    color=nextcord.Color.red()
                )
                await message.edit(embed=embed)
                return
            
            # Create search results embed
            embed = nextcord.Embed(
                title=f"🔍 Alternative Search Results for: {query}",
                color=nextcord.Color.green()
            )
            
            description = ""
            for i, result in enumerate(results, 1):
                title = result.get('title', 'Unknown')
                uploader = result.get('uploader', 'Unknown')
                duration = result.get('duration', 0)
                
                duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "Unknown"
                description += f"**{i}.** {title}\n"
                description += f"    By {uploader} • {duration_str}\n\n"
            
            embed.description = description
            embed.set_footer(text="Use '.play2 <number>' to play a song from the results")
            
            # Store search results
            if not hasattr(self.bot, 'alt_search_results'):
                self.bot.alt_search_results = {}
            self.bot.alt_search_results[ctx.author.id] = results
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logging.error(f"Alternative search error: {e}")
            embed = nextcord.Embed(
                description=f"❌ Alternative search failed: {str(e)}",
                color=nextcord.Color.red()
            )
            await message.edit(embed=embed)
    
    @commands.command(name='play2', aliases=['aplay', 'pplay'])
    async def alternative_play(self, ctx, choice: str = None):
        """Advanced play command with multiple fallback methods"""
        if not ctx.author.voice:
            embed = nextcord.Embed(
                description="❌ You need to be in a voice channel!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect()
            except Exception as e:
                embed = nextcord.Embed(
                    description=f"❌ Failed to connect: {str(e)}",
                    color=nextcord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        # If choice is a number, use search results
        if choice and choice.isdigit():
            choice_num = int(choice) - 1
            
            if (hasattr(self.bot, 'alt_search_results') and 
                ctx.author.id in self.bot.alt_search_results and
                0 <= choice_num < len(self.bot.alt_search_results[ctx.author.id])):
                
                result = self.bot.alt_search_results[ctx.author.id][choice_num]
                video_url = result['url']
                title = result['title']
            else:
                embed = nextcord.Embed(
                    description="❌ Invalid choice or no search results found. Use `.search2` first!",
                    color=nextcord.Color.red()
                )
                return await ctx.send(embed=embed)
        
        elif choice:
            # Direct search and play
            loading_embed = nextcord.Embed(
                description=f"🔍 Searching and playing: **{choice}**",
                color=nextcord.Color.yellow()
            )
            message = await ctx.send(embed=loading_embed)
            
            results = await self.search_youtube_multi(choice, max_results=1)
            if not results:
                embed = nextcord.Embed(
                    description="❌ No results found with alternative search.",
                    color=nextcord.Color.red()
                )
                return await message.edit(embed=embed)
            
            result = results[0]
            video_url = result['url']
            title = result['title']
        else:
            embed = nextcord.Embed(
                description="❌ Please provide a search query or choice number!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Try to play
        try:
            loading_embed = nextcord.Embed(
                description=f"⏳ Preparing to play: **{title}**",
                color=nextcord.Color.blue()
            )
            
            if 'message' not in locals():
                message = await ctx.send(embed=loading_embed)
            else:
                await message.edit(embed=loading_embed)
            
            source = await self.create_audio_source_safe(video_url, title)
            
            if ctx.voice_client.is_playing():
                ctx.voice_client.stop()
            
            ctx.voice_client.play(source)
            
            embed = nextcord.Embed(
                description=f"🎵 Now playing: **{source.title}**{f' by *{source.uploader}*' if hasattr(source, 'uploader') and source.uploader else ''}",
                color=nextcord.Color.green()
            )
            
            embed.set_footer(text=f"Requested by {ctx.author.display_name}")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logging.error(f"Alternative play error: {e}")
            embed = nextcord.Embed(
                description=f"❌ Failed to play with alternative method: {str(e)}",
                color=nextcord.Color.red()
            )
            
            if 'message' not in locals():
                await ctx.send(embed=embed)
            else:
                await message.edit(embed=embed)
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        asyncio.create_task(self.session.close())

async def setup(bot):
    bot.add_cog(AlternativeMusicPlayer(bot))
