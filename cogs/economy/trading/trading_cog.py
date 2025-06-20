"""
Main Trading Cog
Core trading commands and functionality.
"""

import nextcord
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import AsyncDatabase
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from typing import Dict, List, Optional, Union
import asyncio
from datetime import datetime, timedelta

# Import modular components
from .constants import ITEM_VALUES, TRADE_EMOJIS
from .trade_offer import ModernTradeOffer
from .trading_views import TradeConfirmationView, QuickTradeView
from .trading_utils import TradeStats, TradeValidator, TradeFormatter

db = AsyncDatabase.get_instance()

class Trading(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_trades = {}  # trade_id -> TradeOffer
        self.stats = TradeStats(self)
        self.validator = TradeValidator(ITEM_VALUES)
    
    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        # Check if user has accepted ToS
        if not await check_tos_acceptance(ctx.author.id):
            await prompt_tos_acceptance(ctx)
            return False
        return True

    def get_item_value(self, item: dict) -> int:
        """Get estimated value of an item"""
        return ITEM_VALUES.get(item.get('id', ''), item.get('price', 0))
    
    @commands.group(name="trade", invoke_without_command=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def trade(self, ctx):
        """🤝 Advanced Trading System - Trade items, currency, and more!"""
        if ctx.invoked_subcommand is None:
            embed = nextcord.Embed(
                title="🤝 Advanced Trading System",
                description="Trade items and currency with other players safely and efficiently!",
                color=0x3498db
            )
            
            # Core Commands
            embed.add_field(
                name="📝 **Basic Commands**",
                value=f"`{ctx.prefix}trade offer @user` - Start a trade\n"
                      f"`{ctx.prefix}trade add item <item> [amount]` - Add items\n"
                      f"`{ctx.prefix}trade add money <amount>` - Add currency\n"
                      f"`{ctx.prefix}trade send` - Send offer to other user",
                inline=False
            )
            
            # Management Commands
            embed.add_field(
                name="⚙️ **Management**",
                value=f"`{ctx.prefix}trade show` - View current trade\n"
                      f"`{ctx.prefix}trade remove item/money` - Remove items\n"
                      f"`{ctx.prefix}trade cancel` - Cancel trade\n"
                      f"`{ctx.prefix}trade note <message>` - Add trade note",
                inline=False
            )
            
            # Advanced Features
            embed.add_field(
                name="🚀 **Advanced Features**",
                value=f"`{ctx.prefix}trade quick @user <item> [amount]` - Quick trade\n"
                      f"`{ctx.prefix}trade auto on/off` - Auto-accept balanced trades\n"
                      f"`{ctx.prefix}trade value <item>` - Check item value\n"
                      f"`{ctx.prefix}trade market` - View trade marketplace",
                inline=False
            )
            
            # Stats & History
            embed.add_field(
                name="📊 **Statistics**",
                value=f"`{ctx.prefix}trade history [user]` - Trade history\n"
                      f"`{ctx.prefix}trade stats [user]` - Trading stats\n"
                      f"`{ctx.prefix}trade leaderboard` - Top traders",
                inline=False
            )
            
            embed.add_field(
                name="🛡️ **Safety Features**",
                value="• Automatic balance checking\n"
                      "• Risk assessment warnings\n"
                      "• Trade confirmation system\n"
                      "• Fraud protection",
                inline=False
            )
            
            embed.set_footer(text="💡 Use 'trade help <command>' for detailed help on any command!")
            await ctx.send(embed=embed)
    
    @trade.command(name="offer")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def trade_offer(self, ctx, target: nextcord.Member):
        """Start a new trade offer with another user"""
        if target.id == ctx.author.id:
            return await ctx.send("❌ You can't trade with yourself!")
        
        if target.bot:
            return await ctx.send("❌ You can't trade with bots!")
        
        # Check if user already has an active trade
        existing_trade = None
        for trade_id, trade in self.active_trades.items():
            if trade.initiator_id == ctx.author.id or trade.target_id == ctx.author.id:
                existing_trade = trade
                break
        
        if existing_trade:
            return await ctx.send(f"❌ You already have an active trade! Use `{ctx.prefix}trade cancel` first.")
        
        # Create new trade offer
        trade_offer = ModernTradeOffer(ctx.author.id, target.id, ctx.guild.id)
        self.active_trades[trade_offer.trade_id] = trade_offer
        
        embed = nextcord.Embed(
            title=f"🤝 Trade Started #{trade_offer.trade_id}",
            description=f"Trade offer created between {ctx.author.mention} and {target.mention}!\n\n"
                       f"Use `{ctx.prefix}trade add item <item>` to add items\n"
                       f"Use `{ctx.prefix}trade add money <amount>` to add currency\n"
                       f"Use `{ctx.prefix}trade send` when ready to send the offer",
            color=0x3498db
        )
        
        await ctx.send(embed=embed)
    
    @trade.group(name="add", invoke_without_command=True)
    async def trade_add(self, ctx):
        """Add items or currency to your current trade"""
        await ctx.send_help(ctx.command)
    
    @trade_add.command(name="item")
    async def trade_add_item(self, ctx, item_name: str, amount: int = 1):
        """Add an item to your trade offer"""
        # Find active trade
        active_trade = self._get_user_active_trade(ctx.author.id)
        if not active_trade:
            return await ctx.send(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` first.")
        
        if active_trade.status != "drafting":
            return await ctx.send("❌ You can't modify a trade that's already been sent!")
        
        # Validate item exists in user's inventory (simplified)
        # This would integrate with actual inventory system
        item_data = {
            'id': item_name.lower(),
            'name': item_name.title(),
            'quantity': amount,
            'value': self.get_item_value({'id': item_name.lower()})
        }
        
        # Add to appropriate side
        if active_trade.initiator_id == ctx.author.id:
            active_trade.initiator_items.append(item_data)
        else:
            active_trade.target_items.append(item_data)
        
        embed = nextcord.Embed(
            title="✅ Item Added",
            description=f"Added **{amount}x {item_name.title()}** to your trade offer!",
            color=0x00ff00
        )
        
        await ctx.send(embed=embed)
    
    @trade_add.command(name="money", aliases=["currency", "cash"])
    async def trade_add_money(self, ctx, amount: int):
        """Add currency to your trade offer"""
        if amount <= 0:
            return await ctx.send("❌ Amount must be positive!")
        
        # Find active trade
        active_trade = self._get_user_active_trade(ctx.author.id)
        if not active_trade:
            return await ctx.send(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` first.")
        
        if active_trade.status != "drafting":
            return await ctx.send("❌ You can't modify a trade that's already been sent!")
        
        # Check balance
        balance = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        if balance < amount:
            return await ctx.send(f"❌ Insufficient funds! You have {balance:,} but need {amount:,}")
        
        # Add to appropriate side
        if active_trade.initiator_id == ctx.author.id:
            active_trade.initiator_currency += amount
        else:
            active_trade.target_currency += amount
        
        embed = nextcord.Embed(
            title="✅ Currency Added",
            description=f"Added **{amount:,}** {self.currency} to your trade offer!",
            color=0x00ff00
        )
        
        await ctx.send(embed=embed)
    
    @trade.command(name="show", aliases=["view", "display"])
    async def trade_show(self, ctx):
        """Show your current trade offer"""
        active_trade = self._get_user_active_trade(ctx.author.id)
        if not active_trade:
            return await ctx.send(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` first.")
        
        embed = TradeFormatter.format_trade_embed(active_trade, self.bot)
        await ctx.send(embed=embed)
    
    @trade.command(name="send")
    async def trade_send(self, ctx):
        """Send your trade offer to the other user"""
        active_trade = self._get_user_active_trade(ctx.author.id)
        if not active_trade:
            return await ctx.send(f"❌ You don't have an active trade! Use `{ctx.prefix}trade offer @user` first.")
        
        if active_trade.status != "drafting":
            return await ctx.send("❌ This trade has already been sent!")
        
        if active_trade.initiator_id != ctx.author.id:
            return await ctx.send("❌ Only the trade initiator can send the offer!")
        
        # Validate trade
        is_valid, issues = self.validator.validate_trade_contents(active_trade)
        if not is_valid:
            return await ctx.send(f"❌ Trade validation failed:\n" + "\n".join(f"• {issue}" for issue in issues))
        
        # Update trade status
        active_trade.status = "pending"
        active_trade.assess_risk()
        
        # Create trade embed and view
        embed = TradeFormatter.format_trade_embed(active_trade, self.bot)
        view = QuickTradeView(active_trade, self.bot)
        
        # Send to target user
        target = self.bot.get_user(active_trade.target_id)
        if target:
            try:
                dm_message = await target.send(
                    f"🤝 You have received a trade offer from **{ctx.author.display_name}**!",
                    embed=embed,
                    view=view
                )
                view.message = dm_message
                
                await ctx.send(f"✅ Trade offer sent to {target.mention}!")
                
            except nextcord.Forbidden:
                # Fallback to channel if DMs are disabled
                message = await ctx.send(
                    f"{target.mention}, you have received a trade offer!",
                    embed=embed,
                    view=view
                )
                view.message = message
        else:
            return await ctx.send("❌ Could not find the target user!")
    
    @trade.command(name="cancel")
    async def trade_cancel(self, ctx):
        """Cancel your current trade"""
        active_trade = self._get_user_active_trade(ctx.author.id)
        if not active_trade:
            return await ctx.send("❌ You don't have an active trade to cancel!")
        
        # Remove from active trades
        if active_trade.trade_id in self.active_trades:
            del self.active_trades[active_trade.trade_id]
        
        embed = nextcord.Embed(
            title="❌ Trade Cancelled",
            description=f"Trade #{active_trade.trade_id} has been cancelled.",
            color=0xff0000
        )
        
        await ctx.send(embed=embed)
    
    @trade.command(name="history")
    async def trade_history(self, ctx, user: nextcord.Member = None):
        """View trade history for yourself or another user"""
        target_user = user or ctx.author
        
        try:
            trades = await db.get_user_trade_history(target_user.id, ctx.guild.id)
            embed = TradeFormatter.format_trade_history_embed(trades, target_user, self.bot)
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error fetching trade history: {e}")
            await ctx.send("❌ Error fetching trade history.")
    
    @trade.command(name="stats")
    async def trade_stats(self, ctx, user: nextcord.Member = None):
        """View detailed trading statistics"""
        target_user = user or ctx.author
        
        try:
            stats = await self.stats.get_user_stats(target_user.id, ctx.guild.id)
            
            embed = nextcord.Embed(
                title=f"📊 {target_user.display_name}'s Trading Stats",
                color=0x3498db
            )
            
            embed.add_field(
                name="📈 **General Stats**",
                value=f"**Total Trades:** {stats['total_trades']:,}\n"
                      f"**Trades Initiated:** {stats['trades_initiated']:,}\n"
                      f"**Trades Received:** {stats['trades_received']:,}\n"
                      f"**Unique Partners:** {stats['unique_partners']:,}",
                inline=True
            )
            
            embed.add_field(
                name="💰 **Value Stats**",
                value=f"**Total Value Traded:** {stats['total_value_traded']:,} {self.currency}\n"
                      f"**Average Trade Value:** {stats['total_value_traded'] // max(stats['total_trades'], 1):,} {self.currency}",
                inline=True
            )
            
            if stats['most_traded_items']:
                top_items = list(stats['most_traded_items'].most_common(5))
                items_text = "\n".join(f"**{item}:** {count}x" for item, count in top_items)
                embed.add_field(
                    name="🎯 **Most Traded Items**",
                    value=items_text,
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error fetching trade stats: {e}")
            await ctx.send("❌ Error fetching trade statistics.")
    
    @trade.command(name="leaderboard", aliases=["lb", "top"])
    async def trade_leaderboard(self, ctx):
        """View the trading leaderboard"""
        try:
            leaderboard = await self.stats.get_guild_leaderboard(ctx.guild.id)
            
            if not leaderboard:
                return await ctx.send("❌ No trading data found for this server.")
            
            embed = nextcord.Embed(
                title="🏆 Trading Leaderboard",
                description="Top traders in this server",
                color=0xffd700
            )
            
            for i, entry in enumerate(leaderboard, 1):
                user = self.bot.get_user(entry['user_id'])
                stats = entry['stats']
                
                if user:
                    embed.add_field(
                        name=f"{i}. {user.display_name}",
                        value=f"**Trades:** {stats['total_trades']}\n"
                              f"**Value:** {stats['total_value_traded']:,} {self.currency}",
                        inline=True
                    )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error fetching leaderboard: {e}")
            await ctx.send("❌ Error fetching trading leaderboard.")
    
    def _get_user_active_trade(self, user_id: int) -> Optional[ModernTradeOffer]:
        """Get a user's active trade if any"""
        for trade in self.active_trades.values():
            if trade.initiator_id == user_id or trade.target_id == user_id:
                if not trade.is_expired():
                    return trade
                else:
                    # Clean up expired trade
                    if trade.trade_id in self.active_trades:
                        del self.active_trades[trade.trade_id]
        return None
    
    @trade.error
    async def trade_error(self, ctx, error):
        """Handle trade command errors"""
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"⏰ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument provided.")
        else:
            self.logger.error(f"Trade command error: {error}")
            await ctx.send("❌ An error occurred while processing the command.")


async def setup(bot):
    """Setup function for the trading cog"""
    bot.add_cog(Trading(bot))
