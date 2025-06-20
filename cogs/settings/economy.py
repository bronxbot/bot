# Economy Settings
# Handles server-specific economy configuration, custom shops, and economy toggles

import nextcord
from nextcord.ext import commands
from typing import Optional, List, Dict, Union
import json
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('EconomySettings')

class EconomySettings(commands.Cog, ErrorHandler):
    """Economy configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='economy', aliases=['eco'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def economy_settings(self, ctx):
        """Economy settings management"""
        embed = nextcord.Embed(
            title="💰 Economy Settings",
            description=(
                "Configure economy settings for this server\n\n"
                "**Available Commands:**\n"
                "`economy toggle` - Toggle server-specific economy\n"
                "`economy shop` - Manage server shop items\n"
                "`economy rewards` - Configure economy rewards\n"
                "`economy view` - View current economy settings\n"
                "`economy reset` - Reset economy settings"
            ),
            color=0xf1c40f
        )
        await ctx.send(embed=embed)

    @economy_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_economy_settings(self, ctx):
        """View current economy settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        
        embed = nextcord.Embed(
            title="💰 Economy Settings Overview",
            color=0xf1c40f
        )
        
        # Server economy toggle
        server_economy = eco_settings.get('server_economy', {})
        embed.add_field(
            name="🏦 Server Economy",
            value=(
                f"**Enabled:** {'✅' if server_economy.get('enabled', False) else '❌'}\n"
                f"**Starting Balance:** {server_economy.get('starting_balance', 1000)} coins\n"
                f"**Currency Symbol:** {server_economy.get('currency_symbol', '🪙')}\n"
                f"**Global Sync:** {'✅' if server_economy.get('global_sync', True) else '❌'}"
            ),
            inline=False
        )
        
        # Shop settings
        shop_settings = eco_settings.get('shop', {})
        custom_items = shop_settings.get('custom_items', [])
        embed.add_field(
            name="🛒 Server Shop",
            value=(
                f"**Custom Items:** {len(custom_items)} items\n"
                f"**Shop Enabled:** {'✅' if shop_settings.get('enabled', True) else '❌'}\n"
                f"**Global Items:** {'✅' if shop_settings.get('include_global', True) else '❌'}\n"
                f"Use `economy shop view` for details"
            ),
            inline=False
        )
        
        # Reward settings
        rewards = eco_settings.get('rewards', {})
        embed.add_field(
            name="🎁 Rewards Configuration",
            value=(
                f"**Daily Reward:** {rewards.get('daily', 100)} coins\n"
                f"**Message Reward:** {rewards.get('message', 1)} coins\n"
                f"**Voice Reward:** {rewards.get('voice_per_minute', 2)} coins/min\n"
                f"**Level Up Multiplier:** {rewards.get('level_multiplier', 10)}x"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Server Economy Toggle
    @economy_settings.command(name='toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle_server_economy(self, ctx, enabled: bool = None):
        """Toggle server-specific economy on/off
        
        When enabled, users will have separate balances for this server.
        When disabled, the global BronxBot economy is used.
        """
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        server_economy = eco_settings.get('server_economy', {})
        
        if enabled is None:
            current_status = server_economy.get('enabled', False)
            embed = nextcord.Embed(
                title="🏦 Server Economy Status",
                color=0xf1c40f
            )
            embed.add_field(
                name="Current Status",
                value=f"Server Economy: {'✅ Enabled' if current_status else '❌ Disabled'}",
                inline=False
            )
            embed.add_field(
                name="What this means",
                value=(
                    "**Enabled:** Users have separate economy data for this server\n"
                    "**Disabled:** Users share the global BronxBot economy"
                ),
                inline=False
            )
            embed.add_field(
                name="Usage",
                value="`economy toggle true` - Enable server economy\n"
                      "`economy toggle false` - Use global economy",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        server_economy['enabled'] = enabled
        eco_settings['server_economy'] = server_economy
        await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
        
        if enabled:
            # Initialize server economy data if needed
            await self._initialize_server_economy(ctx.guild.id)
            
            embed = nextcord.Embed(
                title="✅ Server Economy Enabled",
                description=(
                    "Server-specific economy has been enabled!\n\n"
                    "**What this means:**\n"
                    "• Users will have separate balances for this server\n"
                    "• You can configure custom shop items\n"
                    "• Economy data is stored separately from global economy\n\n"
                    "**Next Steps:**\n"
                    "• Configure starting balance: `economy config balance <amount>`\n"
                    "• Add custom shop items: `economy shop add`\n"
                    "• Set up custom rewards: `economy rewards`"
                ),
                color=0x2ecc71
            )
        else:
            embed = nextcord.Embed(
                title="✅ Server Economy Disabled",
                description=(
                    "Server-specific economy has been disabled.\n"
                    "Users will now use the global BronxBot economy system."
                ),
                color=0x2ecc71
            )
        
        await ctx.send(embed=embed)

    @economy_settings.group(name='config', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def economy_config(self, ctx):
        """Configure economy settings"""
        embed = nextcord.Embed(
            title="⚙️ Economy Configuration",
            description="Configure various economy settings",
            color=0xf1c40f
        )
        embed.add_field(
            name="Commands",
            value=(
                "`config balance <amount>` - Set starting balance\n"
                "`config symbol <symbol>` - Set currency symbol\n"
                "`config sync <true/false>` - Toggle global sync\n"
                "`config view` - View current configuration"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @economy_config.command(name='balance')
    @commands.has_permissions(manage_guild=True)
    async def set_starting_balance(self, ctx, amount: int):
        """Set the starting balance for new users"""
        if amount < 0 or amount > 10000:
            return await ctx.send("❌ Starting balance must be between 0 and 10,000!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        server_economy = eco_settings.get('server_economy', {})
        
        server_economy['starting_balance'] = amount
        eco_settings['server_economy'] = server_economy
        await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
        
        embed = nextcord.Embed(
            title="✅ Starting Balance Updated",
            description=f"New users will now start with {amount} coins!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @economy_config.command(name='symbol')
    @commands.has_permissions(manage_guild=True)
    async def set_currency_symbol(self, ctx, symbol: str):
        """Set the currency symbol for this server"""
        if len(symbol) > 3:
            return await ctx.send("❌ Currency symbol cannot be longer than 3 characters!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        server_economy = eco_settings.get('server_economy', {})
        
        server_economy['currency_symbol'] = symbol
        eco_settings['server_economy'] = server_economy
        await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
        
        embed = nextcord.Embed(
            title="✅ Currency Symbol Updated",
            description=f"Currency symbol set to: {symbol}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    # Shop Management
    @economy_settings.group(name='shop', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def shop_settings(self, ctx):
        """Manage server shop settings"""
        embed = nextcord.Embed(
            title="🛒 Server Shop Management",
            description="Configure custom shop items for your server",
            color=0xf1c40f
        )
        embed.add_field(
            name="Commands",
            value=(
                "`shop view` - View current shop items\n"
                "`shop add` - Add a custom item to the shop\n"
                "`shop remove <item_id>` - Remove an item from the shop\n"
                "`shop edit <item_id>` - Edit an existing shop item\n"
                "`shop toggle` - Enable/disable the server shop"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @shop_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_shop(self, ctx):
        """View current server shop items"""
        settings = await db.get_guild_settings(ctx.guild.id)
        shop_settings = settings.get('economy', {}).get('shop', {})
        custom_items = shop_settings.get('custom_items', [])
        
        embed = nextcord.Embed(
            title="🛒 Server Shop Items",
            color=0xf1c40f
        )
        
        if not custom_items:
            embed.description = "No custom shop items configured.\nUse `economy shop add` to add items!"
            return await ctx.send(embed=embed)
        
        for i, item in enumerate(custom_items, 1):
            embed.add_field(
                name=f"{i}. {item.get('name', 'Unknown Item')}",
                value=(
                    f"**Price:** {item.get('price', 0)} coins\n"
                    f"**Type:** {item.get('type', 'item').title()}\n"
                    f"**Description:** {item.get('description', 'No description')}\n"
                    f"**Role Reward:** {'✅' if item.get('role_reward') else '❌'}"
                ),
                inline=True
            )
        
        embed.set_footer(text=f"Total custom items: {len(custom_items)}")
        await ctx.send(embed=embed)

    @shop_settings.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_shop_item(self, ctx):
        """Add a custom item to the server shop (Interactive)"""
        embed = nextcord.Embed(
            title="🛒 Add Shop Item",
            description="Let's create a custom shop item for your server!",
            color=0xf1c40f
        )
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            # Get item name
            embed.add_field(name="Step 1", value="What should this item be called?", inline=False)
            await ctx.send(embed=embed)
            
            name_msg = await self.bot.wait_for('message', check=check, timeout=60)
            item_name = name_msg.content
            
            # Get item price
            embed.clear_fields()
            embed.add_field(name="Step 2", value="How much should this item cost? (in coins)", inline=False)
            await ctx.send(embed=embed)
            
            price_msg = await self.bot.wait_for('message', check=check, timeout=60)
            try:
                item_price = int(price_msg.content)
                if item_price < 1:
                    return await ctx.send("❌ Item price must be at least 1 coin!")
            except ValueError:
                return await ctx.send("❌ Please enter a valid number for the price!")
            
            # Get item description
            embed.clear_fields()
            embed.add_field(name="Step 3", value="Enter a description for this item:", inline=False)
            await ctx.send(embed=embed)
            
            desc_msg = await self.bot.wait_for('message', check=check, timeout=60)
            item_description = desc_msg.content
            
            # Get item type
            embed.clear_fields()
            embed.add_field(
                name="Step 4", 
                value="What type of item is this?\n1. **Item** - Just for collection\n2. **Role** - Gives a role when purchased\n3. **Consumable** - Can be used/consumed",
                inline=False
            )
            await ctx.send(embed=embed)
            
            type_msg = await self.bot.wait_for('message', check=check, timeout=60)
            type_choice = type_msg.content.lower()
            
            if type_choice in ['1', 'item']:
                item_type = 'item'
                role_reward = None
            elif type_choice in ['2', 'role']:
                item_type = 'role'
                embed.clear_fields()
                embed.add_field(name="Role Selection", value="Which role should be given when this item is purchased? (mention the role)", inline=False)
                await ctx.send(embed=embed)
                
                role_msg = await self.bot.wait_for('message', check=check, timeout=60)
                if role_msg.role_mentions:
                    role_reward = role_msg.role_mentions[0].id
                else:
                    return await ctx.send("❌ Please mention a valid role!")
            elif type_choice in ['3', 'consumable']:
                item_type = 'consumable'
                role_reward = None
            else:
                return await ctx.send("❌ Please choose 1, 2, or 3!")
            
            # Create the item
            new_item = {
                'id': len(await self._get_shop_items(ctx.guild.id)) + 1,
                'name': item_name,
                'price': item_price,
                'description': item_description,
                'type': item_type,
                'role_reward': role_reward,
                'created_by': ctx.author.id,
                'created_at': ctx.message.created_at.isoformat()
            }
            
            # Save the item
            settings = await db.get_guild_settings(ctx.guild.id)
            eco_settings = settings.get('economy', {})
            shop_settings = eco_settings.get('shop', {})
            custom_items = shop_settings.get('custom_items', [])
            
            custom_items.append(new_item)
            shop_settings['custom_items'] = custom_items
            eco_settings['shop'] = shop_settings
            await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
            
            # Confirmation
            embed = nextcord.Embed(
                title="✅ Shop Item Added!",
                description=f"Successfully added **{item_name}** to the server shop!",
                color=0x2ecc71
            )
            embed.add_field(
                name="Item Details",
                value=(
                    f"**Name:** {item_name}\n"
                    f"**Price:** {item_price} coins\n"
                    f"**Type:** {item_type.title()}\n"
                    f"**Description:** {item_description}"
                ),
                inline=False
            )
            
            if role_reward:
                role = ctx.guild.get_role(role_reward)
                embed.add_field(name="Role Reward", value=role.mention if role else "Unknown Role", inline=False)
            
            await ctx.send(embed=embed)
            
        except asyncio.TimeoutError:
            await ctx.send("❌ Shop item creation timed out. Please try again.")

    @shop_settings.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_shop_item(self, ctx, item_id: int):
        """Remove an item from the server shop"""
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        shop_settings = eco_settings.get('shop', {})
        custom_items = shop_settings.get('custom_items', [])
        
        # Find and remove the item
        item_to_remove = None
        for item in custom_items:
            if item.get('id') == item_id:
                item_to_remove = item
                break
        
        if not item_to_remove:
            return await ctx.send(f"❌ No shop item found with ID {item_id}!")
        
        custom_items.remove(item_to_remove)
        shop_settings['custom_items'] = custom_items
        eco_settings['shop'] = shop_settings
        await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
        
        embed = nextcord.Embed(
            title="✅ Shop Item Removed",
            description=f"Successfully removed **{item_to_remove['name']}** from the server shop!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    # Rewards Configuration
    @economy_settings.group(name='rewards', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def rewards_settings(self, ctx):
        """Configure economy rewards"""
        embed = nextcord.Embed(
            title="🎁 Economy Rewards Configuration",
            description="Configure how users earn coins in your server",
            color=0xf1c40f
        )
        embed.add_field(
            name="Commands",
            value=(
                "`rewards daily <amount>` - Set daily reward amount\n"
                "`rewards message <amount>` - Set coins per message\n"
                "`rewards voice <amount>` - Set coins per minute in voice\n"
                "`rewards level <multiplier>` - Set level up reward multiplier\n"
                "`rewards view` - View current reward settings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @rewards_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_rewards(self, ctx):
        """View current reward settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        rewards = settings.get('economy', {}).get('rewards', {})
        
        embed = nextcord.Embed(
            title="🎁 Current Reward Settings",
            color=0xf1c40f
        )
        
        embed.add_field(
            name="💰 Reward Amounts",
            value=(
                f"**Daily Reward:** {rewards.get('daily', 100)} coins\n"
                f"**Message Reward:** {rewards.get('message', 1)} coins\n"
                f"**Voice Reward:** {rewards.get('voice_per_minute', 2)} coins/minute\n"
                f"**Level Up Multiplier:** {rewards.get('level_multiplier', 10)}x level"
            ),
            inline=False
        )
        
        # Show additional settings if they exist
        if rewards.get('bonus_roles'):
            role_bonuses = []
            for role_id, bonus in rewards['bonus_roles'].items():
                role = ctx.guild.get_role(int(role_id))
                role_name = role.mention if role else f"<@&{role_id}>"
                role_bonuses.append(f"{role_name}: +{bonus}%")
            
            embed.add_field(
                name="🎭 Role Bonuses",
                value='\n'.join(role_bonuses),
                inline=False
            )
        
        await ctx.send(embed=embed)

    @rewards_settings.command(name='daily')
    @commands.has_permissions(manage_guild=True)
    async def set_daily_reward(self, ctx, amount: int):
        """Set the daily reward amount"""
        if amount < 0 or amount > 1000:
            return await ctx.send("❌ Daily reward must be between 0 and 1,000 coins!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        eco_settings = settings.get('economy', {})
        rewards = eco_settings.get('rewards', {})
        
        rewards['daily'] = amount
        eco_settings['rewards'] = rewards
        await db.update_guild_settings(ctx.guild.id, {'economy': eco_settings})
        
        embed = nextcord.Embed(
            title="✅ Daily Reward Updated",
            description=f"Daily reward set to {amount} coins!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    async def _initialize_server_economy(self, guild_id: int):
        """Initialize server economy data"""
        settings = await db.get_guild_settings(guild_id)
        eco_settings = settings.get('economy', {})
        
        # Set default values if not already set
        if 'server_economy' not in eco_settings:
            eco_settings['server_economy'] = {}
        
        server_economy = eco_settings['server_economy']
        server_economy.setdefault('enabled', True)
        server_economy.setdefault('starting_balance', 1000)
        server_economy.setdefault('currency_symbol', '🪙')
        server_economy.setdefault('global_sync', False)
        
        if 'shop' not in eco_settings:
            eco_settings['shop'] = {
                'enabled': True,
                'include_global': True,
                'custom_items': []
            }
        
        if 'rewards' not in eco_settings:
            eco_settings['rewards'] = {
                'daily': 100,
                'message': 1,
                'voice_per_minute': 2,
                'level_multiplier': 10
            }
        
        await db.update_guild_settings(guild_id, {'economy': eco_settings})

    async def _get_shop_items(self, guild_id: int) -> List[Dict]:
        """Get all shop items for a guild"""
        settings = await db.get_guild_settings(guild_id)
        return settings.get('economy', {}).get('shop', {}).get('custom_items', [])

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "economy settings")

async def setup(bot):
    bot.add_cog(EconomySettings(bot))
