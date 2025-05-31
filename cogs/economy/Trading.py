from discord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import async_db as db
from typing import Dict, List, Optional, Tuple
from collections import Counter
import discord
import asyncio
import hashlib
from datetime import datetime, timedelta
import math
import random

class TradeOffer:
    def __init__(self, initiator_id: int, target_id: int, guild_id: int):
        self.initiator_id = initiator_id
        self.target_id = target_id
        self.guild_id = guild_id
        self.initiator_items = []
        self.initiator_currency = 0
        self.target_items = []
        self.target_currency = 0
        self.status = "pending"  # pending, accepted, cancelled, expired
        self.created_at = datetime.utcnow()
        self.expires_at = datetime.utcnow() + timedelta(minutes=10)
        self.trade_id = self._generate_trade_id()
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        data = f"{self.initiator_id}{self.target_id}{self.created_at.timestamp()}"
        return hashlib.md5(data.encode()).hexdigest()[:8].upper()
    
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at
    
    def get_total_value(self, side: str) -> int:
        """Calculate total value of one side of the trade"""
        if side == "initiator":
            return sum(item.get('value', 0) for item in self.initiator_items) + self.initiator_currency
        else:
            return sum(item.get('value', 0) for item in self.target_items) + self.target_currency
    
    def is_balanced(self, tolerance: float = 0.3) -> bool:
        """Check if trade is reasonably balanced"""
        initiator_value = self.get_total_value("initiator")
        target_value = self.get_total_value("target")
        
        if initiator_value == 0 and target_value == 0:
            return True
        
        if initiator_value == 0 or target_value == 0:
            return False
        
        ratio = abs(initiator_value - target_value) / max(initiator_value, target_value)
        return ratio <= tolerance

