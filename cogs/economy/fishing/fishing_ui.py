# Fishing UI Components Module
# Contains all Discord UI views and paginators for fishing system

import nextcord
import math
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()

def safe_user_check(interaction, user_id):
    """Safely check if interaction user matches expected user_id"""
    try:
        return hasattr(interaction, 'user') and interaction.user and interaction.user.id == user_id
    except AttributeError:
        return False

class FishInventoryPaginator(nextcord.ui.View):
    """Paginator for fish inventory with gear info on first page"""
    
    def __init__(self, user_id, user_fish, current_page, total_pages, currency, rod_data, bait_data, get_user_bait_func, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.user_fish = user_fish
        self.current_page = current_page
        self.total_pages = total_pages
        self.currency = currency
        self.rod_data = rod_data
        self.bait_data = bait_data
        self.get_user_bait = get_user_bait_func
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states - buttons are never disabled for wrap-around navigation"""
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1
    
    @nextcord.ui.button(label="⬅️", style=nextcord.ButtonStyle.secondary)
    async def prev_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page > 1:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = self.total_pages
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="➡️", style=nextcord.ButtonStyle.secondary)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 1
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current page"""
        if self.current_page == 1:
            # Gear page
            embed = nextcord.Embed(
                title="🎣 Fishing Inventory",
                description="Your fishing gear and statistics",
                color=0x2b2d31
            )
            
            # Get active gear
            active_gear = await db.get_active_fishing_gear(self.user_id)
            
            # Show equipped rod
            if active_gear and active_gear.get("rod"):
                rod_id = active_gear["rod"]
                if rod_id in self.rod_data:
                    rod = self.rod_data[rod_id]
                    embed.add_field(
                        name="🎣 Equipped Rod",
                        value=f"**{rod['name']}**\n"
                              f"Multiplier: {rod.get('multiplier', 1.0)}x\n"
                              f"Power: {rod.get('power', 1)}\n"
                              f"Durability: {(rod.get('durability', 0.95)*100):.1f}%",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="🎣 Equipped Rod",
                        value="Rod data not found",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🎣 Equipped Rod",
                    value="No rod equipped\nUse `.rod` to equip one",
                    inline=True
                )
            
            # Show equipped bait
            if active_gear and active_gear.get("bait"):
                bait_id = active_gear["bait"]
                user_bait = await self.get_user_bait(self.user_id)
                equipped_bait = next((b for b in user_bait if b.get("_id") == bait_id), None)
                
                if equipped_bait:
                    embed.add_field(
                        name="🪱 Equipped Bait",
                        value=f"**{equipped_bait['name']}**\n"
                              f"Amount: {equipped_bait.get('amount', 1)}\n"
                              f"Type: {equipped_bait.get('rarity', 'Common').title()}",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="🪱 Equipped Bait",
                        value="Bait data not found",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="🪱 Equipped Bait",
                    value="No bait equipped\nUse `.bait` to equip some",
                    inline=True
                )
            
            # Add fish stats
            total_fish = len(self.user_fish)
            total_value = sum(fish.get("value", 0) for fish in self.user_fish)
            
            embed.add_field(
                name="📊 Collection Stats",
                value=f"**Total Fish:** {total_fish:,}\n**Total Value:** {total_value:,} {self.currency}",
                inline=False
            )
            
            return embed
        else:
            # Fish pages
            items_per_page = 5
            fish_page = self.current_page - 1  # Adjust for gear page
            start_idx = (fish_page - 1) * items_per_page
            end_idx = start_idx + items_per_page
            
            # Sort fish by value (highest first)
            sorted_fish = sorted(self.user_fish, key=lambda x: x.get("value", 0), reverse=True)
            page_fish = sorted_fish[start_idx:end_idx]
            
            embed = nextcord.Embed(
                title="🐟 Fish Collection",
                description=f"Your caught fish sorted by value",
                color=0x2b2d31
            )
            
            # Add fish to embed
            for i, fish in enumerate(page_fish, start=start_idx + 1):
                fish_info = (
                    f"**#{i}** • **{fish.get('value', 0):,}** {self.currency}\n"
                    f"**Weight:** {fish.get('weight', 0):.2f} kg\n"
                    f"**Rarity:** {fish.get('type', 'unknown').title()}\n"
                    f"**ID:** `{fish.get('id', 'unknown')[:8]}...`"
                )
                
                embed.add_field(
                    name=f"🐟 {fish.get('name', 'Unknown Fish')}",
                    value=fish_info,
                    inline=False
                )
            
            embed.set_footer(text=f"Page {self.current_page}/{self.total_pages}")
            return embed

class GlobalFishPaginator(nextcord.ui.View):
    """Paginator for global fish leaderboard"""
    
    def __init__(self, user_id, all_fish, current_page, total_pages, currency, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.all_fish = all_fish
        self.current_page = current_page
        self.total_pages = total_pages
        self.currency = currency
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states - buttons are never disabled for wrap-around navigation"""
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1
    
    @nextcord.ui.button(label="⬅️", style=nextcord.ButtonStyle.secondary)
    async def prev_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if self.total_pages <= 1:
            return
        
        if self.current_page > 1:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = self.total_pages
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @nextcord.ui.button(label="➡️", style=nextcord.ButtonStyle.secondary)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if self.total_pages <= 1:
            return
        
        if self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 1
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current page"""
        items_per_page = 10
        start_idx = (self.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_fish = self.all_fish[start_idx:end_idx]
        
        embed = nextcord.Embed(
            title="🌍 Global Fish Leaderboard",
            description="Top catches from all players",
            color=0x2b2d31
        )
        
        for i, fish in enumerate(page_fish, start=start_idx + 1):
            user_name = fish.get('username', 'Unknown User')
            fish_info = (
                f"**#{i}** • **{fish.get('value', 0):,}** {self.currency}\n"
                f"**Fisher:** {user_name}\n"
                f"**Weight:** {fish.get('weight', 0):.2f} kg\n"
                f"**Rarity:** {fish.get('type', 'unknown').title()}"
            )
            
            embed.add_field(
                name=f"🐟 {fish.get('name', 'Unknown Fish')}",
                value=fish_info,
                inline=True
            )
        
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages}")
        return embed

class RodPaginator(nextcord.ui.View):
    """Paginator for rod inventory with equip functionality"""
    
    def __init__(self, user_id, user_rods, active_rod_id, fishing_cog, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.user_rods = user_rods
        self.active_rod_id = active_rod_id
        self.fishing_cog = fishing_cog
        self.current_page = 1
        self.total_pages = math.ceil(len(user_rods) / 3) if user_rods else 1
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states - buttons are never disabled for wrap-around navigation"""
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1
        
        # Clear items and re-add with proper row assignment
        self.clear_items()
        
        # Row 0: Navigation buttons
        self.prev_button.row = 0
        self.next_button.row = 0
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        
        # Row 1: Rod select dropdown
        rod_select = RodSelect(self.user_rods, self.active_rod_id, self.fishing_cog)
        rod_select.row = 1
        self.add_item(rod_select)

    @nextcord.ui.button(label="⬅️", style=nextcord.ButtonStyle.secondary)
    async def prev_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page > 1:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = self.total_pages
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @nextcord.ui.button(label="➡️", style=nextcord.ButtonStyle.secondary)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 1
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current page"""
        embed = nextcord.Embed(
            title="🎣 Rod Inventory",
            description="Select a rod to equip using the dropdown below",
            color=0x2b2d31
        )
        
        items_per_page = 3
        start_idx = (self.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_rods = self.user_rods[start_idx:end_idx]
        
        for rod in page_rods:
            rod_id = rod.get('_id', 'unknown')
            is_active = "✅ **EQUIPPED**" if rod_id == self.active_rod_id else ""
            
            rod_info = (
                f"{is_active}\n"
                f"**Multiplier:** {rod.get('multiplier', 1.0)}x\n"
                f"**Durability:** {(rod.get('durability', 0.95) * 100):.1f}%\n"
                f"**Power:** {rod.get('power', 1)}\n"
                f"**Quantity:** {rod.get('quantity', 1)}"
            )
            
            embed.add_field(
                name=f"🎣 {rod.get('name', 'Unknown Rod')}",
                value=rod_info,
                inline=True
            )
        
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages}")
        return embed

class RodSelect(nextcord.ui.Select):
    """Dropdown for selecting rod to equip"""
    
    def __init__(self, user_rods, active_rod_id, fishing_cog):
        self.fishing_cog = fishing_cog
        
        options = []
        for rod in user_rods[:25]:  # Discord limit
            rod_id = rod.get('_id', 'unknown')
            is_active = rod_id == active_rod_id
            
            options.append(nextcord.SelectOption(
                label=rod.get('name', 'Unknown Rod'),
                description=f"x{rod.get('multiplier', 1.0)} • {(rod.get('durability', 0.95) * 100):.1f}% durability",
                value=rod_id,
                emoji="✅" if is_active else "🎣"
            ))
        
        super().__init__(placeholder="Choose a rod to equip...", options=options)
    
    async def callback(self, interaction: nextcord.Interaction):
        rod_id = self.values[0]
        
        if await self.fishing_cog.set_active_rod_manual(interaction.user.id, rod_id):
            # Find rod name
            user_rods = await self.fishing_cog.get_user_rods(interaction.user.id)
            rod = next((r for r in user_rods if r.get("_id") == rod_id), None)
            rod_name = rod.get('name', 'Unknown Rod') if rod else 'Unknown Rod'
            
            await interaction.response.send_message(
                f"✅ Equipped **{rod_name}**!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to equip rod!", 
                ephemeral=True
            )

class BaitPaginator(nextcord.ui.View):
    """Paginator for bait inventory with equip functionality"""
    
    def __init__(self, user_id, user_bait, active_bait_id, fishing_cog, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.user_bait = user_bait
        self.active_bait_id = active_bait_id
        self.fishing_cog = fishing_cog
        self.current_page = 1
        self.total_pages = math.ceil(len(user_bait) / 3) if user_bait else 1
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states - buttons are never disabled for wrap-around navigation"""
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1
        
        # Clear items and re-add with proper row assignment
        self.clear_items()
        
        # Row 0: Navigation buttons
        self.prev_button.row = 0
        self.next_button.row = 0
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        
        # Row 1: Bait select dropdown
        bait_select = BaitSelect(self.user_bait, self.active_bait_id)
        bait_select.row = 1
        self.add_item(bait_select)
    
    @nextcord.ui.button(label="⬅️", style=nextcord.ButtonStyle.secondary)
    async def prev_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page > 1:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = self.total_pages
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="➡️", style=nextcord.ButtonStyle.secondary)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your inventory!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 1
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current page"""
        embed = nextcord.Embed(
            title="🪱 Bait Inventory",
            description="Select bait to equip using the dropdown below",
            color=0x2b2d31
        )
        
        items_per_page = 3
        start_idx = (self.current_page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_bait = self.user_bait[start_idx:end_idx]
        
        for bait in page_bait:
            bait_id = bait.get('_id', 'unknown')
            is_active = "✅ **EQUIPPED**" if bait_id == self.active_bait_id else ""
            
            bait_info = (
                f"{is_active}\n"
                f"**Amount:** {bait.get('amount', 1)}\n"
                f"**Rarity:** {bait.get('rarity', 'Common').title()}\n"
                f"**Description:** {bait.get('description', 'No description')[:50]}..."
            )
            
            embed.add_field(
                name=f"🪱 {bait.get('name', 'Unknown Bait')}",
                value=bait_info,
                inline=True
            )
        
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages}")
        return embed

class BaitSelect(nextcord.ui.Select):
    """Dropdown for selecting bait to equip"""
    
    def __init__(self, user_bait, active_bait_id):
        
        options = []
        for bait in user_bait[:25]:  # Discord limit
            bait_id = bait.get('_id', 'unknown')
            is_active = bait_id == active_bait_id
            
            options.append(nextcord.SelectOption(
                label=bait.get('name', 'Unknown Bait'),
                description=f"{bait.get('rarity', 'Common').title()} • {bait.get('amount', 1)} remaining",
                value=bait_id,
                emoji="✅" if is_active else "🪱"
            ))
        
        super().__init__(placeholder="Choose bait to equip...", options=options)
    
    async def callback(self, interaction: nextcord.Interaction):
        bait_id = self.values[0]
        
        if await db.set_active_bait(interaction.user.id, bait_id):
            # Find bait name
            user_data = await db.db.users.find_one({"_id": str(interaction.user.id)})
            inventory = user_data.get("inventory", {}) if user_data else {}
            bait_inventory = inventory.get("bait", {})
            
            # Load bait data to get name
            from .fishing_data import FishingData
            data_manager = FishingData()
            bait_data = data_manager.get_bait_data()
            
            bait_name = bait_data.get(bait_id, {}).get('name', 'Unknown Bait')
            
            await interaction.response.send_message(
                f"✅ Equipped **{bait_name}**!", 
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❌ Failed to equip bait!", 
                ephemeral=True
            )

class InteractiveFishSeller(nextcord.ui.View):
    """Interactive fish browser with sell buttons"""
    
    def __init__(self, user_id, user_fish, currency, selling_cog, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.user_fish = user_fish
        self.currency = currency
        self.selling_cog = selling_cog
        self.current_page = 1
        self.items_per_page = 5  # Increased from 3 to 5 since we have better layout
        self.total_pages = math.ceil(len(user_fish) / self.items_per_page) if user_fish else 1
        self.message = None
        self.update_buttons()
    
    def update_buttons(self):
        """Update button states - buttons are never disabled for wrap-around navigation"""
        self.prev_button.disabled = self.total_pages <= 1
        self.next_button.disabled = self.total_pages <= 1
        
        # Update sell buttons for current page
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_fish = self.user_fish[start_idx:end_idx]
        
        # Remove old items
        self.clear_items()
        
        # Row 0: Navigation buttons only
        self.prev_button.row = 0
        self.next_button.row = 0
        self.add_item(self.prev_button)
        self.add_item(self.next_button)
        
        # Row 1: Individual fish sell buttons (up to 5 per page now)
        for i, fish in enumerate(page_fish[:5]):  # Increased to 5 since we have full row
            button = nextcord.ui.Button(
                label=f"Sell #{start_idx + i + 1}",
                style=nextcord.ButtonStyle.red,
                custom_id=f"sell_{fish.get('id', 'unknown')}",
                row=1
            )
            button.callback = self.create_sell_callback(fish)
            self.add_item(button)
        
        # Row 2: Bulk action buttons if we have fish
        if len(self.user_fish) > 0:
            # Sell all button
            sell_all_button = nextcord.ui.Button(
                label="💸 Sell All Fish",
                style=nextcord.ButtonStyle.danger,
                emoji="🐟",
                row=2
            )
            sell_all_button.callback = self.sell_all_fish
            self.add_item(sell_all_button)
            
            # Refresh button to update rarity dropdown
            refresh_button = nextcord.ui.Button(
                label="🔄 Refresh",
                style=nextcord.ButtonStyle.secondary,
                emoji="🔄",
                row=2
            )
            refresh_button.callback = self.refresh_view
            self.add_item(refresh_button)
        
        # Row 3: Rarity select dropdown (on its own row for clarity)
        if len(self.user_fish) > 0:
            rarity_select = RaritySelect(self.user_id, self.user_fish, self.currency, self.selling_cog)
            rarity_select.row = 3
            self.add_item(rarity_select)
    
    def create_sell_callback(self, fish):
        """Create callback for sell button"""
        async def sell_callback(interaction: nextcord.Interaction):
            if not safe_user_check(interaction, self.user_id):
                return await interaction.response.send_message("❌ This isn't your fish!", ephemeral=True)
            
            try:
                fish_id = fish.get('id')
                if not fish_id:
                    return await interaction.response.send_message("❌ Fish ID not found!", ephemeral=True)
                
                if await db.remove_fish(self.user_id, fish_id):
                    await db.add_currency(self.user_id, fish['value'])
                    
                    # Remove fish from our list
                    self.user_fish = [f for f in self.user_fish if f.get('id') != fish_id]
                    
                    # Recalculate pages
                    self.total_pages = math.ceil(len(self.user_fish) / self.items_per_page) if self.user_fish else 1
                    if self.current_page > self.total_pages:
                        self.current_page = max(1, self.total_pages)
                    
                    if self.user_fish:
                        # Update view
                        self.update_buttons()
                        embed = await self.create_embed()
                        await interaction.response.edit_message(embed=embed, view=self)
                    else:
                        # No more fish
                        embed = nextcord.Embed(
                            title="🐟 All Fish Sold!",
                            description="You've sold all your fish!",
                            color=0x00ff00
                        )
                        await interaction.response.edit_message(embed=embed, view=None)
                    
                    await interaction.followup.send(
                        f"✅ Sold **{fish['name']}** for **{fish['value']:,}** {self.currency}!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message("❌ Failed to sell fish!", ephemeral=True)
            except Exception as e:
                print(f"Error in sell_callback: {e}")
                await interaction.response.send_message("❌ An error occurred while selling fish!", ephemeral=True)
        
        return sell_callback
    
    @nextcord.ui.button(label="⬅️", style=nextcord.ButtonStyle.secondary, row=0)
    async def prev_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your fish!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page > 1:
            self.current_page -= 1
        else:
            # Wrap to last page
            self.current_page = self.total_pages
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    @nextcord.ui.button(label="➡️", style=nextcord.ButtonStyle.secondary, row=0)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your fish!", ephemeral=True)
        
        if self.total_pages <= 1:
            return
        
        if self.current_page < self.total_pages:
            self.current_page += 1
        else:
            # Wrap to first page
            self.current_page = 1
        
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def create_embed(self):
        """Create embed for current page"""
        start_idx = (self.current_page - 1) * self.items_per_page
        end_idx = start_idx + self.items_per_page
        page_fish = self.user_fish[start_idx:end_idx]
        
        embed = nextcord.Embed(
            title="💰 Interactive Fish Seller",
            description="• Click **Sell** buttons to sell individual fish\n• Use **💸 Sell All Fish** to sell everything\n• Use the dropdown to sell by rarity\n• Use **🔄 Refresh** to update the rarity dropdown\n• Navigate with ⬅️ ➡️ buttons",
            color=0x2b2d31
        )
        
        for i, fish in enumerate(page_fish, start=start_idx + 1):
            fish_info = (
                f"**#{i}** • **{fish.get('value', 0):,}** {self.currency}\n"
                f"**Weight:** {fish.get('weight', 0):.2f} kg\n"
                f"**Rarity:** {fish.get('type', 'unknown').title()}\n"
                f"**ID:** `{fish.get('id', 'unknown')[:8]}...`"
            )
            
            embed.add_field(
                name=f"🐟 {fish.get('name', 'Unknown Fish')}",
                value=fish_info,
                inline=False
            )
        
        total_value = sum(fish.get('value', 0) for fish in self.user_fish)
        embed.set_footer(text=f"Page {self.current_page}/{self.total_pages} • Total Collection Value: {total_value:,} {self.currency}")
        
        return embed
    
    async def sell_all_fish(self, interaction: nextcord.Interaction):
        """Sell all fish"""
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your fish market!", ephemeral=True)
        
        try:
            total_value = sum(fish.get("value", 0) for fish in self.user_fish)
            fish_count = len(self.user_fish)
            
            if fish_count == 0:
                return await interaction.response.send_message("❌ You don't have any fish to sell!", ephemeral=True)
            
            if await db.clear_fish(self.user_id):
                await db.add_currency(self.user_id, total_value)
                
                embed = nextcord.Embed(
                    title="🐟 All Fish Sold!",
                    description=f"Sold **{fish_count:,}** fish for **{total_value:,}** {self.currency}",
                    color=0x00ff00
                )
                
                # Add breakdown by rarity
                rarity_counts = {}
                rarity_values = {}
                for fish in self.user_fish:
                    rarity = fish.get("type", "unknown")
                    rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
                    rarity_values[rarity] = rarity_values.get(rarity, 0) + fish.get("value", 0)
                
                if rarity_counts:
                    breakdown = []
                    for rarity, count in sorted(rarity_counts.items()):
                        value = rarity_values[rarity]
                        breakdown.append(f"**{rarity.title()}:** {count}x ({value:,} {self.currency})")
                    
                    embed.add_field(
                        name="📈 Breakdown by Rarity",
                        value="\n".join(breakdown[:10]) + ("..." if len(breakdown) > 10 else ""),
                        inline=False
                    )
                
                # Clear the fish list and update view
                self.user_fish = []
                empty_embed = nextcord.Embed(
                    title="🐟 Fish Market",
                    description="✅ All fish sold! Your market is now empty.",
                    color=0x00ff00
                )
                self.clear_items()
                await interaction.response.edit_message(embed=empty_embed, view=self)
                
                # Send success message as followup
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("❌ Failed to sell fish!", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("❌ An error occurred while selling fish!", ephemeral=True)
    
    async def refresh_view(self, interaction: nextcord.Interaction):
        """Refresh the view to update rarity dropdown and buttons"""
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your fish market!", ephemeral=True)
        
        # Update buttons to refresh rarity dropdown with current fish
        self.update_buttons()
        embed = await self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

class RaritySelect(nextcord.ui.Select):
    """Dropdown for selecting rarity to sell"""
    
    def __init__(self, user_id: int, fish_list: list, currency: str, selling_cog):
        self.user_id = user_id
        self.fish_list = fish_list
        self.currency = currency
        self.selling_cog = selling_cog
        
        # Get unique rarities from fish list
        rarities = set(fish.get("type", "unknown") for fish in fish_list)
        
        # Create options for each rarity
        options = []
        for rarity in sorted(rarities):
            rarity_fish = [f for f in fish_list if f.get("type") == rarity]
            count = len(rarity_fish)
            total_value = sum(f.get("value", 0) for f in rarity_fish)
            
            # Get rarity config
            rarity_config = selling_cog._get_rarity_config()
            config = rarity_config.get(rarity, {"emoji": "🐟"})
            
            options.append(nextcord.SelectOption(
                label=f"{rarity.title()} ({count}x)",
                value=rarity,
                description=f"Sell all {rarity} fish for {total_value:,} coins",
                emoji=config.get("emoji", "🐟")
            ))
        
        super().__init__(
            placeholder="Sell all fish of a specific rarity...",
            options=options[:25],  # Discord limit
            min_values=1,
            max_values=1,
            row=2
        )
    
    async def callback(self, interaction: nextcord.Interaction):
        """Handle rarity selection"""
        if not safe_user_check(interaction, self.user_id):
            return await interaction.response.send_message("❌ This isn't your fish market!", ephemeral=True)
        
        selected_rarity = self.values[0]
        
        try:
            # Get fish of selected rarity
            matching_fish = [fish for fish in self.fish_list if fish.get("type", "").lower() == selected_rarity.lower()]
            
            if not matching_fish:
                return await interaction.response.send_message(f"❌ No {selected_rarity} fish found!", ephemeral=True)
            
            # Calculate total value
            total_value = sum(fish.get("value", 0) for fish in matching_fish)
            fish_count = len(matching_fish)
            
            # Remove fish from database
            fish_ids = [fish["id"] for fish in matching_fish]
            
            success_count = 0
            for fish_id in fish_ids:
                if await db.remove_fish(self.user_id, fish_id):
                    success_count += 1
            
            if success_count > 0:
                await db.add_currency(self.user_id, total_value)
                
                # Get rarity config for colors
                rarity_config = self.selling_cog._get_rarity_config()
                config = rarity_config.get(selected_rarity, {"color": 0x2b2d31, "emoji": "🐟"})
                
                embed = nextcord.Embed(
                    title=f"{config['emoji']} {selected_rarity.title()} Fish Sold!",
                    description=f"Sold **{success_count:,}** {selected_rarity} fish for **{total_value:,}** {self.currency}",
                    color=config['color']
                )
                
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
                # Update the parent view to remove sold fish
                parent_view = self.view
                if isinstance(parent_view, InteractiveFishSeller):
                    # Remove sold fish from parent's fish list
                    parent_view.user_fish = [f for f in parent_view.user_fish if f.get("type", "").lower() != selected_rarity.lower()]
                    
                    # Update pagination
                    parent_view.total_pages = math.ceil(len(parent_view.user_fish) / parent_view.items_per_page) if parent_view.user_fish else 1
                    if parent_view.current_page > parent_view.total_pages:
                        parent_view.current_page = max(1, parent_view.total_pages)
                    
                    # Update the parent view with refreshed dropdown
                    if parent_view.user_fish:
                        parent_view.update_buttons()  # This will create a new RaritySelect with updated fish
                        parent_embed = await parent_view.create_embed()
                        await interaction.edit_original_response(embed=parent_embed, view=parent_view)
                    else:
                        # No fish left
                        empty_embed = nextcord.Embed(
                            title="🐟 Fish Market",
                            description="✅ All fish sold! Your market is now empty.",
                            color=0x00ff00
                        )
                        parent_view.clear_items()
                        await interaction.edit_original_response(embed=empty_embed, view=parent_view)
            else:
                await interaction.response.send_message("❌ Failed to sell any fish!", ephemeral=True)
                
        except Exception as e:
            await interaction.response.send_message("❌ An error occurred while selling fish!", ephemeral=True)
