# Fishing Selling and Trading Module
# Handles fish selling with various filters and interactive selection

from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.safe_reply import safe_reply
from utils.amount_parser import parse_amount
import nextcord
from .fishing_ui import InteractiveFishSeller

class FishingSelling(commands.Cog, name="FishingSelling"):
    """Fish selling and trading functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger("FishingSelling")
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

    @commands.command(name="sellfish", aliases=["sf"])
    async def sell_fish(self, ctx, *args):
        """Enhanced fish selling with filtering and interactive selection
        
        Usage:
        .sf - Interactive fish browser with buttons
        .sf all - Sell all fish
        .sf <fish_id> - Sell specific fish by ID
        .sf <rarity> - Sell all fish of a specific rarity
        .sf > <value> - Sell fish with value greater than specified amount
        .sf < <value> - Sell fish with value less than specified amount
        .sf >= <value> - Sell fish with value greater than or equal to specified amount  
        .sf <= <value> - Sell fish with value less than or equal to specified amount
        
        Value formats supported:
        • Numbers: 100000, 2000000
        • Scientific notation: 2e5 (200,000), 1.5e6 (1,500,000)
        • Multipliers: 200k, 2m, 1.5m
        
        Examples:
        .sf > 2e5 - Sell fish worth more than 200,000
        .sf < 1m - Sell fish worth less than 1,000,000
        .sf >= 500k - Sell fish worth 500,000 or more
        """
        try:
            user_fish = await db.get_fish(ctx.author.id)
            if not user_fish:
                return await ctx.reply("❌ You haven't caught any fish yet!")
            
            # Parse arguments
            if not args:
                # Interactive fish browser
                return await self._interactive_fish_sale(ctx, user_fish)
            
            arg1 = args[0].lower()
            
            # Handle value-based filtering
            if arg1 in ['>', '<', '>=', '<='] and len(args) > 1:
                # Use amount parser to handle various formats (2e5, 2m, 2k, etc.)
                value_threshold, error = parse_amount(args[1], 999999999999)  # Use large number as we don't care about balance for filtering
                if error:
                    return await ctx.reply(f"❌ Invalid value format! {error}\n\n**Supported formats:**\n• Numbers: `100000`, `2000000`\n• Scientific: `2e5`, `1.5e6`\n• Multipliers: `200k`, `2m`, `1.5m`")
                
                return await self._sell_fish_by_value(ctx, user_fish, arg1, value_threshold)
            
            # Handle specific fish ID
            elif len(arg1) > 8:  # Fish IDs are usually longer
                return await self._sell_specific_fish(ctx, user_fish, arg1)
            
            # Handle "all" command
            elif arg1 == "all":
                return await self._sell_all_fish(ctx, user_fish)
            
            # Handle rarity-based selling
            else:
                return await self._sell_fish_by_rarity(ctx, user_fish, arg1)
                
        except Exception as e:
            self.logger.error(f"Sell fish error: {e}")
            await ctx.reply("❌ An error occurred while selling fish!")

    async def _interactive_fish_sale(self, ctx, user_fish):
        """Interactive fish browser with sell buttons"""
        # Sort fish by value (highest first)
        user_fish.sort(key=lambda x: x.get("value", 0), reverse=True)
        
        view = InteractiveFishSeller(ctx.author.id, user_fish, self.currency, self)
        embed = await view.create_embed()
        
        message = await ctx.reply(embed=embed, view=view)
        view.message = message

    async def _sell_specific_fish(self, ctx, user_fish, fish_id):
        """Sell a specific fish by ID"""
        fish = next((f for f in user_fish if f.get("id") == fish_id), None)
        if not fish:
            return await ctx.reply("❌ Fish not found in your inventory!")
        
        if await db.remove_fish(ctx.author.id, fish_id):
            await db.add_currency(ctx.author.id, fish["value"])
            
            # Get rarity config for colors
            rarity_config = self._get_rarity_config()
            config = rarity_config.get(fish.get("type", "common"), {"color": 0x2b2d31, "emoji": "🐟"})
            
            embed = nextcord.Embed(
                title=f"{config['emoji']} Fish Sold!",
                description=f"Sold **{fish['name']}** for **{fish['value']:,}** {self.currency}",
                color=config['color']
            )
            embed.add_field(
                name="📊 Details",
                value=f"**Rarity:** {fish.get('type', 'unknown').title()}\n**Weight:** {fish.get('weight', 0):.2f}kg",
                inline=False
            )
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("❌ Failed to sell fish!")

    async def _sell_all_fish(self, ctx, user_fish):
        """Sell all fish"""
        total_value = sum(fish.get("value", 0) for fish in user_fish)
        fish_count = len(user_fish)
        
        if await db.clear_fish(ctx.author.id):
            await db.add_currency(ctx.author.id, total_value)
            embed = nextcord.Embed(
                title="🐟 All Fish Sold!",
                description=f"Sold **{fish_count:,}** fish for **{total_value:,}** {self.currency}",
                color=0x00ff00
            )
            
            # Add breakdown by rarity
            rarity_counts = {}
            rarity_values = {}
            for fish in user_fish:
                rarity = fish.get("type", "unknown")
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
                rarity_values[rarity] = rarity_values.get(rarity, 0) + fish.get("value", 0)
            
            if rarity_counts:
                breakdown = []
                for rarity, count in sorted(rarity_counts.items()):
                    value = rarity_values[rarity]
                    breakdown.append(f"**{rarity.title()}:** {count}x ({value:,} {self.currency})")
                
                embed.add_field(
                    name="📈 Breakdown by Rarity",
                    value="\n".join(breakdown[:10]) + ("..." if len(breakdown) > 10 else ""),
                    inline=False
                )
            
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("❌ Failed to sell fish!")

    async def _sell_fish_by_rarity(self, ctx, user_fish, rarity):
        """Sell all fish of a specific rarity"""
        # Normalize rarity input
        rarity = rarity.lower()
        
        # Filter fish by rarity
        matching_fish = [f for f in user_fish if f.get("type", "").lower() == rarity]
        
        if not matching_fish:
            return await ctx.reply(f"❌ You don't have any **{rarity}** fish!")
        
        total_value = sum(fish.get("value", 0) for fish in matching_fish)
        fish_count = len(matching_fish)
        fish_ids = [fish.get("id") for fish in matching_fish]
        
        # Remove fish from database
        success_count = 0
        for fish_id in fish_ids:
            if await db.remove_fish(ctx.author.id, fish_id):
                success_count += 1
        
        if success_count > 0:
            # Add money for successfully sold fish
            earned = sum(fish.get("value", 0) for fish in matching_fish[:success_count])
            await db.add_currency(ctx.author.id, earned)
            
            # Get rarity config for colors
            rarity_config = self._get_rarity_config()
            config = rarity_config.get(rarity, {"color": 0x00ff00, "emoji": "🐟"})
            
            embed = nextcord.Embed(
                title=f"{config['emoji']} {rarity.title()} Fish Sold!",
                description=f"Sold **{success_count:,}** {rarity} fish for **{earned:,}** {self.currency}",
                color=config['color']
            )
            
            if success_count < fish_count:
                embed.add_field(
                    name="⚠️ Warning",
                    value=f"Only {success_count}/{fish_count} fish were sold successfully.",
                    inline=False
                )
            
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("❌ Failed to sell any fish!")

    async def _sell_fish_by_value(self, ctx, user_fish, operator, value_threshold):
        """Sell fish based on value comparison"""
        # Filter fish based on operator
        matching_fish = []
        
        for fish in user_fish:
            fish_value = fish.get("value", 0)
            
            if operator == ">":
                if fish_value > value_threshold:
                    matching_fish.append(fish)
            elif operator == "<":
                if fish_value < value_threshold:
                    matching_fish.append(fish)
            elif operator == ">=":
                if fish_value >= value_threshold:
                    matching_fish.append(fish)
            elif operator == "<=":
                if fish_value <= value_threshold:
                    matching_fish.append(fish)
        
        if not matching_fish:
            return await ctx.reply(f"❌ You don't have any fish with value {operator} {value_threshold:,} {self.currency}!")
        
        total_value = sum(fish.get("value", 0) for fish in matching_fish)
        fish_count = len(matching_fish)
        fish_ids = [fish.get("id") for fish in matching_fish]
        
        # Remove fish from database
        success_count = 0
        for fish_id in fish_ids:
            if await db.remove_fish(ctx.author.id, fish_id):
                success_count += 1
        
        if success_count > 0:
            # Add money for successfully sold fish
            earned = sum(fish.get("value", 0) for fish in matching_fish[:success_count])
            await db.add_currency(ctx.author.id, earned)
            
            embed = nextcord.Embed(
                title="💰 Fish Sold by Value!",
                description=f"Sold **{success_count:,}** fish (value {operator} {value_threshold:,}) for **{earned:,}** {self.currency}",
                color=0x00ff00
            )
            
            if success_count < fish_count:
                embed.add_field(
                    name="⚠️ Warning",
                    value=f"Only {success_count}/{fish_count} fish were sold successfully.",
                    inline=False
                )
            
            # Add breakdown by rarity
            rarity_counts = {}
            for fish in matching_fish[:success_count]:
                rarity = fish.get("type", "unknown")
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            
            if rarity_counts:
                breakdown = []
                for rarity, count in sorted(rarity_counts.items()):
                    breakdown.append(f"**{rarity.title()}:** {count}x")
                
                embed.add_field(
                    name="📊 Sold by Rarity",
                    value="\n".join(breakdown[:8]) + ("..." if len(breakdown) > 8 else ""),
                    inline=False
                )
            
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("❌ Failed to sell any fish!")

async def setup(bot):
    bot.add_cog(FishingSelling(bot))
