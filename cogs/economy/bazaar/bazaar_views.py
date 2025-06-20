"""
Bazaar Views Module
UI components and modals for the bazaar system.
"""

import nextcord
from utils.db import AsyncDatabase
from typing import List, Dict, Any
import asyncio

db = AsyncDatabase.get_instance()

class ItemSelectModal(nextcord.ui.Modal):
    def __init__(self, cog, items):
        super().__init__(title="Bazaar Purchase", timeout=120)
        self.cog = cog
        self.items = items
        
        # Create a view to hold our select menu
        self.select_view = nextcord.ui.View(timeout=120)
        
        # Create the select menu
        self.item_select = nextcord.ui.Select(
            placeholder="Select an item to purchase...",
            options=[
                nextcord.SelectOption(
                    label=f"{item['name']}",
                    description=f"{item['price']} (Save {int(item['discount']*100)}%)",
                    value=str(idx),
                    emoji="🛒" if idx == 0 else "📦"
                ) for idx, item in enumerate(items)
            ]
        )
        self.select_view.add_item(self.item_select)
        
        # Add amount input
        self.amount = nextcord.ui.TextInput(
            label="Purchase Amount (1-10)",
            placeholder="Enter how many you want to buy...",
            default="1",
            min_length=1,
            max_length=2,
            required=True
        )
        self.add_item(self.amount)

    async def on_submit(self, interaction: nextcord.Interaction):
        try:
            # Get selected item index from the first select interaction
            if not hasattr(self, '_selected_item_idx'):
                # If no item was selected via select menu, use first item as default
                item_idx = 0
            else:
                item_idx = self._selected_item_idx
            
            amount = int(self.amount.value)
            
            if amount < 1 or amount > 10:
                await interaction.response.send_message("❌ Amount must be between 1 and 10.", ephemeral=True)
                return
            
            # Process the purchase
            await self.cog.process_bazaar_purchase(interaction, item_idx, amount)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ An error occurred: {str(e)}", ephemeral=True)


