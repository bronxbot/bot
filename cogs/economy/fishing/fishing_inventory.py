# Fishing Inventory and Equipment Management Module
# Handles fish inventory, rod/bait equipment, and gear management

from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from utils.safe_reply import safe_reply
from utils.weight_formatter import format_weight
import nextcord
import math
from .fishing_ui import FishInventoryPaginator, RodPaginator, BaitPaginator

class FishingInventory(commands.Cog, name="FishingInventory"):
    """Fishing inventory and equipment management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger("FishingInventory")
        self.currency = "<:bronkbuk:1377389238290747582>"
        
        # Load data from fishing data manager
        from .fishing_data import FishingData
        self.data_manager = FishingData()
        
        self.rod_data = self.data_manager.get_rod_data()
        self.bait_data = self.data_manager.get_bait_data()
        self.rod_aliases = self.data_manager.get_rod_aliases()
        self.bait_aliases = self.data_manager.get_bait_aliases()

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

    def _resolve_rod_alias(self, rod_input: str) -> str:
        """Resolve rod alias to full rod ID"""
        return self.data_manager.resolve_rod_alias(rod_input)

    def _resolve_bait_alias(self, bait_input: str) -> str:
        """Resolve bait alias to full bait ID"""
        return self.data_manager.resolve_bait_alias(bait_input)

    async def set_active_rod_manual(self, user_id: int, rod_id: str) -> bool:
        """Set user's active fishing rod manually"""
        try:
            result = await db.db.users.update_one(
                {"_id": str(user_id)},
                {"$set": {"active_fishing.rod": rod_id}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Failed to set active rod: {e}")
            return False

    @commands.command(name="fishinv", aliases=["fi", "finv", "fishbag"])
    async def fish_inventory(self, ctx, page: int = 1):
        """View your fish inventory with pagination - first page shows gear, rest show fish"""
        try:
            user_fish = await db.get_fish(ctx.author.id)
            
            # Page 1: Show active gear and summary
            if page == 1:
                # Get active gear
                active_gear = await db.get_active_fishing_gear(ctx.author.id)
                
                # Get total fish stats
                total_fish = len(user_fish)
                total_value = sum(fish.get("value", 0) for fish in user_fish) if user_fish else 0
                
                embed = nextcord.Embed(
                    title="🎣 Fishing Overview",
                    description=f"**Total Fish:** {total_fish:,} | **Total Value:** {total_value:,} {self.currency}",
                    color=0x2b2d31
                )
                
                # Show equipped rod
                if active_gear and active_gear.get("rod"):
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
                        value="❌ No rod equipped\nUse `.rod` to equip one",
                        inline=True
                    )
                
                # Show equipped bait
                if active_gear and active_gear.get("bait"):
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
                        value="❌ No bait equipped\nUse `.bait` to equip some",
                        inline=True
                    )
                
                # Add quick stats if user has fish
                if user_fish:
                    # Sort by value and get top catches
                    sorted_fish = sorted(user_fish, key=lambda x: x.get("value", 0), reverse=True)
                    top_fish = sorted_fish[:3]
                    
                    top_catches = []
                    for i, fish in enumerate(top_fish, 1):
                        top_catches.append(f"{i}. **{fish.get('name', 'Unknown')}** - {fish.get('value', 0):,} {self.currency}")
                    
                    embed.add_field(
                        name="🏆 Top Catches",
                        value="\n".join(top_catches),
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="🐟 Fish Collection",
                        value="No fish caught yet! Use `.fish` to start fishing.",
                        inline=False
                    )
                
                # Calculate total pages
                items_per_page = 5
                fish_pages = math.ceil(len(user_fish) / items_per_page) if user_fish else 0
                total_pages = 1 + fish_pages
                
                embed.set_footer(text=f"Page 1/{total_pages} • Use buttons to view your fish collection")
                
                # Create pagination view
                view = FishInventoryPaginator(ctx.author.id, user_fish, 1, total_pages, self.currency, self.rod_data, self.bait_data, self.get_user_bait)
                message = await ctx.reply(embed=embed, view=view)
                view.message = message
                return
            
            # Pages 2+: Show fish
            if not user_fish:
                return await ctx.reply("❌ You haven't caught any fish yet!")
            
            # Sort by value (highest first)
            user_fish.sort(key=lambda x: x.get("value", 0), reverse=True)
            
            items_per_page = 5
            fish_pages = math.ceil(len(user_fish) / items_per_page)
            total_pages = 1 + fish_pages
            
            if page > total_pages:
                return await ctx.reply(f"❌ Page {page} doesn't exist! Max page: {total_pages}")
            
            # Calculate fish for this page
            fish_page = page - 1  # Adjust for gear page
            start_idx = (fish_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            page_fish = user_fish[start_idx:end_idx]
            
            embed = nextcord.Embed(
                title="🐟 Fish Collection",
                description=f"Your caught fish sorted by value",
                color=0x2b2d31
            )
            
            # Add fish to embed
            for i, fish in enumerate(page_fish, start=start_idx + 1):
                fish_info = (
                    f"**#{i}** • **{fish.get('value', 0):,}** {self.currency}\n"
                    f"**Weight:** {format_weight(fish.get('weight', 0))}\n"
                    f"**Rarity:** {fish.get('type', 'unknown').title()}\n"
                    f"**ID:** `{fish.get('id', 'unknown')[:8]}...`"
                )
                
                embed.add_field(
                    name=f"🐟 {fish.get('name', 'Unknown Fish')}",
                    value=fish_info,
                    inline=False
                )
            
            embed.set_footer(text=f"Page {page}/{total_pages} • Use buttons to navigate")
            
            # Create pagination view
            view = FishInventoryPaginator(ctx.author.id, user_fish, page, total_pages, self.currency, self.rod_data, self.bait_data, self.get_user_bait)
            message = await ctx.reply(embed=embed, view=view)
            view.message = message
            
        except Exception as e:
            self.logger.error(f"Fish inventory error: {e}")
            await ctx.reply("❌ An error occurred while viewing your fish inventory!")

    @commands.command(name="rod", aliases=["erod", 'equiprod', "equip_rod"])
    async def rod(self, ctx, *, rod_name: str = None):
        """Equip a fishing rod from your inventory"""
        try:
            user_rods = await self.get_user_rods(ctx.author.id)
            if not user_rods:
                return await ctx.reply("❌ You don't have any fishing rods! Buy one from `.shop rod`")
            
            # Get active gear to show which rod is currently equipped
            active_gear = await db.get_active_fishing_gear(ctx.author.id)
            active_rod_id = active_gear.get("rod") if active_gear else None
            
            if not rod_name:
                # Show paginated rod inventory
                view = RodPaginator(ctx.author.id, user_rods, active_rod_id, self)
                embed = await view.create_embed()
                message = await ctx.reply(embed=embed, view=view)
                view.message = message
                return
            
            # Find rod by name, ID, or alias
            target_rod = None
            
            # First try to resolve alias
            resolved_rod_id = self._resolve_rod_alias(rod_name)
            
            for rod in user_rods:
                rod_id = rod.get('_id', '').lower()
                rod_full_name = rod['name'].lower()
                
                # Match by exact ID, resolved alias, or name contains
                if (rod_name.lower() == rod_id or 
                    (resolved_rod_id and resolved_rod_id == rod_id) or
                    rod_name.lower() in rod_full_name):
                    target_rod = rod
                    break
            
            if not target_rod:
                embed = nextcord.Embed(
                    title="❌ Rod Not Found",
                    description=f"Rod '{rod_name}' not found in your inventory!",
                    color=0xff0000
                )
                embed.add_field(
                    name="💡 Tip",
                    value="Use `.rod` without arguments to see all your rods with a dropdown selector!",
                    inline=False
                )
                embed.add_field(
                    name="Available Aliases",
                    value="quantum, cosmic, void, divine, basic, pro, etc.",
                    inline=False
                )
                return await ctx.reply(embed=embed)
            
            # Equip the rod
            if await self.set_active_rod_manual(ctx.author.id, target_rod['_id']):
                embed = nextcord.Embed(
                    title="🎣 Rod Equipped",
                    description=f"You equipped **{target_rod['name']}**",
                    color=0x00ff00
                )
                embed.add_field(
                    name="📊 Stats",
                    value=f"**Multiplier:** {target_rod.get('multiplier', 1.0)}x\n"
                          f"**Durability:** {((target_rod.get('durability', 0.95))*100):.1f}%\n"
                          f"**Power Level:** {target_rod.get('power', 1)}",
                    inline=False
                )
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("❌ Failed to equip rod!")
                
        except Exception as e:
            self.logger.error(f"Equip rod error: {e}")
            await ctx.reply("❌ An error occurred while equipping the rod!")

    @commands.command(name="bait", aliases=["ebait", 'equipbait', "equip_bait"])
    async def bait(self, ctx, *, bait_name: str = None):
        """Equip bait from your inventory"""
        try:
            user_bait = await self.get_user_bait(ctx.author.id)
            if not user_bait:
                return await ctx.reply("❌ You don't have any bait! Buy some from `.shop bait`")
            
            # Get active gear to show which bait is currently equipped
            active_gear = await db.get_active_fishing_gear(ctx.author.id)
            active_bait_id = active_gear.get("bait") if active_gear else None
            
            if not bait_name:
                # Show paginated bait inventory
                view = BaitPaginator(ctx.author.id, user_bait, active_bait_id, self)
                embed = await view.create_embed()
                message = await ctx.reply(embed=embed, view=view)
                view.message = message
                return
            
            # Find bait by name, ID, or alias
            target_bait = None
            
            # First try to resolve alias
            resolved_bait_id = self._resolve_bait_alias(bait_name)
            
            # Try exact matches first
            for bait in user_bait:
                bait_id = bait.get('_id', '').lower()
                bait_full_name = bait['name'].lower()
                
                # Exact ID match
                if bait_name.lower() == bait_id:
                    target_bait = bait
                    break
                    
                # Exact resolved alias match
                if resolved_bait_id and resolved_bait_id == bait_id:
                    target_bait = bait
                    break
            
            # If no exact match found, try partial name matches
            if not target_bait:
                for bait in user_bait:
                    bait_full_name = bait['name'].lower()
                    
                    # Only match if the input is a significant part of the name
                    if (len(bait_name) >= 3 and 
                        bait_name.lower() in bait_full_name and
                        len(bait_name) / len(bait_full_name) > 0.3):  # At least 30% of the name
                        target_bait = bait
                        break
            
            if not target_bait:
                embed = nextcord.Embed(
                    title="❌ Bait Not Found",
                    description=f"Bait '{bait_name}' not found in your inventory!",
                    color=0xff0000
                )
                embed.add_field(
                    name="💡 Tip",
                    value="Use `.bait` without arguments to see all your bait with a dropdown selector!",
                    inline=False
                )
                embed.add_field(
                    name="Available Aliases",
                    value="quantum, void, crystal, divine, basic, pro, etc.",
                    inline=False
                )
                return await ctx.reply(embed=embed)
            
            # Equip the bait
            bait_id = target_bait.get('_id')
            if not bait_id:
                return await ctx.reply("❌ Invalid bait ID!")
                
            if await db.set_active_bait(ctx.author.id, bait_id):
                embed = nextcord.Embed(
                    title="🪱 Bait Equipped",
                    description=f"You equipped **{target_bait['name']}**",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Description",
                    value=target_bait.get('description', 'No description available'),
                    inline=False
                )
                await ctx.reply(embed=embed)
            else:
                await ctx.reply("❌ Failed to equip bait! Database operation failed.")
                
        except Exception as e:
            self.logger.error(f"Equip bait error: {e}")
            await ctx.reply("❌ An error occurred while equipping the bait!")

async def setup(bot):
    bot.add_cog(FishingInventory(bot))
