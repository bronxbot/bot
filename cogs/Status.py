import nextcord
from nextcord.ext import commands
import datetime
from cogs.logging.logger import CogLogger
from cogs.Help import HelpPaginator

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.shard_stats = {}
        self.update_shard_stats()

    def update_shard_stats(self):
        """Update stats for all shards."""
        shard_count = self.bot.shard_count or 1
        for shard_id in range(shard_count):
            guilds = [g for g in self.bot.guilds if getattr(g, "shard_id", 0) == shard_id]
            users = sum(g.member_count or 0 for g in guilds)
            latency = 0
            if hasattr(self.bot, "latencies") and len(self.bot.latencies) > shard_id:
                latency = self.bot.latencies[shard_id][1] * 1000
            else:
                latency = self.bot.latency * 1000

            if shard_id not in self.shard_stats:
                self.shard_stats[shard_id] = {
                    'start_time': datetime.datetime.now(),
                    'last_seen': datetime.datetime.now(),
                    'status': 'online'
                }

            self.shard_stats[shard_id].update({
                'guild_count': len(guilds),
                'user_count': users,
                'latency': latency,
                'last_seen': datetime.datetime.now()
            })

    @commands.command(name="shards", aliases=["status"])
    async def shards(self, ctx):
        """View bot shard status."""
        self.update_shard_stats()

        pages = []
        overview = nextcord.Embed(
            title="🔋 Shard Status",
            color=getattr(ctx.author, "color", nextcord.Color.blurple())
        )

        total_guilds = sum(s['guild_count'] for s in self.shard_stats.values())
        total_users = sum(s['user_count'] for s in self.shard_stats.values())
        avg_latency = (
            sum(s['latency'] for s in self.shard_stats.values()) / len(self.shard_stats)
            if self.shard_stats else 0
        )

        overview.description = (
            f"**Total Servers:** `{total_guilds:,}`\n"
            f"**Total Users:** `{total_users:,}`\n"
            f"**Average Latency:** `{avg_latency:.1f}ms`\n"
            f"**Shards:** `{self.bot.shard_count or 1}`\n\n"
            "**Shard Status**\n"
        )

        # Add short status for all shards (up to 10, then paginate)
        max_inline = 5
        for shard_id, stats in list(self.shard_stats.items())[:max_inline]:
            status = stats.get('status', 'offline')
            emoji = "🟢" if status == "online" else "🔴"
            overview.description += (
                f"{emoji} Shard `{shard_id}`: `{stats['guild_count']} servers` | "
                f"`{stats['latency']:.1f}ms`\n"
            )

        if len(self.shard_stats) > max_inline:
            overview.description += f"*Use the arrows to see more shards*"

        pages.append(overview)

        # Create detail pages - 5 shards per page
        shards = list(self.shard_stats.items())
        for i in range(0, len(shards), 5):
            embed = nextcord.Embed(
                title="🔋 Shard Details",
                color=getattr(ctx.author, "color", nextcord.Color.blurple())
            )

            for shard_id, stats in shards[i:i+5]:
                uptime = datetime.datetime.now() - stats['start_time']
                days, hours = uptime.days, uptime.seconds // 3600
                minutes = (uptime.seconds // 60) % 60

                status = stats.get('status', 'offline')
                emoji = "🟢" if status == "online" else "🔴"

                embed.add_field(
                    name=f"{emoji} Shard {shard_id}",
                    value=(
                        f"**Servers:** `{stats['guild_count']:,}`\n"
                        f"**Users:** `{stats['user_count']:,}`\n"
                        f"**Latency:** `{stats['latency']:.1f}ms`\n"
                        f"**Uptime:** `{days}d {hours}h {minutes}m`"
                    ),
                    inline=False
                )

            pages.append(embed)

        # Improved paginator: disables buttons if only one page
        view = HelpPaginator(pages, ctx.author)
        view.update_buttons()
        has_select = hasattr(view, "select") and getattr(view.select, "options", None)
        if has_select and view.select.options:
            message = await ctx.reply(embed=pages[0], view=view)
        else:
            message = await ctx.reply(embed=pages[0])
        view.message = message

    @commands.Cog.listener()
    async def on_shard_ready(self, shard_id):
        """Track when a shard comes online."""
        self.logger.info(f"Shard {shard_id} ready")
        if shard_id not in self.shard_stats:
            self.shard_stats[shard_id] = {}
        self.shard_stats[shard_id].update({
            'start_time': datetime.datetime.now(),
            'last_seen': datetime.datetime.now(),
            'status': 'online'
        })
        self.update_shard_stats()

    @commands.Cog.listener()
    async def on_shard_disconnect(self, shard_id):
        """Track when a shard disconnects."""
        self.logger.warning(f"Shard {shard_id} disconnected")
        if shard_id in self.shard_stats:
            self.shard_stats[shard_id]['status'] = 'offline'

    @commands.Cog.listener()
    async def on_shard_resumed(self, shard_id):
        """Track when a shard resumes."""
        self.logger.info(f"Shard {shard_id} resumed")
        if shard_id in self.shard_stats:
            self.shard_stats[shard_id]['status'] = 'online'
            self.shard_stats[shard_id]['last_seen'] = datetime.datetime.now()

async def setup(bot):
    bot.add_cog(Status(bot))