class TradeConfirmationView(discord.ui.View):
    def __init__(self, trade_offer: TradeOffer, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_offer = trade_offer
        self.bot = bot
        self.initiator_confirmed = False
        self.target_confirmed = False
        self.message = None
    
    @discord.ui.button(label="✅ Confirm Trade", style=discord.ButtonStyle.success)
    async def confirm_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id == self.trade_offer.initiator_id:
            self.initiator_confirmed = True
            await interaction.response.send_message("✅ You have confirmed the trade!", ephemeral=True)
        elif user_id == self.trade_offer.target_id:
            self.target_confirmed = True
            await interaction.response.send_message("✅ You have confirmed the trade!", ephemeral=True)
        else:
            return await interaction.response.send_message("❌ This trade doesn't involve you!", ephemeral=True)
        
        # Update the embed to show confirmation status
        await self._update_confirmation_status()
        
        # If both confirmed, execute the trade
        if self.initiator_confirmed and self.target_confirmed:
            await self._execute_trade()
    
    @discord.ui.button(label="❌ Cancel Trade", style=discord.ButtonStyle.danger)
    async def cancel_trade(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        
        if user_id not in [self.trade_offer.initiator_id, self.trade_offer.target_id]:
            return await interaction.response.send_message("❌ This trade doesn't involve you!", ephemeral=True)
        
        self.trade_offer.status = "cancelled"
        
        embed = discord.Embed(
            title="❌ Trade Cancelled",
            description=f"Trade #{self.trade_offer.trade_id} has been cancelled.",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    async def _update_confirmation_status(self):
        """Update the trade embed with confirmation status"""
        if not self.message:
            return
        
        initiator = self.bot.get_user(self.trade_offer.initiator_id)
        target = self.bot.get_user(self.trade_offer.target_id)
        
        embed = discord.Embed(
            title=f"🤝 Trade Confirmation #{self.trade_offer.trade_id}",
            color=0xffa500
        )
        
        # Initiator side
        initiator_status = "✅ Confirmed" if self.initiator_confirmed else "⏳ Waiting"
        initiator_items_text = self._format_trade_items(self.trade_offer.initiator_items, self.trade_offer.initiator_currency)
        
        embed.add_field(
            name=f"{initiator.display_name if initiator else 'Unknown'} offers: {initiator_status}",
            value=initiator_items_text or "Nothing",
            inline=False
        )
        
        # Target side
        target_status = "✅ Confirmed" if self.target_confirmed else "⏳ Waiting"
        target_items_text = self._format_trade_items(self.trade_offer.target_items, self.trade_offer.target_currency)
        
        embed.add_field(
            name=f"{target.display_name if target else 'Unknown'} offers: {target_status}",
            value=target_items_text or "Nothing",
            inline=False
        )
        
        # Trade balance check
        if self.trade_offer.is_balanced():
            embed.add_field(name="⚖️ Balance", value="✅ Fair trade", inline=True)
        else:
            embed.add_field(name="⚖️ Balance", value="⚠️ Unbalanced", inline=True)
        
        embed.set_footer(text="Both players must confirm to complete the trade • Trade expires in 5 minutes")
        
        try:
            await self.message.edit(embed=embed, view=self)
        except discord.NotFound:
            pass
    
    def _format_trade_items(self, items: list, currency: int) -> str:
        """Format items and currency for display"""
        parts = []
        
        if items:
            print(items)
            print(item_counts := Counter((item['name']) for item in items))
            item_counts = Counter((item['name']) for item in items)
            for item_name, count in item_counts.items():
                if count > 1:
                    parts.append(f"**{count}x** {item_name}")
                else:
                    parts.append(f"**{item_name}**")
        
        if currency > 0:
            parts.append(f"**{currency:,}** <:bronkbuk:1377389238290747582>")
        
        return "\n".join(parts) if parts else "Nothing"
    
    async def _execute_trade(self):
        """Execute the confirmed trade"""
        try:
            # Verify both users still have the items and currency
            if not await self.verify_trade_validity():  # Changed from _verify_trade_validity
                embed = discord.Embed(
                    title="❌ Trade Failed",
                    description="One or both users no longer have the required items or currency.",
                    color=0xff0000
                )
                await self.message.edit(embed=embed, view=None)
                return
            
            # Execute the trade
            success = await self._perform_trade_exchange()
            
            if success:
                # Log the trade
                await self._log_trade()
                
                embed = discord.Embed(
                    title="✅ Trade Completed!",
                    description=f"Trade #{self.trade_offer.trade_id} has been successfully completed!",
                    color=0x00ff00
                )
                
                initiator = self.bot.get_user(self.trade_offer.initiator_id)
                target = self.bot.get_user(self.trade_offer.target_id)
                
                if initiator and target:
                    embed.add_field(
                        name="Trade Summary",
                        value=f"**{initiator.display_name}** ↔️ **{target.display_name}**",
                        inline=False
                    )
                
                await self.message.edit(embed=embed, view=None)
            else:
                embed = discord.Embed(
                    title="❌ Trade Failed",
                    description="An error occurred while processing the trade.",
                    color=0xff0000
                )
                await self.message.edit(embed=embed, view=None)
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ Trade Error",
                description=f"An unexpected error occurred during the trade.\n```py\n{str(e)}\n```",
                color=0xff0000
            )
            await self.message.edit(embed=embed, view=None)
        
        self.stop()
    
    async def verify_trade_validity(self) -> bool:
        """Verify that both users still have what they're trading"""
        
        # Check initiator's items and currency
        initiator_inventory = await db.get_inventory(self.trade_offer.initiator_id, self.trade_offer.guild_id)
        initiator_balance = await db.get_wallet_balance(self.trade_offer.initiator_id, self.trade_offer.guild_id)
        
        # Only check currency if they're actually trading currency
        if self.trade_offer.initiator_currency > 0:
            if initiator_balance < self.trade_offer.initiator_currency:
                return False
        
        # Only check items if they're actually trading items
        if self.trade_offer.initiator_items:
            # Count required items for initiator
            required_items = Counter(item['id'] for item in self.trade_offer.initiator_items)
            available_items = Counter(item['id'] for item in initiator_inventory)
            for item_id, required_count in required_items.items():
                if available_items[item_id] < required_count:
                    return False
        
        # Check target's items and currency
        target_inventory = await db.get_inventory(self.trade_offer.target_id, self.trade_offer.guild_id)
        target_balance = await db.get_wallet_balance(self.trade_offer.target_id, self.trade_offer.guild_id)
        
        # Only check currency if they're actually trading currency
        if self.trade_offer.target_currency > 0:
            if target_balance < self.trade_offer.target_currency:
                return False
        
        # Only check items if they're actually trading items
        if self.trade_offer.target_items:
            # Count required items for target
            required_items = Counter(item['id'] for item in self.trade_offer.target_items)
            available_items = Counter(item['id'] for item in target_inventory)
            for item_id, required_count in required_items.items():
                if available_items[item_id] < required_count:
                    return False
        
        return True
    
    async def _perform_trade_exchange(self) -> bool:
        """Perform the actual item and currency exchange"""
        try:
            # Remove items from initiator, add to target
            for item in self.trade_offer.initiator_items:
                # Remove from initiator
                if not await db.remove_from_inventory(self.trade_offer.initiator_id, 
                                                self.trade_offer.guild_id, 
                                                item['id']):
                    return False
                
                # Add to target
                if not await db.add_to_inventory(self.trade_offer.target_id, 
                                            self.trade_offer.guild_id, 
                                            item):
                    # If adding fails, try to return item to initiator
                    await db.add_to_inventory(self.trade_offer.initiator_id, 
                                        self.trade_offer.guild_id, 
                                        item)
                    return False
            
            # Remove items from target, add to initiator
            for item in self.trade_offer.target_items:
                # Remove from target
                if not await db.remove_from_inventory(self.trade_offer.target_id, 
                                                self.trade_offer.guild_id, 
                                                item['id']):
                    return False
                
                # Add to initiator
                if not await db.add_to_inventory(self.trade_offer.initiator_id, 
                                            self.trade_offer.guild_id, 
                                            item):
                    # If adding fails, try to return item to target
                    await db.add_to_inventory(self.trade_offer.target_id, 
                                        self.trade_offer.guild_id, 
                                        item)
                    return False
            
            # Exchange currency
            if self.trade_offer.initiator_currency > 0:
                if not await db.update_wallet(self.trade_offer.initiator_id, 
                                        -self.trade_offer.initiator_currency, 
                                        self.trade_offer.guild_id):
                    return False
                if not await db.update_wallet(self.trade_offer.target_id, 
                                        self.trade_offer.initiator_currency, 
                                        self.trade_offer.guild_id):
                    # Refund if the second transfer fails
                    await db.update_wallet(self.trade_offer.initiator_id, 
                                        self.trade_offer.initiator_currency, 
                                        self.trade_offer.guild_id)
                    return False
            
            if self.trade_offer.target_currency > 0:
                if not await db.update_wallet(self.trade_offer.target_id, 
                                        -self.trade_offer.target_currency, 
                                        self.trade_offer.guild_id):
                    return False
                if not await db.update_wallet(self.trade_offer.initiator_id, 
                                        self.trade_offer.target_currency, 
                                        self.trade_offer.guild_id):
                    # Refund if the second transfer fails
                    await db.update_wallet(self.trade_offer.target_id, 
                                        self.trade_offer.target_currency, 
                                        self.trade_offer.guild_id)
                    return False
            
            return True
        except Exception:
            return False
    
    async def _log_trade(self):
        """Log the completed trade to database"""
        try:
            trade_log = {
                "trade_id": self.trade_offer.trade_id,
                "initiator_id": str(self.trade_offer.initiator_id),
                "target_id": str(self.trade_offer.target_id),
                "guild_id": str(self.trade_offer.guild_id),
                "initiator_items": self.trade_offer.initiator_items,
                "initiator_currency": self.trade_offer.initiator_currency,
                "target_items": self.trade_offer.target_items,
                "target_currency": self.trade_offer.target_currency,
                "completed_at": datetime.utcnow(),
                "initiator_value": self.trade_offer.get_total_value("initiator"),
                "target_value": self.trade_offer.get_total_value("target")
            }
            
            await db.db.trade_history.insert_one(trade_log)
        except Exception:
            pass  # Don't fail the trade if logging fails
    
    async def on_timeout(self):
        """Handle view timeout"""
        embed = discord.Embed(
            title="⏰ Trade Expired",
            description=f"Trade #{self.trade_offer.trade_id} has expired.",
            color=0x808080
        )
        
        try:
            if self.message:
                await self.message.edit(embed=embed, view=None)
        except discord.NotFound:
            pass

class TradeStats:
    def __init__(self, trading_cog):
        self.trading = trading_cog
    
    async def get_user_trade_stats(self, user_id: int, days: int = 30) -> dict:
        """Get trading statistics for a user"""
        try:
            start_date = datetime.utcnow() - timedelta(days=days)
            
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"initiator_id": str(user_id)},
                            {"target_id": str(user_id)}
                        ],
                        "completed_at": {"$gte": start_date}
                    }
                }
            ]
            
            trades = await db.db.trade_history.aggregate(pipeline).to_list(length=None)
            
            stats = {
                "total_trades": len(trades),
                "trades_initiated": len([t for t in trades if t["initiator_id"] == str(user_id)]),
                "trades_received": len([t for t in trades if t["target_id"] == str(user_id)]),
                "total_value_traded": 0,
                "most_traded_items": Counter(),
                "trading_partners": set()
            }
            
            for trade in trades:
                if trade["initiator_id"] == str(user_id):
                    stats["total_value_traded"] += trade.get("initiator_value", 0)
                    stats["trading_partners"].add(trade["target_id"])
                    for item in trade.get("initiator_items", []):
                        stats["most_traded_items"][item.get("name", "Unknown")] += 1
                else:
                    stats["total_value_traded"] += trade.get("target_value", 0)
                    stats["trading_partners"].add(trade["initiator_id"])
                    for item in trade.get("target_items", []):
                        stats["most_traded_items"][item.get("name", "Unknown")] += 1
            
            stats["unique_partners"] = len(stats["trading_partners"])
            return stats
            
        except Exception:
            return {
                "total_trades": 0,
                "trades_initiated": 0,
                "trades_received": 0,
                "total_value_traded": 0,
                "most_traded_items": Counter(),
                "unique_partners": 0
            }

