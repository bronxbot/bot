# Fishing Statistics and Leaderboards Module
# Handles fishing statistics, leaderboards, and user fishing data

from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.safe_reply import safe_reply
from utils.weight_formatter import format_weight
import nextcord
import math
from .fishing_ui import GlobalFishPaginator

class FishingStats(commands.Cog, name="FishingStats"):
    """Fishing statistics and leaderboard functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger("FishingStats")
        self.currency = "<:bronkbuk:1377389238290747582>"

    def _get_rarity_config(self):
        """Get rarity configuration for colors and emojis"""
        return {
            "junk": {"color": 0x8b4513, "emoji": "🗑️"},
            "tiny": {"color": 0x808080, "emoji": "🐟"},
            "small": {"color": 0x90EE90, "emoji": "🐠"},
            "common": {"color": 0x00ff00, "emoji": "🐟"},
            "uncommon": {"color": 0x1e90ff, "emoji": "🐠"},
            "rare": {"color": 0x9932cc, "emoji": "🐟"},
            "epic": {"color": 0xff69b4, "emoji": "🎣"},
            "legendary": {"color": 0xffa500, "emoji": "🌟"},
            "mythical": {"color": 0xff0000, "emoji": "⭐"},
            "ancient": {"color": 0x8b0000, "emoji": "🏺"},
            "divine": {"color": 0xffd700, "emoji": "✨"},
            "cosmic": {"color": 0x4b0082, "emoji": "🌌"},
            "transcendent": {"color": 0xdda0dd, "emoji": "💫"},
            "void": {"color": 0x2f4f4f, "emoji": "🕳️"},
            "celestial": {"color": 0x87ceeb, "emoji": "🌠"},
            "mutated": {"color": 0x32cd32, "emoji": "☢️"},
            "crystalline": {"color": 0x40e0d0, "emoji": "💎"},
            "subatomic": {"color": 0xff1493, "emoji": "⚛️"},
            "super": {"color": 0x00ffff, "emoji": "🦸"},
            "dev": {"color": 0xff69b4, "emoji": "👑"}
        }

    @commands.command(name="topfish", aliases=["gf", "globalfish", "flb", "fishleaderboard"])
    async def global_fish_leaderboard(self, ctx, page: int = 1):
        """Global fish leaderboard showing all catches"""
        try:
            # Get all users with fish
            users_with_fish = await db.db.users.find({"fish": {"$exists": True, "$ne": []}}).to_list(None)
            
            if not users_with_fish:
                return await ctx.reply("❌ No fish caught by anyone yet!")
            
            # Collect all fish with user info
            all_fish = []
            for user_data in users_with_fish:
                user_id = user_data["_id"]
                try:
                    user = self.bot.get_user(int(user_id))
                    username = user.display_name if user else f"User {user_id}"
                except:
                    username = f"User {user_id}"
                
                user_fish = user_data.get("fish", [])
                for fish in user_fish:
                    fish_with_user = fish.copy()
                    fish_with_user["user_id"] = user_id
                    fish_with_user["username"] = username
                    all_fish.append(fish_with_user)
            
            if not all_fish:
                return await ctx.reply("❌ No fish found in the database!")
            
            # Sort by value (highest first)
            all_fish.sort(key=lambda x: x.get("value", 0), reverse=True)
            
            # Pagination
            items_per_page = 10
            total_pages = math.ceil(len(all_fish) / items_per_page)
            
            if page < 1 or page > total_pages:
                return await ctx.reply(f"❌ Invalid page! Please use 1-{total_pages}")
            
            # Create paginated view
            view = GlobalFishPaginator(ctx.author.id, all_fish, page, total_pages, self.currency)
            embed = await view.create_embed()
            
            message = await ctx.reply(embed=embed, view=view)
            view.message = message
            
        except Exception as e:
            self.logger.error(f"Global fish leaderboard error: {e}")
            await ctx.reply("❌ An error occurred while fetching the leaderboard!")

    @commands.command(name="fishstats", aliases=["fs_stats"])
    async def fish_stats(self, ctx, user: nextcord.Member = None):
        """View fishing statistics for yourself or another user"""
        try:
            target_user = user or ctx.author
            user_fish = await db.get_fish(target_user.id)
            
            if not user_fish:
                target = "You haven't" if target_user == ctx.author else f"{target_user.display_name} hasn't"
                return await ctx.reply(f"❌ {target} caught any fish yet!")
            
            # Calculate statistics
            total_fish = len(user_fish)
            total_value = sum(fish.get("value", 0) for fish in user_fish)
            total_weight = sum(fish.get("weight", 0) for fish in user_fish)
            
            # Calculate rarity breakdown
            rarity_counts = {}
            rarity_values = {}
            for fish in user_fish:
                rarity = fish.get("type", "unknown")
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
                rarity_values[rarity] = rarity_values.get(rarity, 0) + fish.get("value", 0)
            
            # Find best catches
            sorted_fish = sorted(user_fish, key=lambda x: x.get("value", 0), reverse=True)
            best_catch = sorted_fish[0] if sorted_fish else None
            heaviest_fish = max(user_fish, key=lambda x: x.get("weight", 0)) if user_fish else None
            
            # Create embed
            embed = nextcord.Embed(
                title=f"🎣 {target_user.display_name}'s Fishing Statistics",
                color=0x2b2d31
            )
            
            # Basic stats
            embed.add_field(
                name="📊 Overview",
                value=f"**Total Fish:** {total_fish:,}\n"
                      f"**Total Value:** {total_value:,} {self.currency}\n"
                      f"**Total Weight:** {format_weight(total_weight)}\n"
                      f"**Average Value:** {(total_value / total_fish):,.0f} {self.currency}",
                inline=True
            )
            
            # Best catches
            if best_catch:
                embed.add_field(
                    name="🏆 Best Catch",
                    value=f"**{best_catch['name']}**\n"
                          f"Value: {best_catch['value']:,} {self.currency}\n"
                          f"Weight: {format_weight(best_catch['weight'])}\n"
                          f"Rarity: {best_catch['type'].title()}",
                    inline=True
                )
            
            if heaviest_fish and heaviest_fish != best_catch:
                embed.add_field(
                    name="⚖️ Heaviest Catch",
                    value=f"**{heaviest_fish['name']}**\n"
                          f"Weight: {heaviest_fish['weight']:.2f} kg\n"
                          f"Value: {heaviest_fish['value']:,} {self.currency}\n"
                          f"Rarity: {heaviest_fish['type'].title()}",
                    inline=True
                )
            
            # Rarity breakdown (top 6 most caught)
            if rarity_counts:
                sorted_rarities = sorted(rarity_counts.items(), key=lambda x: x[1], reverse=True)
                rarity_config = self._get_rarity_config()
                
                rarity_text = ""
                for rarity, count in sorted_rarities[:6]:
                    emoji = rarity_config.get(rarity, {}).get("emoji", "🐟")
                    value = rarity_values.get(rarity, 0)
                    percentage = (count / total_fish) * 100
                    rarity_text += f"{emoji} **{rarity.title()}:** {count}x ({percentage:.1f}%)\n"
                
                embed.add_field(
                    name="🎯 Rarity Breakdown",
                    value=rarity_text,
                    inline=False
                )
            
            # User avatar
            embed.set_thumbnail(url=target_user.display_avatar.url)
            embed.set_footer(text=f"Use .fishinv to view {target_user.display_name}'s full collection")
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Fish stats error: {e}")
            await ctx.reply("❌ An error occurred while calculating fishing statistics!")

async def setup(bot):
    bot.add_cog(FishingStats(bot))
