# Core Fishing Commands Module
# Contains the main fishing command and related mechanics

from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.safe_reply import safe_reply
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from utils.weight_formatter import format_weight
import nextcord
import random
import uuid
import datetime
import asyncio
import math

class FishingCore(commands.Cog, name="FishingCore"):
    """Core fishing commands - fish, rates, gear display"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger("FishingCore")
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
        
        # Load data from parent fishing cog
        from .fishing_data import FishingData
        self.data_manager = FishingData()
        
        # Load all fish, rod and bait data
        self.rod_data = self.data_manager.get_rod_data()
        self.bait_data = self.data_manager.get_bait_data()
        self.fish_database = self.data_manager.get_fish_database()
        self.rod_aliases = self.data_manager.get_rod_aliases()
        self.bait_aliases = self.data_manager.get_bait_aliases()

    async def cog_check(self, ctx):
        """Check if user accepted ToS and not in blocked channels"""
        if ctx.channel.id in self.blocked_channels:
            return False
        return await check_tos_acceptance(ctx.author.id)

    def _resolve_rod_alias(self, rod_input: str) -> str:
        """Resolve rod alias to full rod ID"""
        return self.data_manager.resolve_rod_alias(rod_input)

    def _resolve_bait_alias(self, bait_input: str) -> str:
        """Resolve bait alias to full bait ID"""
        return self.data_manager.resolve_bait_alias(bait_input)

    def _apply_rod_multiplier_properly(self, bait_rates, rod_multiplier):
        """Apply rod multiplier to favor higher rarities"""
        return self.data_manager.apply_rod_multiplier(bait_rates, rod_multiplier)

    async def display_catch_percentages_fixed(self, bait_rates, rod_multiplier):
        """Display catch percentages using the fixed calculation"""
        return self.data_manager.calculate_catch_percentages(bait_rates, rod_multiplier)

    async def get_user_inventory(self, user_id: int):
        """Get user's inventory from database"""
        user_data = await db.db.users.find_one({"_id": str(user_id)})
        return user_data.get("inventory", {}) if user_data else {}

    async def get_user_rods(self, user_id: int):
        """Get user's rods with full data"""
        inventory = await self.get_user_inventory(user_id)
        if not inventory:
            return []
        
        rod_inventory = inventory.get("rod", {})
        rods = []
        
        for rod_id, quantity in rod_inventory.items():
            if quantity > 0 and rod_id in self.rod_data:
                rod_info = self.rod_data[rod_id].copy()
                rod_info["_id"] = rod_id
                rod_info["quantity"] = quantity
                rods.append(rod_info)
        
        return rods

    async def get_user_bait(self, user_id: int):
        """Get user's bait with full data"""
        inventory = await self.get_user_inventory(user_id)
        if not inventory:
            return []
        
        bait_inventory = inventory.get("bait", {})
        bait_list = []
        
        for bait_id, amount in bait_inventory.items():
            if amount > 0 and bait_id in self.bait_data:
                bait_info = self.bait_data[bait_id].copy()
                bait_info["_id"] = bait_id
                bait_info["amount"] = amount
                bait_list.append(bait_info)
        
        return bait_list

    async def remove_bait(self, user_id: int, bait_id: str) -> bool:
        """Remove one bait from user's inventory"""
        try:
            result = await db.db.users.update_one(
                {"_id": str(user_id), f"inventory.bait.{bait_id}": {"$gt": 0}},
                {"$inc": {f"inventory.bait.{bait_id}": -1}}
            )
            return result.modified_count > 0
        except Exception as e:
            self.logger.error(f"Failed to remove bait: {e}")
            return False

    async def set_active_rod_manual(self, user_id: int, rod_id: str) -> bool:
        """Set user's active fishing rod manually"""
        try:
            result = await db.db.users.update_one(
                {"_id": str(user_id)},
                {"$set": {"active_fishing_gear.rod": rod_id}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Failed to set active rod: {e}")
            return False

    async def check_rod_durability(self, durability: float, rod_price: int = 0) -> bool:
        """Check if rod survives this fishing attempt - Improved durability system"""
        # Ensure minimum 95% durability (0.95 = 5% break chance maximum)
        durability = max(0.95, min(0.998, durability))  # Cap durability at 99.8%
        
        base_break_chance = 1 - durability
        
        # High-end rods get durability bonuses (10-20% break chance reduction)
        if rod_price >= 100000:  # Ultra expensive rods
            base_break_chance *= 0.80  # 20% break chance reduction
        elif rod_price >= 50000:  # Very expensive rods  
            base_break_chance *= 0.85  # 15% break chance reduction
        elif rod_price >= 20000:  # Expensive rods
            base_break_chance *= 0.90  # 10% break chance reduction
        
        # Cap maximum break chance at 10% (was unlimited)
        final_break_chance = min(0.10, base_break_chance)
        
        return random.random() > final_break_chance

    async def select_fish_from_rarity(self, rarity: str):
        """Select a random fish from the given rarity category"""
        if rarity not in self.fish_database:
            return None
        
        fish_list = self.fish_database[rarity]
        if not fish_list:
            return None
        
        return random.choice(fish_list)

    async def check_fish_escape(self, fish_template, rod_power: int):
        """Check if fish escapes - Implements weight rule and balanced escape chances"""
        base_escape_chance = fish_template.get("escape_chance", 0.1)
        
        # Generate fish weight first
        min_weight = fish_template.get("min_weight", 0.1)
        max_weight = fish_template.get("max_weight", 1.0)
        fish_weight = random.uniform(min_weight, max_weight)
        
        # WEIGHT RULE: Fish under 100kg (220 lbs) CANNOT escape - guaranteed catch!
        if fish_weight < 100.0:
            return False, fish_weight  # Fish cannot escape
        
        # For fish over 100kg, apply escape chance calculations
        # Reduce escape chance based on rod power (limited scaling)
        power_reduction = min(0.30, (rod_power - 1) * 0.05)  # Max 30% reduction (was 80%)
        final_escape_chance = max(0.01, base_escape_chance * (1 - power_reduction))
        
        # Value-based escape penalties for high-value fish
        fish_value = fish_template.get("base_value", 0)
        if fish_value >= 1000000:  # 1M+ coins
            final_escape_chance = min(0.99, final_escape_chance + 0.50)
        elif fish_value >= 100000:  # 100K+ coins
            final_escape_chance = min(0.98, final_escape_chance + 0.30)
        elif fish_value >= 50000:   # 50K+ coins
            final_escape_chance = min(0.95, final_escape_chance + 0.20)
        
        # Check if fish escapes
        escaped = random.random() < final_escape_chance
        
        return escaped, fish_weight

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

    @commands.command(name="fish", aliases=["fishing", 'fs'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def fish(self, ctx):
        """Go fishing with advanced mechanics including rod breaking and fish escaping"""
        try:
            rods = await self.get_user_rods(ctx.author.id)
            bait = await self.get_user_bait(ctx.author.id)
            
            if not rods:
                embed = nextcord.Embed(
                    title="🎣 First Time Fishing",
                    description="You need a fishing rod to start! Buy one from `.shop rod`",
                    color=0x4a90e2
                )
                embed.add_field(
                    name="🛒 Getting Started",
                    value="• Use `.shop rod` to browse fishing rods\n• Use `.shop bait` to get bait\n• Then use `.fish` to start fishing!",
                    inline=False
                )
                return await ctx.reply(embed=embed)
            
            if not bait:
                embed = nextcord.Embed(
                    title="🪱 No Bait Available",
                    description="You need bait to go fishing! Buy some from `.shop bait`",
                    color=0xff6b6b
                )
                return await ctx.reply(embed=embed)
            
            # Get active gear
            active_gear = await db.get_active_fishing_gear(ctx.author.id)
            active_rod_id = active_gear.get("rod") if active_gear else None
            active_bait_id = active_gear.get("bait") if active_gear else None
            
            if active_rod_id:
                rod = next((r for r in rods if r.get("_id") == active_rod_id), None)
            else:
                rod = rods[0]
                active_rod_id = rod.get("_id")
                await self.set_active_rod_manual(ctx.author.id, active_rod_id)
            
            if not rod:
                return await ctx.reply("❌ Your active rod is no longer available!")
            
            # Use active bait or first available bait
            current_bait = None
            bait_id = None
            
            if active_bait_id:
                current_bait = next((b for b in bait if b.get("_id") == active_bait_id), None)
                if current_bait and current_bait.get("amount", 0) > 0:
                    bait_id = active_bait_id
                else:
                    await db.set_active_bait(ctx.author.id, None)
                    current_bait = None
            
            if not current_bait:
                current_bait = bait[0]
                bait_id = current_bait.get("_id")
                await db.set_active_bait(ctx.author.id, bait_id)
            
            # Remove bait
            if not await self.remove_bait(ctx.author.id, bait_id):
                return await ctx.reply("❌ Failed to use bait or you're out of bait!")
            
            # Get rod stats
            rod_multiplier = rod.get("multiplier", 1.0)
            rod_durability = rod.get("durability", 0.95)
            rod_power = rod.get("power", 1)
            rod_price = rod.get("price", 0)
            bait_rates = current_bait.get("catch_rates", {})
            
            # Display suspense message
            suspense_embed = nextcord.Embed(
                title="🎣 Casting your line...",
                description=f"🎣 Using **{rod['name']}** with **{current_bait['name']}**",
                color=0x4a90e2
            )
            
            flavor_texts = [
                "🌊 The water ripples gently...",
                "🐟 Something stirs beneath the surface...",
                "⭐ Your line dances in the current...",
                "🌀 The depths hold mysterious treasures...",
                "💫 Fortune favors the patient angler..."
            ]
            suspense_embed.add_field(
                name="🎯 Status", 
                value=random.choice(flavor_texts), 
                inline=False
            )
            
            suspense_embed.set_footer(text="Waiting for a bite...")
            message = await ctx.reply(embed=suspense_embed)
            
            # Suspense delay
            await asyncio.sleep(random.uniform(2.5, 4.5))
            
            # Check rod durability first
            if not await self.check_rod_durability(rod_durability, rod_price):
                # Rod breaks!
                break_embed = nextcord.Embed(
                    title="💥 Rod Broke!",
                    description=f"Your **{rod['name']}** snapped under pressure!",
                    color=0xff4444
                )
                break_embed.add_field(
                    name="🗑️ Rod Removed",
                    value="The broken rod has been removed from your inventory.",
                    inline=False
                )
                break_embed.add_field(
                    name="💡 Tip",
                    value="Higher quality rods are more durable!",
                    inline=False
                )
                break_embed.set_footer(text="⚡ Time to buy a new rod from the shop!")
                
                # Remove rod from inventory
                await db.db.users.update_one(
                    {"_id": str(ctx.author.id)},
                    {"$inc": {f"inventory.rod.{active_rod_id}": -1}}
                )
                
                await message.edit(embed=break_embed)
                return
            
            # Determine what fish is hooked
            adjusted_rates = self._apply_rod_multiplier_properly(bait_rates, rod_multiplier)
            
            # BEGINNER ROD SAFETY NET: 10% chance to catch ANY fish, even ultra-rare ones
            beginner_luck = False
            if rod.get("_id", "").lower() in ["basic_rod", "beginner_rod"]:
                if random.random() < 0.10:  # 10% chance
                    beginner_luck = True
                    # Pick from ALL rarities equally
                    all_rarities = list(self.fish_database.keys())
                    caught_rarity = random.choice(all_rarities)
                    fish_template = await self.select_fish_from_rarity(caught_rarity)
            
            if not beginner_luck:
                # Normal fishing logic
                total_weight = sum(adjusted_rates.values())
                if total_weight == 0:
                    await message.edit(embed=nextcord.Embed(
                        title="🌊 No Bite",
                        description="Nothing seems interested in your bait...",
                        color=0x6495ed
                    ))
                    return
                
                # Roll for fish rarity
                roll = random.random() * total_weight
                cumulative = 0
                caught_rarity = "junk"
                
                for rarity, weight in adjusted_rates.items():
                    cumulative += weight
                    if roll <= cumulative:
                        caught_rarity = rarity
                        break
                
                # Select specific fish
                fish_template = await self.select_fish_from_rarity(caught_rarity)
                if not fish_template:
                    caught_rarity = "junk"
                    fish_template = await self.select_fish_from_rarity(caught_rarity)
            
            # Check if fish escapes
            escaped, fish_weight = await self.check_fish_escape(fish_template, rod_power)
            
            if escaped:
                # Fish escaped!
                rarity_config = self._get_rarity_config()
                config = rarity_config.get(caught_rarity, {"color": 0x8b0000, "emoji": "🐟"})
                
                escape_embed = nextcord.Embed(
                    title="💔 The one that got away...",
                    description=f"A **{fish_template['name']}** ({format_weight(fish_weight)}) broke free!",
                    color=config['color']
                )
                escape_embed.add_field(
                    name="💸 Potential Value",
                    value=f"You could have earned **{fish_template['base_value']:,}** {self.currency}",
                    inline=True
                )
                escape_embed.add_field(
                    name="💡 Tip",
                    value="Try using a stronger rod for big fish!",
                    inline=True
                )
                escape_embed.add_field(
                    name="🎯 Rarity Lost",
                    value=f"{config['emoji']} **{caught_rarity.title()}**",
                    inline=True
                )
                
                if caught_rarity in ["legendary", "mythical", "ancient", "divine", "cosmic", "transcendent"]:
                    escape_embed.set_footer(text="💀 A legendary fish has escaped! The ocean mocks your efforts...")
                elif caught_rarity in ["epic", "rare"]:
                    escape_embed.set_footer(text="😤 A rare catch slipped away! Better luck next time...")
                else:
                    escape_embed.set_footer(text="🎣 It happens to the best of us. Keep fishing!")
                
                await message.edit(embed=escape_embed)
                return
            
            # Successfully caught!
            final_value = random.randint(
                int(fish_template["base_value"] * 0.8),
                int(fish_template["base_value"] * 1.2)
            )
            
            fish = {
                "id": str(uuid.uuid4()),
                "type": caught_rarity,
                "name": fish_template["name"],
                "value": final_value,
                "weight": fish_weight,
                "caught_at": datetime.datetime.now().isoformat(),
                "bait_used": bait_id,
                "rod_used": active_rod_id
            }
            
            if await db.add_fish(ctx.author.id, fish):
                # Define rarity colors and emojis
                rarity_config = self._get_rarity_config()
                config = rarity_config.get(caught_rarity, {"color": 0x2b2d31, "emoji": "🐟"})
                
                # Check how many of this fish the user already has
                user_fish = await db.get_fish(ctx.author.id)
                fish_count = len([f for f in user_fish if f.get('name') == fish['name']])
                
                # Create enhanced success embed
                success_embed = nextcord.Embed(
                    title=f"{config['emoji']} Fish Caught!",
                    description=f"You caught a **{fish['name']}**!",
                    color=config['color']
                )
                
                # Add BEGINNER'S LUCK message if this was a miracle catch
                if beginner_luck:
                    success_embed.description += f"\n\n🍀 **BEGINNER'S LUCK!** 🍀\n*Your basic rod defied the odds!*"
                
                if fish_count > 1:
                    success_embed.description += f"\n*(You have **{fish_count}x** of this fish)*"
                
                success_embed.add_field(
                    name="💰 Value",
                    value=f"**{final_value:,}** {self.currency}",
                    inline=True
                )
                
                success_embed.add_field(
                    name="⚖️ Weight",
                    value=format_weight(fish_weight),
                    inline=True
                )
                
                success_embed.add_field(
                    name="✨ Rarity",
                    value=f"**{caught_rarity.title()}**",
                    inline=True
                )
                
                # Add special messages for rare fish
                if caught_rarity == "subatomic":
                    success_embed.set_footer(text="🔬 LEGENDARY SUBATOMIC CATCH! You've caught microscopic life worth a fortune!")
                elif caught_rarity == "super":
                    success_embed.set_footer(text="🦸 SUPER HERO CATCH! You've reeled in a legendary superhero fish!")
                elif caught_rarity in ["legendary", "mythical", "ancient", "divine", "cosmic", "transcendent", "void", "celestial"]:
                    success_embed.set_footer(text="🌟 Incredible catch! This is extremely rare!")
                elif caught_rarity in ["epic", "rare"]:
                    success_embed.set_footer(text="🎣 Nice catch! This is quite rare!")
                elif caught_rarity == "crystalline":
                    success_embed.set_footer(text="💎 Shimmering crystalline catch! Worth a small fortune!")
                elif caught_rarity == "mutated":
                    success_embed.set_footer(text="☢️ Mutated specimen! Science will pay well for this!")
                
                await message.edit(embed=success_embed)
                
            else:
                await message.edit(embed=nextcord.Embed(
                    title="❌ Storage Error",
                    description="Failed to store your catch! Please try again.",
                    color=0xff0000
                ))
                
        except Exception as e:
            self.logger.error(f"Fishing error: {e}")
            await ctx.reply("❌ An error occurred while fishing!")

    @commands.command(name="fishrates", aliases=["rates", "catchrates"])
    async def fish_rates(self, ctx):
        """Show all fishing catch rates with your current gear"""
        try:
            # Get user's active gear
            active_gear = await db.get_active_fishing_gear(ctx.author.id)
            if not active_gear:
                return await ctx.reply("❌ You need fishing gear first! Use `.shop rod` and `.shop bait`")
            
            active_rod_id = active_gear.get("rod")
            active_bait_id = active_gear.get("bait")
            
            if not active_rod_id or not active_bait_id:
                return await ctx.reply("❌ You need both a rod and bait equipped!")
            
            # Get rod data
            user_rods = await self.get_user_rods(ctx.author.id)
            rod = next((r for r in user_rods if r.get("_id") == active_rod_id), None)
            
            if not rod:
                return await ctx.reply("❌ Could not find your equipped rod!")
            
            # Get bait data
            user_bait = await self.get_user_bait(ctx.author.id)
            bait = next((b for b in user_bait if b.get("_id") == active_bait_id), None)
            
            if not bait:
                return await ctx.reply("❌ Could not find your equipped bait!")
            
            # Calculate catch rates
            rod_multiplier = rod.get("multiplier", 1.0)
            bait_rates = bait.get("catch_rates", {})
            
            percentages = await self.display_catch_percentages_fixed(bait_rates, rod_multiplier)
            
            if not percentages:
                return await ctx.reply("❌ Could not calculate catch rates!")
            
            # Create embed
            embed = nextcord.Embed(
                title="🎣 Fishing Catch Rates",
                description=f"**Rod:** {rod['name']} (x{rod_multiplier})\n**Bait:** {bait['name']}",
                color=0x4a90e2
            )
            
            # Sort by chance (highest first)
            sorted_rates = sorted(percentages.items(), key=lambda x: x[1], reverse=True)
            
            # Split into two columns for better display
            half = len(sorted_rates) // 2
            left_column = sorted_rates[:half]
            right_column = sorted_rates[half:]
            
            left_text = ""
            for rarity, chance in left_column:
                emoji = self._get_rarity_config().get(rarity, {}).get("emoji", "🐟")
                left_text += f"{emoji} **{rarity.title()}:** {chance:.3f}%\n"
            
            right_text = ""
            for rarity, chance in right_column:
                emoji = self._get_rarity_config().get(rarity, {}).get("emoji", "🐟")
                right_text += f"{emoji} **{rarity.title()}:** {chance:.3f}%\n"
            
            if left_text:
                embed.add_field(name="📊 Catch Rates (Part 1)", value=left_text, inline=True)
            if right_text:
                embed.add_field(name="📊 Catch Rates (Part 2)", value=right_text, inline=True)
            
            embed.set_footer(text="Higher multiplier rods favor rarer fish!")
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Fish rates error: {e}")
            await ctx.reply("❌ An error occurred while calculating catch rates!")

    @commands.command(name="fishgear", aliases=["gear", "equipped"])
    async def fish_gear(self, ctx):
        """View your currently equipped fishing gear"""
        try:
            active_gear = await db.get_active_fishing_gear(ctx.author.id)
            
            embed = nextcord.Embed(
                title="🎣 Currently Equipped Gear",
                color=0x2b2d31
            )
            
            if not active_gear:
                embed.description = "❌ No gear equipped! Use `.rod` and `.bait` to equip some."
                return await ctx.reply(embed=embed)
            
            # Show equipped rod
            if active_gear.get("rod"):
                rod_id = active_gear["rod"]
                if rod_id in self.rod_data:
                    rod = self.rod_data[rod_id]
                    embed.add_field(
                        name="🎣 Equipped Rod",
                        value=f"**{rod['name']}**\n"
                              f"Multiplier: {rod.get('multiplier', 1.0)}x\n"
                              f"Power: {rod.get('power', 1)}\n"
                              f"Durability: {(rod.get('durability', 0.95)*100):.1f}%",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="🎣 Equipped Rod",
                        value="❌ Rod data not found",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🎣 Equipped Rod",
                    value="❌ No rod equipped",
                    inline=True
                )
            
            # Show equipped bait
            if active_gear.get("bait"):
                bait_id = active_gear["bait"]
                user_bait = await self.get_user_bait(ctx.author.id)
                equipped_bait = next((b for b in user_bait if b.get("_id") == bait_id), None)
                
                if equipped_bait:
                    embed.add_field(
                        name="🪱 Equipped Bait",
                        value=f"**{equipped_bait['name']}**\n"
                              f"Amount: {equipped_bait.get('amount', 1)}\n"
                              f"Type: {equipped_bait.get('rarity', 'Common').title()}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="🪱 Equipped Bait",
                        value="❌ Bait data not found",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🪱 Equipped Bait",
                    value="❌ No bait equipped",
                    inline=True
                )
            
            embed.set_footer(text="Use .rod and .bait to change your equipment!")
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Fish gear error: {e}")
            await ctx.reply("❌ An error occurred while viewing your gear!")

async def setup(bot):
    bot.add_cog(FishingCore(bot))
