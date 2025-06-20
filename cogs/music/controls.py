"""
Music Controls module for BronxBot
Handles advanced music controls, loops, autoplay, and user interaction
"""

import nextcord
from nextcord.ext import commands
import asyncio
from typing import Dict, Optional
import random
import logging

class LoopMode:
    """Enum for loop modes"""
    NONE = 0
    SONG = 1
    QUEUE = 2

class MusicControlPanel(nextcord.ui.View):
    """Interactive music control panel"""
    
    def __init__(self, bot, guild_id: int):
        super().__init__(timeout=300)  # 5 minute timeout
        self.bot = bot
        self.guild_id = guild_id
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states based on current player state"""
        guild = self.bot.get_guild(self.guild_id)
        if not guild or not guild.voice_client:
            # Disable all buttons if not connected
            for item in self.children:
                item.disabled = True
            return
        
        voice_client = guild.voice_client
        
        # Update pause/resume button
        if voice_client.is_paused():
            self.pause_resume.label = "▶️ Resume"
            self.pause_resume.style = nextcord.ButtonStyle.success
        else:
            self.pause_resume.label = "⏸️ Pause"
            self.pause_resume.style = nextcord.ButtonStyle.secondary
        
        # Update play/stop states
        is_playing = voice_client.is_playing() or voice_client.is_paused()
        self.pause_resume.disabled = not is_playing
        self.skip.disabled = not is_playing
        self.stop.disabled = not is_playing
        
        # Check queue for skip button
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_length = len(queue_cog.get_queue(self.guild_id))
            # Skip is only useful if there's something in queue or if we can stop current song
            self.skip.disabled = not is_playing
    
    @nextcord.ui.button(label="⏸️ Pause", style=nextcord.ButtonStyle.secondary)
    async def pause_resume(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if not guild or not guild.voice_client:
            await interaction.response.send_message("❌ Not connected to voice!", ephemeral=True)
            return
        
        voice_client = guild.voice_client
        
        if voice_client.is_paused():
            voice_client.resume()
            await interaction.response.send_message("▶️ Music resumed!", ephemeral=True)
        elif voice_client.is_playing():
            voice_client.pause()
            await interaction.response.send_message("⏸️ Music paused!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
        
        self.update_buttons()
        await interaction.edit_original_response(view=self)
    
    @nextcord.ui.button(label="⏭️ Skip", style=nextcord.ButtonStyle.primary)
    async def skip(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        guild = self.bot.get_guild(self.guild_id)
        if not guild or not guild.voice_client:
            await interaction.response.send_message("❌ Not connected to voice!", ephemeral=True)
            return
        
        if not guild.voice_client.is_playing():
            await interaction.response.send_message("❌ Nothing is playing!", ephemeral=True)
            return
        
        guild.voice_client.stop()  # This will trigger the next song
        await interaction.response.send_message("⏭️ Skipped current song!", ephemeral=True)
        
        self.update_buttons()
        await interaction.edit_original_response(view=self)
    
    @nextcord.ui.button(label="⏹️ Stop", style=nextcord.ButtonStyle.danger)
    async def stop(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        # Check permissions
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission to stop music!", ephemeral=True)
            return
        
        guild = self.bot.get_guild(self.guild_id)
        if not guild or not guild.voice_client:
            await interaction.response.send_message("❌ Not connected to voice!", ephemeral=True)
            return
        
        # Stop current song
        if guild.voice_client.is_playing():
            guild.voice_client.stop()
        
        # Clear queue
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_cog.clear_queue(self.guild_id)
        
        await interaction.response.send_message("⏹️ Stopped music and cleared queue!", ephemeral=True)
        
        self.update_buttons()
        await interaction.edit_original_response(view=self)
    
    @nextcord.ui.button(label="📋 Queue", style=nextcord.ButtonStyle.secondary)
    async def show_queue(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        queue_cog = self.bot.get_cog('MusicQueue')
        if not queue_cog:
            await interaction.response.send_message("❌ Queue system not available!", ephemeral=True)
            return
        
        from .queue import QueueView
        view = QueueView(queue_cog, self.guild_id)
        embed = view.get_queue_embed()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    @nextcord.ui.button(label="🔀 Shuffle", style=nextcord.ButtonStyle.secondary)
    async def shuffle(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        # Check permissions
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.response.send_message("❌ You need 'Manage Messages' permission to shuffle!", ephemeral=True)
            return
        
        queue_cog = self.bot.get_cog('MusicQueue')
        if not queue_cog:
            await interaction.response.send_message("❌ Queue system not available!", ephemeral=True)
            return
        
        if queue_cog.shuffle_queue(self.guild_id):
            await interaction.response.send_message("🔀 Queue shuffled!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Queue is empty or has only one song!", ephemeral=True)
    
    async def on_timeout(self):
        """Called when the view times out"""
        for item in self.children:
            item.disabled = True
        
        try:
            await self.message.edit(view=self)
        except:
            pass

class MusicControls(commands.Cog):
    """Advanced music controls and features"""
    
    def __init__(self, bot):
        self.bot = bot
        self.loop_modes: Dict[int, int] = {}  # guild_id -> loop_mode
        self.autoplay_enabled: Dict[int, bool] = {}  # guild_id -> bool
        self.volume_settings: Dict[int, float] = {}  # guild_id -> volume (0.0-1.0)
    
    def get_loop_mode(self, guild_id: int) -> int:
        """Get the loop mode for a guild"""
        return self.loop_modes.get(guild_id, LoopMode.NONE)
    
    def set_loop_mode(self, guild_id: int, mode: int):
        """Set the loop mode for a guild"""
        self.loop_modes[guild_id] = mode
    
    def is_autoplay_enabled(self, guild_id: int) -> bool:
        """Check if autoplay is enabled for a guild"""
        return self.autoplay_enabled.get(guild_id, False)
    
    def set_autoplay(self, guild_id: int, enabled: bool):
        """Set autoplay for a guild"""
        self.autoplay_enabled[guild_id] = enabled

    @commands.command(name='controls', aliases=['panel'])
    async def show_controls(self, ctx):
        """Show interactive music control panel"""
        if not ctx.voice_client:
            embed = nextcord.Embed(
                description="❌ I'm not connected to any voice channel!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        embed = nextcord.Embed(
            title="🎵 Music Control Panel",
            description="Use the buttons below to control music playback",
            color=nextcord.Color.blue()
        )
        
        # Add current status
        if ctx.voice_client.is_playing():
            embed.add_field(name="Status", value="▶️ Playing", inline=True)
        elif ctx.voice_client.is_paused():
            embed.add_field(name="Status", value="⏸️ Paused", inline=True)
        else:
            embed.add_field(name="Status", value="⏹️ Stopped", inline=True)
        
        # Add current song info if available
        if hasattr(ctx.voice_client.source, 'title'):
            embed.add_field(name="Current Song", value=ctx.voice_client.source.title, inline=False)
        
        # Add queue info
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            queue_length = len(queue_cog.get_queue(ctx.guild.id))
            embed.add_field(name="Queue", value=f"{queue_length} songs", inline=True)
        
        # Add loop mode
        loop_mode = self.get_loop_mode(ctx.guild.id)
        loop_text = ["Off", "Song", "Queue"][loop_mode]
        embed.add_field(name="Loop", value=loop_text, inline=True)
        
        view = MusicControlPanel(self.bot, ctx.guild.id)
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    @commands.command(name='loop')
    async def loop_command(self, ctx, mode: str = None):
        """Set loop mode: off, song, queue"""
        if not mode:
            current_mode = self.get_loop_mode(ctx.guild.id)
            mode_text = ["off", "song", "queue"][current_mode]
            embed = nextcord.Embed(
                description=f"🔁 Current loop mode: **{mode_text}**\n\nUse `.loop <off/song/queue>` to change",
                color=nextcord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        mode = mode.lower()
        if mode in ['off', 'none', '0']:
            self.set_loop_mode(ctx.guild.id, LoopMode.NONE)
            embed = nextcord.Embed(
                description="🔁 Loop mode disabled",
                color=nextcord.Color.green()
            )
        elif mode in ['song', 'track', '1']:
            self.set_loop_mode(ctx.guild.id, LoopMode.SONG)
            embed = nextcord.Embed(
                description="🔂 Loop mode: Current song",
                color=nextcord.Color.green()
            )
        elif mode in ['queue', 'all', '2']:
            self.set_loop_mode(ctx.guild.id, LoopMode.QUEUE)
            embed = nextcord.Embed(
                description="🔁 Loop mode: Entire queue",
                color=nextcord.Color.green()
            )
        else:
            embed = nextcord.Embed(
                description="❌ Invalid loop mode! Use: `off`, `song`, or `queue`",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='autoplay')
    async def autoplay_command(self, ctx, enabled: str = None):
        """Toggle autoplay (automatically play related songs when queue is empty)"""
        if not enabled:
            current = self.is_autoplay_enabled(ctx.guild.id)
            status = "enabled" if current else "disabled"
            embed = nextcord.Embed(
                description=f"🤖 Autoplay is currently **{status}**\n\nUse `.autoplay <on/off>` to change",
                color=nextcord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        enabled = enabled.lower()
        if enabled in ['on', 'true', 'yes', 'enable', '1']:
            self.set_autoplay(ctx.guild.id, True)
            embed = nextcord.Embed(
                description="🤖 Autoplay enabled - I'll automatically play related songs when the queue is empty",
                color=nextcord.Color.green()
            )
        elif enabled in ['off', 'false', 'no', 'disable', '0']:
            self.set_autoplay(ctx.guild.id, False)
            embed = nextcord.Embed(
                description="🤖 Autoplay disabled",
                color=nextcord.Color.orange()
            )
        else:
            embed = nextcord.Embed(
                description="❌ Invalid option! Use: `on` or `off`",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='repeat')
    async def repeat_command(self, ctx):
        """Repeat the current song (add it back to the queue)"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get current song info
        source = ctx.voice_client.source
        if not hasattr(source, 'title'):
            embed = nextcord.Embed(
                description="❌ Cannot repeat this song!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Add current song to queue
        queue_cog = self.bot.get_cog('MusicQueue')
        player_cog = self.bot.get_cog('MusicPlayer')
        
        if not queue_cog or not player_cog:
            embed = nextcord.Embed(
                description="❌ Queue or player system not available!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        try:
            # Create a new audio source for the same song
            if hasattr(source, 'url'):
                # This is a simplified version - you might need to recreate the source properly
                queue_cog.add_to_queue(ctx.guild.id, source, ctx.author)
                
                embed = nextcord.Embed(
                    description=f"🔂 Added **{source.title}** back to the queue",
                    color=nextcord.Color.green()
                )
            else:
                embed = nextcord.Embed(
                    description="❌ Cannot repeat this song - no URL available!",
                    color=nextcord.Color.red()
                )
        except Exception as e:
            logging.error(f"Error repeating song: {e}")
            embed = nextcord.Embed(
                description="❌ Failed to add song to queue!",
                color=nextcord.Color.red()
            )
        
        await ctx.send(embed=embed)

    @commands.command(name='skipto')
    async def skip_to(self, ctx, position: int):
        """Skip to a specific position in the queue"""
        # Check permissions
        if not ctx.author.guild_permissions.manage_messages:
            embed = nextcord.Embed(
                description="❌ You need 'Manage Messages' permission to skip to a specific position!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        queue_cog = self.bot.get_cog('MusicQueue')
        if not queue_cog:
            embed = nextcord.Embed(
                description="❌ Queue system not available!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        queue = queue_cog.get_queue(ctx.guild.id)
        
        if position < 1 or position > len(queue):
            embed = nextcord.Embed(
                description=f"❌ Invalid position! Queue has {len(queue)} songs.",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Remove songs before the target position
        for i in range(position - 1):
            queue_cog.get_next_song(ctx.guild.id)
        
        # Skip current song to play the target song
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
        
        embed = nextcord.Embed(
            description=f"⏭️ Skipped to position #{position} in queue",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='replay')
    async def replay_current(self, ctx):
        """Replay the current song from the beginning (alias: restart removed for bot restart priority)"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = nextcord.Embed(
                description="❌ Nothing is currently playing!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Get current song
        source = ctx.voice_client.source
        if not hasattr(source, 'url'):
            embed = nextcord.Embed(
                description="❌ Cannot replay this song!",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        
        # Stop current playback
        ctx.voice_client.stop()
        
        # Add current song to the front of the queue
        queue_cog = self.bot.get_cog('MusicQueue')
        if queue_cog:
            # Insert at the beginning of the queue
            if ctx.guild.id not in queue_cog.queues:
                queue_cog.queues[ctx.guild.id] = []
            queue_cog.queues[ctx.guild.id].appendleft((source, ctx.author))
        
        embed = nextcord.Embed(
            description=f"🔄 Replaying **{getattr(source, 'title', 'current song')}**",
            color=nextcord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name='restart', aliases=['musicrestart'])
    async def restart_music(self, ctx):
        """Restart the current song from the beginning (music command takes priority over bot restart)"""
        # This is just an alias for replay with priority over bot restart
        await self.replay_current(ctx)

async def setup(bot):
    bot.add_cog(MusicControls(bot))
