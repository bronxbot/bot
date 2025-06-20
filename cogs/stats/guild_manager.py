"""
Guild Manager
Handles guild information and statistics management.
"""

import nextcord
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from utils.db import db
from cogs.logging.logger import CogLogger
from .constants import (
    GUILD_SETTINGS, COLLECTIONS, COLORS, LIMITS
)

logger = CogLogger('GuildManager')

class GuildManager:
    """Manages guild information and statistics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = db
        
        # Guild cache
        self.guild_cache = {}
        self.last_cache_update = 0
        
    async def show_guild_stats(self, ctx):
        """Show comprehensive guild statistics"""
        try:
            embed = nextcord.Embed(
                title="🏰 Guild Statistics",
                color=COLORS['stats']
            )
            
            # Basic guild info
            total_guilds = len(self.bot.guilds)
            total_users = len(self.bot.users)
            
            # Calculate guild size distribution
            small_guilds = len([g for g in self.bot.guilds if g.member_count < 100])
            medium_guilds = len([g for g in self.bot.guilds if 100 <= g.member_count < 1000])
            large_guilds = len([g for g in self.bot.guilds if g.member_count >= 1000])
            
            # Find largest and smallest guilds
            largest_guild = max(self.bot.guilds, key=lambda g: g.member_count, default=None)
            smallest_guild = min(self.bot.guilds, key=lambda g: g.member_count, default=None)
            
            embed.add_field(
                name="📊 Overview",
                value=(
                    f"**Total Guilds:** {total_guilds:,}\n"
                    f"**Total Users:** {total_users:,}\n"
                    f"**Average Members:** {total_users // total_guilds if total_guilds > 0 else 0:,}"
                ),
                inline=True
            )
            
            embed.add_field(
                name="📈 Guild Sizes",
                value=(
                    f"**Small (<100):** {small_guilds}\n"
                    f"**Medium (100-999):** {medium_guilds}\n"
                    f"**Large (1000+):** {large_guilds}"
                ),
                inline=True
            )
            
            if largest_guild and smallest_guild:
                embed.add_field(
                    name="🏆 Extremes",
                    value=(
                        f"**Largest:** {largest_guild.name}\n"
                        f"└ {largest_guild.member_count:,} members\n"
                        f"**Smallest:** {smallest_guild.name}\n"
                        f"└ {smallest_guild.member_count:,} members"
                    ),
                    inline=False
                )
            
            # Recent guild activity
            recent_joins = await self._get_recent_guild_activity()
            if recent_joins:
                embed.add_field(
                    name="📅 Recent Activity (24h)",
                    value=recent_joins,
                    inline=False
                )
            
            embed.set_footer(text=f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing guild stats: {e}")
            await ctx.send("❌ Error retrieving guild statistics")

    async def show_guild_list(self, ctx, page: int = 1):
        """Show paginated list of all guilds"""
        try:
            guilds = sorted(self.bot.guilds, key=lambda g: g.member_count, reverse=True)
            per_page = GUILD_SETTINGS['max_guilds_per_page']
            total_pages = math.ceil(len(guilds) / per_page)
            
            if page < 1 or page > total_pages:
                await ctx.send(f"❌ Invalid page number. Valid range: 1-{total_pages}")
                return
            
            start_idx = (page - 1) * per_page
            end_idx = start_idx + per_page
            page_guilds = guilds[start_idx:end_idx]
            
            embed = nextcord.Embed(
                title=f"🏰 Guild List (Page {page}/{total_pages})",
                description=f"Showing {len(page_guilds)} of {len(guilds)} guilds",
                color=COLORS['info']
            )
            
            for i, guild in enumerate(page_guilds, start=start_idx + 1):
                # Get guild creation date
                created_ago = (datetime.now() - guild.created_at.replace(tzinfo=None)).days
                
                # Get bot join date if available
                bot_member = guild.get_member(self.bot.user.id)
                joined_ago = "Unknown"
                if bot_member and bot_member.joined_at:
                    joined_ago = f"{(datetime.now() - bot_member.joined_at.replace(tzinfo=None)).days}d ago"
                
                embed.add_field(
                    name=f"{i}. {guild.name}",
                    value=(
                        f"**ID:** {guild.id}\n"
                        f"**Members:** {guild.member_count:,}\n"
                        f"**Created:** {created_ago}d ago\n"
                        f"**Joined:** {joined_ago}"
                    ),
                    inline=True
                )
            
            # Add navigation info
            if total_pages > 1:
                embed.set_footer(text=f"Use 'guildlist {page+1}' for next page")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing guild list: {e}")
            await ctx.send("❌ Error retrieving guild list")

    async def show_guild_info(self, ctx, guild_query: str):
        """Show detailed information about a specific guild"""
        try:
            # Find guild by ID or name
            guild = None
            
            # Try to find by ID first
            if guild_query.isdigit():
                guild = self.bot.get_guild(int(guild_query))
            
            # If not found, search by name
            if not guild:
                for g in self.bot.guilds:
                    if guild_query.lower() in g.name.lower():
                        guild = g
                        break
            
            if not guild:
                await ctx.send(f"❌ Guild not found: `{guild_query}`")
                return
            
            embed = nextcord.Embed(
                title=f"🏰 {guild.name}",
                color=COLORS['info']
            )
            
            if guild.icon:
                embed.set_thumbnail(url=guild.icon.url)
            
            # Basic info
            embed.add_field(
                name="ℹ️ Basic Info",
                value=(
                    f"**ID:** {guild.id}\n"
                    f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                    f"**Created:** {guild.created_at.strftime('%Y-%m-%d')}\n"
                    f"**Region:** {getattr(guild, 'region', 'Unknown')}"
                ),
                inline=True
            )
            
            # Member info
            embed.add_field(
                name="👥 Members",
                value=(
                    f"**Total:** {guild.member_count:,}\n"
                    f"**Humans:** {len([m for m in guild.members if not m.bot]):,}\n"
                    f"**Bots:** {len([m for m in guild.members if m.bot]):,}\n"
                    f"**Online:** {len([m for m in guild.members if m.status != nextcord.Status.offline]):,}"
                ),
                inline=True
            )
            
            # Channel info
            text_channels = len(guild.text_channels)
            voice_channels = len(guild.voice_channels)
            categories = len(guild.categories)
            
            embed.add_field(
                name="📺 Channels",
                value=(
                    f"**Text:** {text_channels}\n"
                    f"**Voice:** {voice_channels}\n"
                    f"**Categories:** {categories}\n"
                    f"**Total:** {text_channels + voice_channels}"
                ),
                inline=True
            )
            
            # Role info
            embed.add_field(
                name="🎭 Roles",
                value=(
                    f"**Total:** {len(guild.roles)}\n"
                    f"**Hoisted:** {len([r for r in guild.roles if r.hoist])}\n"
                    f"**Mentionable:** {len([r for r in guild.roles if r.mentionable])}"
                ),
                inline=True
            )
            
            # Features and boosts
            embed.add_field(
                name="✨ Features",
                value=(
                    f"**Boost Level:** {guild.premium_tier}\n"
                    f"**Boost Count:** {guild.premium_subscription_count or 0}\n"
                    f"**Features:** {len(guild.features)}"
                ),
                inline=True
            )
            
            # Bot join info
            bot_member = guild.get_member(self.bot.user.id)
            if bot_member and bot_member.joined_at:
                joined_date = bot_member.joined_at.strftime('%Y-%m-%d')
                days_ago = (datetime.now() - bot_member.joined_at.replace(tzinfo=None)).days
                
                embed.add_field(
                    name="🤖 Bot Info",
                    value=(
                        f"**Joined:** {joined_date}\n"
                        f"**Days Ago:** {days_ago}\n"
                        f"**Permissions:** {len([p for p, v in bot_member.guild_permissions if v])}"
                    ),
                    inline=True
                )
            
            # Large guild warning
            if guild.member_count > 10000:
                embed.add_field(
                    name="⚠️ Large Guild",
                    value="This is a large guild which may impact bot performance",
                    inline=False
                )
            
            embed.set_footer(text=f"Requested by {ctx.author}")
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error showing guild info: {e}")
            await ctx.send("❌ Error retrieving guild information")

    async def get_guild_summary(self) -> Dict:
        """Get summary of guild statistics for API"""
        try:
            guilds = self.bot.guilds
            
            return {
                'total_guilds': len(guilds),
                'total_users': len(self.bot.users),
                'average_members': len(self.bot.users) // len(guilds) if guilds else 0,
                'guild_sizes': {
                    'small': len([g for g in guilds if g.member_count < 100]),
                    'medium': len([g for g in guilds if 100 <= g.member_count < 1000]),
                    'large': len([g for g in guilds if g.member_count >= 1000])
                },
                'largest_guild': {
                    'name': max(guilds, key=lambda g: g.member_count).name if guilds else None,
                    'members': max(guilds, key=lambda g: g.member_count).member_count if guilds else 0
                },
                'guild_list': [
                    {
                        'id': str(g.id),
                        'name': g.name,
                        'members': g.member_count,
                        'created': g.created_at.isoformat()
                    } for g in guilds[:50]  # Limit to prevent large payloads
                ],
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error getting guild summary: {e}")
            return {
                'total_guilds': 0,
                'total_users': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

    async def _get_recent_guild_activity(self) -> str:
        """Get recent guild join/leave activity"""
        try:
            # This would ideally be stored in database
            # For now, return a placeholder
            return "Activity tracking not yet implemented"
            
        except Exception as e:
            logger.error(f"Error getting recent guild activity: {e}")
            return "Error retrieving activity"

    async def update_guild_cache(self):
        """Update the guild information cache"""
        try:
            current_time = datetime.now()
            cache_duration = timedelta(minutes=GUILD_SETTINGS['cache_duration_minutes'])
            
            if (current_time - datetime.fromtimestamp(self.last_cache_update)) < cache_duration:
                return  # Cache still valid
            
            # Update cache with current guild data
            self.guild_cache = {
                'guilds': [
                    {
                        'id': g.id,
                        'name': g.name,
                        'member_count': g.member_count,
                        'created_at': g.created_at.isoformat(),
                        'features': list(g.features)
                    } for g in self.bot.guilds
                ],
                'updated_at': current_time.isoformat()
            }
            
            self.last_cache_update = current_time.timestamp()
            logger.debug("Guild cache updated")
            
        except Exception as e:
            logger.error(f"Error updating guild cache: {e}")

    def get_cached_guild_data(self) -> Optional[Dict]:
        """Get cached guild data if available"""
        if not self.guild_cache:
            return None
        
        # Check if cache is still valid
        cache_age = datetime.now() - datetime.fromisoformat(self.guild_cache['updated_at'])
        if cache_age.total_seconds() > (GUILD_SETTINGS['cache_duration_minutes'] * 60):
            return None
        
        return self.guild_cache
