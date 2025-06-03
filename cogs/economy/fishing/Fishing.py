from discord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import async_db as db
import discord
import random
import uuid
import datetime
import asyncio

class Fishing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
    
    # piece de resistance: cog_check
    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        if ctx.channel.id in self.blocked_channels and not ctx.author.guild_permissions.administrator:
            await ctx.reply(
                random.choice([f"❌ Economy commands are disabled in this channel. "
                f"Please use them in another channel.",
                "<#1314685928614264852> is a good place for that."])
            )
            return False
        return True

    @commands.command(name="fish", aliases=["fishing", 'fs'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def fish(self, ctx):
        """Go fishing! Requires a rod and bait."""
        fishing_items = await db.get_fishing_items(ctx.author.id)
        
        if not fishing_items["rods"]:
            embed = discord.Embed(
                title="🎣 First Time Fishing!",
                description="You need a fishing rod and bait to start fishing!\nVisit the shop to get your free beginner gear:",
                color=0x2b2d31
            )
            embed.add_field(
                name="Free Starter Pack",
                value="• Beginner Rod (0 coins)\n• 10x Beginner Bait (0 coins)",
                inline=False
            )
            return await ctx.reply(embed=embed)
        
        if not fishing_items["bait"]:
            return await ctx.reply("❌ You need bait to go fishing! Buy some from `.shop bait`")
        
        rod = fishing_items["rods"][0]
        bait = fishing_items["bait"][0]
        
        # Add debug logging
        self.logger.info(f"Attempting to use bait: {bait}")
        
        try:
            bait_removed = await db.remove_bait(ctx.author.id, bait["id"])
            if not bait_removed:
                self.logger.error(f"Failed to remove bait: {bait}")
                return await ctx.reply("❌ Failed to use bait! Please try again or contact support.")
        except Exception as e:
            self.logger.error(f"Error removing bait: {e}")
            return await ctx.reply("❌ An error occurred while using bait. Please try again.")
        
        # Rest of the fishing logic remains the same...
        base_chances = {
            "normal": 0.7 * bait.get("catch_rates", {}).get("normal", 1.0),
            "rare": 0.2 * bait.get("catch_rates", {}).get("rare", 0.1),
            "event": 0.08 * bait.get("catch_rates", {}).get("event", 0.0),
            "mutated": 0.02 * bait.get("catch_rates", {}).get("mutated", 0.0)
        }
        
        rod_mult = rod.get("multiplier", 1.0)
        chances = {k: v * rod_mult for k, v in base_chances.items()}
        
        roll = random.random()
        cumulative = 0
        caught_type = "normal"
        
        for fish_type, chance in chances.items():
            cumulative += chance
            if roll <= cumulative:
                caught_type = fish_type
                break
                
        value_range = {
            "normal": (10, 100),
            "rare": (100, 500),
            "event": (500, 2000),
            "mutated": (2000, 10000)
        }[caught_type]
        
        fish = {
            "id": str(uuid.uuid4()),
            "type": caught_type,
            "name": f"{caught_type.title()} Fish",
            "value": random.randint(*value_range),
            "caught_at": datetime.datetime.utcnow().isoformat(),
            "bait_used": bait["id"],
            "rod_used": rod["id"]
        }
        
        if await db.add_fish(ctx.author.id, fish):
            embed = discord.Embed(
                title="🎣 Caught a Fish!",
                description=f"You caught a **{fish['name']}**!\nValue: **{fish['value']}** {self.currency}",
                color=discord.Color.blue()
            )
            
            if caught_type in ["rare", "event", "mutated"]:
                embed.set_footer(text="Wow! That's a special catch!")
            
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("❌ Failed to store your catch!")

    @commands.command(name="fishinv", aliases=["finv", 'fi'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def fish_inventory(self, ctx):
        """View your fishing inventory"""
        fishing_items = await db.get_fishing_items(ctx.author.id)
        fish = await db.get_fish(ctx.author.id)
        active_gear = await db.get_active_fishing_gear(ctx.author.id)
        
        pages = []
        
        # Equipment page with active gear
        equip_embed = discord.Embed(
            title="🎣 Fishing Equipment",
            color=discord.Color.blue()
        )
        
        # Show active rod if available
        active_rod = next((r for r in fishing_items["rods"] if r["_id"] == active_gear.get("rod")), None)
        if active_rod:
            equip_embed.add_field(
                name="🎣 Active Rod",
                value=f"**{active_rod['name']}**\n• Multiplier: {active_rod['multiplier']}x\n• {active_rod.get('description', '')}",
                inline=False
            )
        
        # Show active bait if available
        active_bait = next((b for b in fishing_items["bait"] if b["_id"] == active_gear.get("bait")), None)
        if active_bait:
            equip_embed.add_field(
                name="🪱 Active Bait",
                value=f"**{active_bait['name']}** (x{active_bait.get('amount', 1)})\n• {active_bait.get('description', '')}",
                inline=False
            )
        
        # List all rods
        rods_text = ""
        for rod in fishing_items["rods"]:
            active_status = " (Active)" if rod["_id"] == active_gear.get("rod") else ""
            rods_text += f"**{rod['name']}{active_status}**\n• Multiplier: {rod['multiplier']}x\n• {rod.get('description', '')}\n\n"
        equip_embed.add_field(
            name="🎣 Fishing Rods",
            value=rods_text or "No rods",
            inline=False
        )
        
        # List all bait
        bait_text = ""
        for bait in fishing_items["bait"]:
            active_status = " (Active)" if bait["_id"] == active_gear.get("bait") else ""
            bait_text += f"**{bait['name']}{active_status}** (x{bait.get('amount', 1)})\n• {bait.get('description', '')}\n\n"
        equip_embed.add_field(
            name="🪱 Bait",
            value=bait_text or "No bait",
            inline=False
        )
        
        pages.append(equip_embed)
        
        # Fish collection pages
        if fish:
            fish_by_type = {}
            for f in fish:
                fish_by_type.setdefault(f["type"], []).append(f)
                
            for fish_type, fish_list in fish_by_type.items():
                embed = discord.Embed(
                    title=f"🐟 {fish_type.title()} Fish Collection",
                    color=discord.Color.blue()
                )
                
                total_value = sum(f["value"] for f in fish_list)
                embed.description = f"Total Value: **{total_value}** {self.currency}\nAmount: {len(fish_list)}"
                
                for fish in sorted(fish_list, key=lambda x: x["value"], reverse=True)[:5]:
                    embed.add_field(
                        name=f"{fish['name']} ({fish['value']} {self.currency})",
                        value=f"Caught: {fish['caught_at'].split('T')[0]}",
                        inline=False
                    )
                    
                pages.append(embed)
        else:
            pages.append(discord.Embed(
                title="🐟 Fish Collection",
                description="You haven't caught any fish yet!\nUse `.fish` to start fishing.",
                color=discord.Color.blue()
            ))
        
        class PaginationView(discord.ui.View):
            def __init__(self, pages, author, timeout=60):
                super().__init__(timeout=timeout)
                self.pages = pages
                self.author = author
                self.current_page = 0
                
            async def update_message(self, interaction):
                self.current_page %= len(self.pages)  # Wrap around
                page = self.pages[self.current_page]
                self.update_buttons()
                await interaction.response.edit_message(embed=page, view=self)
                
            def update_buttons(self):
                self.clear_items()
                if len(self.pages) > 1:
                    prev_button = discord.ui.Button(label="◀ Previous", style=discord.ButtonStyle.primary)
                    prev_button.callback = self.previous_page
                    self.add_item(prev_button)
                    
                    page_button = discord.ui.Button(label=f"Page {self.current_page + 1}/{len(self.pages)}", disabled=True)
                    self.add_item(page_button)
                    
                    next_button = discord.ui.Button(label="Next ▶", style=discord.ButtonStyle.primary)
                    next_button.callback = self.next_page
                    self.add_item(next_button)
                
                @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
                async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
                    await interaction.response.defer()
                    await interaction.message.delete()
                
                # Add rod/bait selection buttons if on equipment page
                if self.current_page == 0:
                    select_rod = discord.ui.Button(label="Change Rod", style=discord.ButtonStyle.secondary, row=1)
                    select_rod.callback = self.select_rod
                    self.add_item(select_rod)
                    
                    select_bait = discord.ui.Button(label="Change Bait", style=discord.ButtonStyle.secondary, row=1)
                    select_bait.callback = self.select_bait
                    self.add_item(select_bait)
                
            async def select_rod(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Use `.rod` to view and select a different fishing rod!",
                    ephemeral=True
                )
                
            async def select_bait(self, interaction: discord.Interaction):
                await interaction.response.send_message(
                    "Use `.bait` to view and select different bait!",
                    ephemeral=True
                )
                
            async def previous_page(self, interaction: discord.Interaction):
                self.current_page -= 1
                await self.update_message(interaction)
                
            async def next_page(self, interaction: discord.Interaction):
                self.current_page += 1
                await self.update_message(interaction)
                
            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user != self.author:
                    await interaction.response.send_message("This isn't your inventory!", ephemeral=True)
                    return False
                return True
        
        view = PaginationView(pages, ctx.author)
        await ctx.reply(embed=pages[0], view=view)

    @commands.command(name="sellfish", aliases=["sellf", 'sell_fish', 'sf'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def sellfish(self, ctx, fish_id: str = "all"):
        """Sell fish from your inventory"""
        fish = await db.get_fish(ctx.author.id)
        if not fish:
            return await ctx.reply("You don't have any fish to sell!")
            
        if fish_id.lower() == "all":
            total_value = sum(f["value"] for f in fish)
            if await db.update_balance(ctx.author.id, total_value):
                await db.clear_fish(ctx.author.id)
                embed = discord.Embed(
                    title="🐟 Fish Sold!",
                    description=f"Sold {len(fish)} fish for **{total_value}** {self.currency}",
                    color=discord.Color.green()
                )
                return await ctx.reply(embed=embed)
            await ctx.reply("❌ Failed to sell fish!")
        else:
            fish_to_sell = next((f for f in fish if f["id"] == fish_id), None)
            if not fish_to_sell:
                return await ctx.reply("❌ Fish not found in your inventory!")
                
            if await db.update_balance(ctx.author.id, fish_to_sell["value"]):
                await db.remove_fish(ctx.author.id, fish_id)
                embed = discord.Embed(
                    title="🐟 Fish Sold!",
                    description=f"Sold {fish_to_sell['name']} for **{fish_to_sell['value']}** {self.currency}",
                    color=discord.Color.green()
                )
                return await ctx.reply(embed=embed)
            await ctx.reply("❌ Failed to sell fish!")

    # Add to Fishing cog

    @commands.command(name="rod", aliases=["selectrod", "changerod"])
    async def select_rod(self, ctx, rod_id: str = None):
        """Select or view your active fishing rod"""
        fishing_items = await db.get_fishing_items(ctx.author.id)
        
        if not fishing_items["rods"]:
            return await ctx.reply("You don't have any fishing rods! Get one from the shop.")
        
        active_gear = await db.get_active_fishing_gear(ctx.author.id)
        
        if not rod_id:
            # Show list of rods with active one marked
            embed = discord.Embed(
                title="🎣 Your Fishing Rods",
                description="Select a rod using `.rod <id>`",
                color=discord.Color.blue()
            )
            
            for rod in fishing_items["rods"]:
                status = "✅" if rod["_id"] == active_gear.get("rod") else ""
                embed.add_field(
                    name=f"{status} {rod['name']} (ID: {rod['_id']})",
                    value=f"Multiplier: {rod['multiplier']}x\n{rod.get('description', '')}",
                    inline=False
                )
            
            return await ctx.reply(embed=embed)
        
        # Try to set active rod
        if await db.set_active_rod(ctx.author.id, rod_id):
            rod = next((r for r in fishing_items["rods"] if r["_id"] == rod_id), None)
            if rod:
                await ctx.reply(f"🎣 Successfully set **{rod['name']}** as your active fishing rod!")
        else:
            await ctx.reply("❌ Couldn't find that fishing rod in your inventory!")

    @commands.command(name="bait", aliases=["selectbait", "changebait"])
    async def select_bait(self, ctx, bait_id: str = None):
        """Select or view your active bait"""
        fishing_items = await db.get_fishing_items(ctx.author.id)
        
        if not fishing_items["bait"]:
            return await ctx.reply("You don't have any bait! Get some from the shop.")
        
        active_gear = await db.get_active_fishing_gear(ctx.author.id)
        
        if not bait_id:
            # Show list of bait with active one marked
            embed = discord.Embed(
                title="🪱 Your Bait",
                description="Select bait using `.bait <id>`",
                color=discord.Color.blue()
            )
            
            for bait in fishing_items["bait"]:
                status = "✅" if bait["_id"] == active_gear.get("bait") else ""
                embed.add_field(
                    name=f"{status} {bait['name']} (ID: {bait['_id']}) - x{bait.get('amount', 1)}",
                    value=f"{bait.get('description', '')}",
                    inline=False
                )
            
            return await ctx.reply(embed=embed)
        
        # Try to set active bait
        if await db.set_active_bait(ctx.author.id, bait_id):
            bait = next((b for b in fishing_items["bait"] if b["_id"] == bait_id), None)
            if bait:
                await ctx.reply(f"🪱 Successfully set **{bait['name']}** as your active bait!")
        else:
            await ctx.reply("❌ Couldn't find that bait in your inventory!")



async def setup(bot):
    await bot.add_cog(Fishing(bot))