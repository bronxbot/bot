"""
Trading Utilities Module
Helper functions and classes for the trading system.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple, Union, TYPE_CHECKING
from datetime import datetime, timedelta
import asyncio
import math
import random
from utils.db import AsyncDatabase

if TYPE_CHECKING:
    import nextcord

db = AsyncDatabase.get_instance()

class TradeStats:
    """Trading statistics manager"""
    
    def __init__(self, trading_cog):
        self.trading_cog = trading_cog
    
    async def get_user_stats(self, user_id: int, guild_id: int) -> dict:
        """Get comprehensive trading stats for a user"""
        try:
            # Get basic trade stats
            trade_history = await db.get_user_trade_history(user_id, guild_id)
            
            if not trade_history:
                return self._get_empty_stats()
            
            total_trades = len(trade_history)
            trades_initiated = sum(1 for trade in trade_history if trade.get('initiator_id') == user_id)
            trades_received = total_trades - trades_initiated
            
            # Calculate total value traded
            total_value_traded = 0
            most_traded_items = Counter()
            partners = set()
            
            for trade in trade_history:
                # Add trade values
                if trade.get('initiator_id') == user_id:
                    total_value_traded += trade.get('initiator_value', 0)
                    partners.add(trade.get('target_id'))
                else:
                    total_value_traded += trade.get('target_value', 0)
                    partners.add(trade.get('initiator_id'))
                
                # Count items traded
                items = trade.get('items_traded', [])
                for item in items:
                    most_traded_items[item.get('name', 'Unknown')] += item.get('quantity', 1)
            
            return {
                "total_trades": total_trades,
                "trades_initiated": trades_initiated,
                "trades_received": trades_received,
                "total_value_traded": total_value_traded,
                "most_traded_items": most_traded_items,
                "unique_partners": len(partners)
            }
            
        except Exception:
            return self._get_empty_stats()
    
    def _get_empty_stats(self) -> dict:
        """Return empty stats structure"""
        return {
            "total_trades": 0,
            "trades_initiated": 0,
            "trades_received": 0,
            "total_value_traded": 0,
            "most_traded_items": Counter(),
            "unique_partners": 0
        }
    
    async def get_guild_leaderboard(self, guild_id: int, limit: int = 10) -> List[dict]:
        """Get trading leaderboard for a guild"""
        try:
            # Get all user trade stats
            users = await db.get_guild_members(guild_id)
            user_stats = []
            
            for user_id in users:
                stats = await self.get_user_stats(user_id, guild_id)
                if stats['total_trades'] > 0:
                    user_stats.append({
                        'user_id': user_id,
                        'stats': stats
                    })
            
            # Sort by total trades
            user_stats.sort(key=lambda x: x['stats']['total_trades'], reverse=True)
            
            return user_stats[:limit]
            
        except Exception:
            return []
    
    async def get_market_trends(self, guild_id: int, days: int = 30) -> dict:
        """Get market trends and popular items"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_trades = await db.get_trades_since(guild_id, cutoff_date)
            
            item_popularity = Counter()
            average_values = defaultdict(list)
            trade_volume = 0
            
            for trade in recent_trades:
                trade_volume += 1
                items = trade.get('items_traded', [])
                
                for item in items:
                    item_name = item.get('name', 'Unknown')
                    item_value = item.get('value', 0)
                    quantity = item.get('quantity', 1)
                    
                    item_popularity[item_name] += quantity
                    if item_value > 0:
                        average_values[item_name].append(item_value)
            
            # Calculate average values
            avg_item_values = {}
            for item_name, values in average_values.items():
                avg_item_values[item_name] = sum(values) / len(values) if values else 0
            
            return {
                'popular_items': dict(item_popularity.most_common(10)),
                'average_values': avg_item_values,
                'trade_volume': trade_volume,
                'period_days': days
            }
            
        except Exception:
            return {
                'popular_items': {},
                'average_values': {},
                'trade_volume': 0,
                'period_days': days
            }


