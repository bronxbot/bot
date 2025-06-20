"""
Music Queue management for BronxBot
Handles queue operations, interactive queue display, and queue manipulation
"""

import nextcord
from nextcord.ext import commands
from collections import deque
from typing import Dict, List, Optional, Tuple
import asyncio
import logging

class QueueView(nextcord.ui.View):
    """Interactive queue view with pagination and controls"""
    
    def __init__(self, queue_cog, guild_id: int, per_page: int = 10):
        super().__init__(timeout=300)  # 5 minute timeout
        self.queue_cog = queue_cog
        self.guild_id = guild_id
        self.per_page = per_page
        self.current_page = 0
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current page and queue length"""
        queue_length = len(self.queue_cog.get_queue(self.guild_id))
        max_pages = max(1, (queue_length + self.per_page - 1) // self.per_page)
        
        # Update previous button
        self.previous_page.disabled = self.current_page <= 0
        
        # Update next button
        self.next_page.disabled = self.current_page >= max_pages - 1
        
        # Update clear button - disable if queue is empty
        self.clear_queue.disabled = queue_length == 0
    
    def get_queue_embed(self) -> nextcord.Embed:
        """Generate embed for current page of queue"""
        queue = self.queue_cog.get_queue(self.guild_id)
        
        if not queue:
            embed = nextcord.Embed(
                title="📋 Music Queue",
                description="Queue is empty! Use `.play <song>` to add songs.",
                color=nextcord.Color.blue()
            )
            return embed
        
        # Calculate pagination
        start_idx = self.current_page * self.per_page
        end_idx = min(start_idx + self.per_page, len(queue))
        max_pages = max(1, (len(queue) + self.per_page - 1) // self.per_page)
        
        embed = nextcord.Embed(
            title="📋 Music Queue",
            color=nextcord.Color.blue()
        )
        
        # Add queue items for current page with simplified format
        queue_text = ""
        total_duration = 0
        
        for i in range(start_idx, end_idx):
            player, requester = queue[i]
            
            # Get title and truncate if too long
            title = getattr(player, 'title', 'Unknown')
            if len(title) > 45:
                title = title[:42] + "..."
            
            # Get duration
            duration = getattr(player, 'duration', 0)
            if duration:
                duration_str = f"{duration // 60}:{duration % 60:02d}"
                total_duration += duration
            else:
                duration_str = "Live"
            
            # Get requester name and truncate
            requester_name = getattr(requester, 'display_name', 'Unknown')
            if len(requester_name) > 15:
                requester_name = requester_name[:12] + "..."
            
            # Simple format to avoid character limits
            queue_text += f"**{i + 1}.** {title} `{duration_str}`\n"
            
            # Check if we're approaching Discord's embed limits
            if len(queue_text) > 1800:
                remaining = len(queue) - i - 1
                if remaining > 0:
                    queue_text += f"*... and {remaining} more songs*"
                break
        
        embed.description = queue_text if queue_text else "No songs in queue"
        
        # Add footer with page info and total duration
        total_duration_all = sum(getattr(player, 'duration', 0) or 0 for player, _ in queue)
        
        hours = total_duration_all // 3600
        minutes = (total_duration_all % 3600) // 60
        seconds = total_duration_all % 60
        
        if hours > 0:
            duration_str = f"{hours}h {minutes}m"
        else:
            duration_str = f"{minutes}m {seconds}s"
        
        embed.set_footer(
            text=f"Page {self.current_page + 1}/{max_pages} • {len(queue)} songs • {duration_str}"
        )
        
        return embed
    
    @nextcord.ui.button(label="◀️ Previous", style=nextcord.ButtonStyle.secondary)
    async def previous_page(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            embed = self.get_queue_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @nextcord.ui.button(label="▶️ Next", style=nextcord.ButtonStyle.secondary)
    async def next_page(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        queue_length = len(self.queue_cog.get_queue(self.guild_id))
        max_pages = max(1, (queue_length + self.per_page - 1) // self.per_page)
        
        if self.current_page < max_pages - 1:
            self.current_page += 1
            self.update_buttons()
            embed = self.get_queue_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()
    
    @nextcord.ui.button(label="🔄 Refresh", style=nextcord.ButtonStyle.primary)
    async def refresh(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        self.update_buttons()
        embed = self.get_queue_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="🗑️ Clear", style=nextcord.ButtonStyle.danger)
    async def clear_queue(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        # Check if user has permission to clear queue
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission to clear the queue!", ephemeral=True)
            return
        
        self.queue_cog.clear_queue(self.guild_id)
        self.current_page = 0
        self.update_buttons()
        embed = self.get_queue_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="🔀 Shuffle", style=nextcord.ButtonStyle.secondary)
    async def shuffle_queue(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        # Check if user has permission to shuffle queue
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission to shuffle the queue!", ephemeral=True)
            return
        
        shuffled = self.queue_cog.shuffle_queue(self.guild_id)
        if shuffled:
            self.current_page = 0
            self.update_buttons()
            embed = self.get_queue_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Queue is empty or has only one song!", ephemeral=True)
    
    async def on_timeout(self):
        """Called when the view times out"""
        # Disable all buttons
        for item in self.children:
            item.disabled = True
        
        # Try to edit the message to show it's timed out
        try:
            embed = nextcord.Embed(
                title="📋 Music Queue",
                description="❌ This queue display has timed out. Use `.queue` to view again.",
                color=nextcord.Color.red()
            )
            await self.message.edit(embed=embed, view=self)
        except:
            pass  # Message might have been deleted

class MusicQueue(commands.Cog):
    """Music queue management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.queues: Dict[int, deque] = {}  # guild_id -> deque of (player, requester) tuples
        self.now_playing: Dict[int, Tuple] = {}  # guild_id -> (player, requester) for current song
        self.history: Dict[int, List[Tuple]] = {}  # guild_id -> list of (player, requester) history

    def get_queue(self, guild_id: int) -> List[Tuple]:
        """Get the queue for a guild as a list"""
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        return list(self.queues[guild_id])
    
    def add_to_queue(self, guild_id: int, player, requester):
        """Add a song to the queue"""
        if guild_id not in self.queues:
            self.queues[guild_id] = deque()
        self.queues[guild_id].append((player, requester))
    
    def get_next_song(self, guild_id: int) -> Optional[Tuple]:
        """Get the next song from the queue"""
        if guild_id not in self.queues or not self.queues[guild_id]:
            return None
        return self.queues[guild_id].popleft()
    
    def clear_queue(self, guild_id: int):
        """Clear the queue for a guild"""
        if guild_id in self.queues:
            self.queues[guild_id].clear()
    
    def remove_from_queue(self, guild_id: int, index: int) -> bool:
        """Remove a song from the queue by index (0-based)"""
        if guild_id not in self.queues or index < 0 or index >= len(self.queues[guild_id]):
            return False
        
        # Convert deque to list, remove item, convert back
        queue_list = list(self.queues[guild_id])
        queue_list.pop(index)
        self.queues[guild_id] = deque(queue_list)
        return True
    
    def shuffle_queue(self, guild_id: int) -> bool:
        """Shuffle the queue"""
        if guild_id not in self.queues or len(self.queues[guild_id]) <= 1:
            return False
        
        import random
        queue_list = list(self.queues[guild_id])
        random.shuffle(queue_list)
        self.queues[guild_id] = deque(queue_list)
        return True
    
    def move_song(self, guild_id: int, from_index: int, to_index: int) -> bool:
        """Move a song from one position to another"""
        if guild_id not in self.queues:
            return False
        
        queue_list = list(self.queues[guild_id])
        
        if from_index < 0 or from_index >= len(queue_list) or to_index < 0 or to_index >= len(queue_list):
            return False
        
        # Remove from old position and insert at new position
        song = queue_list.pop(from_index)
        queue_list.insert(to_index, song)
        
        self.queues[guild_id] = deque(queue_list)
        return True

    async def play_next(self, guild_id: int):
        """Play the next song in the queue"""
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        
        # Get next song from queue
        next_item = self.get_next_song(guild_id)
        if not next_item:
            # Queue is empty
            self.now_playing.pop(guild_id, None)
            return
        
        source, requester = next_item
        
        try:
            # Get alternative music player
            alt_player = self.bot.get_cog('AlternativeMusicPlayer')
            if not alt_player:
                return
            
            # Create audio source
            audio_source = await alt_player.create_audio_source_safe(source.url, source.title)
            
            # Capture references for the callback
            bot_ref = self.bot
            now_playing_ref = self.now_playing
            history_ref = self.history
            
            def after_playing(error):
                if error:
                    logging.error(f"Player error: {error}")
                # Add current song to history
                if guild_id in now_playing_ref:
                    if guild_id not in history_ref:
                        history_ref[guild_id] = []
                    history_ref[guild_id].append(now_playing_ref[guild_id])
                    # Keep only last 20 songs in history
                    if len(history_ref[guild_id]) > 20:
                        history_ref[guild_id].pop(0)
                
                # Play next song
                queue_cog = bot_ref.get_cog('MusicQueue')
                if queue_cog:
                    bot_ref.loop.create_task(queue_cog.play_next(guild_id))
            
            # Update now playing
            self.now_playing[guild_id] = (source, requester)
            
            # Play the song
            guild.voice_client.play(audio_source, after=after_playing)
            
            # Send now playing message
            try:
                # Find the first text channel the bot can send messages to
                channel = None
                for text_channel in guild.text_channels:
                    if text_channel.permissions_for(guild.me).send_messages:
                        channel = text_channel
                        break
                
                if channel:
                    # Use the proper title from the audio source
                    display_title = getattr(audio_source, 'title', source.title)
                    uploader_text = f" by *{getattr(audio_source, 'uploader', source.uploader or 'Unknown')}*" if getattr(audio_source, 'uploader', source.uploader) else ""
                    
                    embed = nextcord.Embed(
                        title="🎵 Now Playing",
                        description=f"**{display_title}**{uploader_text}",
                        color=nextcord.Color.green()
                    )
                    if hasattr(audio_source, 'thumbnail') and audio_source.thumbnail:
                        embed.set_thumbnail(url=audio_source.thumbnail)
                    elif hasattr(source, 'thumbnail') and source.thumbnail:
                        embed.set_thumbnail(url=source.thumbnail)
                    
                    embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)
                    
                    # Show queue length
                    queue_length = len(self.get_queue(guild_id))
                    if queue_length > 0:
                        embed.add_field(name="Up Next", value=f"{queue_length} songs in queue", inline=True)
                    
                    await channel.send(embed=embed)
            except Exception as e:
                logging.warning(f"Could not send now playing message: {e}")
                
        except Exception as e:
            logging.error(f"Error playing next song: {e}")
            # Try to play the next song in queue
            self.bot.loop.create_task(self.play_next(guild_id))

    def get_now_playing(self, guild_id: int) -> Optional[Tuple]:
        """Get the currently playing song"""
        return self.now_playing.get(guild_id)
    
    def get_history(self, guild_id: int) -> List[Tuple]:
        """Get the song history for a guild"""
        return self.history.get(guild_id, [])
    
    def add_to_now_playing(self, guild_id: int, source, requester):
        """Add current song to now playing (for first song)"""
        self.now_playing[guild_id] = (source, requester)

    @commands.command(name='queue', aliases=['q', 'list'])
    async def show_queue(self, ctx):
        """Show the music queue with interactive controls"""
        view = QueueView(self, ctx.guild.id)
        embed = view.get_queue_embed()
        message = await ctx.send(embed=embed, view=view)
        view.message = message  # Store message reference for timeout handling

    @commands.command(name='remove', aliases=['rm'])
    async def remove_song(self, ctx, index: int):
        """Remove a song from the queue by its number"""
        # Check permissions
        if not ctx.author.guild_permissions.manage_messages:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to remove songs from the queue!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Convert to 0-based index
        index -= 1
        
        if self.remove_from_queue(ctx.guild.id, index):
            embed = nextcord.Embed(
                description=f"✅ Removed song #{index + 1} from the queue",
                color=nextcord.Color.green()
            )
        else:
            embed = nextcord.Embed(
                description="❌ Invalid song number! Use `.queue` to see song numbers.",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='move')
    async def move_song(self, ctx, from_pos: int, to_pos: int):
        """Move a song from one position to another in the queue"""
        # Check permissions
        if not ctx.author.guild_permissions.manage_messages:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to move songs in the queue!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Convert to 0-based indices
        from_pos -= 1
        to_pos -= 1
        
        if self.move_song(ctx.guild.id, from_pos, to_pos):
            embed = nextcord.Embed(
                description=f"✅ Moved song from position #{from_pos + 1} to #{to_pos + 1}",
                color=nextcord.Color.green()
            )
        else:
            embed = nextcord.Embed(
                description="❌ Invalid position numbers! Use `.queue` to see song positions.",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='shuffle')
    async def shuffle(self, ctx):
        """Shuffle the music queue"""
        # Check permissions
        if not ctx.author.guild_permissions.manage_messages:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to shuffle the queue!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        if self.shuffle_queue(ctx.guild.id):
            embed = nextcord.Embed(
                description="🔀 Queue shuffled successfully!",
                color=nextcord.Color.green()
            )
        else:
            embed = nextcord.Embed(
                description="❌ Queue is empty or has only one song!",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='clear')
    async def clear(self, ctx):
        """Clear the music queue"""
        # Check permissions
        if not ctx.author.guild_permissions.manage_messages:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to clear the queue!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        queue_length = len(self.get_queue(ctx.guild.id))
        
        if queue_length == 0:
            embed = nextcord.Embed(
                description="❌ Queue is already empty!",
                color=nextcord.Color.red()
            )
        else:
            self.clear_queue(ctx.guild.id)
            embed = nextcord.Embed(
                description=f"🗑️ Cleared {queue_length} songs from the queue",
                color=nextcord.Color.green()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='nowplaying', aliases=['np', 'current'])
    async def now_playing(self, ctx):
        """Show information about the currently playing song"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get current song info from now playing state first
        now_playing_info = self.get_now_playing(ctx.guild.id)
        
        if now_playing_info:
            source, requester = now_playing_info
            embed = nextcord.Embed(
                title="🎵 Now Playing",
                description=f"**{getattr(source, 'title', 'Unknown')}**",
                color=nextcord.Color.green()
            )
            
            if hasattr(source, 'thumbnail') and source.thumbnail:
                embed.set_thumbnail(url=source.thumbnail)
            
            if hasattr(source, 'duration') and source.duration:
                embed.add_field(
                    name="Duration", 
                    value=f"{source.duration // 60}:{source.duration % 60:02d}", 
                    inline=True
                )
            
            if hasattr(source, 'uploader') and source.uploader:
                embed.add_field(name="Uploader", value=source.uploader, inline=True)
            
            embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)
            
        else:
            # Fallback to voice client source
            if hasattr(ctx.voice_client.source, 'title'):
                source = ctx.voice_client.source
                embed = nextcord.Embed(
                    title="🎵 Now Playing",
                    description=f"**{getattr(source, 'title', 'Unknown')}**",
                    color=nextcord.Color.green()
                )
                
                if hasattr(source, 'thumbnail') and source.thumbnail:
                    embed.set_thumbnail(url=source.thumbnail)
                
                if hasattr(source, 'duration') and source.duration:
                    embed.add_field(
                        name="Duration", 
                        value=f"{source.duration // 60}:{source.duration % 60:02d}", 
                        inline=True
                    )
                
                if hasattr(source, 'uploader') and source.uploader:
                    embed.add_field(name="Uploader", value=source.uploader, inline=True)
                
            else:
                embed = nextcord.Embed(
                    title="🎵 Now Playing",
                    description="Currently playing music",
                    color=nextcord.Color.green()
                )
        
        # Show queue length
        queue_length = len(self.get_queue(ctx.guild.id))
        if queue_length > 0:
            embed.add_field(name="Up Next", value=f"{queue_length} songs in queue", inline=True)
        
        await ctx.send(embed=embed)

    @commands.command(name='next', aliases=['n'])
    async def next_song(self, ctx):
        """Skip to the next song in the queue"""
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
        
        queue_length = len(self.get_queue(ctx.guild.id))
        if queue_length == 0:
            embed = nextcord.Embed(
                description="❌ No songs in queue to skip to!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Skip current song
        ctx.voice_client.stop()
        
        embed = nextcord.Embed(
            description="⏭️ Skipped to next song!",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)
    
    @commands.command(name='previous', aliases=['prev', 'back'])
    async def previous_song(self, ctx):
        """Play the previous song from history"""
        if not ctx.voice_client:
            embed = nextcord.Embed(
                description="❌ I'm not connected to any voice channel!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        history = self.get_history(ctx.guild.id)
        if not history:
            embed = nextcord.Embed(
                description="❌ No previous songs in history!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get the last song from history
        previous_song, previous_requester = history[-1]
        
        # Remove it from history
        self.history[ctx.guild.id].pop()
        
        # Add current song to front of queue if something is playing
        if ctx.voice_client.is_playing() and ctx.guild.id in self.now_playing:
            current_song, current_requester = self.now_playing[ctx.guild.id]
            if ctx.guild.id not in self.queues:
                self.queues[ctx.guild.id] = deque()
            self.queues[ctx.guild.id].appendleft((current_song, current_requester))
        
        # Add previous song to front of queue
        if ctx.guild.id not in self.queues:
            self.queues[ctx.guild.id] = deque()
        self.queues[ctx.guild.id].appendleft((previous_song, previous_requester))
        
        # Stop current song to trigger playing previous
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        else:
            # If nothing is playing, start the previous song
            await self.play_next(ctx.guild.id)
        
        embed = nextcord.Embed(
            description=f"⏮️ Playing previous song: **{getattr(previous_song, 'title', 'Unknown')}**",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

async def setup(bot):
    bot.add_cog(MusicQueue(bot))
