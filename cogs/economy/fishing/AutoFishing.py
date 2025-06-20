from nextcord.ext import commands
import nextcord
import random
import asyncio
import uuid
import datetime
from utils.db import db
from utils.safe_reply import safe_reply

class AutoFishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.BASE_PRICE = 1000
        self.PRICE_MULTIPLIER = 2.5
        self.MAX_AUTOFISHERS = 30
        self.BAIT_COST = 50
        self.CATCH_CHANCE = 0.5
        self.AUTOFISH_INTERVAL = 30  # seconds
        self.autofishing_task = None
        self.last_autofish_time = datetime.datetime.now()
        
        # Load available rods and baits from JSON files
        self.available_rods = self._load_available_rods()
        self.available_baits = self._load_available_baits()
        
        # Load aliases dynamically from JSON files
        self.rod_aliases = self._load_rod_aliases()
        self.bait_aliases = self._load_bait_aliases()
        
        # Bag limit system - based on total deposited amount
        self.BAG_LIMITS = {
            0: 10,        # Default: 10 fish
            1000: 15,     # 1k deposited: 15 fish
            5000: 30,     # 5k deposited: 30 fish
            10000: 50,    # 10k deposited: 50 fish
            20000: 75,    # 20k deposited: 75 fish
            30000: 100,   # 30k deposited: 100 fish
            50000: 150,   # 50k deposited: 150 fish
            100000: 200,  # 100k deposited: 200 fish
            250000: 350,  # 250k deposited: 350 fish
            500000: 500,  # 500k deposited: 500 fish
            1000000: 750, # 1M deposited: 750 fish
            2000000: 1000, # 2M deposited: 1000 fish
            5000000: 2500, # 5M deposited: 2500 fish
            10000000: 5000, # 10M deposited: 5000 fish
            25000000: 10000, # 25M deposited: 10000 fish
            50000000: 25000, # 50M deposited: 25000 fish
            100000000: 50000, # 100M deposited: 50000 fish
            250000000: 100000, # 250M deposited: 100000 fish
            500000000: 250000, # 500M deposited: 250000 fish
            1000000000: 1000000000 # 1B deposited: 1 billion fish limit
        }
        
    async def cog_load(self):
        self.autofishing_task = self.bot.loop.create_task(self.autofishing_loop())

    def cog_unload(self):
        if self.autofishing_task:
            self.autofishing_task.cancel()

    async def autofishing_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                self.last_autofish_time = datetime.datetime.now()
                # Get all users with autofishers
                users = await self.get_all_autofisher_users()
                for user_id in users:
                    try:
                        await self.process_autofishing(user_id)
                    except Exception as e:
                        print(f"Error processing autofishing for {user_id}: {e}")
                await asyncio.sleep(self.AUTOFISH_INTERVAL)  # Run every 30 seconds
            except Exception as e:
                print(f"Error in autofishing loop: {e}")
                await asyncio.sleep(60)

    async def get_all_autofisher_users(self):
        """Get all users who have autofishers"""
        try:
            cursor = db.db.users.find({"autofisher.count": {"$gt": 0}})
            users = []
            async for user in cursor:
                users.append(int(user["_id"]))
            return users
        except Exception as e:
            print(f"Error getting autofisher users: {e}")
            return []

    async def get_user_inventory(self, user_id: int):
        """Get user's inventory from database"""
        try:
            user_data = await db.db.users.find_one({"_id": str(user_id)})
            if not user_data:
                return None
            return user_data.get("inventory", {})
        except Exception as e:
            print(f"Error getting user inventory: {e}")
            return None

    async def has_bait(self, user_id: int):
        """Check if user has any bait"""
        inventory = await self.get_user_inventory(user_id)
        if not inventory:
            return False
        
        bait_inventory = inventory.get("bait", {})
        for bait_id, quantity in bait_inventory.items():
            if quantity > 0:
                return True
        return False

    async def remove_any_bait(self, user_id: int):
        """Remove one bait of any type from user's inventory - Fixed version"""
        try:
            inventory = await self.get_user_inventory(user_id)
            if not inventory:
                return False
            
            bait_inventory = inventory.get("bait", {})
            for bait_id, quantity in bait_inventory.items():
                if quantity > 0:
                    # Use the new inventory structure
                    result = await db.db.users.update_one(
                        {"_id": str(user_id), f"inventory.bait.{bait_id}": {"$gt": 0}},
                        {"$inc": {f"inventory.bait.{bait_id}": -1}}
                    )
                    if result.modified_count > 0:
                        return True
                    
            # Try old structure as fallback
            user_data = await db.db.users.find_one({"_id": str(user_id)})
            if user_data and "bait" in user_data:
                old_bait = user_data.get("bait", [])
                if old_bait:
                    # Remove first available bait
                    result = await db.db.users.update_one(
                        {"_id": str(user_id)},
                        {"$pop": {"bait": -1}}  # Remove first element
                    )
                    return result.modified_count > 0
                    
            return False
        except Exception as e:
            print(f"Error removing bait: {e}")
            return False

    async def buy_bait_for_autofisher(self, user_id: int, cost: int):
        """Buy bait using autofisher balance"""
        try:
            # Remove cost from autofisher balance and add bait
            result = await db.db.users.update_one(
                {"_id": str(user_id), "autofisher.balance": {"$gte": cost}},
                {
                    "$inc": {
                        "autofisher.balance": -cost,
                        "inventory.bait.pro_bait": 10
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error buying bait for autofisher: {e}")
            return False

    def get_bag_limit(self, total_deposited):
        """Calculate bag limit based on total amount deposited"""
        for threshold in sorted(self.BAG_LIMITS.keys(), reverse=True):
            if total_deposited >= threshold:
                return self.BAG_LIMITS[threshold]
        return self.BAG_LIMITS[0]  # Default limit

    async def get_current_fish_count(self, user_id):
        """Get current number of fish from autofisher"""
        try:
            user_data = await db.db.users.find_one({"_id": str(user_id)})
            if not user_data:
                return 0
            
            # Count fish that were auto-caught
            fish_list = user_data.get("fish", [])
            auto_fish_count = 0
            for fish in fish_list:
                # Handle both dict and list formats safely
                if isinstance(fish, dict) and fish.get("auto_caught", False):
                    auto_fish_count += 1
                elif isinstance(fish, list):
                    # Skip malformed entries
                    continue
            return auto_fish_count
        except Exception as e:
            print(f"Error getting fish count: {e}")
            return 0

    async def can_catch_fish(self, user_id):
        """Check if user can catch more fish (bag limit check)"""
        try:
            user_data = await db.db.users.find_one({"_id": str(user_id)})
            if not user_data:
                return False
            
            autofisher_data = user_data.get("autofisher", {})
            total_deposited = autofisher_data.get("total_deposited", 0)
            
            current_fish_count = await self.get_current_fish_count(user_id)
            bag_limit = self.get_bag_limit(total_deposited)
            
            return current_fish_count < bag_limit
        except Exception as e:
            print(f"Error checking bag limit: {e}")
            return False

    async def process_autofishing(self, user_id):
        try:
            # Get autofisher data
            user_data = await db.db.users.find_one({"_id": str(user_id)})
            if not user_data:
                return
                
            autofisher_data = user_data.get("autofisher", {})
            if not autofisher_data or not autofisher_data.get("count", 0):
                return
            
            # Check if user has any rods
            inventory = user_data.get("inventory", {})
            rod_inventory = inventory.get("rod", {})
            has_rods = any(quantity > 0 for quantity in rod_inventory.values())
            
            if not has_rods:
                return  # Can't fish without rods
                
            autofisher_count = autofisher_data.get("count", 0)
            autofisher_balance = autofisher_data.get("balance", 0)
            active_rod = autofisher_data.get("active_rod", "advanced_rod")
            active_bait = autofisher_data.get("active_bait", "pro_bait")
            caught_fish = []
            
            # Process each autofisher
            for _ in range(autofisher_count):
                # Check bag limit first
                if not await self.can_catch_fish(user_id):
                    break  # Bag is full, stop fishing
                    
                # Random chance to catch something
                if random.random() > self.CATCH_CHANCE:
                    continue
                    
                # Check if has bait, if not try to buy some
                if not await self.has_bait(user_id):
                    if autofisher_balance >= self.BAIT_COST:
                        if await self.buy_bait_for_autofisher(user_id, self.BAIT_COST):
                            autofisher_balance -= self.BAIT_COST
                        else:
                            continue  # Failed to buy bait
                    else:
                        continue  # Not enough balance for bait
                        
                # Remove bait
                if not await self.remove_any_bait(user_id):
                    continue  # No bait available
                    
                # Generate fish (simpler catches for autofisher)
                fish_type = self.determine_auto_fish_type()
                fish_value = self.get_fish_value(fish_type)
                
                fish = {
                    "id": str(uuid.uuid4()),
                    "type": fish_type,
                    "name": f"{fish_type.title()} Fish",
                    "value": fish_value,
                    "caught_at": datetime.datetime.now().isoformat(),
                    "auto_caught": True,
                    "bait_used": active_bait,
                    "rod_used": active_rod
                }
                caught_fish.append(fish)
                
            # Add caught fish to database
            if caught_fish:
                await self.add_fish_batch(user_id, caught_fish)
                
            # Update autofisher balance if it changed
            if autofisher_balance != autofisher_data.get("balance", 0):
                await db.db.users.update_one(
                    {"_id": str(user_id)},
                    {"$set": {"autofisher.balance": autofisher_balance}}
                )
                
        except Exception as e:
            print(f"Error processing autofishing for {user_id}: {e}")

    def determine_auto_fish_type(self):
        """Determine what type of fish to catch (autofishers catch mostly normal fish)"""
        rand = random.random()
        if rand < 0.7:
            return "normal"
        elif rand < 0.85:
            return "uncommon"
        elif rand < 0.95:
            return "rare"
        else:
            return "epic"

    def get_fish_value(self, fish_type):
        """Get value range for fish type (increased values)"""
        value_ranges = {
            "normal": (50, 300),      # Was 10-100, now 50-300
            "uncommon": (200, 600),   # Was 50-200, now 200-600
            "rare": (500, 1500),      # Was 100-500, now 500-1500
            "epic": (1000, 3000),     # Was 200-1000, now 1000-3000
            "legendary": (2500, 6000), # Was 500-2000, now 2500-6000
            "mythical": (5000, 15000), # Was 1000-5000, now 5000-15000
        }
        min_val, max_val = value_ranges.get(fish_type, (50, 300))
        return random.randint(min_val, max_val)

    async def add_fish_batch(self, user_id: int, fish_list):
        """Add multiple fish to user's collection"""
        try:
            result = await db.db.users.update_one(
                {"_id": str(user_id)},
                {"$push": {"fish": {"$each": fish_list}}},
                upsert=True
            )
            return result.modified_count > 0 or result.upserted_id is not None
        except Exception as e:
            print(f"Error adding fish batch: {e}")
            return False

    @commands.group(aliases=['af', 'afish'], invoke_without_command=True)
    async def auto(self, ctx):
        """Autofisher management system"""
        try:
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            autofisher_data = user_data.get("autofisher", {}) if user_data else {}
            
            embed = nextcord.Embed(title="🤖 Autofisher System", color=0x2b2d31)
            
            if not autofisher_data or not autofisher_data.get("count", 0):
                embed.description = "You don't have any autofishers yet!"
                embed.add_field(name="First Autofisher Cost", 
                               value=f"{self.BASE_PRICE} {self.currency}")
                return await safe_reply(ctx, embed=embed)
                
            count = autofisher_data.get("count", 0)
            balance = autofisher_data.get("balance", 0)
            total_deposited = autofisher_data.get("total_deposited", 0)
            next_cost = int(self.BASE_PRICE * (self.PRICE_MULTIPLIER ** count)) if count < self.MAX_AUTOFISHERS else "MAX"
            
            # Get bag information
            current_fish_count = await self.get_current_fish_count(ctx.author.id)
            bag_limit = self.get_bag_limit(total_deposited)
            
            embed.add_field(name="Autofishers", value=f"{count:,}/{self.MAX_AUTOFISHERS}", inline=True)
            embed.add_field(name="Balance", value=f"{balance:,} {self.currency}", inline=True)
            embed.add_field(name="Fish Bag", value=f"{current_fish_count:,}/{bag_limit:,}", inline=True)
            
            # Show next bag upgrade
            next_upgrade = None
            for threshold in sorted(self.BAG_LIMITS.keys()):
                if threshold > total_deposited:
                    next_upgrade = threshold
                    break
            
            if next_upgrade:
                next_limit = self.BAG_LIMITS[next_upgrade]
                needed = next_upgrade - total_deposited
                embed.add_field(
                    name="Next Bag Upgrade", 
                    value=f"{next_limit} fish (deposit {needed:,} more)", 
                    inline=False
                )
            else:
                embed.add_field(name="Bag Status", value="Maximum bag capacity!", inline=False)
            
            # Calculate time until next autofish
            if hasattr(self, 'last_autofish_time'):
                time_since_last = (datetime.datetime.now() - self.last_autofish_time).total_seconds()
                time_until_next = max(0, self.AUTOFISH_INTERVAL - time_since_last)
                if time_until_next > 0:
                    embed.add_field(name="Next Autofish", value=f"{int(time_until_next)}s", inline=True)
                else:
                    embed.add_field(name="Next Autofish", value="Now!", inline=True)
            
            if count < self.MAX_AUTOFISHERS:
                embed.add_field(name="Next Autofisher Cost", value=f"{next_cost:,} {self.currency}", inline=False)
                
                # Create view with buy button
                view = nextcord.ui.View(timeout=60.0)
                
                async def buy_callback(interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("❌ This isn't your button!", ephemeral=True)
                    
                    # Check if user can afford it
                    balance = await db.get_wallet_balance(ctx.author.id)
                    if balance < next_cost:
                        return await interaction.response.send_message(
                            f"❌ You need {next_cost:,} {self.currency} but only have {balance:,} {self.currency}!", 
                            ephemeral=True
                        )
                    
                    # Buy the autofisher
                    if await db.update_wallet(ctx.author.id, -next_cost):
                        new_count = count + 1
                        await db.db.users.update_one(
                            {"_id": str(ctx.author.id)},
                            {"$set": {
                                "autofisher.count": new_count,
                                "autofisher.balance": autofisher_data.get("balance", 0)
                            }},
                            upsert=True
                        )
                        
                        # Update the original embed
                        embed.set_field_at(0, name="Autofishers", value=f"{new_count:,}/{self.MAX_AUTOFISHERS}", inline=True)
                        
                        if new_count < self.MAX_AUTOFISHERS:
                            new_next_cost = int(self.BASE_PRICE * (self.PRICE_MULTIPLIER ** new_count))
                            embed.set_field_at(-1, name="Next Autofisher Cost", value=f"{new_next_cost:,} {self.currency}", inline=False)
                        else:
                            embed.set_field_at(-1, name="Status", value="Maximum autofishers reached!", inline=False)
                            view.clear_items()
                        
                        # Add success message to embed description
                        embed.description = f"✅ Successfully purchased autofisher #{new_count:,}!"
                        
                        await interaction.response.edit_message(embed=embed, view=view)
                    else:
                        await interaction.response.send_message("❌ Failed to purchase autofisher!", ephemeral=True)
                
                buy_button = nextcord.ui.Button(
                    label=f"Buy Autofisher #{count + 1:,}", 
                    style=nextcord.ButtonStyle.green,
                    emoji="🤖"
                )
                buy_button.callback = buy_callback
                view.add_item(buy_button)
                
                await safe_reply(ctx, embed=embed, view=view)
            else:
                embed.add_field(name="Status", value="Maximum autofishers reached!", inline=False)
                await safe_reply(ctx, embed=embed)
        except Exception as e:
            print(f"Error in auto command: {e}")
            await safe_reply(ctx, "❌ Error retrieving autofisher data!")

    @auto.command(aliases=['buyauto'])
    async def buy(self, ctx):
        """Buy an autofisher"""
        try:
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            autofisher_data = user_data.get("autofisher", {"count": 0, "balance": 0}) if user_data else {"count": 0, "balance": 0}
            
            current_count = autofisher_data.get("count", 0)
            
            if current_count >= self.MAX_AUTOFISHERS:
                return await safe_reply(ctx, f"You've reached the max of {self.MAX_AUTOFISHERS} autofishers!")
                
            cost = int(self.BASE_PRICE * (self.PRICE_MULTIPLIER ** current_count))
            balance = await db.get_wallet_balance(ctx.author.id)
            
            if balance < cost:
                return await safe_reply(ctx, f"Need {cost:,} {self.currency} (You have {balance:,})")
                
            if await db.update_wallet(ctx.author.id, -cost):
                new_count = current_count + 1
                await db.db.users.update_one(
                    {"_id": str(ctx.author.id)},
                    {"$set": {
                        "autofisher.count": new_count,
                        "autofisher.balance": autofisher_data.get("balance", 0)
                    }},
                    upsert=True
                )
                await safe_reply(ctx, f"✅ Purchased autofisher #{new_count:,}!")
            else:
                await safe_reply(ctx, "❌ Failed to purchase autofisher!")
        except Exception as e:
            print(f"Error buying autofisher: {e}")
            await safe_reply(ctx, "❌ Error purchasing autofisher!")

    @auto.command(aliases=['dep', 'd'])
    async def deposit(self, ctx, amount: int):
        """Deposit money into autofisher balance"""
        if amount <= 0:
            return await safe_reply(ctx, "Amount must be positive!")
            
        try:
            # Check if user has autofisher
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            if not user_data or not user_data.get("autofisher", {}).get("count", 0):
                return await safe_reply(ctx, "❌ Buy an autofisher first!")
                
            # Check user balance
            balance = await db.get_wallet_balance(ctx.author.id)
            if balance < amount:
                return await safe_reply(ctx, f"❌ You only have {balance:,} {self.currency}")
                
            # Attempt to update balance
            balance_updated = await db.update_wallet(ctx.author.id, -amount)
            if not balance_updated:
                return await safe_reply(ctx, "❌ Failed to deduct money from your wallet!")
            
            # Update autofisher data
            result = await db.db.users.update_one(
                {"_id": str(ctx.author.id)},
                {"$inc": {
                    "autofisher.balance": amount,
                    "autofisher.total_deposited": amount
                }},
                upsert=True
            )
            
            if result.modified_count > 0 or result.upserted_id:
                # Verify the deposit worked
                updated_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
                new_balance = updated_data.get("autofisher", {}).get("balance", 0)
                total_deposited = updated_data.get("autofisher", {}).get("total_deposited", 0)
                
                embed = nextcord.Embed(
                    title="✅ Deposit Successful!",
                    description=f"Deposited **{amount:,}** {self.currency} into autofisher",
                    color=nextcord.Color.green()
                )
                embed.add_field(name="New Balance", value=f"{new_balance:,} {self.currency}", inline=True)
                embed.add_field(name="Total Deposited", value=f"{total_deposited:,} {self.currency}", inline=True)
                
                # Show bag limit upgrade if applicable
                bag_limit = self.get_bag_limit(total_deposited)
                embed.add_field(name="Fish Bag Limit", value=f"{bag_limit:,} fish", inline=True)
                
                await safe_reply(ctx, embed=embed)
            else:
                # Refund if autofisher update failed
                await db.update_wallet(ctx.author.id, amount)
                await safe_reply(ctx, "❌ Failed to update autofisher balance! Money refunded.")
                
        except Exception as e:
            print(f"Error depositing to autofisher: {e}")
            # Try to refund on error
            try:
                await db.update_wallet(ctx.author.id, amount)
            except:
                pass
            await safe_reply(ctx, "❌ Error depositing money! Please try again.")

    @auto.command()
    async def collect(self, ctx):
        """Collect and sell auto-caught fish"""
        try:
            fish = await db.get_fish(ctx.author.id)
            if not fish:
                return await safe_reply(ctx, "No fish in your collection!")
                
            auto_fish = [f for f in fish if f.get("auto_caught")]
            
            if not auto_fish:
                return await safe_reply(ctx, "No auto-caught fish to collect!")
                
            total_value = sum(f["value"] for f in auto_fish)
            
            # Remove auto-caught fish and add money
            auto_fish_ids = [f["id"] for f in auto_fish]
            
            result = await db.db.users.update_one(
                {"_id": str(ctx.author.id)},
                {"$pull": {"fish": {"id": {"$in": auto_fish_ids}}}}
            )
            
            if result.modified_count > 0:
                if await db.update_wallet(ctx.author.id, total_value):
                    embed = nextcord.Embed(
                        title="🤖 Auto-Fish Collection",
                        description=f"Sold {len(auto_fish):,} auto-caught fish for **{total_value:,}** {self.currency}",
                        color=nextcord.Color.green()
                    )
                    await safe_reply(ctx, embed=embed)
                else:
                    await safe_reply(ctx, "❌ Error updating balance!")
            else:
                await safe_reply(ctx, "❌ No auto-caught fish found!")
                
        except Exception as e:
            print(f"Error collecting auto fish: {e}")
            await safe_reply(ctx, "❌ Error collecting auto-caught fish!")

    @auto.command()
    async def status(self, ctx):
        """Check autofisher status and recent catches"""
        try:
            fish = await db.get_fish(ctx.author.id)
            auto_fish = [f for f in fish if f.get("auto_caught")] if fish else []
            
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            autofisher_data = user_data.get("autofisher", {}) if user_data else {}
            
            embed = nextcord.Embed(title="🤖 Autofisher Status", color=0x2b2d31)
            
            if not autofisher_data or not autofisher_data.get("count", 0):
                embed.description = "You don't have any autofishers!"
                return await safe_reply(ctx, embed=embed)
            
            count = autofisher_data.get("count", 0)
            balance = autofisher_data.get("balance", 0)
            active_rod = autofisher_data.get("active_rod", "advanced_rod")
            active_bait = autofisher_data.get("active_bait", "pro_bait")
            
            embed.add_field(name="Active Autofishers", value=f"{count}", inline=True)
            embed.add_field(name="Balance", value=f"{balance} {self.currency}", inline=True)
            embed.add_field(name="Pending Fish", value=f"{len(auto_fish)}", inline=True)
            
            # Show active gear
            embed.add_field(
                name="🎣 Active Rod", 
                value=active_rod.replace('_', ' ').title(), 
                inline=True
            )
            embed.add_field(
                name="🪱 Active Bait", 
                value=active_bait.replace('_', ' ').title(), 
                inline=True
            )
            embed.add_field(name="⚙️", value="Use `.auto configure` to change gear", inline=True)
            
            if auto_fish:
                total_value = sum(f["value"] for f in auto_fish)
                embed.add_field(name="Pending Value", value=f"{total_value:,} {self.currency}", inline=False)
                embed.set_footer(text="Use '.auto collect' to collect your fish!")
            
            await safe_reply(ctx, embed=embed)
            
        except Exception as e:
            print(f"Error checking autofisher status: {e}")
            await safe_reply(ctx, "❌ Error checking autofisher status!")

    def _load_available_rods(self):
        """Load available rod types from JSON file"""
        try:
            import json
            import os
             # Start with hardcoded rods - UPDATED to include new rods
            available = [
                "basic_rod", "advanced_rod", "reinforced_rod", "pro_rod", "expert_rod", "champion_rod",
                "master_rod", "titanium_rod", "plasma_rod", "enchanted_rod", "legendary_rod", 
                "dragon_rod", "phoenix_rod", "shadow_rod", "crystal_rod", "leviathan_rod", 
                "stellar_rod", "mythical_rod", "cosmic_rod", "nebula_rod", "galactic_rod",
                "quantum_rod", "astral_rod", "ethereal_rod", "void_rod", "infinity_rod",
                "omniversal_rod", "genesis_rod", "subatomic_rod", "dev_rod"
            ]
            
            # Try to load from JSON
            json_path = "data/shop/rods.json"
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    rods_data = json.load(f)
                
                # Add JSON rods
                for rod_id in rods_data.keys():
                    if rod_id not in available:
                        available.append(rod_id)
                        
                print(f"Loaded {len(rods_data)} rod types from JSON")
            else:
                print(f"Rod JSON file not found at {json_path}")
                    
            return available
        except Exception as e:
            print(f"Could not load rods from JSON: {e}")
            return ["basic_rod", "advanced_rod", "pro_rod", "master_rod", "legendary_rod", "mythical_rod", "cosmic_rod"]

    def _load_available_baits(self):
        """Load available bait types from JSON file"""
        try:
            import json
            import os
            
            # Start with hardcoded baits - UPDATED to include new baits
            available = [
                "beginner_bait", "advanced_bait", "enhanced_bait", "master_bait", "legendary_bait", 
                "enchanted_bait", "phoenix_bait", "cosmic_bait", "solar_bait", "plasma_bait",
                "mystic_bait", "ethereal_bait", "divine_bait", "shadow_bait", "arcane_bait",
                "void_bait", "crystalline_bait", "temporal_bait", "celestial_bait", 
                "primordial_bait", "reality_bait", "dimensional_bait", "quantum_bait",
                "omega_bait", "nano_bait", "subatomic_bait"
            ]
            
            # Try to load from JSON
            json_path = "data/shop/bait.json"
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    baits_data = json.load(f)
                
                # Add JSON baits
                for bait_id in baits_data.keys():
                    if bait_id not in available:
                        available.append(bait_id)
                        
                print(f"Loaded {len(baits_data)} bait types from JSON")
            else:
                print(f"Bait JSON file not found at {json_path}")
                    
            return available
        except Exception as e:
            print(f"Could not load baits from JSON: {e}")
            return ["beginner_bait", "pro_bait", "premium_bait", "legendary_bait", "mythical_bait", "divine_bait", "cosmic_bait"]

    def _load_rod_aliases(self):
        """Load rod aliases dynamically from JSON file"""
        try:
            import json
            import os
            
            aliases = {}
            json_path = "data/shop/rods.json"
            
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    rods_data = json.load(f)
                
                # Build aliases dictionary from JSON data
                for rod_id, rod_data in rods_data.items():
                    if "aliases" in rod_data:
                        for alias in rod_data["aliases"]:
                            aliases[alias.lower()] = rod_id
                
                print(f"Loaded {len(aliases)} rod aliases from JSON")
            else:
                print(f"Rod JSON file not found at {json_path}")
                
            return aliases
        except Exception as e:
            print(f"Could not load rod aliases from JSON: {e}")
            return {}

    def _load_bait_aliases(self):
        """Load bait aliases dynamically from JSON file"""
        try:
            import json
            import os
            
            aliases = {}
            json_path = "data/shop/bait.json"
            
            if os.path.exists(json_path):
                with open(json_path, "r") as f:
                    baits_data = json.load(f)
                
                # Build aliases dictionary from JSON data
                for bait_id, bait_data in baits_data.items():
                    if "aliases" in bait_data:
                        for alias in bait_data["aliases"]:
                            aliases[alias.lower()] = bait_id
                
                print(f"Loaded {len(aliases)} bait aliases from JSON")
            else:
                print(f"Bait JSON file not found at {json_path}")
                
            return aliases
        except Exception as e:
            print(f"Could not load bait aliases from JSON: {e}")
            return {}

    def _resolve_rod_alias(self, rod_input: str) -> str:
        """Resolve rod alias to full rod ID"""
        if not rod_input:
            return None
        
        rod_input = rod_input.lower().strip()
        
        # Check if it's already a valid rod ID
        if rod_input in self.available_rods:
            return rod_input
        
        # Check aliases
        if rod_input in self.rod_aliases:
            return self.rod_aliases[rod_input]
        
        # Check partial matches (e.g., "quantum_r" -> "quantum_rod")
        for rod_id in self.available_rods:
            if rod_id.startswith(rod_input):
                return rod_id
        
        return None

    def _resolve_bait_alias(self, bait_input: str) -> str:
        """Resolve bait alias to full bait ID"""
        if not bait_input:
            return None
        
        bait_input = bait_input.lower().strip()
        
        # Check if it's already a valid bait ID
        if bait_input in self.available_baits:
            return bait_input
        
        # Check aliases
        if bait_input in self.bait_aliases:
            return self.bait_aliases[bait_input]
        
        # Check partial matches (e.g., "quantum_b" -> "quantum_bait")
        for bait_id in self.available_baits:
            if bait_id.startswith(bait_input):
                return bait_id
        
        return None

    @auto.command(aliases=['config', 'cfg'])
    async def configure(self, ctx, rod_type: str = None, bait_type: str = None):
        """Configure active rod and bait for autofishing"""
        if not rod_type and not bait_type:
            # Show current configuration and available options
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            autofisher_data = user_data.get("autofisher", {}) if user_data else {}
            
            current_rod = autofisher_data.get("active_rod", "advanced_rod")
            current_bait = autofisher_data.get("active_bait", "pro_bait")
            
            embed = nextcord.Embed(title="🎣 Autofisher Configuration", color=0x2b2d31)
            embed.add_field(name="Active Rod", value=current_rod.replace('_', ' ').title(), inline=True)
            embed.add_field(name="Active Bait", value=current_bait.replace('_', ' ').title(), inline=True)
            
            # Show available rods with aliases
            rods_text = ", ".join(self.available_rods[:10])  # Show first 10
            if len(self.available_rods) > 10:
                rods_text += f"... (+{len(self.available_rods) - 10} more)"
            embed.add_field(name="Available Rods", value=rods_text, inline=False)
            
            # Show available baits with aliases
            baits_text = ", ".join(self.available_baits[:10])  # Show first 10
            if len(self.available_baits) > 10:
                baits_text += f"... (+{len(self.available_baits) - 10} more)"
            embed.add_field(name="Available Baits", value=baits_text, inline=False)
            
            # Show some common aliases
            embed.add_field(
                name="Common Aliases", 
                value="**Rods:** quantum, cosmic, void, divine, etc.\n**Baits:** quantum, void, crystal, divine, etc.", 
                inline=False
            )
            
            embed.add_field(
                name="Usage", 
                value="`.auto configure <rod_type> <bait_type>`\nExample: `.auto config quantum void`", 
                inline=False
            )
            return await safe_reply(ctx, embed=embed)
        
        # Resolve rod alias
        if rod_type:
            resolved_rod = self._resolve_rod_alias(rod_type)
            if not resolved_rod:
                embed = nextcord.Embed(title="❌ Invalid Rod Type", color=0xff0000)
                embed.add_field(
                    name="Available Rods", 
                    value=", ".join(self.available_rods), 
                    inline=False
                )
                embed.add_field(
                    name="Common Aliases",
                    value="quantum, cosmic, void, divine, basic, pro, etc.",
                    inline=False
                )
                return await safe_reply(ctx, embed=embed)
            rod_type = resolved_rod
        
        # Resolve bait alias
        if bait_type:
            resolved_bait = self._resolve_bait_alias(bait_type)
            if not resolved_bait:
                embed = nextcord.Embed(title="❌ Invalid Bait Type", color=0xff0000)
                embed.add_field(
                    name="Available Baits", 
                    value=", ".join(self.available_baits), 
                    inline=False
                )
                embed.add_field(
                    name="Common Aliases",
                    value="quantum, void, crystal, divine, basic, pro, etc.",
                    inline=False
                )
                return await safe_reply(ctx, embed=embed)
            bait_type = resolved_bait
        
        # Check if user has the specified rod and bait in their inventory
        user_inventory = await self.get_user_inventory(ctx.author.id)
        if not user_inventory:
            return await safe_reply(ctx, "❌ You don't have any fishing gear!")
        
        rod_inventory = user_inventory.get("rod", {})
        bait_inventory = user_inventory.get("bait", {})
        
        # Verify rod ownership
        if rod_type and rod_inventory.get(rod_type, 0) <= 0:
            return await safe_reply(ctx, f"❌ You don't have a {rod_type.replace('_', ' ').title()} in your inventory!")
        
        # Verify bait ownership
        if bait_type and bait_inventory.get(bait_type, 0) <= 0:
            return await safe_reply(ctx, f"❌ You don't have {bait_type.replace('_', ' ').title()} in your inventory!")
        
        # Update configuration
        update_data = {}
        if rod_type:
            update_data["autofisher.active_rod"] = rod_type
        if bait_type:
            update_data["autofisher.active_bait"] = bait_type
        
        result = await db.db.users.update_one(
            {"_id": str(ctx.author.id)},
            {"$set": update_data},
            upsert=True
        )
        
        if result.modified_count > 0 or result.upserted_id:
            embed = nextcord.Embed(title="✅ Configuration Updated", color=0x00ff00)
            if rod_type:
                embed.add_field(name="Active Rod", value=rod_type.replace('_', ' ').title(), inline=True)
            if bait_type:
                embed.add_field(name="Active Bait", value=bait_type.replace('_', ' ').title(), inline=True)
            
            embed.set_footer(text="Your autofishers will now use this gear for future catches!")
            await safe_reply(ctx, embed=embed)
        else:
            await safe_reply(ctx, "❌ Failed to update configuration!")

    @auto.command(name="test_bag", hidden=True)
    @commands.is_owner()
    async def test_bag_system(self, ctx):
        """Test the bag limit system"""
        try:
            user_data = await db.db.users.find_one({"_id": str(ctx.author.id)})
            autofisher_data = user_data.get("autofisher", {}) if user_data else {}
            
            total_deposited = autofisher_data.get("total_deposited", 0)
            current_fish_count = await self.get_current_fish_count(ctx.author.id)
            bag_limit = self.get_bag_limit(total_deposited)
            can_catch = await self.can_catch_fish(ctx.author.id)
            
            embed = nextcord.Embed(
                title="🧪 Bag System Test",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(name="Total Deposited", value=f"{total_deposited:,} {self.currency}", inline=True)
            embed.add_field(name="Current Fish Count", value=f"{current_fish_count}", inline=True)
            embed.add_field(name="Bag Limit", value=f"{bag_limit}", inline=True)
            embed.add_field(name="Can Catch More", value="✅ Yes" if can_catch else "❌ No", inline=True)
            
            # Show bag limit tiers
            tiers_text = ""
            for threshold in sorted(self.BAG_LIMITS.keys()):
                limit = self.BAG_LIMITS[threshold]
                status = "✅" if total_deposited >= threshold else "❌"
                tiers_text += f"{status} {threshold:,} {self.currency} → {limit} fish\n"
            
            embed.add_field(name="Bag Limit Tiers", value=tiers_text, inline=False)
            
            await safe_reply(ctx, embed=embed)
            
        except Exception as e:
            await safe_reply(ctx, f"❌ Test failed: {e}")

async def setup(bot):
    bot.add_cog(AutoFishing(bot))
