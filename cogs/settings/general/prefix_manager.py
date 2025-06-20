"""
Prefix Manager
Handles server prefix management functionality.
"""

import nextcord
from nextcord.ext import commands
from typing import List

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from .constants import LIMITS

logger = CogLogger('PrefixManager')

class PrefixManager:
    """Manages server prefix settings"""
    
    def __init__(self, bot):
        self.bot = bot

    async def show_prefixes(self, ctx):
        """Show prefix management interface"""
        embed = nextcord.Embed(
            title="📌 Prefix Management",
            description=(
                "Manage bot prefixes for this server\n\n"
                "**Available Commands:**\n"
                "`general prefix add <prefix>` - Add a new prefix\n"
                "`general prefix remove <prefix>` - Remove a prefix\n"
                "`general prefix list` - List all prefixes"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)

    async def add_prefix(self, ctx, prefix: str):
        """Add a new server prefix"""
        if len(prefix) > LIMITS["max_prefix_length"]:
            await ctx.send(f"❌ Prefix must be {LIMITS['max_prefix_length']} characters or less")
            return

        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get("prefixes", ["."])
        
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        if prefix in prefixes:
            await ctx.send(f"❌ Prefix `{prefix}` is already configured")
            return

        if len(prefixes) >= LIMITS["max_prefixes"]:
            await ctx.send(f"❌ Maximum of {LIMITS['max_prefixes']} prefixes allowed")
            return

        prefixes.append(prefix)
        await db.update_guild_settings(ctx.guild.id, {"prefixes": prefixes})
        
        embed = nextcord.Embed(
            title="✅ Prefix Added",
            description=f"Added prefix: `{prefix}`",
            color=0x2ecc71
        )
        embed.add_field(
            name="Current Prefixes",
            value=f"`{'`, `'.join(prefixes)}`",
            inline=False
        )
        await ctx.send(embed=embed)
        logger.info(f"Prefix '{prefix}' added to guild {ctx.guild.id}")

    async def remove_prefix(self, ctx, prefix: str):
        """Remove a server prefix"""
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get("prefixes", ["."])
        
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        if prefix not in prefixes:
            await ctx.send(f"❌ Prefix `{prefix}` is not configured")
            return

        if len(prefixes) <= 1:
            await ctx.send("❌ Cannot remove the last prefix! Add another prefix first.")
            return

        prefixes.remove(prefix)
        await db.update_guild_settings(ctx.guild.id, {"prefixes": prefixes})
        
        embed = nextcord.Embed(
            title="✅ Prefix Removed",
            description=f"Removed prefix: `{prefix}`",
            color=0x2ecc71
        )
        embed.add_field(
            name="Remaining Prefixes",
            value=f"`{'`, `'.join(prefixes)}`",
            inline=False
        )
        await ctx.send(embed=embed)
        logger.info(f"Prefix '{prefix}' removed from guild {ctx.guild.id}")

    async def list_prefixes(self, ctx):
        """List all server prefixes"""
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get("prefixes", ["."])
        
        if isinstance(prefixes, str):
            prefixes = [prefixes]

        embed = nextcord.Embed(
            title="📌 Server Prefixes",
            color=0x3498db
        )
        
        prefix_list = "\n".join([f"• `{prefix}`" for prefix in prefixes])
        embed.add_field(
            name=f"Prefixes ({len(prefixes)}/{LIMITS['max_prefixes']})",
            value=prefix_list if prefix_list else "No prefixes configured",
            inline=False
        )
        
        embed.set_footer(text="Use 'general prefix add/remove <prefix>' to manage prefixes")
        await ctx.send(embed=embed)

    async def get_prefixes(self, guild_id: int) -> List[str]:
        """Get list of prefixes for a guild"""
        settings = await db.get_guild_settings(guild_id)
        prefixes = settings.get("prefixes", ["."])
        
        if isinstance(prefixes, str):
            prefixes = [prefixes]
            
        return prefixes
