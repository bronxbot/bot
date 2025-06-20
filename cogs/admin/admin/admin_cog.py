"""
Main Admin Cog
Core admin commands and functionality.
"""

import nextcord
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import AsyncDatabase
from typing import Optional, List
import json
import asyncio

# Import modular components
from .constants import (CURRENCY_EMOJI, ADMIN_CATEGORIES, ERROR_MESSAGES, SUCCESS_MESSAGES, 
                       CONFIRMATION_PHRASES, SHOP_CATEGORIES)
from .shop_manager import ShopManager, ServerShopManager
from .economy_admin import EconomyAdmin
from .buff_manager import BuffManager
from .system_admin import SystemAdmin

db = AsyncDatabase.get_instance()

class Admin(commands.Cog):
    """Admin-only commands for bot management"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = CURRENCY_EMOJI
        
        # Initialize managers
        self.shop_manager = ShopManager()
        self.server_shop_manager = ServerShopManager()
        self.economy_admin = EconomyAdmin()
        self.buff_manager = BuffManager()
        self.system_admin = SystemAdmin(bot)
        
        # Background tasks would be initialized here if using nextcord.ext.tasks
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        # Cancel any background tasks here
        pass
    
    async def cog_check(self, ctx):
        """Global check for admin commands"""
        return ctx.author.guild_permissions.administrator or await self.bot.is_owner(ctx.author)
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Called when the bot is ready"""
        self.logger.info("Admin cog ready")
    
    # Shop Management Commands
    @commands.group(name="shop_admin", aliases=["sa"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def shop_admin(self, ctx):
        """🏪 Shop administration commands"""
        embed = nextcord.Embed(
            title=f"{ADMIN_CATEGORIES['shop']['emoji']} {ADMIN_CATEGORIES['shop']['name']}",
            description=ADMIN_CATEGORIES['shop']['description'],
            color=0x3498db
        )
        
        embed.add_field(
            name="📝 **Management Commands**",
            value=f"`{ctx.prefix}sa add <shop_type> <item_data>` - Add item to shop\n"
                  f"`{ctx.prefix}sa remove <shop_type> <item_id>` - Remove item\n"
                  f"`{ctx.prefix}sa edit <shop_type> <item_id> <field> <value>` - Edit item\n"
                  f"`{ctx.prefix}sa list <shop_type>` - List shop items",
            inline=False
        )
        
        embed.add_field(
            name="🏪 **Shop Types**",
            value=" • ".join(f"`{shop}`" for shop in SHOP_CATEGORIES.keys()),
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @shop_admin.command(name="add")
    async def shop_add(self, ctx, shop_type: str, *, item_data: str):
        """Add an item to a shop category"""
        if not self.shop_manager.validate_shop_type(shop_type):
            return await ctx.send(ERROR_MESSAGES["invalid_shop_type"])
        
        # Validate JSON data
        parsed_data = self.shop_manager.validate_item_data(item_data)
        if not parsed_data:
            return await ctx.send(ERROR_MESSAGES["invalid_json"])
        
        # Generate item ID if not provided
        item_id = parsed_data.get("id", parsed_data["name"].lower().replace(" ", "_"))
        
        # Add to shop
        success = self.shop_manager.add_item_to_shop(shop_type, item_id, parsed_data)
        
        if success:
            embed = nextcord.Embed(
                title="✅ Item Added",
                description=f"**{parsed_data['name']}** added to {shop_type} shop",
                color=0x00ff00
            )
            embed.add_field(name="Price", value=f"{parsed_data['price']:,} {self.currency}")
            if "description" in parsed_data:
                embed.add_field(name="Description", value=parsed_data["description"])
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to add item to shop")
    
    @shop_admin.command(name="remove")
    async def shop_remove(self, ctx, shop_type: str, item_id: str):
        """Remove an item from a shop category"""
        if not self.shop_manager.validate_shop_type(shop_type):
            return await ctx.send(ERROR_MESSAGES["invalid_shop_type"])
        
        success = self.shop_manager.remove_item_from_shop(shop_type, item_id)
        
        if success:
            await ctx.send(f"✅ Removed **{item_id}** from {shop_type} shop")
        else:
            await ctx.send(ERROR_MESSAGES["item_not_found"])
    
    @shop_admin.command(name="list")
    async def shop_list(self, ctx, shop_type: str):
        """List all items in a shop category"""
        if not self.shop_manager.validate_shop_type(shop_type):
            return await ctx.send(ERROR_MESSAGES["invalid_shop_type"])
        
        items = self.shop_manager.get_shop_items(shop_type)
        
        if not items:
            return await ctx.send(f"❌ No items found in {shop_type} shop")
        
        embed = nextcord.Embed(
            title=f"🏪 {shop_type.title()} Shop Items",
            color=0x3498db
        )
        
        for item_id, item_data in items.items():
            name = item_data.get("name", item_id)
            price = item_data.get("price", 0)
            description = item_data.get("description", "No description")
            
            embed.add_field(
                name=f"{name} ({item_id})",
                value=f"**Price:** {price:,} {self.currency}\n{description}",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @shop_admin.command(name="edit")
    async def shop_edit(self, ctx, shop_type: str, item_id: str, field: str, *, value: str):
        """Edit a field of an item in the shop"""
        if not self.shop_manager.validate_shop_type(shop_type):
            return await ctx.send(ERROR_MESSAGES["invalid_shop_type"])
        
        success = self.shop_manager.update_item_in_shop(shop_type, item_id, field, value)
        
        if success:
            await ctx.send(f"✅ Updated **{field}** for **{item_id}** in {shop_type} shop")
        else:
            await ctx.send(ERROR_MESSAGES["item_not_found"])
    
    # Economy Administration Commands
    @commands.command(name="reset")
    @commands.has_permissions(administrator=True)
    async def reset_user_balance(self, ctx, user: nextcord.Member, new_balance: int = 0):
        """Reset a user's balance"""
        success = await self.economy_admin.reset_user_balance(user.id, ctx.guild.id, new_balance)
        
        if success:
            embed = nextcord.Embed(
                title="✅ Balance Reset",
                description=f"{user.mention}'s balance has been reset to {new_balance:,} {self.currency}",
                color=0x00ff00
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(ERROR_MESSAGES["database_error"])
    
    @commands.command(aliases=["resetecon"], hidden=True)
    @commands.has_permissions(administrator=True)
    async def reset_economy(self, ctx, *, confirmation: Optional[str] = None):
        """Reset the entire guild economy (DANGEROUS)"""
        if not confirmation:
            embed = nextcord.Embed(
                title="⚠️ DANGEROUS OPERATION",
                description="This will reset ALL user balances and economy data for this server!\n\n"
                           f"Type `{ctx.prefix}reset_economy CONFIRM` to proceed.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        success, message = await self.economy_admin.reset_guild_economy(ctx.guild.id, confirmation)
        
        embed = nextcord.Embed(
            title="🔄 Economy Reset" if success else "❌ Reset Failed",
            description=message,
            color=0x00ff00 if success else 0xff0000
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="repair")
    @commands.has_permissions(administrator=True)
    async def repair_user_data(self, ctx, user: nextcord.Member = None):
        """Repair corrupted user data"""
        target_user = user or ctx.author
        
        success, repairs = await self.economy_admin.repair_user_data(target_user.id, ctx.guild.id)
        
        embed = nextcord.Embed(
            title="🔧 Data Repair Results",
            color=0x00ff00 if success else 0xff0000
        )
        
        if success and repairs:
            embed.description = f"Repaired data for {target_user.mention}:"
            embed.add_field(
                name="Repairs Made",
                value="\n".join(f"• {repair}" for repair in repairs),
                inline=False
            )
        elif success:
            embed.description = f"No repairs needed for {target_user.mention}"
        else:
            embed.description = "❌ Error occurred during repair"
        
        await ctx.send(embed=embed)
    
    # Buff Management Commands
    @commands.command(name="trigger")
    @commands.has_permissions(administrator=True)
    async def trigger_buff(self, ctx, buff_type: str = None):
        """Trigger a global buff"""
        if not buff_type:
            available_buffs = self.buff_manager.get_available_buff_types()
            embed = nextcord.Embed(
                title="✨ Available Buff Types",
                color=0x9932cc
            )
            
            for buff_id, buff_data in available_buffs.items():
                embed.add_field(
                    name=f"{buff_data['emoji']} {buff_data['name']}",
                    value=f"{buff_data['description']}\n**Duration:** {buff_data['duration_hours']}h",
                    inline=False
                )
            
            await ctx.send(embed=embed)
            return
        
        success, message = await self.buff_manager.activate_buff(ctx.guild.id, buff_type)
        
        embed = nextcord.Embed(
            title="✨ Buff Activation",
            description=message,
            color=0x00ff00 if success else 0xff0000
        )
        await ctx.send(embed=embed)
    
    # System Administration Commands
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def clearcommands(self, ctx):
        """Clear application commands"""
        success, message = await self.system_admin.clear_application_commands(ctx.guild.id)
        
        embed = nextcord.Embed(
            title="🔧 Clear Commands",
            description=message,
            color=0x00ff00 if success else 0xff0000
        )
        await ctx.send(embed=embed)
    
    @commands.command(name="botstats")
    @commands.has_permissions(administrator=True)
    async def get_bot_stats(self, ctx):
        """Get comprehensive bot statistics"""
        stats = await self.system_admin.get_bot_stats()
        
        if not stats:
            return await ctx.send("❌ Unable to retrieve bot statistics")
        
        embed = nextcord.Embed(
            title="📊 Bot Statistics",
            color=0x3498db
        )
        
        embed.add_field(
            name="🏛️ **General**",
            value=f"**Guilds:** {stats.get('guilds', 0):,}\n"
                  f"**Users:** {stats.get('users', 0):,}\n"
                  f"**Latency:** {stats.get('latency_ms', 0)}ms",
            inline=True
        )
        
        embed.add_field(
            name="💾 **Resources**",
            value=f"**Memory:** {stats.get('memory_mb', 0):.1f} MB\n"
                  f"**CPU:** {stats.get('cpu_percent', 0):.1f}%\n"
                  f"**Uptime:** {stats.get('uptime_seconds', 0):,}s",
            inline=True
        )
        
        await ctx.send(embed=embed)
    
    # Background Tasks
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Handle admin command errors"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(ERROR_MESSAGES["no_permission"])
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(ERROR_MESSAGES["no_permission"])
    
    async def rotate_global_buff(self):
        """Manually rotate global buff"""
        message = await self.buff_manager.rotate_global_buff()
        self.logger.info(f"Global buff rotation: {message}")
        
    # This would be a scheduled task if using nextcord.ext.tasks
    # @tasks.loop(hours=24)
    # async def rotate_global_buff_task(self):
    #     await self.rotate_global_buff()


async def setup(bot):
    """Setup function for the admin cog"""
    bot.add_cog(Admin(bot))
