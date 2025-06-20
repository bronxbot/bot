"""
Main Bazaar Cog
Core bazaar commands and functionality.
"""

import nextcord
from nextcord.ext import commands, tasks
from cogs.logging.logger import CogLogger
from utils.db import AsyncDatabase
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from typing import Dict, List, Optional, Any
import random
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict

# Import modular components
from .constants import BAZAAR_CONFIG, BAZAAR_EMOJIS, BAZAAR_MESSAGES, PURCHASE_LIMITS
from .bazaar_views import BazaarView, StockPurchaseModal, StockSaleModal, BazaarStatsView
from .bazaar_utils import BazaarItemGenerator, BazaarStockManager, BazaarAnalytics

db = AsyncDatabase.get_instance()

class Bazaar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = BAZAAR_EMOJIS["coin"]
        
        # Initialize components
        self.item_generator = BazaarItemGenerator(BAZAAR_CONFIG)
        self.stock_manager = BazaarStockManager()
        self.analytics = BazaarAnalytics()
        
        # Bazaar state
        self.current_items = []
        self.current_secret_items = []
        self.last_reset = datetime.now()
        self.secret_last_reset = datetime.now()
        self.current_stock_price = 100.0
        
        # Statistics
        self.visitors = set()
        self.total_spent = 0
        
        # Initialize bazaar (will be done async)
        self.bot.loop.create_task(self.reset_bazaar_items())
        
        # Start background tasks
        self.reset_bazaar_task.start()
        self.update_stock_prices_task.start()
        self.save_stats_task.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.reset_bazaar_task.cancel()
        self.update_stock_prices_task.cancel()
        self.save_stats_task.cancel()
    
    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        # Check if user has accepted ToS
        if not await check_tos_acceptance(ctx.author.id):
            await prompt_tos_acceptance(ctx)
            return False
        return True
    
    @tasks.loop(hours=BAZAAR_CONFIG["refresh_hours"])
    async def reset_bazaar_task(self):
        """Periodically reset bazaar items"""
        await self.reset_bazaar_items()
    
    @tasks.loop(hours=1)
    async def update_stock_prices_task(self):
        """Update stock prices for all guilds"""
        try:
            # Get all guilds with bazaar activity
            guilds = await db.get_guilds_with_bazaar_activity()
            
            for guild_id in guilds:
                await self.stock_manager.update_stock_price(guild_id)
                
                # Process dividends every 24 hours
                if datetime.now().hour == 0:  # Midnight
                    await self.stock_manager.process_dividend_payments(guild_id)
                    
        except Exception as e:
            self.logger.error(f"Error updating stock prices: {e}")
    
    @tasks.loop(minutes=30)
    async def save_stats_task(self):
        """Save bazaar statistics"""
        try:
            await db.save_bazaar_stats({
                'visitors': len(self.visitors),
                'total_spent': self.total_spent,
                'last_updated': datetime.now()
            })
        except Exception as e:
            self.logger.error(f"Error saving bazaar stats: {e}")
    
    async def reset_bazaar_items(self):
        """Reset bazaar items with new random selection"""
        try:
            self.current_items = self.item_generator.generate_bazaar_items(
                BAZAAR_CONFIG["max_items"]
            )
            self.last_reset = datetime.now()
            self.logger.debug(f"Bazaar reset with {len(self.current_items)} items")
            
        except Exception as e:
            self.logger.error(f"Error resetting bazaar items: {e}")
    
    @commands.command(name="bazaar", aliases=["market"])
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def bazaar(self, ctx):
        """🏪 Visit the traveling bazaar for discounted items!"""
        try:
            # Track visitor
            self.visitors.add(ctx.author.id)
            
            if not self.current_items:
                await self.reset_bazaar_items()
            
            # Create bazaar embed
            embed = nextcord.Embed(
                title=f"{BAZAAR_EMOJIS['bazaar']} Traveling Bazaar",
                description=BAZAAR_MESSAGES["welcome"],
                color=0x3498db
            )
            
            # Add items to embed
            if self.current_items:
                items_text = []
                for i, item in enumerate(self.current_items, 1):
                    discount_percent = int(item['discount'] * 100)
                    items_text.append(
                        f"**{i}.** {item['name']} - ~~{item['original_price']:,}~~ "
                        f"**{item['price']:,}** {self.currency} "
                        f"({discount_percent}% off)"
                    )
                
                embed.add_field(
                    name="🛒 Available Items",
                    value="\n".join(items_text),
                    inline=False
                )
            else:
                embed.description = BAZAAR_MESSAGES["no_items"]
            
            # Add bazaar info
            time_until_reset = (self.last_reset + timedelta(hours=BAZAAR_CONFIG["refresh_hours"])) - datetime.now()
            hours_left = max(0, int(time_until_reset.total_seconds() / 3600))
            
            embed.add_field(
                name="ℹ️ Info",
                value=f"**Stock Price:** {self.current_stock_price:.0f} {self.currency}\n"
                      f"**Next Reset:** {hours_left} hours\n"
                      f"**Items Available:** {len(self.current_items)}/6",
                inline=True
            )
            
            # Create view
            view = BazaarView(self)
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            
        except Exception as e:
            self.logger.error(f"Error in bazaar command: {e}")
            await ctx.send("❌ An error occurred while loading the bazaar.")
    
    @commands.command(name="bazaarstats", aliases=["bstats"])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def bazaar_stats(self, ctx, user: nextcord.Member = None):
        """📊 View your bazaar statistics and investment portfolio"""
        target_user = user or ctx.author
        
        try:
            # Get user statistics
            user_stats = await self.analytics.get_user_bazaar_stats(target_user.id, ctx.guild.id)
            
            embed = nextcord.Embed(
                title=f"📊 {target_user.display_name}'s Bazaar Stats",
                color=0x9932cc
            )
            
            # Purchase statistics
            embed.add_field(
                name="🛒 Purchase History",
                value=f"**Total Purchases:** {user_stats['total_purchases']:,}\n"
                      f"**Total Spent:** {user_stats['total_spent']:,} {self.currency}\n"
                      f"**Unique Items:** {user_stats['unique_items']:,}\n"
                      f"**Average Purchase:** {user_stats['average_purchase']:,.0f} {self.currency}",
                inline=True
            )
            
            # Investment statistics
            stock_value = user_stats['stock_holdings'] * self.current_stock_price
            embed.add_field(
                name="📈 Investments",
                value=f"**Stock Holdings:** {user_stats['stock_holdings']:,} shares\n"
                      f"**Stock Value:** {stock_value:,.0f} {self.currency}\n"
                      f"**Most Purchased:** {user_stats['most_purchased_item']}\n"
                      f"**Purchase Count:** {user_stats['most_purchased_count']:,}x",
                inline=True
            )
            
            # Create stats view
            view = BazaarStatsView(self, user_stats)
            await ctx.send(embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Error in bazaar stats: {e}")
            await ctx.send("❌ Error retrieving bazaar statistics.")
    
    @commands.command(name="bazaarinfo", aliases=["binfo"])
    async def bazaar_info(self, ctx):
        """ℹ️ Information about the bazaar system"""
        embed = nextcord.Embed(
            title="🏪 Traveling Bazaar Information",
            description="The traveling bazaar offers rare items at discounted prices!",
            color=0x3498db
        )
        
        embed.add_field(
            name="🛒 How to Shop",
            value="• Use `bazaar` to visit the market\n"
                  "• Click 'Buy Items' to purchase\n"
                  "• Items rotate every 12 hours\n"
                  "• Get 10-40% discounts!",
            inline=False
        )
        
        embed.add_field(
            name="📈 Stock System",
            value="• Buy bazaar stock to earn dividends\n"
                  "• Stock prices fluctuate with market\n"
                  "• Earn passive income from holdings\n"
                  "• Trade stocks anytime",
            inline=False
        )
        
        embed.add_field(
            name="💡 Tips",
            value="• Check regularly for rare items\n"
                  "• Stock up during high discounts\n"
                  "• Invest in stock for long-term gains\n"
                  "• Use `bstats` to track performance",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    async def process_bazaar_purchase(self, interaction: nextcord.Interaction, item_idx: int, amount: int):
        """Process a bazaar item purchase"""
        try:
            if item_idx >= len(self.current_items):
                await interaction.response.send_message("❌ Invalid item selection.", ephemeral=True)
                return
            
            item = self.current_items[item_idx]
            total_cost = item['price'] * amount
            
            # Check user balance
            balance = await db.get_wallet_balance(interaction.user.id, interaction.guild.id)
            if balance < total_cost:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You need {total_cost:,} {self.currency} but have {balance:,}.",
                    ephemeral=True
                )
                return
            
            # Check stock
            if item['stock'] < amount:
                await interaction.response.send_message(
                    f"❌ Not enough stock! Only {item['stock']} available.",
                    ephemeral=True
                )
                return
            
            # Process purchase
            await db.deduct_from_wallet(interaction.user.id, interaction.guild.id, total_cost)
            
            # Add items to inventory (simplified)
            await db.add_to_inventory(interaction.user.id, interaction.guild.id, item['id'], amount)
            
            # Update item stock
            item['stock'] -= amount
            if item['stock'] <= 0:
                self.current_items.remove(item)
            
            # Log purchase
            await db.log_bazaar_purchase(
                interaction.user.id, interaction.guild.id,
                item['id'], item['name'], amount, item['price'], total_cost
            )
            
            # Update statistics
            self.total_spent += total_cost
            
            embed = nextcord.Embed(
                title="✅ Purchase Successful!",
                description=f"You bought **{amount}x {item['name']}** for **{total_cost:,}** {self.currency}!",
                color=0x00ff00
            )
            
            savings = (item['original_price'] - item['price']) * amount
            embed.add_field(
                name="💰 Savings",
                value=f"You saved **{savings:,}** {self.currency} with this deal!",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error processing purchase: {e}")
            await interaction.response.send_message("❌ Error processing purchase.", ephemeral=True)
    
    async def handle_stock_purchase(self, interaction: nextcord.Interaction):
        """Handle stock purchase interaction"""
        modal = StockPurchaseModal(self)
        await interaction.response.send_modal(modal)
    
    async def handle_stock_sale(self, interaction: nextcord.Interaction):
        """Handle stock sale interaction"""
        modal = StockSaleModal(self)
        await interaction.response.send_modal(modal)
    
    async def process_stock_purchase(self, interaction: nextcord.Interaction, amount: int):
        """Process stock purchase"""
        try:
            stock_price = await self.stock_manager.get_current_stock_price(interaction.guild.id)
            shares = amount / stock_price
            
            # Deduct currency
            await db.deduct_from_wallet(interaction.user.id, interaction.guild.id, amount)
            
            # Add stock
            await db.add_bazaar_stock(interaction.user.id, interaction.guild.id, shares)
            
            # Log transaction
            await db.log_bazaar_stock_purchase(
                interaction.user.id, interaction.guild.id, shares, stock_price, amount
            )
            
            embed = nextcord.Embed(
                title="📈 Stock Purchase Successful!",
                description=f"You bought **{shares:.2f} shares** for **{amount:,}** {self.currency}!",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📊 Details",
                value=f"**Price per share:** {stock_price:.2f} {self.currency}\n"
                      f"**Total shares:** {shares:.2f}\n"
                      f"**Investment:** {amount:,} {self.currency}",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error processing stock purchase: {e}")
            await interaction.followup.send("❌ Error processing stock purchase.", ephemeral=True)
    
    async def process_stock_sale(self, interaction: nextcord.Interaction, shares: float):
        """Process stock sale"""
        try:
            stock_price = await self.stock_manager.get_current_stock_price(interaction.guild.id)
            total_value = shares * stock_price
            
            # Remove stock
            await db.remove_bazaar_stock(interaction.user.id, interaction.guild.id, shares)
            
            # Add currency
            await db.add_to_wallet(interaction.user.id, interaction.guild.id, int(total_value))
            
            # Log transaction
            await db.log_bazaar_stock_sale(
                interaction.user.id, interaction.guild.id, shares, stock_price, int(total_value)
            )
            
            embed = nextcord.Embed(
                title="📉 Stock Sale Successful!",
                description=f"You sold **{shares:.2f} shares** for **{int(total_value):,}** {self.currency}!",
                color=0x00ff00
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
        except Exception as e:
            self.logger.error(f"Error processing stock sale: {e}")
            await interaction.followup.send("❌ Error processing stock sale.", ephemeral=True)


async def setup(bot):
    """Setup function for the bazaar cog"""
    bot.add_cog(Bazaar(bot))