class TradeValidator:
    """Trade validation and risk assessment"""
    
    def __init__(self, item_values: dict):
        self.item_values = item_values
    
    def validate_trade_contents(self, trade_offer) -> Tuple[bool, List[str]]:
        """Validate trade contents and return any issues"""
        issues = []
        
        # Check if trade is empty
        if (not trade_offer.initiator_items and trade_offer.initiator_currency == 0 and
            not trade_offer.target_items and trade_offer.target_currency == 0):
            issues.append("Trade cannot be empty on both sides")
        
        # Check for negative values
        if trade_offer.initiator_currency < 0 or trade_offer.target_currency < 0:
            issues.append("Currency amounts cannot be negative")
        
        # Check for duplicate items on same side
        if self._has_duplicate_items(trade_offer.initiator_items):
            issues.append("Initiator has duplicate items")
        
        if self._has_duplicate_items(trade_offer.target_items):
            issues.append("Target has duplicate items")
        
        # Check for unreasonably high values
        initiator_value = self._calculate_side_value(trade_offer.initiator_items, trade_offer.initiator_currency)
        target_value = self._calculate_side_value(trade_offer.target_items, trade_offer.target_currency)
        
        if initiator_value > 1000000 or target_value > 1000000:
            issues.append("Trade value exceeds reasonable limits")
        
        return len(issues) == 0, issues
    
    def _has_duplicate_items(self, items: List[dict]) -> bool:
        """Check if there are duplicate items in the list"""
        item_ids = [item.get('id') for item in items if item.get('id')]
        return len(item_ids) != len(set(item_ids))
    
    def _calculate_side_value(self, items: List[dict], currency: int) -> int:
        """Calculate total value of one side of trade"""
        item_value = sum(
            self.item_values.get(item.get('id', ''), item.get('value', 0))
            for item in items
        )
        return item_value + currency
    
    def assess_trade_risk(self, trade_offer) -> Tuple[str, List[str]]:
        """Assess trade risk level and return warnings"""
        warnings = []
        
        # Calculate balance ratio
        initiator_value = self._calculate_side_value(trade_offer.initiator_items, trade_offer.initiator_currency)
        target_value = self._calculate_side_value(trade_offer.target_items, trade_offer.target_currency)
        
        if initiator_value == 0 and target_value == 0:
            balance_ratio = 1.0
        elif initiator_value == 0 or target_value == 0:
            balance_ratio = 0.0
        else:
            balance_ratio = min(initiator_value, target_value) / max(initiator_value, target_value)
        
        # Determine risk level
        if balance_ratio < 0.5:
            warnings.append("⚠️ Highly unbalanced trade")
            risk = "extreme"
        elif balance_ratio < 0.7:
            warnings.append("⚠️ Unbalanced trade")
            risk = "high"
        elif balance_ratio < 0.85:
            risk = "medium"
        else:
            risk = "low"
        
        # Check high value trades
        max_value = max(initiator_value, target_value)
        if max_value > 100000:
            warnings.append("💰 High value trade - double check items")
            if risk == "low":
                risk = "medium"
        
        # Check for duplicate items
        if (self._has_duplicate_items(trade_offer.initiator_items) or 
            self._has_duplicate_items(trade_offer.target_items)):
            warnings.append("🔄 Contains duplicate items")
        
        return risk, warnings


