import motor.motor_asyncio
import pymongo
import json
import datetime
import os
import asyncio
import logging
from typing import Dict, Any, Optional
import threading

def load_config() -> dict:
    """Load config from environment variables, then config.json as fallback."""
    config = {
        "MONGO_URI": os.getenv("MONGO_URI"),
        "TOKEN": os.getenv("DISCORD_TOKEN"),
        "CLIENT_ID": os.getenv("DISCORD_CLIENT_ID"),
        "CLIENT_SECRET": os.getenv("DISCORD_CLIENT_SECRET"),
        "OWNER_ID": os.getenv("DISCORD_BOT_OWNER_ID")
    }
    if not all([config["MONGO_URI"], config["TOKEN"], config["CLIENT_ID"]]):
        try:
            with open('data/config.json') as f:
                file_config = json.load(f)
                for key in config:
                    if not config[key] and key in file_config:
                        config[key] = file_config[key]
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logging.warning(f"Could not load config.json: {e}. Using environment variables only.")
    return config

config = load_config()

class AsyncDatabase:
    """Async database class for use with Discord bot (MongoDB)"""
    _instance = None
    _client = None
    _db = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.logger = logging.getLogger('AsyncDatabase')
        self._connected = False

    @property
    def client(self):
        if self._client is None:
            MONGO_URI = os.getenv('MONGO_URI', config['MONGO_URI'])
            self._client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_URI)
        return self._client

    @property
    def db(self):
        if self._db is None:
            self._db = self.client.bronxbot
        return self._db

    async def ensure_connected(self) -> bool:
        """Ensure database connection is active."""
        if not self._connected:
            try:
                await self.client.admin.command('ping')
                self._connected = True
                self.logger.info("Async database connection established")
            except Exception as e:
                self.logger.error(f"Async database connection failed: {e}")
                return False
        return True

    async def get_wallet_balance(self, user_id: int, guild_id: int = None) -> int:
        """Get user's wallet balance"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("wallet", 0) if user else 0

    async def get_bank_balance(self, user_id: int, guild_id: int = None) -> int:
        """Get user's bank balance"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("bank", 0) if user else 0

    async def get_bank_limit(self, user_id: int, guild_id: int = None) -> int:
        """Get user's bank limit"""
        if not await self.ensure_connected():
            return 10000
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("bank_limit", 10000) if user else 10000

    async def update_wallet(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Update user's wallet balance with overflow protection"""
        if not await self.ensure_connected():
            return False
            
        # Get current balance
        current = await self.get_wallet_balance(user_id)
        
        # Check for overflow/underflow
        MAX_BALANCE = 9223372036854775807  # PostgreSQL bigint max
        new_balance = current + amount
        
        if new_balance > MAX_BALANCE:
            new_balance = MAX_BALANCE
        elif new_balance < 0:
            return False
            
        # Update with the safe balance
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"wallet": new_balance}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def update_bank(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Update user's bank balance with overflow protection"""
        if not await self.ensure_connected():
            return False
            
        current = await self.get_bank_balance(user_id)
        MAX_BALANCE = 9223372036854775807
        new_balance = current + amount
        
        if new_balance > MAX_BALANCE:
            new_balance = MAX_BALANCE
        elif new_balance < 0:
            return False
            
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"bank": new_balance}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_guild_settings(self, guild_id: int) -> Dict[str, Any]:
        """Get guild settings"""
        if not await self.ensure_connected():
            return {}
        settings = await self.db.guild_settings.find_one({"_id": str(guild_id)})
        return settings if settings else {}

    async def update_guild_settings(self, guild_id: int, settings: Dict[str, Any]) -> bool:
        """Update guild settings"""
        if not await self.ensure_connected():
            return False
        result = await self.db.guild_settings.update_one(
            {"_id": str(guild_id)},
            {"$set": settings},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def store_stats(self, guild_id: int, stat_type: str) -> None:
        """Store guild stats"""
        if not await self.ensure_connected():
            return
        await self.db.stats.update_one(
            {"_id": str(guild_id)},
            {"$inc": {stat_type: 1}},
            upsert=True
        )

    async def get_stats(self, guild_id: int) -> Dict[str, int]:
        """Get guild stats"""
        if not await self.ensure_connected():
            return {}
        stats = await self.db.stats.find_one({"_id": str(guild_id)})
        return stats if stats else {}

    async def reset_stats(self, guild_id: int) -> bool:
        """Reset guild stats"""
        if not await self.ensure_connected():
            return False
        result = await self.db.stats.delete_one({"_id": str(guild_id)})
        return result.deleted_count > 0

    async def add_global_buff(self, buff_data: Dict[str, Any]) -> bool:
        """Add global buff"""
        if not await self.ensure_connected():
            return False
        result = await self.db.global_buffs.insert_one(buff_data)
        return result.inserted_id is not None

    async def get_user_balance(self, user_id: int, guild_id: int = None) -> int:
        """Get user's total balance"""
        wallet = await self.get_wallet_balance(user_id, guild_id)
        bank = await self.get_bank_balance(user_id, guild_id)
        return wallet + bank

    async def transfer_money(self, from_id: int, to_id: int, amount: int, guild_id: int = None) -> bool:
        """Transfer money between users"""
        if not await self.ensure_connected():
            return False
            
        from_balance = await self.get_wallet_balance(from_id, guild_id)
        if from_balance < amount:
            return False
            
        async with await self.client.start_session() as session:
            async with session.start_transaction():
                if not await self.update_wallet(from_id, -amount, guild_id):
                    return False
                if not await self.update_wallet(to_id, amount, guild_id):
                    await self.update_wallet(from_id, amount, guild_id)  # Rollback
                    return False
                return True

    async def update_balance(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Update user's wallet balance, handling both positive and negative amounts"""
        current = await self.get_wallet_balance(user_id, guild_id)
        if amount < 0 and abs(amount) > current:  # Check if user has enough for deduction
            return False
        return await self.update_wallet(user_id, amount, guild_id)

    async def increase_bank_limit(self, user_id: int, amount: int, guild_id: int = None) -> bool:
        """Increase user's bank storage limit"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$inc": {"bank_limit": amount}},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_global_net_worth(self, user_id: int, excluded_guilds: list = None) -> int:
        """Get user's total net worth across all guilds"""
        if not await self.ensure_connected():
            return 0
        excluded_guilds = excluded_guilds or []
        pipeline = [
            {"$match": {"_id": str(user_id)}},
            {"$project": {
                "total": {"$add": ["$wallet", "$bank"]}
            }}
        ]
        result = await self.db.users.aggregate(pipeline).to_list(1)
        return result[0]["total"] if result else 0

    async def get_inventory(self, user_id: int, guild_id: int = None) -> list:
        """Get user's inventory with proper quantity grouping"""
        if not await self.ensure_connected():
            return []
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user or "inventory" not in user:
            return []
        
        # Group items by id and sum quantities
        from collections import defaultdict
        item_counts = defaultdict(int)
        item_data = {}
        
        for item in user.get("inventory", []):
            item_key = item.get("id", item.get("name", "unknown"))
            item_counts[item_key] += item.get("quantity", 1)  # Add quantity if exists, default to 1
            if item_key not in item_data:
                item_data[item_key] = item.copy()
        
        # Convert to list with quantities
        result = []
        for item_key, quantity in item_counts.items():
            item = item_data[item_key].copy()
            item["quantity"] = quantity
            result.append(item)
        
        return result
    
    async def buy_item(self, user_id: int, item_id: str, guild_id: int = None) -> tuple[bool, str]:
        """Buy an item from any shop"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
            
        try:
            # Check all shop collections for the item
            item = None
            item_type = None
            
            # Check shop_items
            item = await self.db.shop_items.find_one({"id": item_id})
            if item:
                item_type = "item"
            
            # Check shop_fishing
            if not item:
                item = await self.db.shop_fishing.find_one({"id": item_id})
                if item:
                    item_type = "fishing"
            
            # Check shop_potions
            if not item:
                item = await self.db.shop_potions.find_one({"id": item_id})
                if item:
                    item_type = "potion"
                    
            # Check shop_upgrades
            if not item:
                item = await self.db.shop_upgrades.find_one({"id": item_id})
                if item:
                    item_type = "upgrade"
            
            if not item:
                return False, "Item not found in any shop"
                
            # Check if user has enough money
            wallet_balance = await self.get_wallet_balance(user_id, guild_id)
            if wallet_balance < item["price"]:
                return False, f"Insufficient funds. Need {item['price']}, have {wallet_balance}"
                
            # Process the purchase based on item type
            try:
                async with await self.client.start_session() as session:
                    async with session.start_transaction():
                        # Deduct money
                        if not await self.update_wallet(user_id, -item["price"], guild_id):
                            return False, "Failed to deduct payment"
                        
                        # Handle different item types
                        if item_type == "fishing":
                            if item["type"] == "rod":
                                if not await self.add_fishing_item(user_id, item, "rod"):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to add fishing rod"
                            elif item["type"] == "bait":
                                if not await self.add_fishing_item(user_id, item, "bait"):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to add fishing bait"
                                    
                        elif item_type == "potion":
                            if not await self.add_potion(user_id, item):
                                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                return False, "Failed to activate potion"
                                
                        elif item_type == "upgrade":
                            if item["type"] == "bank":
                                if not await self.increase_bank_limit(user_id, item["amount"], guild_id):
                                    await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                    return False, "Failed to upgrade bank"
                            elif item["type"] == "fishing":
                                # Handle rod upgrade logic here
                                pass
                                
                        elif item_type == "item":
                            # Add to inventory
                            result = await self.db.users.update_one(
                                {"_id": str(user_id)},
                                {"$push": {"inventory": item}},
                                upsert=True
                            )
                            if result.modified_count == 0 and not result.upserted_id:
                                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                                return False, "Failed to add item to inventory"
                        
                        await session.commit_transaction()
                        return True, f"Successfully purchased {item['name']}!"
                        
            except Exception as transaction_error:
                # If we're here, the transaction should have been automatically aborted
                self.logger.error(f"Transaction failed for item {item_id}: {transaction_error}")
                return False, f"Purchase failed during transaction: {str(transaction_error)}"
                        
        except Exception as e:
            self.logger.error(f"Failed to buy item {item_id}: {e}")
            return False, f"Purchase failed: {str(e)}"


    async def buy_item_simple(self, user_id: int, item_id: str, guild_id: int = None) -> tuple[bool, str]:
        """Buy an item from any shop (fixed version)"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
            
        try:
            # Find the item in shops
            item = None
            item_type = None
            
            # Check shop_items
            item = await self.db.shop_items.find_one({"id": item_id})
            if item:
                item_type = "item"
            
            # Check other shop types...
            if not item:
                item = await self.db.shop_fishing.find_one({"id": item_id})
                if item:
                    item_type = "fishing"
            
            if not item:
                item = await self.db.shop_potions.find_one({"id": item_id})
                if item:
                    item_type = "potion"
                    
            if not item:
                item = await self.db.shop_upgrades.find_one({"id": item_id})
                if item:
                    item_type = "upgrade"
            
            if not item:
                return False, "Item not found in any shop"
                
            # Check if user has enough money
            wallet_balance = await self.get_wallet_balance(user_id, guild_id)
            if wallet_balance < item["price"]:
                return False, f"Insufficient funds. Need {item['price']:,}, have {wallet_balance:,}"
                
            # Deduct money first
            if not await self.update_wallet(user_id, -item["price"], guild_id):
                return False, "Failed to deduct payment"
            
            # Handle different item types
            success = False
            error_msg = ""
            
            if item_type == "item":
                # Add to inventory - create a clean copy without MongoDB ObjectId
                clean_item = {
                    "id": item["id"],
                    "name": item["name"],
                    "price": item["price"],
                    "description": item.get("description", ""),
                    "type": item.get("type", "item")
                }
                
                result = await self.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$push": {"inventory": clean_item}},
                    upsert=True
                )
                success = result.modified_count > 0 or result.upserted_id is not None
                error_msg = "Failed to add item to inventory"
            
            # Handle other item types as before...
            elif item_type == "potion":
                success = await self.add_potion(user_id, item)
                error_msg = "Failed to activate potion"
            
            # If something went wrong, refund the money
            if not success:
                await self.update_wallet(user_id, item["price"], guild_id)  # Refund
                return False, error_msg
            
            return True, f"Successfully purchased {item['name']}!"
                        
        except Exception as e:
            # Try to refund if we got this far
            try:
                await self.update_wallet(user_id, item["price"], guild_id)
            except:
                pass
            return False, f"Purchase failed: {str(e)}"

    async def remove_from_inventory(self, user_id: int, guild_id: int, item_id: str, quantity: int = 1) -> bool:
        """Remove specific quantity of items from user's inventory"""
        if not await self.ensure_connected():
            return False
        
        user = await self.db.users.find_one({"_id": str(user_id)})
        if not user or "inventory" not in user:
            return False
        
        inventory = user["inventory"]
        items_to_keep = []
        remaining_to_remove = quantity
        
        # Filter items to keep/remove
        for item in inventory:
            if (item.get("id") == item_id or item.get("name") == item_id) and remaining_to_remove > 0:
                item_quantity = item.get("quantity", 1)
                if item_quantity > remaining_to_remove:
                    # Keep the item but reduce its quantity
                    new_item = item.copy()
                    new_item["quantity"] = item_quantity - remaining_to_remove
                    items_to_keep.append(new_item)
                    remaining_to_remove = 0
                else:
                    # Remove the entire item (or reduce quantity to 0)
                    remaining_to_remove -= item_quantity
            else:
                items_to_keep.append(item.copy())
        
        if remaining_to_remove > 0:
            return False  # Not enough items to remove
        
        # Update the user's inventory
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"inventory": items_to_keep}}
        )
        
        return result.modified_count > 0

    async def get_fish(self, user_id: int) -> list:
        """Get user's caught fish"""
        if not await self.ensure_connected():
            return []
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("fish", []) if user else []

    async def add_fish(self, user_id: int, fish: dict) -> bool:
        """Add a fish to user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$push": {"fish": fish}}
        )
        return result.modified_count > 0

    async def get_fishing_items(self, user_id: int) -> dict:
        """Get user's fishing items (rods and bait)"""
        if not await self.ensure_connected():
            return {"rods": [], "bait": []}
        user = await self.db.users.find_one({"_id": str(user_id)})
        return {
            "rods": user.get("fishing_rods", []),
            "bait": user.get("fishing_bait", [])
        } if user else {"rods": [], "bait": []}

    async def add_fishing_item(self, user_id: int, item: dict, item_type: str) -> bool:
        """Add a fishing item (rod or bait) to user's inventory"""
        if not await self.ensure_connected():
            return False
        field = "fishing_rods" if item_type == "rod" else "fishing_bait"
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$push": {field: item}}
        )
        return result.modified_count > 0

    async def remove_bait(self, user_id: int, bait_id: str, amount: int = 1) -> bool:
        """Remove bait from user's inventory after use"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$inc": {"fishing_bait.$[bait].amount": -amount}},
            array_filters=[{"bait.id": bait_id}]
        )
        if result.modified_count > 0:
            # Remove the bait entry if amount reaches 0
            await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$pull": {"fishing_bait": {"amount": {"$lte": 0}}}}
            )
        return result.modified_count > 0

    async def init_collections(self):
        """Initialize database collections and indexes"""
        if not await self.ensure_connected():
            return False
            
        if await self.db.shop_upgrades.count_documents({}) == 0:
            await self.db.shop_upgrades.insert_many([
                {
                    "id": "bank_note_small",
                    "name": "Small Bank Note",
                    "price": 5000,
                    "type": "bank",
                    "amount": 10000,
                    "description": "Expand your bank storage"
                },
                {
                    "id": "bank_note_large",
                    "name": "Large Bank Note",
                    "price": 20000,
                    "type": "bank",
                    "amount": 50000,
                    "description": "Significantly expand your bank storage"
                }
            ])

        # Create collections if they don't exist
        collections = [
            "users",
            "guild_settings", 
            "stats",
            "shops",
            "shop_items",
            "shop_potions",
            "shop_upgrades",
            "shop_fishing",
            "shop_bait",
            "shop_rod",
            "active_potions",
            "active_buffs"
        ]
        
        for coll_name in collections:
            if coll_name not in await self.db.list_collection_names():
                await self.db.create_collection(coll_name)

        # Set up indexes
        await self.db.users.create_index("_id")  # User ID
        await self.db.shops.create_index([("guild_id", 1), ("type", 1)])  # Shop lookups
        await self.db.active_potions.create_index("expires_at", expireAfterSeconds=0)  # TTL index
        await self.db.active_buffs.create_index("expires_at", expireAfterSeconds=0)  # TTL index
        
        # Initialize default shops if empty
        if await self.db.shop_items.count_documents({}) == 0:
            await self.db.shop_items.insert_many([
                {
                    "id": "vip",
                    "name": "VIP Role",
                    "price": 10000,
                    "description": "Grants VIP status and perks",
                    "type": "role"
                },
                {
                    "id": "color_role",
                    "name": "Custom Color",
                    "price": 5000,
                    "description": "Create a custom colored role",
                    "type": "role"
                },
                {
                    "id": "interest_token",
                    "name": "Interest Token",
                    "price": 50000,
                    "description": "Required to upgrade interest rate beyond level 20",
                    "type": "special"
                }
            ])
            
        if await self.db.shop_potions.count_documents({}) == 0:
            await self.db.shop_potions.insert_many([
                {
                    "id": "fishing_luck",
                    "name": "Fishing Luck",
                    "price": 1000,
                    "type": "fishing",
                    "multiplier": 1.5,
                    "duration": 60,
                    "description": "50% better fishing luck for 1 hour"
                },
                {
                    "id": "money_boost",
                    "name": "Money Boost",
                    "price": 2000,
                    "type": "money",
                    "multiplier": 2.0,
                    "duration": 30,
                    "description": "Double money from all sources for 30 minutes"
                }
            ])
            
        if await self.db.shop_upgrades.count_documents({}) == 0:
            await self.db.shop_upgrades.insert_many([
                {
                    "id": "bank_upgrade",
                    "name": "Bank Upgrade",
                    "price": 2500,
                    "type": "bank",
                    "amount": 5000,
                    "description": "Increase bank limit by 5000"
                },
                {
                    "id": "rod_upgrade",
                    "name": "Rod Enhancement",
                    "price": 10000,
                    "type": "fishing",
                    "multiplier": 0.2,
                    "description": "Upgrade your current rod's multiplier by 0.2x"
                }
            ])
            
        if await self.db.shop_fishing.count_documents({}) == 0:
            await self.db.shop_fishing.insert_many([
                {
                    "id": "beginner_rod",
                    "type": "rod",
                    "name": "Beginner Rod",
                    "price": 0,
                    "description": "Basic fishing rod",
                    "multiplier": 1.0
                },
                {
                    "id": "beginner_bait",
                    "type": "bait",
                    "name": "Beginner Bait",
                    "price": 0,
                    "amount": 10,
                    "description": "Basic bait for catching fish",
                    "catch_rates": {"normal": 1.0, "rare": 0.1}
                }
            ])
        if await self.db.shop_bait.count_documents({}) == 0:
            await self.db.shop_bait.insert_many([
                {
                    "id": "basic_bait",
                    "name": "Basic Bait",
                    "price": 100,
                    "amount": 5,
                    "description": "Basic bait for catching fish",
                    "catch_rates": {"normal": 1.0, "rare": 0.1}
                }
            ])
        if await self.db.shop_rod.count_documents({}) == 0:
            await self.db.shop_rod.insert_many([
                {
                    "id": "basic_rod",
                    "name": "Basic Rod",
                    "price": 500,
                    "description": "Basic fishing rod",
                    "multiplier": 1.0
                }
            ])
        return True
        
    async def get_shop_items(self, shop_type: str, guild_id: int = None) -> list:
        """Get items from a specific shop type"""
        if not await self.ensure_connected():
            return []
        
        collection = getattr(self.db, f"shop_{shop_type}", None)
        if not collection:
            return []
        
        if guild_id:
            # Get both guild-specific and global items
            pipeline = [
                {
                    "$match": {
                        "$or": [
                            {"guild_id": str(guild_id)},
                            {"guild_id": None}
                        ]
                    }
                }
            ]
            items = await collection.aggregate(pipeline).to_list(None)
        else:
            # Get only global items
            items = await collection.find({"guild_id": None}).to_list(None)
        
        return items
        
    async def add_shop_item(self, item: dict, shop_type: str, guild_id: int = None) -> bool:
        """Add an item to a specific shop"""
        if not await self.ensure_connected():
            return False
            
        collection = getattr(self.db, f"shop_{shop_type}", None)
        if not collection:
            return False
            
        if guild_id:
            item["guild_id"] = str(guild_id)
            
        result = await collection.update_one(
            {"id": item["id"], "guild_id": str(guild_id) if guild_id else None},
            {"$set": item},
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None

    async def get_interest_level(self, user_id: int) -> int:
        """Get user's interest level"""
        if not await self.ensure_connected():
            return 0
        user = await self.db.users.find_one({"_id": str(user_id)})
        return user.get("interest_level", 0) if user else 0

    async def upgrade_interest(self, user_id: int, cost: int, item_required: bool = False) -> tuple[bool, str]:
        """Upgrade user's interest level"""
        if not await self.ensure_connected():
            return False, "Database connection failed"
        
        current_level = await self.get_interest_level(user_id)
        
        # Check max level
        if current_level >= 60:
            return False, "You've reached the maximum interest level!\n-# for now..."
        
        # Check wallet balance
        wallet_balance = await self.get_wallet_balance(user_id)
        if wallet_balance < cost:
            return False, f"Insufficient funds! You need {cost:,} coins but only have {wallet_balance:,}."
        
        # Check if user has required item (for levels >= 20)
        if current_level >= 20:
            inventory = await self.get_inventory(user_id)
            has_token = False
            
            for item in inventory:
                if (item.get("id") == "interest_token" or 
                    item.get("name", "").lower() == "interest token"):
                    has_token = True
                    break
            
            if not has_token:
                return False, "You need an Interest Token to upgrade beyond level 20!"
        
        try:
            # Start transaction-like operations
            # 1. Deduct cost
            if not await self.update_wallet(user_id, -cost):
                return False, "Failed to deduct upgrade cost!"
            
            # 2. Remove ONE interest token if needed (not all of them!)
            if current_level >= 20:
                token_removed = await self.remove_from_inventory(user_id, None, "interest_token", 1)
                if not token_removed:
                    # Try with name instead of ID
                    token_removed = await self.remove_from_inventory(user_id, None, "Interest Token", 1)
                
                if not token_removed:
                    # Refund the money
                    await self.update_wallet(user_id, cost)
                    return False, "Failed to consume Interest Token!"
            
            # 3. Update interest level
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$inc": {"interest_level": 1}},
                upsert=True
            )
            
            if result.modified_count > 0 or result.upserted_id is not None:
                new_level = current_level + 1
                new_rate = 0.003 + (new_level * 0.05)
                return True, f"✅ Interest level upgraded to **{new_level}**! Your new daily rate is **{new_rate:.3f}%**"
            else:
                # Something went wrong, refund everything
                await self.update_wallet(user_id, cost)
                if current_level >= 20:
                    # Add the token back (create new token item)
                    token_item = {
                        "id": "interest_token",
                        "name": "Interest Token",
                        "price": 50000,
                        "description": "Required to upgrade interest rate beyond level 20",
                        "type": "special"
                    }
                    await self.db.users.update_one(
                        {"_id": str(user_id)},
                        {"$push": {"inventory": token_item}},
                        upsert=True
                    )
                return False, "Failed to upgrade interest level"
                
        except Exception as e:
            # Error occurred, try to refund
            await self.update_wallet(user_id, cost)
            return False, f"Upgrade failed: {str(e)}"

    async def clear_fish(self, user_id: int) -> bool:
        """Clear all fish from user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$set": {"fish": []}}
        )
        return result.modified_count > 0

    async def remove_fish(self, user_id: int, fish_id: str) -> bool:
        """Remove a specific fish from user's collection"""
        if not await self.ensure_connected():
            return False
        result = await self.db.users.update_one(
            {"_id": str(user_id)},
            {"$pull": {"fish": {"id": fish_id}}}
        )
        return result.modified_count > 0
    
    async def add_to_inventory(self, user_id: int, guild_id: int, item_data: dict, quantity: int = 1) -> bool:
        """Add an item to user's inventory with quantity support"""
        if not await self.ensure_connected():
            return False
        
        if not item_data or not item_data.get('id'):
            return False
        
        try:
            # Create a clean item copy without MongoDB-specific fields
            clean_item = {
                'id': item_data['id'],
                'name': item_data.get('name', item_data['id']),
                'description': item_data.get('description', ''),
                'type': item_data.get('type', 'item'),
                'price': item_data.get('price', 0),
                'value': item_data.get('value', item_data.get('price', 0))
            }
            
            # If the item has additional properties, include them
            for key, value in item_data.items():
                if key not in clean_item and not key.startswith('_'):
                    clean_item[key] = value
            
            # Add the item to inventory (multiple times if quantity > 1)
            result = await self.db.users.update_one(
                {"_id": str(user_id)},
                {"$push": {"inventory": {"$each": [clean_item] * (quantity if quantity > 0 else 1)}}},
                upsert=True
            )
            
            return result.modified_count > 0 or result.upserted_id is not None
            
        except Exception as e:
            self.logger.error(f"Failed to add item to inventory: {e}")
            return False

