"""
Stats Cog
Main cog for statistics and monitoring management.
"""

import nextcord
import logging
from datetime import datetime
from nextcord.ext import commands
from typing import Dict, List, Optional

from utils.db import db
from utils.command_tracker import usage_tracker
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

from .constants import DASHBOARD_SETTINGS, COLORS, LIMITS
from .stats_manager import StatsManager
from .performance_manager import PerformanceManager
from .task_manager import TaskManager
from .dashboard_manager import DashboardManager
from .guild_manager import GuildManager
from .command_tracker import CommandTracker

logger = CogLogger('Stats')

class Stats(commands.Cog, ErrorHandler):
    """Statistics and monitoring system for the Discord bot"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.db = db
        
        # Initialize managers
        self.stats_manager = StatsManager(bot)
        self.performance_manager = PerformanceManager(bot)
        self.task_manager = TaskManager(bot)
        self.dashboard_manager = DashboardManager(bot)
        self.guild_manager = GuildManager(bot)
        self.command_tracker = CommandTracker(bot)
        
        # Basic stats tracking
        self.start_time = datetime.now()
        self.command_count = 0
        self.daily_commands = 0
        self.command_types = {}
        self.last_stats_update = 0
        
        # Start background tasks
        self.task_manager.start_all_tasks()
        
        logger.info("Stats cog initialized")

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        # Stop all background tasks
        self.task_manager.stop_all_tasks()
        
        # Save stats before unloading
        self.bot.loop.create_task(self.stats_manager.save_stats_to_mongodb())
        logger.info("Stats cog unloaded")

    @commands.command(name='statstatus', aliases=['statsinfo'])
    @commands.is_owner()
    async def stats_status(self, ctx):
        """Show current statistics status and information"""
        await self.stats_manager.show_stats_status(ctx)

    @commands.command(name='forcestatsupdate', aliases=['updatestats'])
    @commands.is_owner()
    async def force_stats_update(self, ctx):
        """Force an immediate stats update to the dashboard"""
        await self.dashboard_manager.force_stats_update(ctx)

    @commands.command(name='testperformance', aliases=['perftest'])
    @commands.is_owner()
    async def test_performance_update(self, ctx):
        """Test the performance monitoring system"""
        await self.performance_manager.test_performance_update(ctx)

    @commands.command(name='resetstats')
    @commands.is_owner()
    async def reset_stats(self, ctx):
        """Reset all statistics (requires confirmation)"""
        await self.stats_manager.reset_stats(ctx)

    @commands.command(name='guildstats', aliases=['serverstats'])
    @commands.is_owner()
    async def guild_stats(self, ctx):
        """Show comprehensive guild statistics"""
        await self.guild_manager.show_guild_stats(ctx)

    @commands.command(name='guildlist', aliases=['serverlist'])
    @commands.is_owner()
    async def guild_list(self, ctx, page: int = 1):
        """List all guilds the bot is in"""
        await self.guild_manager.show_guild_list(ctx, page)

    @commands.command(name='guildinfo', aliases=['server'])
    @commands.is_owner()
    async def guild_info(self, ctx, *, guild_query: str):
        """Get detailed information about a specific guild"""
        await self.guild_manager.show_guild_info(ctx, guild_query)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        """Track command completion"""
        await self.command_tracker.track_command_completion(ctx)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Track command errors"""
        await self.command_tracker.track_command_error(ctx, error)

    # Utility methods for other cogs to use
    async def get_stats_summary(self) -> Dict:
        """Get a summary of current statistics"""
        return await self.stats_manager.get_stats_summary()

    async def send_realtime_command_update(self, command_name: str, user_id: int, guild_id: Optional[int] = None, 
                                          execution_time: float = 0.0, success: bool = True):
        """Send real-time command update to dashboard"""
        await self.dashboard_manager.send_realtime_command_update(
            command_name, user_id, guild_id, execution_time, success
        )

    async def cog_command_error(self, ctx, error):
        """Handle cog-specific errors"""
        await self.handle_error(ctx, error, "stats")

async def setup(bot):
    bot.add_cog(Stats(bot))