class Trading(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_trades = {}  # trade_id -> TradeOffer
        self.stats = TradeStats(self)
        
        # Item value estimates (for balance checking)
        self.ITEM_VALUES = {
            "beginner_rod": 0,
            "advanced_rod": 500,
            "pro_bait": 50,
            "beginner_bait": 0,
            "vip": 10000,
            "color": 5000,
            "bank_upgrade": 2500
        }
    
    def get_item_value(self, item: dict) -> int:
        """Get estimated value of an item"""
        return self.ITEM_VALUES.get(item.get('id', ''), item.get('price', 0))
    
    @commands.group(name="trade", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def trade(self, ctx):
        """Trading system commands"""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🤝 Trading System",
                description="Trade items and currency with other players!",
                color=0x3498db
            )
            
            commands_list = [
                (f"`{ctx.prefix}trade offer @user`", "Start a trade with another user"),
                (f"`{ctx.prefix}trade add item <item_id> [amount]`", "Add items to your trade offer"),
                (f"`{ctx.prefix}trade add money <amount>`", "Add currency to your trade offer"),
                (f"`{ctx.prefix}trade remove item <item_id> [amount]`", "Remove items from trade offer"),
                (f"`{ctx.prefix}trade remove money <amount>`", "Remove currency from trade offer"),
                (f"`{ctx.prefix}trade show`", "Show current trade offer"),
                (f"`{ctx.prefix}trade send`", "Send the trade offer to the other user"),
                (f"`{ctx.prefix}trade cancel`", "Cancel your current trade"),
                (f"`{ctx.prefix}trade history [user]`", "View trade history"),
                (f"`{ctx.prefix}trade stats [user]`", "View trading statistics")
            ]
            
            for command, description in commands_list:
                embed.add_field(name=command, value=description, inline=False)
            
            embed.set_footer(text="💡 Tip: You can trade items from your inventory and currency!")
            await ctx.reply(embed=embed)
    
    @trade.command(name="offer")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def trade_offer(self, ctx, target: discord.Member = None):
        """Start a trade offer with another user"""
        if not target:
            return await ctx.reply(f"❌ Please specify who you want to trade with!\nUsage: `{ctx.prefix}trade offer @user`")
        
        if target.id == ctx.author.id:
            return await ctx.reply("❌ You can't trade with yourself!")
        
        if target.bot:
            return await ctx.reply("❌ You can't trade with bots!")
        
        # Check if user already has an active trade
        user_trade = None
        for trade in self.active_trades.values():
            if ctx.author.id in [trade.initiator_id, trade.target_id] and trade.status == "pending":
                return await ctx.reply(f"❌ You already have an active trade with {target.mention}! Use `{ctx.prefix}trade cancel` to cancel it first, or, ask them to accept your current trade.")
        # Create new trade offer
        trade_offer = TradeOffer(ctx.author.id, target.id, ctx.guild.id)
        self.active_trades[trade_offer.trade_id] = trade_offer
        
        embed = discord.Embed(
            title="🤝 New Trade Created",
            description=f"Trade #{trade_offer.trade_id} created with {target.mention}!",
            color=0x00ff00
        )
        
        embed.add_field(
            name="Next Steps:",
            value=f"1. Use `{ctx.prefix}trade add item <item_id>` to add items\n"
                  f"2. Use `{ctx.prefix}trade add money <amount>` to add currency\n"
                  f"3. Use `{ctx.prefix}trade send` when ready to send the offer",
            inline=False
        )
        
        embed.set_footer(text=f"Trade expires in 10 minutes if not sent • Trade ID: {trade_offer.trade_id}")
        await ctx.reply(embed=embed)
    
    @trade.group(name="add", invoke_without_command=True)
    async def trade_add(self, ctx):
        """Add items or currency to your trade offer"""
        await ctx.reply(f"Use `{ctx.prefix}trade add item <item_id>` or `{ctx.prefix}trade add money <amount>`")
    
    @trade_add.command(name="item")
    async def trade_add_item(self, ctx, item_id: str, amount: int = 1):
        """Add items to your trade offer"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        if amount <= 0 or amount > 50:
            return await ctx.reply("❌ Amount must be between 1 and 50.")
        
        # Check if user has the items
        inventory = await db.get_inventory(ctx.author.id, ctx.guild.id)
        
        # Find the specific item and its quantity
        item_details = None
        available_quantity = 0
        for item in inventory:
            if item.get('id') == item_id:
                item_details = item
                available_quantity = item.get('quantity', 1)
                break
        
        if not item_details:
            return await ctx.reply(f"❌ Item `{item_id}` not found in your inventory!")
        
        if available_quantity < amount:
            return await ctx.reply(f"❌ You only have {available_quantity} of that item! (Requested: {amount})")
        
        # Add items to trade offer
        for _ in range(amount):
            trade_item = item_details.copy()
            trade_item['value'] = self.get_item_value(trade_item)
            
            if ctx.author.id == trade_offer.initiator_id:
                trade_offer.initiator_items.append(trade_item)
            else:
                trade_offer.target_items.append(trade_item)
        
        item_name = item_details.get('name', item_id.replace('_', ' ').title())
        embed = discord.Embed(
            title="✅ Items Added to Trade",
            description=f"Added **{amount}x {item_name}** to trade #{trade_offer.trade_id}",
            color=0x00ff00
        )
        
        await ctx.reply(embed=embed)
    
    @trade_add.command(name="money", aliases=["currency", "coins"])
    async def trade_add_money(self, ctx, amount: int):
        """Add currency to your trade offer"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        if amount <= 0:
            return await ctx.reply("❌ Amount must be positive!")
        
        if amount > 1000000:
            return await ctx.reply("❌ Amount too large! Maximum 1,000,000 per trade.")
        
        # Check if user has enough currency
        balance = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        current_offer = trade_offer.initiator_currency if ctx.author.id == trade_offer.initiator_id else trade_offer.target_currency
        
        if balance < current_offer + amount:
            return await ctx.reply(f"❌ Insufficient funds! You have {balance:,} {self.currency}, but need {current_offer + amount:,}")
        
        # Add currency to trade offer
        if ctx.author.id == trade_offer.initiator_id:
            trade_offer.initiator_currency += amount
        else:
            trade_offer.target_currency += amount
        
        embed = discord.Embed(
            title="✅ Currency Added to Trade",
            description=f"Added **{amount:,}** {self.currency} to trade #{trade_offer.trade_id}",
            color=0x00ff00
        )
        
        await ctx.reply(embed=embed)
    
    @trade.group(name="remove", invoke_without_command=True)
    async def trade_remove(self, ctx):
        """Remove items or currency from your trade offer"""
        await ctx.reply(f"Use `{ctx.prefix}trade remove item <item_id>` or `{ctx.prefix}trade remove money <amount>`")
    
    @trade_remove.command(name="item")
    async def trade_remove_item(self, ctx, item_id: str, amount: int = 1):
        """Remove items from your trade offer"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        items_list = trade_offer.initiator_items if ctx.author.id == trade_offer.initiator_id else trade_offer.target_items
        
        # Count items in trade offer
        offered_items = Counter(item['id'] for item in items_list)
        
        if offered_items[item_id] < amount:
            return await ctx.reply(f"❌ You only have {offered_items[item_id]} of that item in your trade offer!")
        
        # Remove items from trade offer
        removed_count = 0
        for i in range(len(items_list) - 1, -1, -1):
            if items_list[i]['id'] == item_id and removed_count < amount:
                items_list.pop(i)
                removed_count += 1
        
        item_name = item_id.replace('_', ' ').title()
        embed = discord.Embed(
            title="✅ Items Removed from Trade",
            description=f"Removed **{removed_count}x {item_name}** from trade #{trade_offer.trade_id}",
            color=0x00ff00
        )
        
        await ctx.reply(embed=embed)
    
    @trade_remove.command(name="money", aliases=["currency", "coins"])
    async def trade_remove_money(self, ctx, amount: int):
        """Remove currency from your trade offer"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        if amount <= 0:
            return await ctx.reply("❌ Amount must be positive!")
        
        current_offer = trade_offer.initiator_currency if ctx.author.id == trade_offer.initiator_id else trade_offer.target_currency
        
        if current_offer < amount:
            return await ctx.reply(f"❌ You only have {current_offer:,} {self.currency} in your trade offer!")
        
        # Remove currency from trade offer
        if ctx.author.id == trade_offer.initiator_id:
            trade_offer.initiator_currency -= amount
        else:
            trade_offer.target_currency -= amount
        
        embed = discord.Embed(
            title="✅ Currency Removed from Trade",
            description=f"Removed **{amount:,}** {self.currency} from trade #{trade_offer.trade_id}",
            color=0x00ff00
        )
        
        await ctx.reply(embed=embed)
    
    @trade.command(name="show", aliases=["view", "display"])
    async def trade_show(self, ctx):
        """Show your current trade offer"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        initiator = self.bot.get_user(trade_offer.initiator_id)
        target = self.bot.get_user(trade_offer.target_id)
        
        embed = discord.Embed(
            title=f"🤝 Trade Offer #{trade_offer.trade_id}",
            color=0x3498db
        )
        
        # Show initiator's offer
        initiator_items = self._format_trade_items(trade_offer.initiator_items, trade_offer.initiator_currency)
        embed.add_field(
            name=f"{initiator.display_name if initiator else 'Unknown'} offers:",
            value=initiator_items or "Nothing",
            inline=False
        )
        
        # Show target's offer
        target_items = self._format_trade_items(trade_offer.target_items, trade_offer.target_currency)
        embed.add_field(
            name=f"{target.display_name if target else 'Unknown'} offers:",
            value=target_items or "Nothing",
            inline=False
        )
        
        # Show trade balance
        if trade_offer.is_balanced():
            embed.add_field(name="⚖️ Balance", value="✅ Fair trade", inline=True)
        else:
            embed.add_field(name="⚖️ Balance", value="⚠️ Unbalanced", inline=True)
        
        # Show expiration time
        # Show expiration time
        time_left = trade_offer.expires_at - datetime.utcnow()
        minutes_left = max(0, int(time_left.total_seconds() / 60))
        
        embed.add_field(name="⏰ Time Left", value=f"{minutes_left} minutes", inline=True)
        embed.add_field(name="📊 Status", value=trade_offer.status.title(), inline=True)
        
        embed.set_footer(text=f"Use '{ctx.prefix}trade send' to send this offer")
        
        await ctx.reply(embed=embed)
    
    @trade.command(name="send")
    async def trade_send(self, ctx):
        """Send your trade offer to the other user"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        if trade_offer.is_expired():
            self._cleanup_expired_trade(trade_offer.trade_id)
            return await ctx.reply("❌ Your trade offer has expired!")
        
        # Only the initiator can send the initial offer
        if ctx.author.id != trade_offer.initiator_id:
            return await ctx.reply("❌ Only the trade initiator can send the offer!")
        
        # Check if the offer has any items or currency
        has_items = len(trade_offer.initiator_items) > 0 or trade_offer.initiator_currency > 0
        if not has_items:
            return await ctx.reply("❌ You need to add items or currency to your trade offer first!")
        
        # Create confirmation view
        view = TradeConfirmationView(trade_offer, self.bot)
        
        initiator = self.bot.get_user(trade_offer.initiator_id)
        target = self.bot.get_user(trade_offer.target_id)
        
        embed = discord.Embed(
            title=f"🤝 Trade Offer #{trade_offer.trade_id}",
            description=f"{initiator.mention} wants to trade with {target.mention}!",
            color=0xffa500
        )
        
        # Show what initiator is offering
        initiator_items = self._format_trade_items(trade_offer.initiator_items, trade_offer.initiator_currency)
        embed.add_field(
            name=f"{initiator.display_name if initiator else 'Unknown'} offers:",
            value=initiator_items or "Nothing",
            inline=False
        )
        
        # Show placeholder for target's offer
        embed.add_field(
            name=f"{target.display_name if target else 'Unknown'} offers:",
            value="*Waiting for response...*",
            inline=False
        )
        
        # Show trade balance
        embed.add_field(name="⚖️ Balance", value="⚠️ Waiting for response", inline=True)
        
        embed.set_footer(text="Both players can add items and currency • Use the buttons to confirm or cancel")
        
        message = await ctx.reply(f"{target.mention}", embed=embed, view=view)
        view.message = message
        
        # Update trade status
        trade_offer.status = "sent"
    
    @trade.command(name="cancel")
    async def trade_cancel(self, ctx):
        """Cancel your current trade"""
        trade_offer = self._get_user_active_trade(ctx.author.id)
        if not trade_offer:
            return await ctx.reply(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` to start one.")
        
        trade_offer.status = "cancelled"
        self._cleanup_expired_trade(trade_offer.trade_id)
        
        embed = discord.Embed(
            title="❌ Trade Cancelled",
            description=f"Trade #{trade_offer.trade_id} has been cancelled.",
            color=0xff0000
        )
        
        await ctx.reply(embed=embed)
    
    @trade.command(name="history")
    async def trade_history(self, ctx, user: discord.Member = None):
        """View trade history for yourself or another user"""
        target_user = user or ctx.author
        
        try:
            # Get recent trades from database
            recent_trades = await db.db.trade_history.find({
                "$or": [
                    {"initiator_id": str(target_user.id)},
                    {"target_id": str(target_user.id)}
                ]
            }).sort("completed_at", -1).limit(10).to_list(length=10)
            
            if not recent_trades:
                return await ctx.reply(f"📊 {target_user.display_name} has no trade history.")
            
            embed = discord.Embed(
                title=f"📊 Trade History - {target_user.display_name}",
                color=0x3498db
            )
            
            for trade in recent_trades:
                initiator_id = int(trade["initiator_id"])
                target_id = int(trade["target_id"])
                
                initiator = self.bot.get_user(initiator_id)
                target_user_obj = self.bot.get_user(target_id)
                
                # Determine if this user was initiator or target
                if target_user.id == initiator_id:
                    partner = target_user_obj
                    role = "Initiated"
                else:
                    partner = initiator
                    role = "Received"
                
                partner_name = partner.display_name if partner else "Unknown User"
                
                # Format trade details
                completed_at = trade["completed_at"].strftime("%m/%d/%Y")
                trade_value = trade.get("initiator_value", 0) if target_user.id == initiator_id else trade.get("target_value", 0)
                
                embed.add_field(
                    name=f"Trade #{trade['trade_id'][:6]}... - {role}",
                    value=f"**Partner:** {partner_name}\n**Value:** {trade_value:,} {self.currency}\n**Date:** {completed_at}",
                    inline=True
                )
            
            embed.set_footer(text=f"Showing last {len(recent_trades)} trades")
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply("❌ Error retrieving trade history.")
    
    @trade.command(name="stats")
    async def trade_stats(self, ctx, user: discord.Member = None):
        """View trading statistics for yourself or another user"""
        target_user = user or ctx.author
        
        try:
            stats = await self.stats.get_user_trade_stats(target_user.id)
            
            embed = discord.Embed(
                title=f"📈 Trading Statistics - {target_user.display_name}",
                color=0x3498db
            )
            
            # Basic stats
            embed.add_field(
                name="📊 Trade Summary (Last 30 Days)",
                value=f"**Total Trades:** {stats['total_trades']}\n"
                      f"**Trades Initiated:** {stats['trades_initiated']}\n"
                      f"**Trades Received:** {stats['trades_received']}\n"
                      f"**Unique Partners:** {stats['unique_partners']}",
                inline=False
            )
            
            # Value stats
            embed.add_field(
                name="💰 Value Traded",
                value=f"**Total Value:** {stats['total_value_traded']:,} {self.currency}",
                inline=True
            )
            
            # Most traded items
            if stats['most_traded_items']:
                top_items = stats['most_traded_items'].most_common(3)
                items_text = "\n".join([f"**{count}x** {name}" for name, count in top_items])
                embed.add_field(
                    name="🔄 Most Traded Items",
                    value=items_text,
                    inline=True
                )
            
            # Trading activity level
            if stats['total_trades'] > 0:
                avg_per_day = stats['total_trades'] / 30
                if avg_per_day >= 1:
                    activity = "🔥 Very Active"
                elif avg_per_day >= 0.5:
                    activity = "📈 Active"
                elif avg_per_day >= 0.1:
                    activity = "📊 Moderate"
                else:
                    activity = "📉 Low"
                
                embed.add_field(
                    name="🎯 Activity Level",
                    value=activity,
                    inline=True
                )
            
            if stats['total_trades'] == 0:
                embed.description = "No trading activity in the last 30 days."
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply("❌ Error retrieving trading statistics.")
    
    @trade.command(name="leaderboard", aliases=["lb", "top"])
    async def trade_leaderboard(self, ctx):
        """Show top traders in the server"""
        try:
            # Get trade stats for all users in the guild
            pipeline = [
                {
                    "$match": {
                        "guild_id": str(ctx.guild.id),
                        "completed_at": {"$gte": datetime.utcnow() - timedelta(days=30)}
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "trades": {"$push": "$$ROOT"}
                    }
                }
            ]
            
            result = await db.db.trade_history.aggregate(pipeline).to_list(length=1)
            
            if not result or not result[0].get("trades"):
                return await ctx.reply("📊 No trading activity found in this server.")
            
            trades = result[0]["trades"]
            
            # Calculate stats per user
            user_stats = {}
            for trade in trades:
                for user_id in [trade["initiator_id"], trade["target_id"]]:
                    if user_id not in user_stats:
                        user_stats[user_id] = {"trades": 0, "value": 0}
                    
                    user_stats[user_id]["trades"] += 1
                    
                    if user_id == trade["initiator_id"]:
                        user_stats[user_id]["value"] += trade.get("initiator_value", 0)
                    else:
                        user_stats[user_id]["value"] += trade.get("target_value", 0)
            
            # Sort by total trades
            sorted_users = sorted(user_stats.items(), key=lambda x: x[1]["trades"], reverse=True)[:10]
            
            embed = discord.Embed(
                title="🏆 Trading Leaderboard (Last 30 Days)",
                color=0xffd700
            )
            
            for i, (user_id, stats) in enumerate(sorted_users, 1):
                user = self.bot.get_user(int(user_id))
                username = user.display_name if user else "Unknown User"
                
                # Determine medal emoji
                if i == 1:
                    medal = "🥇"
                elif i == 2:
                    medal = "🥈"
                elif i == 3:
                    medal = "🥉"
                else:
                    medal = f"#{i}"
                
                embed.add_field(
                    name=f"{medal} {username}",
                    value=f"**{stats['trades']}** trades\n**{stats['value']:,}** {self.currency} traded",
                    inline=True
                )
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply("❌ Error retrieving leaderboard data.")
    
    def _get_user_active_trade(self, user_id: int) -> Optional[TradeOffer]:
        """Get user's active trade if any"""
        for trade in self.active_trades.values():
            if user_id in [trade.initiator_id, trade.target_id] and trade.status in ["pending", "sent"]:
                return trade
        return None
    
    def _format_trade_items(self, items: list, currency: int) -> str:
        """Format items and currency for display"""
        parts = []
        
        if items:
            item_counts = Counter(item['name'] for item in items)
            for item_name, count in item_counts.items():
                if count > 1:
                    parts.append(f"**{count}x** {item_name}")
                else:
                    parts.append(f"**{item_name}**")
        
        if currency > 0:
            parts.append(f"**{currency:,}** {self.currency}")
        
        return "\n".join(parts) if parts else "Nothing"
    
    def _cleanup_expired_trade(self, trade_id: str):
        """Remove expired trade from active trades"""
        if trade_id in self.active_trades:
            del self.active_trades[trade_id]
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Clean up expired trades on bot ready"""
        await self._cleanup_expired_trades()
    
    async def _cleanup_expired_trades(self):
        """Clean up all expired trades"""
        expired_trades = []
        for trade_id, trade in self.active_trades.items():
            if trade.is_expired():
                expired_trades.append(trade_id)
        
        for trade_id in expired_trades:
            self._cleanup_expired_trade(trade_id)
    
    @trade.error
    async def trade_error(self, ctx, error):
        """Handle trade command errors"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.reply(f"⏳ Please wait {error.retry_after:.1f} seconds before using this command again.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.reply(f"❌ Missing required argument. Use `{ctx.prefix}help trade` for usage information.")
        else:
            await ctx.reply("❌ An error occurred while processing your trade command.")
            self.logger.error(f"Trade command error: {error}")

async def setup(bot):
    await bot.add_cog(Trading(bot))