class TradeFormatter:
    """Format trade information for display"""
    
    @staticmethod
    def format_trade_embed(trade_offer, bot) -> 'nextcord.Embed':
        """Format a trade offer as a Discord embed"""
        import nextcord
        
        embed = nextcord.Embed(
            title=f"🤝 Trade Offer #{trade_offer.trade_id}",
            color=0x3498db
        )
        
        # Get users
        initiator = bot.get_user(trade_offer.initiator_id)
        target = bot.get_user(trade_offer.target_id)
        
        # Initiator's offer
        initiator_items = TradeFormatter._format_items_list(
            trade_offer.initiator_items, 
            trade_offer.initiator_currency
        )
        embed.add_field(
            name=f"{initiator.display_name if initiator else 'Unknown'} offers:",
            value=initiator_items or "Nothing",
            inline=False
        )
        
        # Target's offer
        target_items = TradeFormatter._format_items_list(
            trade_offer.target_items,
            trade_offer.target_currency
        )
        embed.add_field(
            name=f"{target.display_name if target else 'Unknown'} offers:",
            value=target_items or "Nothing",
            inline=False
        )
        
        # Trade info
        embed.add_field(
            name="📊 Trade Info",
            value=f"**Balance:** {'✅ Fair' if trade_offer.is_balanced() else '⚠️ Unbalanced'}\n"
                  f"**Risk:** {trade_offer.risk_level.title()}\n"
                  f"**Status:** {trade_offer.status.title()}",
            inline=True
        )
        
        # Warnings
        if trade_offer.warnings:
            embed.add_field(
                name="⚠️ Warnings",
                value="\n".join(trade_offer.warnings),
                inline=False
            )
        
        # Notes
        if trade_offer.notes['initiator'] or trade_offer.notes['target']:
            notes_text = ""
            if trade_offer.notes['initiator']:
                notes_text += f"**{initiator.display_name if initiator else 'Initiator'}:** {trade_offer.notes['initiator']}\n"
            if trade_offer.notes['target']:
                notes_text += f"**{target.display_name if target else 'Target'}:** {trade_offer.notes['target']}"
            
            embed.add_field(
                name="📝 Notes",
                value=notes_text,
                inline=False
            )
        
        embed.set_footer(
            text=f"Created: {trade_offer.created_at.strftime('%Y-%m-%d %H:%M:%S')} • "
                 f"Expires: {trade_offer.expires_at.strftime('%H:%M:%S')}"
        )
        
        return embed
    
    @staticmethod
    def _format_items_list(items: List[dict], currency: int) -> str:
        """Format a list of items and currency for display"""
        parts = []
        
        if items:
            item_counts = Counter(item['name'] for item in items)
            for item_name, count in item_counts.items():
                if count > 1:
                    parts.append(f"**{count}x** {item_name}")
                else:
                    parts.append(f"**{item_name}**")
        
        if currency > 0:
            parts.append(f"**{currency:,}** <:bronkbuk:1377389238290747582>")
        
        return "\n".join(parts) if parts else "Nothing"
    
    @staticmethod
    def format_trade_history_embed(trades: List[dict], user, bot) -> 'nextcord.Embed':
        """Format trade history as a Discord embed"""
        import nextcord
        
        embed = nextcord.Embed(
            title=f"📊 {user.display_name}'s Trade History",
            color=0x3498db
        )
        
        if not trades:
            embed.description = "No trades found."
            return embed
        
        # Show recent trades
        recent_trades = trades[:10]  # Show last 10 trades
        
        trade_text = []
        for trade in recent_trades:
            trade_id = trade.get('trade_id', 'Unknown')
            partner_id = (trade.get('target_id') if trade.get('initiator_id') == user.id 
                         else trade.get('initiator_id'))
            partner = bot.get_user(partner_id)
            partner_name = partner.display_name if partner else "Unknown User"
            
            value = trade.get('initiator_value' if trade.get('initiator_id') == user.id else 'target_value', 0)
            date = trade.get('completed_at', 'Unknown')
            
            trade_text.append(f"**#{trade_id}** with {partner_name} - {value:,} value - {date}")
        
        embed.description = "\n".join(trade_text)
        embed.set_footer(text=f"Showing {len(recent_trades)} of {len(trades)} trades")
        
        return embed


async def get_user_inventory(user_id: int, guild_id: int) -> List[dict]:
    """Get user's inventory for trading"""
    # This would integrate with the actual inventory system
    # For now, return a placeholder structure
    try:
        inventory = await db.get_user_inventory(user_id, guild_id)
        return inventory or []
    except Exception:
        return []


async def validate_user_balance(user_id: int, guild_id: int, amount: int) -> bool:
    """Validate if user has sufficient balance"""
    try:
        balance = await db.get_wallet_balance(user_id, guild_id)
        return balance >= amount
    except Exception:
        return False


async def transfer_items(from_user: int, to_user: int, guild_id: int, items: List[dict]) -> bool:
    """Transfer items between users"""
    # This would integrate with the actual inventory system
    try:
        for item in items:
            await db.transfer_item(from_user, to_user, guild_id, item)
        return True
    except Exception:
        return False
