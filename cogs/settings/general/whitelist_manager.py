"""
Whitelist Manager
Handles command whitelist functionality.
"""

import nextcord
from nextcord.ext import commands
from typing import Dict, List, Set

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from .constants import LIMITS

logger = CogLogger('WhitelistManager')

class WhitelistManager:
    """Manages command whitelist settings"""
    
    def __init__(self, bot):
        self.bot = bot

    async def show_whitelist(self, ctx):
        """Show whitelist management interface"""
        embed = nextcord.Embed(
            title="📋 Whitelist Management",
            description=(
                "Manage command whitelists - restrict commands to specific channels/roles\n\n"
                "**Available Commands:**\n"
                "`general whitelist view` - View current whitelists\n"
                "`general whitelist channel <channel> <command>` - Whitelist for channel\n"
                "`general whitelist role <role> <command>` - Whitelist for role\n"
                "`general whitelist remove channel <channel> <command>` - Remove channel whitelist\n"
                "`general whitelist remove role <role> <command>` - Remove role whitelist"
            ),
            color=0x3498db
        )
        embed.set_footer(text="Whitelist = ONLY these channels/roles can use the command")
        await ctx.send(embed=embed)

    async def view_whitelist(self, ctx):
        """View current whitelist settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        if not whitelist:
            embed = nextcord.Embed(
                title="📋 Command Whitelist",
                description="No command whitelists configured",
                color=0x95a5a6
            )
            await ctx.send(embed=embed)
            return
        
        embed = nextcord.Embed(
            title="📋 Command Whitelist",
            description="Commands restricted to specific channels/roles",
            color=0x3498db
        )
        
        for command, restrictions in whitelist.items():
            channel_list = []
            role_list = []
            
            # Get whitelisted channels
            for channel_id in restrictions.get('channels', []):
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channel_list.append(channel.mention)
                else:
                    channel_list.append(f"<#{channel_id}> (deleted)")
            
            # Get whitelisted roles
            for role_id in restrictions.get('roles', []):
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(role.mention)
                else:
                    role_list.append(f"<@&{role_id}> (deleted)")
            
            restriction_text = []
            if channel_list:
                restriction_text.append(f"**Channels:** {', '.join(channel_list)}")
            if role_list:
                restriction_text.append(f"**Roles:** {', '.join(role_list)}")
            
            embed.add_field(
                name=f"🔒 {command}",
                value="\n".join(restriction_text) if restriction_text else "No restrictions",
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def whitelist_channel(self, ctx, channel: nextcord.TextChannel, command: str):
        """Whitelist a command for a specific channel"""
        if not await self._validate_command(command):
            await ctx.send(f"❌ Command `{command}` not found")
            return
        
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        if command not in whitelist:
            whitelist[command] = {'channels': [], 'roles': []}
        
        if channel.id in whitelist[command]['channels']:
            await ctx.send(f"❌ Command `{command}` is already whitelisted for {channel.mention}")
            return
        
        if len(whitelist[command]['channels']) >= LIMITS['max_whitelist_per_command']:
            await ctx.send(f"❌ Maximum {LIMITS['max_whitelist_per_command']} whitelists per command")
            return
        
        whitelist[command]['channels'].append(channel.id)
        await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
        
        embed = nextcord.Embed(
            title="✅ Whitelist Added",
            description=f"Command `{command}` is now whitelisted for {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' whitelisted for channel {channel.id} in guild {ctx.guild.id}")

    async def whitelist_role(self, ctx, role: nextcord.Role, command: str):
        """Whitelist a command for a specific role"""
        if not await self._validate_command(command):
            await ctx.send(f"❌ Command `{command}` not found")
            return
        
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        if command not in whitelist:
            whitelist[command] = {'channels': [], 'roles': []}
        
        if role.id in whitelist[command]['roles']:
            await ctx.send(f"❌ Command `{command}` is already whitelisted for {role.mention}")
            return
        
        if len(whitelist[command]['roles']) >= LIMITS['max_whitelist_per_command']:
            await ctx.send(f"❌ Maximum {LIMITS['max_whitelist_per_command']} whitelists per command")
            return
        
        whitelist[command]['roles'].append(role.id)
        await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
        
        embed = nextcord.Embed(
            title="✅ Whitelist Added",
            description=f"Command `{command}` is now whitelisted for {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' whitelisted for role {role.id} in guild {ctx.guild.id}")

    async def remove_whitelist_channel(self, ctx, channel: nextcord.TextChannel, command: str):
        """Remove channel whitelist for a command"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        if command not in whitelist or channel.id not in whitelist[command]['channels']:
            await ctx.send(f"❌ Command `{command}` is not whitelisted for {channel.mention}")
            return
        
        whitelist[command]['channels'].remove(channel.id)
        
        # Clean up empty entries
        if not whitelist[command]['channels'] and not whitelist[command]['roles']:
            del whitelist[command]
        
        await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
        
        embed = nextcord.Embed(
            title="✅ Whitelist Removed",
            description=f"Command `{command}` whitelist removed for {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' whitelist removed for channel {channel.id} in guild {ctx.guild.id}")

    async def remove_whitelist_role(self, ctx, role: nextcord.Role, command: str):
        """Remove role whitelist for a command"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        if command not in whitelist or role.id not in whitelist[command]['roles']:
            await ctx.send(f"❌ Command `{command}` is not whitelisted for {role.mention}")
            return
        
        whitelist[command]['roles'].remove(role.id)
        
        # Clean up empty entries
        if not whitelist[command]['channels'] and not whitelist[command]['roles']:
            del whitelist[command]
        
        await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
        
        embed = nextcord.Embed(
            title="✅ Whitelist Removed",
            description=f"Command `{command}` whitelist removed for {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' whitelist removed for role {role.id} in guild {ctx.guild.id}")

    async def is_whitelisted(self, ctx, command_name: str) -> bool:
        """Check if command is whitelisted for the current context"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        # If command is not in whitelist, it's allowed
        if command_name not in whitelist:
            return True
        
        restrictions = whitelist[command_name]
        
        # Check channel whitelist
        if ctx.channel.id in restrictions.get('channels', []):
            return True
        
        # Check role whitelist
        user_role_ids = [role.id for role in ctx.author.roles]
        whitelisted_roles = restrictions.get('roles', [])
        
        if any(role_id in whitelisted_roles for role_id in user_role_ids):
            return True
        
        # If there are restrictions but user doesn't match any, deny access
        if restrictions.get('channels') or restrictions.get('roles'):
            return False
        
        return True

    async def _validate_command(self, command_name: str) -> bool:
        """Validate that a command exists"""
        # Get all bot commands
        all_commands = set()
        
        for command in self.bot.commands:
            all_commands.add(command.name)
            if hasattr(command, 'aliases'):
                all_commands.update(command.aliases)
        
        # Also include group commands
        for cog in self.bot.cogs.values():
            for command in cog.get_commands():
                all_commands.add(command.qualified_name)
        
        return command_name in all_commands
