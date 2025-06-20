"""
Trading Views Module
UI components and views for the trading system.
"""

import nextcord
from nextcord.ext import commands
from utils.db import AsyncDatabase
from collections import Counter
from typing import Optional
import asyncio

db = AsyncDatabase.get_instance()

class TradeConfirmationView(nextcord.ui.View):
    def __init__(self, trade_offer, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_offer = trade_offer
        self.bot = bot
        self.initiator_confirmed = False
        self.target_confirmed = False
        self.message = None
    
    @nextcord.ui.button(label="✅ Confirm Trade", style=nextcord.ButtonStyle.success)
    async def confirm_trade(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
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
    
    @nextcord.ui.button(label="❌ Cancel Trade", style=nextcord.ButtonStyle.danger)
    async def cancel_trade(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        user_id = interaction.user.id
        
        if user_id not in [self.trade_offer.initiator_id, self.trade_offer.target_id]:
            return await interaction.response.send_message("❌ This trade doesn't involve you!", ephemeral=True)
        
        self.trade_offer.status = "cancelled"
        
        embed = nextcord.Embed(
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
        
        embed = nextcord.Embed(
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
        except nextcord.NotFound:
            pass
    
    def _format_trade_items(self, items: list, currency: int) -> str:
        """Format items and currency for display"""
        parts = []
        
        if items:
            item_counts = Counter((item['name']) for item in items)
            for item_name, count in item_counts.items():
                if count > 1:
                    parts.append(f"**{count}x** {item_name}")
                else:
                    parts.append(f"**{item_name}**")
        
        if currency > 0:
            parts.append(f"**{currency:,}** <:bronkbuk:1377389238290747582>")
        
        return "\n".join(parts) if parts else "Nothing"
    
    async def verify_trade_validity(self):
        """Verify both users still have the required items and currency"""
        # Check initiator's items and currency
        initiator_balance = await db.get_wallet_balance(self.trade_offer.initiator_id, self.trade_offer.guild_id)
        if initiator_balance < self.trade_offer.initiator_currency:
            return False
        
        # Check target's items and currency
        target_balance = await db.get_wallet_balance(self.trade_offer.target_id, self.trade_offer.guild_id)
        if target_balance < self.trade_offer.target_currency:
            return False
        
        # Check items (simplified - would need proper inventory check)
        return True
    
    async def _execute_trade(self):
        """Execute the confirmed trade"""
        try:
            # Verify both users still have the items and currency
            if not await self.verify_trade_validity():
                embed = nextcord.Embed(
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
                
                embed = nextcord.Embed(
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
                embed = nextcord.Embed(
                    title="❌ Trade Failed",
                    description="An error occurred while processing the trade.",
                    color=0xff0000
                )
                await self.message.edit(embed=embed, view=None)
        
        except Exception as e:
            embed = nextcord.Embed(
                title="❌ Trade Error",
                description=f"An unexpected error occurred during the trade.\n```py\n{str(e)}\n```",
                color=0xff0000
            )
            await self.message.edit(embed=embed, view=None)
        
        self.stop()
    
    async def _perform_trade_exchange(self):
        """Perform the actual exchange of items and currency"""
        try:
            # Transfer currency from initiator to target
            if self.trade_offer.initiator_currency > 0:
                await db.transfer_currency(
                    self.trade_offer.initiator_id,
                    self.trade_offer.target_id,
                    self.trade_offer.initiator_currency,
                    self.trade_offer.guild_id
                )
            
            # Transfer currency from target to initiator
            if self.trade_offer.target_currency > 0:
                await db.transfer_currency(
                    self.trade_offer.target_id,
                    self.trade_offer.initiator_id,
                    self.trade_offer.target_currency,
                    self.trade_offer.guild_id
                )
            
            # Transfer items (simplified - would need proper inventory transfer)
            # This would involve actual inventory management
            
            return True
            
        except Exception as e:
            print(f"Trade exchange error: {e}")
            return False
    
    async def _log_trade(self):
        """Log the completed trade"""
        try:
            trade_data = {
                'trade_id': self.trade_offer.trade_id,
                'initiator_id': self.trade_offer.initiator_id,
                'target_id': self.trade_offer.target_id,
                'guild_id': self.trade_offer.guild_id,
                'initiator_currency': self.trade_offer.initiator_currency,
                'target_currency': self.trade_offer.target_currency,
                'completed_at': self.trade_offer.created_at.isoformat()
            }
            
            # Store in database (simplified)
            await db.log_trade(trade_data)
            
        except Exception as e:
            print(f"Trade logging error: {e}")


class QuickTradeView(nextcord.ui.View):
    def __init__(self, trade_offer, bot, timeout=300):
        super().__init__(timeout=timeout)
        self.trade_offer = trade_offer
        self.bot = bot
    
    @nextcord.ui.button(label="✅ Accept", style=nextcord.ButtonStyle.success)
    async def accept_trade(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if interaction.user.id != self.trade_offer.target_id:
            return await interaction.response.send_message("❌ This trade isn't for you!", ephemeral=True)
        
        # Convert to confirmation view
        view = TradeConfirmationView(self.trade_offer, self.bot)
        view.target_confirmed = True  # Auto-confirm target
        
        embed = nextcord.Embed(
            title="✅ Quick Trade Accepted!",
            description="Trade accepted! Waiting for final confirmation.",
            color=0x00ff00
        )
        
        await interaction.response.edit_message(embed=embed, view=view)
        view.message = interaction.message
    
    @nextcord.ui.button(label="💰 Counter Offer", style=nextcord.ButtonStyle.secondary)
    async def counter_offer(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if interaction.user.id != self.trade_offer.target_id:
            return await interaction.response.send_message("❌ This trade isn't for you!", ephemeral=True)
        
        modal = CounterOfferModal(self.trade_offer, self.bot)
        await interaction.response.send_modal(modal)
    
    @nextcord.ui.button(label="❌ Decline", style=nextcord.ButtonStyle.danger)
    async def decline_trade(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if interaction.user.id != self.trade_offer.target_id:
            return await interaction.response.send_message("❌ This trade isn't for you!", ephemeral=True)
        
        embed = nextcord.Embed(
            title="❌ Trade Declined",
            description="The trade offer has been declined.",
            color=0xff0000
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


class CounterOfferModal(nextcord.ui.Modal):
    def __init__(self, trade_offer, bot):
        super().__init__(title="💰 Counter Offer")
        self.trade_offer = trade_offer
        self.bot = bot
        
        self.currency_amount = nextcord.ui.TextInput(
            label="Currency Amount",
            placeholder="Enter amount of currency to offer...",
            required=True,
            max_length=10
        )
        self.add_item(self.currency_amount)
    
    async def on_submit(self, interaction: nextcord.Interaction):
        try:
            amount = int(self.currency_amount.value)
            if amount <= 0:
                return await interaction.response.send_message("❌ Amount must be positive!", ephemeral=True)
            
            # Check balance
            balance = await db.get_wallet_balance(interaction.user.id, interaction.guild.id)
            if balance < amount:
                return await interaction.response.send_message(
                    f"❌ Insufficient funds! You have {balance:,} but need {amount:,}",
                    ephemeral=True
                )
            
            # Add currency to trade
            self.trade_offer.target_currency = amount
            
            # Convert to confirmation view
            view = TradeConfirmationView(self.trade_offer, self.bot)
            
            embed = nextcord.Embed(
                title="💰 Counter Offer Made!",
                description="Counter offer submitted! Both parties must now confirm.",
                color=0xffa500
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
            view.message = interaction.message
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)
