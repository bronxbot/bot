"""
Stats Cog - Compatibility Shim
This file maintains backwards compatibility by importing from the modular stats system.
The actual implementation is now in /cogs/stats/
"""

# Import the modular Stats cog
from .stats.stats_cog import Stats

# Re-export for backwards compatibility
__all__ = ['Stats']

# For any direct imports that might reference this module
from .stats.constants import *
from .stats.stats_manager import StatsManager
from .stats.performance_manager import PerformanceManager
from .stats.task_manager import TaskManager
from .stats.dashboard_manager import DashboardManager
from .stats.guild_manager import GuildManager
from .stats.command_tracker import CommandTracker

async def setup(bot):
    """Setup function for the cog"""
    bot.add_cog(Stats(bot))