class BazaarView(nextcord.ui.View):
    def __init__(self, cog, timeout=180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.message = None
        
    @nextcord.ui.button(label="🛒 Buy Items", style=nextcord.ButtonStyle.primary)
    async def buy_items(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not self.cog.current_items:
            await interaction.response.send_message("❌ No items available in the bazaar right now.", ephemeral=True)
            return
        
        modal = ItemSelectModal(self.cog, self.cog.current_items)
        await interaction.response.send_modal(modal)
        
    @nextcord.ui.button(label="📈 Buy Stock", style=nextcord.ButtonStyle.secondary)
    async def buy_stock(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        await self.cog.handle_stock_purchase(interaction)
        
    @nextcord.ui.button(label="📉 Sell Stock", style=nextcord.ButtonStyle.secondary)
    async def sell_stock(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        await self.cog.handle_stock_sale(interaction)
        
    @nextcord.ui.button(label="🗑️ Close", style=nextcord.ButtonStyle.danger)
    async def close(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        await interaction.response.defer()
        if self.message:
            try:
                await self.message.delete()
            except nextcord.NotFound:
                pass


class StockPurchaseModal(nextcord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Purchase Bazaar Stock")
        self.cog = cog
        
        self.amount = nextcord.ui.TextInput(
            label="Investment Amount",
            placeholder="Enter amount to invest in bazaar stock...",
            required=True,
            max_length=10
        )
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: nextcord.Interaction):
        try:
            amount = int(self.amount.value)
            
            if amount <= 0:
                await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
                return
            
            # Check user's balance
            balance = await db.get_wallet_balance(interaction.user.id, interaction.guild.id)
            if balance < amount:
                await interaction.response.send_message(
                    f"❌ Insufficient funds! You have {balance:,} but need {amount:,}.",
                    ephemeral=True
                )
                return
            
            # Process stock purchase
            await self.cog.process_stock_purchase(interaction, amount)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error processing purchase: {str(e)}", ephemeral=True)


class StockSaleModal(nextcord.ui.Modal):
    def __init__(self, cog):
        super().__init__(title="Sell Bazaar Stock")
        self.cog = cog
        
        self.amount = nextcord.ui.TextInput(
            label="Stock Amount to Sell",
            placeholder="Enter amount of stock to sell...",
            required=True,
            max_length=10
        )
        self.add_item(self.amount)
    
    async def on_submit(self, interaction: nextcord.Interaction):
        try:
            amount = int(self.amount.value)
            
            if amount <= 0:
                await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True)
                return
            
            # Check user's stock holdings
            holdings = await db.get_user_bazaar_stock(interaction.user.id, interaction.guild.id)
            if holdings < amount:
                await interaction.response.send_message(
                    f"❌ You don't have enough stock! You own {holdings:,} but trying to sell {amount:,}.",
                    ephemeral=True
                )
                return
            
            # Process stock sale
            await self.cog.process_stock_sale(interaction, amount)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error processing sale: {str(e)}", ephemeral=True)


class BazaarRefreshView(nextcord.ui.View):
    def __init__(self, cog, timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
    
    @nextcord.ui.button(label="🔄 Refresh Bazaar", style=nextcord.ButtonStyle.success)
    async def refresh_bazaar(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        await interaction.response.defer()
        
        # Check if user can refresh (admin or special permission)
        if not interaction.user.guild_permissions.manage_messages:
            await interaction.followup.send("❌ You don't have permission to refresh the bazaar.", ephemeral=True)
            return
        
        # Refresh the bazaar
        await self.cog.refresh_bazaar_items()
        
        embed = nextcord.Embed(
            title="🔄 Bazaar Refreshed!",
            description="The bazaar has been refreshed with new items.",
            color=0x00ff00
        )
        
        await interaction.followup.send(embed=embed)
        
        # Update the original message with new items
        if hasattr(self.cog, 'current_bazaar_message'):
            await self.cog.update_bazaar_display()


class BazaarStatsView(nextcord.ui.View):
    def __init__(self, cog, user_stats: Dict[str, Any], timeout=60):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_stats = user_stats
    
    @nextcord.ui.button(label="📊 View Portfolio", style=nextcord.ButtonStyle.primary)
    async def view_portfolio(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        embed = nextcord.Embed(
            title="📊 Your Bazaar Portfolio",
            description="Your investment summary",
            color=0x3498db
        )
        
        # Add portfolio information
        stock_value = self.user_stats.get('stock_holdings', 0)
        total_invested = self.user_stats.get('total_invested', 0)
        total_returns = self.user_stats.get('total_returns', 0)
        
        embed.add_field(
            name="📈 Current Holdings",
            value=f"**Stock:** {stock_value:,} shares\n"
                  f"**Value:** ~{stock_value * self.cog.current_stock_price:,.0f} <:bronkbuk:1377389238290747582>",
            inline=True
        )
        
        embed.add_field(
            name="💰 Investment Summary",
            value=f"**Total Invested:** {total_invested:,}\n"
                  f"**Total Returns:** {total_returns:,}\n"
                  f"**Net P&L:** {total_returns - total_invested:+,}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @nextcord.ui.button(label="📋 Purchase History", style=nextcord.ButtonStyle.secondary)
    async def view_history(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        # Get user's bazaar purchase history
        history = await db.get_user_bazaar_history(interaction.user.id, interaction.guild.id, limit=10)
        
        embed = nextcord.Embed(
            title="📋 Your Bazaar History",
            description="Recent purchases and transactions",
            color=0x9932cc
        )
        
        if not history:
            embed.description = "No purchase history found."
        else:
            history_text = []
            for entry in history:
                item_name = entry.get('item_name', 'Unknown')
                amount = entry.get('amount', 1)
                price = entry.get('price', 0)
                date = entry.get('date', 'Unknown')
                
                history_text.append(f"**{amount}x {item_name}** - {price:,} 💰 - {date}")
            
            embed.description = "\n".join(history_text)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
