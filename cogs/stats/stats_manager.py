"""
Stats Manager
Handles core statistics collection, storage, and management.
"""

import nextcord
import time
import json
from datetime import datetime, timedelta
from nextcord.utils import utcnow
from typing import Dict, List, Optional

from utils.db import db
from cogs.logging.logger import CogLogger
from .constants import (
    DEFAULT_STATS, COLLECTIONS, RETENTION_SETTINGS, 
    COLORS, LIMITS, TIME_FORMATS
)

logger = CogLogger('StatsManager')

class StatsManager:
    """Manages core statistics collection and storage"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = db
        
        # Initialize stats structure
        self.stats = DEFAULT_STATS.copy()
        self.hourly_stats = {}
        self.daily_stats = {}
        
    async def load_stats_from_mongodb(self):
        """Load statistics from MongoDB"""
        try:
            # Load daily stats
            daily_collection = self.db.db[COLLECTIONS['daily_stats']]
            today = datetime.now().strftime('%Y-%m-%d')
            daily_doc = await daily_collection.find_one({'date': today})
            
            if daily_doc:
                self.stats.update(daily_doc.get('stats', {}))
                logger.info(f"Loaded daily stats for {today}")
            
            # Load recent hourly stats
            hourly_collection = self.db.db[COLLECTIONS['hourly_stats']]
            cutoff_time = datetime.now() - timedelta(hours=RETENTION_SETTINGS['hourly_stats_hours'])
            
            async for doc in hourly_collection.find({
                'timestamp': {'$gte': cutoff_time}
            }).sort('timestamp', -1).limit(168):  # Last 7 days
                hour_key = doc['timestamp'].strftime('%Y-%m-%d-%H')
                self.hourly_stats[hour_key] = doc['stats']
            
            logger.info("Statistics loaded from MongoDB")
            
        except Exception as e:
            logger.error(f"Error loading stats from MongoDB: {e}")

    async def save_stats_to_mongodb(self):
        """Save current statistics to MongoDB"""
        try:
            now = datetime.now()
            
            # Save daily stats
            daily_collection = self.db.db[COLLECTIONS['daily_stats']]
            today = now.strftime('%Y-%m-%d')
            
            await daily_collection.update_one(
                {'date': today},
                {
                    '$set': {
                        'stats': self.stats,
                        'last_updated': now
                    }
                },
                upsert=True
            )
            
            # Save hourly stats
            hourly_collection = self.db.db[COLLECTIONS['hourly_stats']]
            hour_key = now.strftime('%Y-%m-%d-%H')
            
            await hourly_collection.update_one(
                {'hour': hour_key},
                {
                    '$set': {
                        'timestamp': now,
                        'stats': self.get_current_hour_stats()
                    }
                },
                upsert=True
            )
            
            # Clean up old data
            await self._cleanup_old_stats()
            
            logger.debug("Statistics saved to MongoDB")
            
        except Exception as e:
            logger.error(f"Error saving stats to MongoDB: {e}")

    async def _cleanup_old_stats(self):
        """Clean up old statistics based on retention settings"""
        try:
            now = datetime.now()
            
            # Clean up old daily stats
            daily_cutoff = now - timedelta(days=RETENTION_SETTINGS['daily_stats_days'])
            daily_collection = self.db.db[COLLECTIONS['daily_stats']]
            result = await daily_collection.delete_many({
                'last_updated': {'$lt': daily_cutoff}
            })
            
            # Clean up old hourly stats
            hourly_cutoff = now - timedelta(hours=RETENTION_SETTINGS['hourly_stats_hours'])
            hourly_collection = self.db.db[COLLECTIONS['hourly_stats']]
            result2 = await hourly_collection.delete_many({
                'timestamp': {'$lt': hourly_cutoff}
            })
            
            if result.deleted_count > 0 or result2.deleted_count > 0:
                logger.info(f"Cleaned up {result.deleted_count} daily and {result2.deleted_count} hourly stat records")
                
        except Exception as e:
            logger.error(f"Error cleaning up old stats: {e}")

    def get_current_hour_stats(self) -> Dict:
        """Get statistics for the current hour"""
        return {
            'commands': self.stats.get('total_commands', 0),
            'errors': self.stats.get('errors', 0),
            'unique_users': len(set(self.stats.get('top_users', []))),
            'timestamp': datetime.now()
        }

    async def update_command_stats(self, command_name: str, user_id: int, guild_id: Optional[int] = None,
                                 execution_time: float = 0.0, success: bool = True):
        """Update command statistics"""
        try:
            # Update total commands
            self.stats['total_commands'] += 1
            
            # Update command breakdown
            if command_name not in self.stats['command_breakdown']:
                self.stats['command_breakdown'][command_name] = 0
                self.stats['unique_commands'] += 1
            
            self.stats['command_breakdown'][command_name] += 1
            
            # Update hourly usage
            current_hour = datetime.now().hour
            if len(self.stats['hourly_usage']) > current_hour:
                self.stats['hourly_usage'][current_hour] += 1
            
            # Update daily usage
            current_day = datetime.now().weekday()
            if len(self.stats['daily_usage']) > current_day:
                self.stats['daily_usage'][current_day] += 1
            
            # Update top commands
            self._update_top_list('top_commands', command_name, self.stats['command_breakdown'][command_name])
            
            # Update top users
            self._update_top_list('top_users', str(user_id), 1)
            
            # Update top guilds
            if guild_id:
                self._update_top_list('top_guilds', str(guild_id), 1)
            
            # Update error count
            if not success:
                self.stats['errors'] += 1
            
            # Update last updated timestamp
            self.stats['last_updated'] = datetime.now().isoformat()
            
        except Exception as e:
            logger.error(f"Error updating command stats: {e}")

    def _update_top_list(self, list_name: str, item: str, count: int):
        """Update a top items list"""
        if list_name not in self.stats:
            self.stats[list_name] = []
        
        # Find existing item
        for i, (existing_item, existing_count) in enumerate(self.stats[list_name]):
            if existing_item == item:
                self.stats[list_name][i] = (item, existing_count + count)
                break
        else:
            # Add new item
            self.stats[list_name].append((item, count))
        
        # Sort and limit
        self.stats[list_name].sort(key=lambda x: x[1], reverse=True)
        self.stats[list_name] = self.stats[list_name][:LIMITS['max_top_items']]

    async def reset_daily_stats(self):
        """Reset daily statistics"""
        try:
            # Archive current daily stats
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            daily_collection = self.db.db[COLLECTIONS['daily_stats']]
            
            # Save yesterday's final stats
            await daily_collection.update_one(
                {'date': yesterday},
                {
                    '$set': {
                        'final_stats': self.stats.copy(),
                        'archived': True,
                        'archived_at': datetime.now()
                    }
                },
                upsert=True
            )
            
            # Reset daily counters
            self.stats.update({
                'total_commands': 0,
                'errors': 0,
                'hourly_usage': [0] * 24,
                'command_breakdown': {},
                'top_commands': [],
                'top_users': [],
                'top_guilds': []
            })
            
            logger.info("Daily stats reset completed")
            
        except Exception as e:
            logger.error(f"Error resetting daily stats: {e}")

    async def show_stats_status(self, ctx):
        """Show current statistics status"""
        try:
            embed = nextcord.Embed(
                title="📊 Statistics Status",
                color=COLORS['stats']
            )
            
            # Basic stats
            embed.add_field(
                name="📈 Current Stats",
                value=(
                    f"**Total Commands:** {self.stats.get('total_commands', 0):,}\n"
                    f"**Unique Commands:** {self.stats.get('unique_commands', 0):,}\n"
                    f"**Errors:** {self.stats.get('errors', 0):,}\n"
                    f"**Uptime:** {self._format_uptime()}"
                ),
                inline=False
            )
            
            # Top commands
            top_commands = self.stats.get('top_commands', [])[:5]
            if top_commands:
                commands_text = "\n".join([
                    f"**{cmd}:** {count:,}" for cmd, count in top_commands
                ])
                embed.add_field(
                    name="🏆 Top Commands",
                    value=commands_text,
                    inline=True
                )
            
            # System info
            embed.add_field(
                name="🔧 System Info",
                value=(
                    f"**Guilds:** {len(self.bot.guilds):,}\n"
                    f"**Users:** {len(self.bot.users):,}\n"
                    f"**Last Updated:** {self._format_last_updated()}"
                ),
                inline=True
            )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing stats status: {e}")
            await ctx.send("❌ Error retrieving statistics status")

    async def reset_stats(self, ctx):
        """Reset all statistics with confirmation"""
        try:
            # Confirmation embed
            embed = nextcord.Embed(
                title="⚠️ Reset Statistics",
                description="This will permanently reset ALL statistics. Are you sure?",
                color=COLORS['warning']
            )
            
            message = await ctx.send(embed=embed)
            await message.add_reaction('✅')
            await message.add_reaction('❌')
            
            def check(reaction, user):
                return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == message.id
            
            try:
                reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)
                
                if str(reaction.emoji) == '✅':
                    # Reset stats
                    self.stats = DEFAULT_STATS.copy()
                    await self.save_stats_to_mongodb()
                    
                    embed = nextcord.Embed(
                        title="✅ Statistics Reset",
                        description="All statistics have been reset successfully.",
                        color=COLORS['success']
                    )
                    await message.edit(embed=embed)
                    logger.info(f"Statistics reset by {ctx.author}")
                else:
                    embed = nextcord.Embed(
                        title="❌ Reset Cancelled",
                        description="Statistics reset has been cancelled.",
                        color=COLORS['error']
                    )
                    await message.edit(embed=embed)
                    
            except Exception:
                embed = nextcord.Embed(
                    title="⏰ Reset Timed Out",
                    description="Statistics reset has been cancelled due to timeout.",
                    color=COLORS['error']
                )
                await message.edit(embed=embed)
                
        except Exception as e:
            logger.error(f"Error in reset stats: {e}")
            await ctx.send("❌ Error during statistics reset")

    async def get_stats_summary(self) -> Dict:
        """Get a summary of current statistics"""
        return {
            'total_commands': self.stats.get('total_commands', 0),
            'unique_commands': self.stats.get('unique_commands', 0),
            'errors': self.stats.get('errors', 0),
            'top_commands': self.stats.get('top_commands', [])[:10],
            'guilds': len(self.bot.guilds),
            'users': len(self.bot.users),
            'uptime': self._get_uptime_seconds(),
            'last_updated': self.stats.get('last_updated')
        }

    def _format_uptime(self) -> str:
        """Format uptime for display"""
        if not hasattr(self.bot, 'launch_time'):
            return "Unknown"
        
        uptime = utcnow() - self.bot.launch_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m {seconds}s"

    def _get_uptime_seconds(self) -> int:
        """Get uptime in seconds"""
        if not hasattr(self.bot, 'launch_time'):
            return 0
        return int((utcnow() - self.bot.launch_time).total_seconds())

    def _format_last_updated(self) -> str:
        """Format last updated timestamp"""
        last_updated = self.stats.get('last_updated')
        if not last_updated:
            return "Never"
        
        try:
            if isinstance(last_updated, str):
                last_updated = datetime.fromisoformat(last_updated.replace('Z', '+00:00'))
            
            diff = datetime.now() - last_updated.replace(tzinfo=None)
            
            if diff.total_seconds() < 60:
                return "Just now"
            elif diff.total_seconds() < 3600:
                return f"{int(diff.total_seconds() // 60)} minutes ago"
            else:
                return f"{int(diff.total_seconds() // 3600)} hours ago"
                
        except Exception:
            return "Unknown"