class SyncDatabase:
    """Synchronous database class for use with Flask web interface (SQLite & MongoDB)"""
    _instance = None
    _client = None
    _db = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(SyncDatabase, cls).__new__(cls)
                    cls._instance._connected = False
                    cls._instance.logger = logging.getLogger('SyncDatabase')
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return
        self._initialized = True
        self._connected = False
        self.logger = logging.getLogger('SyncDatabase')

        # Ensure data directory exists
        data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
        os.makedirs(data_dir, exist_ok=True)
        db_path = os.getenv('SQLITE_DATABASE_PATH', os.path.join(data_dir, 'database.sqlite'))
        self.logger.info(f"Using SQLite database at {db_path}")

        try:
            import sqlite3
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()
            self._create_tables()
            self.conn.commit()
            self.logger.info("SQLite database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize SQLite database: {e}")
            raise

    def _create_tables(self):
        """Create database tables if they don't exist."""
        try:
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS economy (
                    user_id INTEGER,
                    guild_id INTEGER DEFAULT 0,
                    wallet INTEGER DEFAULT 0,
                    bank INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, guild_id)
                )
            """)
            self.cursor.execute("""
                CREATE TABLE IF NOT EXISTS guild_stats (
                    guild_id INTEGER,
                    stat_type TEXT,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (guild_id, stat_type)
                )
            """)
        except Exception as e:
            self.logger.error(f"Error creating tables: {e}")
            raise

    @property
    def client(self):
        if self._client is None:
            MONGO_URI = os.getenv('MONGO_URI', config['MONGO_URI'])
            self._client = pymongo.MongoClient(MONGO_URI)
        return self._client

    @property
    def db(self):
        if self._db is None:
            self._db = self.client.bronxbot
        return self._db

    def ensure_connected(self) -> bool:
        """Ensure database connection is active."""
        if not self._connected:
            try:
                self.client.admin.command('ping')
                self._connected = True
                self.logger.info("Sync database connection established")
            except Exception as e:
                self.logger.error(f"Sync database connection failed: {e}")
                return False
        return True

    def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        """Get guild settings synchronously"""
        if not self.ensure_connected():
            return {}
        try:
            settings = self.db.guild_settings.find_one({"_id": str(guild_id)})
            return settings if settings else {}
        except Exception as e:
            self.logger.error(f"Error getting guild settings: {e}")
            return {}

    def update_guild_settings(self, guild_id: str, settings: Dict[str, Any]) -> bool:
        """Update guild settings synchronously"""
        if not self.ensure_connected():
            return False
        try:
            result = self.db.guild_settings.update_one(
                {"_id": str(guild_id)},
                {"$set": settings},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            self.logger.error(f"Error updating guild settings: {e}")
            return False

    def get_user_balance(self, user_id: int, guild_id: int = None):
        """Get user's wallet and bank balance"""
        try:
            self.cursor.execute("""
                SELECT wallet, bank FROM economy 
                WHERE user_id = ? AND guild_id = ?
            """, (user_id, guild_id or 0))
            result = self.cursor.fetchone()
            if result:
                return {"wallet": result[0], "bank": result[1]}
            return {"wallet": 0, "bank": 0}
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return {"wallet": 0, "bank": 0}

    # Change store_stats to be async-compatible
    async def store_stats(self, guild_id: int, stat_type: str):
        """Store guild statistics asynchronously"""
        return self.store_stats_sync(guild_id, stat_type)
    
    def store_stats_sync(self, guild_id: int, stat_type: str):
        """Store guild statistics synchronously"""
        try:
            valid_types = ["messages", "gained", "lost"]
            if stat_type not in valid_types:
                return False
                
            self.cursor.execute("""
                INSERT INTO guild_stats (guild_id, stat_type, count)
                VALUES (?, ?, 1)
                ON CONFLICT(guild_id, stat_type) DO UPDATE 
                SET count = count + 1
            """, (guild_id, stat_type))
            self.conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error storing stats: {e}")
            return False

    def get_stats(self, guild_id: int):
        """Get guild statistics"""
        try:
            self.cursor.execute("""
                SELECT stat_type, count FROM guild_stats
                WHERE guild_id = ?
            """, (guild_id,))
            results = self.cursor.fetchall()
            return {stat[0]: stat[1] for stat in results}
        except Exception as e:
            self.logger.error(f"Error getting stats: {e}")
            return {}



# Create global database instances
async_db = AsyncDatabase.get_instance()  # For Discord bot
db = SyncDatabase()  # For Flask web interface