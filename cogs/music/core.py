"""
Core music commands for BronxBot
Handles basic music functionality: join, disconnect, play, stop
"""

import nextcord
from nextcord.ext import commands
import asyncio
import logging
from typing import Optional

class MusicCore(commands.Cog):
    """Core music commands: join, disconnect, play, stop"""
    
    def __init__(self, bot):
        self.bot = bot
        self.voice_clients = {}  # guild_id -> voice_client
        
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        for voice_client in self.voice_clients.values():
            if voice_client:
                asyncio.create_task(voice_client.disconnect())
        self.voice_clients.clear()

    def add_voice_client(self, guild_id: int, voice_client):
        """Add a voice client for a guild"""
        self.voice_clients[guild_id] = voice_client

    def remove_voice_client(self, guild_id: int):
        """Remove the voice client for a guild"""
        if guild_id in self.voice_clients:
            del self.voice_clients[guild_id]

    @commands.command(name='join', aliases=['connect'])
    async def join(self, ctx):
        """Join the user's voice channel"""
        if not ctx.author.voice:
            embed = nextcord.Embed(
                description="❌ You need to be in a voice channel to use this command!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        channel = ctx.author.voice.channel
        
        # Check if bot is already connected to a voice channel
        if ctx.voice_client:
            if ctx.voice_client.channel == channel:
                embed = nextcord.Embed(
                    description="✅ I'm already connected to your voice channel!",
                    color=nextcord.Color.green()
                )
                return await ctx.send(embed=embed)
            else:
                # Move to the new channel
                await ctx.voice_client.move_to(channel)
                embed = nextcord.Embed(
                    description=f"🔄 Moved to **{channel.name}**",
                    color=nextcord.Color.blue()
                )
                return await ctx.send(embed=embed)
        
        try:
            # Connect to the voice channel
            voice_client = await channel.connect()
            self.add_voice_client(ctx.guild.id, voice_client)
            
            embed = nextcord.Embed(
                description=f"✅ Connected to **{channel.name}**",
                color=nextcord.Color.green()
            )
            await ctx.send(embed=embed)
            
        except Exception as e:
            logging.error(f"Error connecting to voice channel: {e}")
            embed = nextcord.Embed(
                description=f"❌ Failed to connect to voice channel: {str(e)}",
                color=nextcord.Color.red()
            )
            await ctx.send(embed=embed)

    @commands.command(name='disconnect', aliases=['leave', 'dc'])
    async def disconnect(self, ctx):
        """Disconnect from the voice channel"""
        if not ctx.voice_client:
            embed = nextcord.Embed(
                description="❌ I'm not connected to any voice channel!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Clear the queue
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_cog.clear_queue(ctx.guild.id)

        # Stop playing and disconnect
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        await ctx.voice_client.disconnect()
        self.remove_voice_client(ctx.guild.id)
        
        embed = nextcord.Embed(
            description="👋 Disconnected from voice channel",
            color=nextcord.Color.orange()
        )
        await ctx.send(embed=embed)

    @commands.command(name='play', aliases=['p'])
    async def play(self, ctx, *, query):
        """Play a song from YouTube"""
        # Check if user is in voice channel
        if not ctx.author.voice:
            embed = nextcord.Embed(
                description="❌ You need to be in a voice channel to play music!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Join voice channel if not connected
        if not ctx.voice_client:
            await self.join(ctx)

        # Check if bot is in the same voice channel as user
        if ctx.voice_client.channel != ctx.author.voice.channel:
            embed = nextcord.Embed(
                description="❌ You need to be in the same voice channel as me!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Show loading message
        loading_embed = nextcord.Embed(
            description=f"🔍 Searching for: **{query}**",
            color=nextcord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)

        try:
            # Get alternative music player (now the main method)
            alt_player = self.bot.get_cog('AlternativeMusicPlayer')
            if not alt_player:
                embed = nextcord.Embed(
                    description="❌ Music player is not available!",
                    color=nextcord.Color.red()
                )
                return await message.edit(embed=embed)

            # Search for the song using robust alternative method
            search_results = await alt_player.search_youtube_multi(query, max_results=1)
            
            if not search_results:
                embed = nextcord.Embed(
                    description=f"❌ No results found for: **{query}**",
                    color=nextcord.Color.red()
                )
                return await message.edit(embed=embed)

            # Get the first result and convert to our source format
            result = search_results[0]
            source = type('Source', (), {
                'title': result.get('title', 'Unknown'),
                'url': result.get('url', ''),
                'duration': result.get('duration'),
                'thumbnail': result.get('thumbnail'),
                'uploader': result.get('uploader')
            })()
            
            # If something is already playing, add to queue
            if ctx.voice_client.is_playing():
                queue_cog = self.bot.get_cog('MusicQueue')
                if queue_cog:
                    queue_cog.add_to_queue(ctx.guild.id, source, ctx.author)
                    
                    uploader_text = f" by *{source.uploader}*" if source.uploader else ""
                    embed = nextcord.Embed(
                        description=f"📋 Added to queue: **{source.title}**{uploader_text}",
                        color=nextcord.Color.blue()
                    )
                    if source.thumbnail:
                        embed.set_thumbnail(url=source.thumbnail)
                    
                    embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                    await message.edit(embed=embed)
                    return
            
            # Play immediately
            try:
                # Get queue cog reference for the entire function
                queue_cog = self.bot.get_cog('MusicQueue')
                
                audio_source = await alt_player.create_audio_source_safe(source.url, source.title)
                
                # Capture bot reference for the callback
                bot_ref = self.bot
                guild_id = ctx.guild.id
                
                def after_playing(error):
                    if error:
                        logging.error(f"Player error: {error}")
                    # Get fresh queue cog reference using captured bot reference
                    current_queue_cog = bot_ref.get_cog('MusicQueue')
                    if not current_queue_cog:
                        return
                    
                    # Add current song to history
                    if guild_id in current_queue_cog.now_playing:
                        if guild_id not in current_queue_cog.history:
                            current_queue_cog.history[guild_id] = []
                        current_queue_cog.history[guild_id].append(current_queue_cog.now_playing[guild_id])
                        # Keep only last 20 songs in history
                        if len(current_queue_cog.history[guild_id]) > 20:
                            current_queue_cog.history[guild_id].pop(0)
                    
                    # Auto-play next song from queue
                    bot_ref.loop.create_task(current_queue_cog.play_next(guild_id))
                
                # Set current song as now playing
                if queue_cog:
                    queue_cog.add_to_now_playing(ctx.guild.id, source, ctx.author)
                
                ctx.voice_client.play(audio_source, after=after_playing)
                
                # Create simple now playing embed with proper title
                uploader_text = f" by *{audio_source.uploader}*" if hasattr(audio_source, 'uploader') and audio_source.uploader else ""
                
                # Use the proper title from audio source, fallback to original search result
                display_title = getattr(audio_source, 'title', source.title)
                description = f"**{display_title}**{uploader_text}"
                
                # Check for next song in queue (use existing queue_cog reference)
                if queue_cog and ctx.guild.id in queue_cog.queues and queue_cog.queues[ctx.guild.id]:
                    next_item = queue_cog.queues[ctx.guild.id][0]
                    next_source = next_item[0] if isinstance(next_item, tuple) else next_item
                    next_title = getattr(next_source, 'title', 'Unknown')
                    next_uploader = getattr(next_source, 'uploader', None)
                    next_uploader_text = f" by *{next_uploader}*" if next_uploader else ""
                    description += f"\n\n*Next up: {next_title}{next_uploader_text}*"
                
                embed = nextcord.Embed(
                    description=f"🎵 Now playing: {description}",
                    color=nextcord.Color.green()
                )
                
                if hasattr(audio_source, 'thumbnail') and audio_source.thumbnail:
                    embed.set_thumbnail(url=audio_source.thumbnail)
                
                embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                
                await message.edit(embed=embed)
                
            except Exception as play_error:
                logging.error(f"Error playing audio: {play_error}")
                embed = nextcord.Embed(
                    description=f"❌ Error playing audio: {str(play_error)}\n\nThis might be due to YouTube restrictions. Try a different song.",
                    color=nextcord.Color.red()
                )
                await message.edit(embed=embed)
                
        except Exception as e:
            logging.error(f"Error in play command: {e}")
            embed = nextcord.Embed(
                description=f"❌ An error occurred while trying to play the song: {str(e)}",
                color=nextcord.Color.red()
            )
            await message.edit(embed=embed)

    @commands.command(name='stop')
    async def stop(self, ctx):
        """Stop playing music and clear the queue"""
        if not ctx.voice_client:
            embed = nextcord.Embed(
                description="❌ I'm not connected to any voice channel!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        if not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)

        # Clear the queue
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_cog.clear_queue(ctx.guild.id)

        # Stop playback
        ctx.voice_client.stop()
        
        embed = nextcord.Embed(
            description="⏹️ Stopped playing music and cleared the queue",
            color=nextcord.Color.orange()
        )
        await ctx.send(embed=embed)

    @commands.command(name='search', aliases=['find'])
    async def search(self, ctx, *, query: str):
        """Search for songs without playing"""
        loading_embed = nextcord.Embed(
            description=f"🔍 Searching for: **{query}**",
            color=nextcord.Color.yellow()
        )
        message = await ctx.send(embed=loading_embed)
        
        try:
            alt_player = self.bot.get_cog('AlternativeMusicPlayer')
            if not alt_player:
                embed = nextcord.Embed(
                    description="❌ Music player is not available!",
                    color=nextcord.Color.red()
                )
                return await message.edit(embed=embed)

            results = await alt_player.search_youtube_multi(query, max_results=5)
            
            if not results:
                embed = nextcord.Embed(
                    description="❌ No results found.",
                    color=nextcord.Color.red()
                )
                await message.edit(embed=embed)
                return
            
            # Create search results embed
            embed = nextcord.Embed(
                title=f"🔍 Search Results for: {query}",
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
            embed.set_footer(text="Use '.play <song name>' to play any of these songs")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logging.error(f"Search error: {e}")
            embed = nextcord.Embed(
                description=f"❌ Search failed: {str(e)}",
                color=nextcord.Color.red()
            )
            await message.edit(embed=embed)

async def setup(bot):
    bot.add_cog(MusicCore(bot))
