"""
Economy Administration Module
Admin functions for managing the economy and user data.
"""

import nextcord
from typing import Dict, List, Optional, Any, Tuple
from utils.db import AsyncDatabase
from .constants import ERROR_MESSAGES, SUCCESS_MESSAGES, CONFIRMATION_PHRASES

db = AsyncDatabase.get_instance()

class EconomyAdmin:
    """Manages economy administration functions"""
    
    def __init__(self):
        pass
    
    async def reset_user_balance(self, user_id: int, guild_id: int, new_balance: int = 0) -> bool:
        """Reset a user's balance to a specific amount"""
        try:
            await db.set_wallet_balance(user_id, guild_id, new_balance)
            return True
        except Exception as e:
            print(f"Error resetting user balance: {e}")
            return False
    
    async def add_to_user_balance(self, user_id: int, guild_id: int, amount: int) -> bool:
        """Add amount to user's balance"""
        try:
            await db.add_to_wallet(user_id, guild_id, amount)
            return True
        except Exception as e:
            print(f"Error adding to user balance: {e}")
            return False
    
    async def deduct_from_user_balance(self, user_id: int, guild_id: int, amount: int) -> bool:
        """Deduct amount from user's balance"""
        try:
            current_balance = await db.get_wallet_balance(user_id, guild_id)
            if current_balance < amount:
                return False
            
            await db.deduct_from_wallet(user_id, guild_id, amount)
            return True
        except Exception as e:
            print(f"Error deducting from user balance: {e}")
            return False
    
    async def get_user_economy_stats(self, user_id: int, guild_id: int) -> Dict[str, Any]:
        """Get comprehensive economy statistics for a user"""
        try:
            balance = await db.get_wallet_balance(user_id, guild_id)
            bank_balance = await db.get_bank_balance(user_id, guild_id)
            total_earned = await db.get_total_earned(user_id, guild_id)
            total_spent = await db.get_total_spent(user_id, guild_id)
            
            return {
                "wallet_balance": balance,
                "bank_balance": bank_balance,
                "total_balance": balance + bank_balance,
                "total_earned": total_earned,
                "total_spent": total_spent,
                "net_worth": (balance + bank_balance) + (total_earned - total_spent)
            }
        except Exception as e:
            print(f"Error getting user economy stats: {e}")
            return {}
    
    async def reset_guild_economy(self, guild_id: int, confirmation: str) -> Tuple[bool, str]:
        """Reset entire guild economy (DANGEROUS OPERATION)"""
        try:
            # Verify confirmation
            if confirmation.upper() not in CONFIRMATION_PHRASES:
                return False, ERROR_MESSAGES["confirmation_required"]
            
            # Reset all user balances in the guild
            users = await db.get_guild_members(guild_id)
            
            for user_id in users:
                await db.set_wallet_balance(user_id, guild_id, 0)
                await db.set_bank_balance(user_id, guild_id, 0)
                await db.reset_user_economy_stats(user_id, guild_id)
            
            # Reset guild-wide economy data
            await db.reset_guild_economy_data(guild_id)
            
            return True, SUCCESS_MESSAGES["economy_reset"]
            
        except Exception as e:
            print(f"Error resetting guild economy: {e}")
            return False, ERROR_MESSAGES["database_error"]
    
    async def give_items_to_user(self, user_id: int, guild_id: int, items: Dict[str, int]) -> bool:
        """Give specific items to a user"""
        try:
            for item_id, amount in items.items():
                await db.add_to_inventory(user_id, guild_id, item_id, amount)
            return True
        except Exception as e:
            print(f"Error giving items to user: {e}")
            return False
    
    async def remove_items_from_user(self, user_id: int, guild_id: int, items: Dict[str, int]) -> bool:
        """Remove specific items from a user"""
        try:
            for item_id, amount in items.items():
                current_amount = await db.get_inventory_item_count(user_id, guild_id, item_id)
                if current_amount < amount:
                    return False  # Not enough items
                
                await db.remove_from_inventory(user_id, guild_id, item_id, amount)
            return True
        except Exception as e:
            print(f"Error removing items from user: {e}")
            return False
    
    async def get_guild_economy_overview(self, guild_id: int) -> Dict[str, Any]:
        """Get guild economy overview statistics"""
        try:
            users = await db.get_guild_members(guild_id)
            
            total_wealth = 0
            active_users = 0
            wealthy_users = 0  # Users with >10k
            
            for user_id in users:
                balance = await db.get_wallet_balance(user_id, guild_id)
                bank_balance = await db.get_bank_balance(user_id, guild_id)
                user_wealth = balance + bank_balance
                
                total_wealth += user_wealth
                
                if user_wealth > 0:
                    active_users += 1
                
                if user_wealth > 10000:
                    wealthy_users += 1
            
            avg_wealth = total_wealth / len(users) if users else 0
            
            return {
                "total_users": len(users),
                "active_users": active_users,
                "wealthy_users": wealthy_users,
                "total_wealth": total_wealth,
                "average_wealth": avg_wealth,
                "economy_health": self._calculate_economy_health(total_wealth, active_users, len(users))
            }
            
        except Exception as e:
            print(f"Error getting guild economy overview: {e}")
            return {}
    
    def _calculate_economy_health(self, total_wealth: int, active_users: int, total_users: int) -> str:
        """Calculate economy health rating"""
        if total_users == 0:
            return "Unknown"
        
        activity_rate = active_users / total_users
        avg_wealth = total_wealth / total_users
        
        if activity_rate > 0.7 and avg_wealth > 5000:
            return "Excellent"
        elif activity_rate > 0.5 and avg_wealth > 2000:
            return "Good"
        elif activity_rate > 0.3 and avg_wealth > 500:
            return "Fair"
        else:
            return "Poor"
    
    async def repair_user_data(self, user_id: int, guild_id: int) -> Tuple[bool, List[str]]:
        """Repair corrupted user data"""
        repairs_made = []
        
        try:
            # Check and fix wallet balance
            balance = await db.get_wallet_balance(user_id, guild_id)
            if balance < 0:
                await db.set_wallet_balance(user_id, guild_id, 0)
                repairs_made.append("Fixed negative wallet balance")
            
            # Check and fix bank balance
            bank_balance = await db.get_bank_balance(user_id, guild_id)
            if bank_balance < 0:
                await db.set_bank_balance(user_id, guild_id, 0)
                repairs_made.append("Fixed negative bank balance")
            
            # Check inventory for invalid items
            inventory = await db.get_user_inventory(user_id, guild_id)
            if inventory:
                for item_id, amount in list(inventory.items()):
                    if amount < 0:
                        await db.set_inventory_item(user_id, guild_id, item_id, 0)
                        repairs_made.append(f"Fixed negative item count for {item_id}")
                    elif amount > 1000000:  # Suspiciously high amount
                        await db.set_inventory_item(user_id, guild_id, item_id, 1000)
                        repairs_made.append(f"Capped excessive item count for {item_id}")
            
            # Verify user exists in database
            user_exists = await db.user_exists(user_id, guild_id)
            if not user_exists:
                await db.create_user_profile(user_id, guild_id)
                repairs_made.append("Created missing user profile")
            
            return len(repairs_made) > 0, repairs_made
            
        except Exception as e:
            print(f"Error repairing user data: {e}")
            return False, [f"Error during repair: {str(e)}"]
    
    async def get_leaderboard(self, guild_id: int, category: str = "wealth", limit: int = 10) -> List[Dict[str, Any]]:
        """Get economy leaderboard for various categories"""
        try:
            users = await db.get_guild_members(guild_id)
            user_data = []
            
            for user_id in users:
                if category == "wealth":
                    balance = await db.get_wallet_balance(user_id, guild_id)
                    bank_balance = await db.get_bank_balance(user_id, guild_id)
                    value = balance + bank_balance
                elif category == "earned":
                    value = await db.get_total_earned(user_id, guild_id)
                elif category == "spent":
                    value = await db.get_total_spent(user_id, guild_id)
                else:
                    continue
                
                user_data.append({
                    "user_id": user_id,
                    "value": value
                })
            
            # Sort by value (descending)
            user_data.sort(key=lambda x: x["value"], reverse=True)
            
            return user_data[:limit]
            
        except Exception as e:
            print(f"Error getting leaderboard: {e}")
            return []
    
    async def transfer_between_users(self, from_user: int, to_user: int, guild_id: int, 
                                   amount: int) -> Tuple[bool, str]:
        """Transfer currency between users (admin function)"""
        try:
            # Check if from_user has enough balance
            from_balance = await db.get_wallet_balance(from_user, guild_id)
            if from_balance < amount:
                return False, f"Source user has insufficient balance ({from_balance:,} < {amount:,})"
            
            # Perform transfer
            await db.deduct_from_wallet(from_user, guild_id, amount)
            await db.add_to_wallet(to_user, guild_id, amount)
            
            # Log the admin transfer
            await db.log_admin_transfer(from_user, to_user, guild_id, amount)
            
            return True, f"Successfully transferred {amount:,} currency"
            
        except Exception as e:
            print(f"Error transferring between users: {e}")
            return False, ERROR_MESSAGES["database_error"]
