"""
System Administration Module
Admin functions for system maintenance and management.
"""

import nextcord
from nextcord.ext import commands
import asyncio
import traceback
from typing import Dict, List, Optional, Any, Tuple
from utils.db import AsyncDatabase
from .constants import ERROR_MESSAGES, SUCCESS_MESSAGES

db = AsyncDatabase.get_instance()

class SystemAdmin:
    """Manages system administration functions"""
    
    def __init__(self, bot):
        self.bot = bot
    
    async def clear_application_commands(self, guild_id: Optional[int] = None) -> Tuple[bool, str]:
        """Clear application commands for a guild or globally"""
        try:
            if guild_id:
                # Clear for specific guild
                guild = self.bot.get_guild(guild_id)
                if guild:
                    await guild.me.edit(nick=None)  # Reset nickname if needed
                    self.bot.tree.clear_commands(guild=guild)
                    await self.bot.tree.sync(guild=guild)
                    return True, f"✅ Commands cleared for guild {guild.name}"
                else:
                    return False, "❌ Guild not found"
            else:
                # Clear globally
                self.bot.tree.clear_commands()
                await self.bot.tree.sync()
                return True, SUCCESS_MESSAGES["commands_cleared"]
                
        except Exception as e:
            print(f"Error clearing commands: {e}")
            return False, f"❌ Error clearing commands: {str(e)}"
    
    async def get_bot_stats(self) -> Dict[str, Any]:
        """Get comprehensive bot statistics"""
        try:
            # Basic bot info
            guild_count = len(self.bot.guilds)
            user_count = len(set(self.bot.get_all_members()))
            
            # Memory usage
            import psutil
            process = psutil.Process()
            memory_usage = process.memory_info().rss / 1024 / 1024  # MB
            cpu_usage = process.cpu_percent()
            
            # Database stats
            db_stats = await db.get_database_stats()
            
            # Command usage stats
            command_stats = await db.get_command_usage_stats()
            
            return {
                "guilds": guild_count,
                "users": user_count,
                "memory_mb": round(memory_usage, 2),
                "cpu_percent": cpu_usage,
                "uptime_seconds": getattr(self.bot, 'uptime_seconds', 0),
                "database_stats": db_stats,
                "command_stats": command_stats,
                "shard_count": getattr(self.bot, 'shard_count', 1),
                "latency_ms": round(self.bot.latency * 1000, 2)
            }
            
        except Exception as e:
            print(f"Error getting bot stats: {e}")
            return {}
    
    async def perform_database_maintenance(self) -> Tuple[bool, List[str]]:
        """Perform database maintenance tasks"""
        maintenance_log = []
        
        try:
            # Clean up expired data
            expired_count = await db.cleanup_expired_data()
            if expired_count > 0:
                maintenance_log.append(f"Cleaned up {expired_count} expired records")
            
            # Optimize database
            await db.optimize_database()
            maintenance_log.append("Database optimization completed")
            
            # Update statistics
            await db.update_database_statistics()
            maintenance_log.append("Database statistics updated")
            
            # Vacuum/compress if supported
            if hasattr(db, 'vacuum_database'):
                await db.vacuum_database()
                maintenance_log.append("Database vacuum completed")
            
            return True, maintenance_log
            
        except Exception as e:
            print(f"Error during database maintenance: {e}")
            return False, [f"Maintenance error: {str(e)}"]
    
    async def backup_guild_data(self, guild_id: int) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Create a backup of guild data"""
        try:
            backup_data = {
                "guild_id": guild_id,
                "backup_timestamp": nextcord.utils.utcnow().isoformat(),
                "user_data": await db.get_all_guild_user_data(guild_id),
                "guild_settings": await db.get_guild_settings(guild_id),
                "shop_data": await db.get_guild_shop_data(guild_id),
                "moderation_data": await db.get_guild_moderation_data(guild_id)
            }
            
            # Store backup
            backup_id = await db.store_guild_backup(guild_id, backup_data)
            backup_data["backup_id"] = backup_id
            
            return True, backup_data
            
        except Exception as e:
            print(f"Error creating guild backup: {e}")
            return False, None
    
    async def restore_guild_data(self, guild_id: int, backup_id: str) -> Tuple[bool, str]:
        """Restore guild data from backup"""
        try:
            backup_data = await db.get_guild_backup(guild_id, backup_id)
            
            if not backup_data:
                return False, "❌ Backup not found"
            
            # Restore user data
            if "user_data" in backup_data:
                await db.restore_guild_user_data(guild_id, backup_data["user_data"])
            
            # Restore guild settings
            if "guild_settings" in backup_data:
                await db.restore_guild_settings(guild_id, backup_data["guild_settings"])
            
            # Restore shop data
            if "shop_data" in backup_data:
                await db.restore_guild_shop_data(guild_id, backup_data["shop_data"])
            
            # Restore moderation data
            if "moderation_data" in backup_data:
                await db.restore_guild_moderation_data(guild_id, backup_data["moderation_data"])
            
            return True, f"✅ Guild data restored from backup {backup_id}"
            
        except Exception as e:
            print(f"Error restoring guild data: {e}")
            return False, f"❌ Error restoring data: {str(e)}"
    
    async def get_error_logs(self, limit: int = 50, severity: str = "all") -> List[Dict[str, Any]]:
        """Get recent error logs from the bot"""
        try:
            return await db.get_error_logs(limit, severity)
        except Exception as e:
            print(f"Error getting error logs: {e}")
            return []
    
    async def analyze_performance(self, hours: int = 24) -> Dict[str, Any]:
        """Analyze bot performance over a time period"""
        try:
            # Get performance metrics
            metrics = await db.get_performance_metrics(hours)
            
            # Calculate averages and trends
            avg_response_time = sum(m.get("response_time", 0) for m in metrics) / len(metrics) if metrics else 0
            avg_memory_usage = sum(m.get("memory_usage", 0) for m in metrics) / len(metrics) if metrics else 0
            
            # Get command failure rate
            command_stats = await db.get_command_stats(hours)
            total_commands = sum(command_stats.values())
            failed_commands = command_stats.get("failed", 0)
            failure_rate = (failed_commands / total_commands * 100) if total_commands > 0 else 0
            
            return {
                "time_period_hours": hours,
                "average_response_time_ms": round(avg_response_time, 2),
                "average_memory_usage_mb": round(avg_memory_usage, 2),
                "total_commands": total_commands,
                "failure_rate_percent": round(failure_rate, 2),
                "performance_score": self._calculate_performance_score(avg_response_time, failure_rate)
            }
            
        except Exception as e:
            print(f"Error analyzing performance: {e}")
            return {}
    
    def _calculate_performance_score(self, avg_response_time: float, failure_rate: float) -> str:
        """Calculate overall performance score"""
        if avg_response_time < 100 and failure_rate < 1:
            return "Excellent"
        elif avg_response_time < 250 and failure_rate < 3:
            return "Good"
        elif avg_response_time < 500 and failure_rate < 5:
            return "Fair"
        else:
            return "Poor"
    
    async def restart_bot_modules(self, modules: List[str]) -> Tuple[bool, List[str]]:
        """Restart specific bot modules/cogs"""
        results = []
        
        try:
            for module in modules:
                try:
                    # Unload the cog
                    if module in self.bot.cogs:
                        await self.bot.unload_extension(f"cogs.{module}")
                        results.append(f"✅ Unloaded {module}")
                    
                    # Reload the cog
                    await self.bot.load_extension(f"cogs.{module}")
                    results.append(f"✅ Reloaded {module}")
                    
                except Exception as e:
                    results.append(f"❌ Error with {module}: {str(e)}")
            
            return True, results
            
        except Exception as e:
            print(f"Error restarting modules: {e}")
            return False, [f"❌ Module restart error: {str(e)}"]
    
    async def update_bot_status(self, activity_type: str, activity_name: str) -> Tuple[bool, str]:
        """Update bot's activity status"""
        try:
            activity_types = {
                "playing": nextcord.ActivityType.playing,
                "listening": nextcord.ActivityType.listening,
                "watching": nextcord.ActivityType.watching,
                "competing": nextcord.ActivityType.competing
            }
            
            if activity_type.lower() not in activity_types:
                return False, f"❌ Invalid activity type. Valid types: {', '.join(activity_types.keys())}"
            
            activity = nextcord.Activity(
                type=activity_types[activity_type.lower()],
                name=activity_name
            )
            
            await self.bot.change_presence(activity=activity)
            
            return True, f"✅ Status updated: {activity_type.title()} {activity_name}"
            
        except Exception as e:
            print(f"Error updating status: {e}")
            return False, f"❌ Error updating status: {str(e)}"
    
    async def get_guild_diagnostics(self, guild_id: int) -> Dict[str, Any]:
        """Get diagnostic information about a specific guild"""
        try:
            guild = self.bot.get_guild(guild_id)
            
            if not guild:
                return {"error": "Guild not found"}
            
            # Basic guild info
            diagnostics = {
                "name": guild.name,
                "id": guild.id,
                "member_count": guild.member_count,
                "channel_count": len(guild.channels),
                "role_count": len(guild.roles),
                "emoji_count": len(guild.emojis),
                "boost_level": guild.premium_tier,
                "boost_count": guild.premium_subscription_count,
                "bot_permissions": {}
            }
            
            # Check bot permissions
            bot_member = guild.get_member(self.bot.user.id)
            if bot_member:
                perms = bot_member.guild_permissions
                diagnostics["bot_permissions"] = {
                    "administrator": perms.administrator,
                    "manage_guild": perms.manage_guild,
                    "manage_channels": perms.manage_channels,
                    "manage_messages": perms.manage_messages,
                    "send_messages": perms.send_messages,
                    "embed_links": perms.embed_links,
                    "add_reactions": perms.add_reactions,
                    "use_slash_commands": perms.use_application_commands
                }
            
            # Database connectivity test
            try:
                await db.test_guild_connection(guild_id)
                diagnostics["database_status"] = "Connected"
            except:
                diagnostics["database_status"] = "Error"
            
            # Get recent activity
            diagnostics["recent_commands"] = await db.get_recent_guild_commands(guild_id, limit=5)
            
            return diagnostics
            
        except Exception as e:
            print(f"Error getting guild diagnostics: {e}")
            return {"error": str(e)}
