# Performance monitoring command for admins
import nextcord
from nextcord.ext import commands
import time
import datetime
import psutil
import asyncio
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from utils.command_tracker import usage_tracker
from cogs.logging.logger import CogLogger

class Performance(commands.Cog):
    """Performance monitoring and diagnostics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
    
    @commands.command(name="health", aliases=["status", "perf"])
    @commands.is_owner()
    async def health_check(self, ctx):
        """Comprehensive bot health check"""
        embed = nextcord.Embed(
            title="🏥 Bot Health Report",
            color=nextcord.Color.blue(),
            timestamp=datetime.datetime.now()
        )
        
        # Bot metrics
        uptime = time.time() - self.bot.start_time
        uptime_str = f"{int(uptime // 3600)}h {int((uptime % 3600) // 60)}m {int(uptime % 60)}s"
        
        embed.add_field(
            name="🤖 Bot Status",
            value=f"**Uptime:** {uptime_str}\n"
                  f"**Latency:** {round(self.bot.latency * 1000, 2)}ms\n"
                  f"**Guilds:** {len(self.bot.guilds)}\n"
                  f"**Users:** {sum(g.member_count or 0 for g in self.bot.guilds):,}\n"
                  f"**Shards:** {self.bot.shard_count}",
            inline=False
        )
        
        # System metrics
        try:
            process = psutil.Process()
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            embed.add_field(
                name="💻 System Resources",
                value=f"**CPU Usage:** {cpu_percent:.1f}%\n"
                      f"**Memory:** {memory_mb:.1f} MB\n"
                      f"**Threads:** {process.num_threads()}",
                inline=True
            )
        except Exception as e:
            embed.add_field(
                name="💻 System Resources",
                value=f"Error getting metrics: {e}",
                inline=True
            )
        
        # Database health
        try:
            db_health = await db.health_check()
            
            status_emoji = "✅" if db_health["connection"] else "❌"
            status_color = nextcord.Color.green() if db_health["connection"] else nextcord.Color.red()
            embed.color = status_color
            
            db_status = f"{status_emoji} **Status:** {db_health['status'].title()}\n"
            if db_health["latency"]:
                db_status += f"🏓 **Latency:** {db_health['latency']}\n"
            
            if db_health["collections"]:
                collection_counts = []
                for name, count in db_health["collections"].items():
                    collection_counts.append(f"• {name}: {count:,}")
                db_status += f"📊 **Collections:**\n" + "\n".join(collection_counts)
            
            if db_health["errors"]:
                db_status += f"\n⚠️ **Errors:** {len(db_health['errors'])}"
            
            embed.add_field(
                name="🗄️ Database Health",
                value=db_status,
                inline=False
            )
            
        except Exception as e:
            embed.add_field(
                name="🗄️ Database Health",
                value=f"❌ Error checking database: {e}",
                inline=False
            )
        
        # Cog status
        loaded_cogs = len(self.bot.cogs)
        total_commands = len([c for c in self.bot.walk_commands()])
        
        embed.add_field(
            name="⚙️ Components",
            value=f"**Loaded Cogs:** {loaded_cogs}\n"
                  f"**Total Commands:** {total_commands}",
            inline=True
        )
        
        # Scalability metrics
        if hasattr(self.bot, 'scalability_manager') and self.bot.scalability_manager:
            try:
                scalability_metrics = self.bot.scalability_manager.get_metrics()
                
                cache_status = scalability_metrics['cache_status']
                cache_emoji = "✅" if cache_status in ['redis', 'memory'] else "❌"
                cache_display = "Redis" if cache_status == 'redis' else "Memory (No Redis)"
                
                perf_metrics = scalability_metrics['performance']
                cache_hit_rate = 0
                if perf_metrics['cache_hits'] + perf_metrics['cache_misses'] > 0:
                    cache_hit_rate = (perf_metrics['cache_hits'] / 
                                    (perf_metrics['cache_hits'] + perf_metrics['cache_misses'])) * 100
                
                scalability_status = (
                    f"{cache_emoji} **Cache:** {cache_display}\n"
                    f"📊 **Hit Rate:** {cache_hit_rate:.1f}%\n"
                    f"🔄 **Queued Requests:** {perf_metrics['requests_queued']:,}\n"
                    f"⚡ **Background Tasks:** {scalability_metrics['background_tasks']}\n"
                    f"🚫 **Rate Limits Hit:** {perf_metrics['rate_limits_hit']:,}"
                )
                
                if scalability_metrics['rate_limit_status']['global_active']:
                    scalability_status += f"\n⚠️ **Global Rate Limit:** Active"
                
                embed.add_field(
                    name="🚀 Scalability Status",
                    value=scalability_status,
                    inline=True
                )
                
            except Exception as e:
                embed.add_field(
                    name="🚀 Scalability Status", 
                    value=f"❌ Error: {e}",
                    inline=True
                )
        else:
            embed.add_field(
                name="🚀 Scalability Status",
                value="❌ Not initialized",
                inline=True
            )

        embed.set_footer(text="Health check completed")
        await ctx.reply(embed=embed)
    
    @commands.command(name="optimize")
    @commands.is_owner()
    async def optimize_database(self, ctx):
        """Run database optimization"""
        embed = nextcord.Embed(
            title="🔧 Database Optimization",
            description="Running optimization...",
            color=nextcord.Color.orange()
        )
        
        message = await ctx.reply(embed=embed)
        
        try:
            result = await db.optimize_database()
            
            if result["success"]:
                embed.color = nextcord.Color.green()
                embed.description = "✅ Optimization completed successfully!"
                
                results = result["results"]
                embed.add_field(
                    name="Results",
                    value=f"**Indexes Created:** {results['indexes_created']}\n"
                          f"**Collections Optimized:** {results['collections_optimized']}\n"
                          f"**Old Trades Cleaned:** {results['cleanup_results'].get('old_trades', 0)}",
                    inline=False
                )
            else:
                embed.color = nextcord.Color.red()
                embed.description = f"❌ Optimization failed: {result['error']}"
            
        except Exception as e:
            embed.color = nextcord.Color.red()
            embed.description = f"❌ Error during optimization: {e}"
        
        await message.edit(embed=embed)
    
    @commands.command(name="metrics")
    @commands.is_owner()
    async def detailed_metrics(self, ctx):
        """Show detailed performance metrics"""
        embed = nextcord.Embed(
            title="📊 Detailed Metrics",
            color=nextcord.Color.blue()
        )
        
        # Command usage stats
        top_commands = usage_tracker.get_top_commands(5)
        if top_commands:
            command_stats = []
            for cmd in top_commands:
                error_rate = f"{cmd['error_rate']:.1%}"
                exec_time = f"{cmd['avg_execution_time']:.2f}s" if cmd['avg_execution_time'] > 0 else "N/A"
                command_stats.append(
                    f"**{cmd['command']}**: {cmd['uses']} uses, {cmd['unique_users']} users, {error_rate} errors, {exec_time}"
                )
            
            embed.add_field(
                name="🏆 Top Commands",
                value="\n".join(command_stats),
                inline=False
            )
        
        # Rate limiting stats
        rate_limit_stats = usage_tracker.get_rate_limit_stats()
        if rate_limit_stats:
            rl_info = []
            for endpoint, stats in list(rate_limit_stats.items())[:3]:  # Top 3 rate limited endpoints
                rl_info.append(f"**{endpoint}**: {stats['recent_hits']} hits (24h), {stats['avg_retry_after']:.1f}s avg wait")
            
            if rl_info:
                embed.add_field(
                    name="⚠️ Rate Limiting",
                    value="\n".join(rl_info),
                    inline=False
                )
        
        # Guild distribution
        guild_sizes = [g.member_count for g in self.bot.guilds if g.member_count]
        if guild_sizes:
            avg_guild_size = sum(guild_sizes) / len(guild_sizes)
            max_guild_size = max(guild_sizes)
            
            embed.add_field(
                name="📈 Guild Statistics",
                value=f"**Average Size:** {avg_guild_size:.0f}\n"
                      f"**Largest Guild:** {max_guild_size:,}\n"
                      f"**Small Guilds (<50):** {len([s for s in guild_sizes if s < 50])}\n"
                      f"**Large Guilds (>500):** {len([s for s in guild_sizes if s > 500])}",
                inline=False
            )
        
        # Shard info
        if self.bot.shard_count and self.bot.shard_count > 1:
            shard_info = []
            for shard_id, shard in self.bot.shards.items():
                guild_count = len([g for g in self.bot.guilds if (g.id >> 22) % self.bot.shard_count == shard_id])
                latency = round(shard.latency * 1000, 2)
                shard_info.append(f"Shard {shard_id}: {guild_count} guilds, {latency}ms")
            
            embed.add_field(
                name="🔀 Shard Distribution",
                value="\n".join(shard_info[:10]),  # Show max 10 shards
                inline=False
            )
        
        await ctx.reply(embed=embed)
    
    @commands.command(name="cmdanalytics", aliases=["analytics"])
    @commands.is_owner()
    async def command_analytics(self, ctx, command_name: str = None):
        """Show detailed command usage analytics"""
        if command_name:
            # Show specific command stats
            stats = usage_tracker.get_command_stats(command_name)
            if not stats or stats['total_uses'] == 0:
                return await ctx.reply(f"❌ No statistics found for command `{command_name}`")
            
            embed = nextcord.Embed(
                title=f"📊 Command Statistics: {command_name}",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="📈 Usage",
                value=f"**Total Uses:** {stats['total_uses']:,}\n"
                      f"**Unique Users:** {len(stats['users'])}\n"
                      f"**Unique Guilds:** {len(stats['guilds'])}\n"
                      f"**Error Rate:** {stats['errors'] / max(stats['total_uses'], 1):.1%}",
                inline=True
            )
            
            embed.add_field(
                name="⏱️ Performance",
                value=f"**Avg Execution:** {stats['avg_execution_time']:.3f}s\n"
                      f"**Last Used:** {stats['last_used'][:19] if stats['last_used'] else 'Never'}\n"
                      f"**Total Errors:** {stats['errors']}",
                inline=True
            )
            
            # Recent usage
            if stats['hourly_usage']:
                recent_hours = list(stats['hourly_usage'])[-6:]  # Last 6 hours
                hourly_info = [f"Hour {h['hour']}: {h['count']} uses" for h in recent_hours]
                embed.add_field(
                    name="🕐 Recent Activity (Last 6 Hours)",
                    value="\n".join(hourly_info) if hourly_info else "No recent activity",
                    inline=False
                )
        
        else:
            # Show top commands overview
            top_commands = usage_tracker.get_top_commands(15)
            if not top_commands:
                return await ctx.reply("❌ No command usage statistics available yet.")
            
            embed = nextcord.Embed(
                title="📊 Command Usage Statistics",
                color=nextcord.Color.blue()
            )
            
            # Split into groups of 5 for better readability
            for i in range(0, min(15, len(top_commands)), 5):
                commands_group = top_commands[i:i+5]
                field_name = f"🏆 Commands {i+1}-{i+len(commands_group)}"
                
                cmd_lines = []
                for idx, cmd in enumerate(commands_group, i+1):
                    error_indicator = "⚠️" if cmd['error_rate'] > 0.1 else ""
                    cmd_lines.append(f"{idx}. **{cmd['command']}** - {cmd['uses']} uses {error_indicator}")
                
                embed.add_field(
                    name=field_name,
                    value="\n".join(cmd_lines),
                    inline=True
                )
        
        await ctx.reply(embed=embed)
    
    @commands.command(name="scalability", aliases=["scale"])
    @commands.is_owner()
    async def scalability_status(self, ctx):
        """Detailed scalability and performance metrics"""
        if not hasattr(self.bot, 'scalability_manager') or not self.bot.scalability_manager:
            return await ctx.reply("❌ Scalability manager not initialized")
        
        try:
            metrics = self.bot.scalability_manager.get_metrics()
            
            embed = nextcord.Embed(
                title="🚀 Scalability Manager Status",
                color=nextcord.Color.blue(),
                timestamp=datetime.datetime.now()
            )
            
            # Performance metrics
            perf = metrics['performance']
            embed.add_field(
                name="📊 Performance Metrics",
                value=(
                    f"**Requests Queued:** {perf['requests_queued']:,}\n"
                    f"**Cache Hits:** {perf['cache_hits']:,}\n" 
                    f"**Cache Misses:** {perf['cache_misses']:,}\n"
                    f"**Rate Limits Hit:** {perf['rate_limits_hit']:,}"
                ),
                inline=True
            )
            
            # Cache status
            cache_status = metrics['cache_status']
            cache_emoji = "✅" if cache_status in ['redis', 'memory'] else "❌"
            cache_display = "Redis" if cache_status == 'redis' else "Memory (No Redis)"
            
            cache_hit_rate = 0
            total_requests = perf['cache_hits'] + perf['cache_misses']
            if total_requests > 0:
                cache_hit_rate = (perf['cache_hits'] / total_requests) * 100
            
            embed.add_field(
                name="💾 Cache System",
                value=(
                    f"{cache_emoji} **Status:** {cache_display}\n"
                    f"📈 **Hit Rate:** {cache_hit_rate:.1f}%\n"
                    f"📊 **Total Requests:** {total_requests:,}"
                ),
                inline=True
            )
            
            # Rate limiting status
            rate_limit = metrics['rate_limit_status']
            rate_emoji = "⚠️" if rate_limit['global_active'] else "✅"
            
            embed.add_field(
                name="🚫 Rate Limiting",
                value=(
                    f"{rate_emoji} **Global Limit:** {'Active' if rate_limit['global_active'] else 'Normal'}\n"
                    f"🔄 **Queued Requests:** {rate_limit['queued_requests']}\n"
                    f"📈 **Total Hits:** {perf['rate_limits_hit']:,}"
                ),
                inline=True
            )
            
            # Background tasks
            task_count = metrics['background_tasks']
            task_stats = metrics['task_statistics']
            
            if task_stats:
                task_info = []
                for name, stats in task_stats.items():
                    status = "✅" if stats['errors'] == 0 else f"⚠️ ({stats['errors']} errors)"
                    task_info.append(f"• **{name}:** {status}")
                    if stats['last_run']:
                        task_info.append(f"  Last: {stats['last_run'][:16]}")
                
                embed.add_field(
                    name=f"⚡ Background Tasks ({task_count})",
                    value="\n".join(task_info) if task_info else "No active tasks",
                    inline=False
                )
            
            embed.set_footer(text="Use .performance for general bot metrics")
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply(f"❌ Error getting scalability metrics: {e}")

async def setup(bot):
    bot.add_cog(Performance(bot))
