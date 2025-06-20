"""
Blacklist Manager
Handles command blacklist functionality.
"""

import nextcord
from nextcord.ext import commands
from typing import Dict, List, Set

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from .constants import LIMITS

logger = CogLogger('BlacklistManager')

class BlacklistManager:
    """Manages command blacklist settings"""
    
    def __init__(self, bot):
        self.bot = bot

    async def show_blacklist(self, ctx):
        """Show blacklist management interface"""
        embed = nextcord.Embed(
            title="🚫 Blacklist Management",
            description=(
                "Manage command blacklists - prevent specific channels/roles/users from using commands\n\n"
                "**Available Commands:**\n"
                "`general blacklist view` - View current blacklists\n"
                "`general blacklist channel <channel> <command>` - Blacklist for channel\n"
                "`general blacklist role <role> <command>` - Blacklist for role\n"
                "`general blacklist user <user> <command>` - Blacklist for user\n"
                "`general blacklist remove channel <channel> <command>` - Remove channel blacklist\n"
                "`general blacklist remove role <role> <command>` - Remove role blacklist\n"
                "`general blacklist remove user <user> <command>` - Remove user blacklist"
            ),
            color=0xe74c3c
        )
        embed.set_footer(text="Blacklist = These channels/roles/users CANNOT use the command")
        await ctx.send(embed=embed)

    async def view_blacklist(self, ctx):
        """View current blacklist settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if not blacklist:
            embed = nextcord.Embed(
                title="🚫 Command Blacklist",
                description="No command blacklists configured",
                color=0x95a5a6
            )
            await ctx.send(embed=embed)
            return
        
        embed = nextcord.Embed(
            title="🚫 Command Blacklist",
            description="Commands blocked for specific channels/roles/users",
            color=0xe74c3c
        )
        
        for command, restrictions in blacklist.items():
            restriction_parts = []
            
            # Get blacklisted channels
            channels = []
            for channel_id in restrictions.get('channels', []):
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channels.append(channel.mention)
                else:
                    channels.append(f"<#{channel_id}> (deleted)")
            
            if channels:
                restriction_parts.append(f"**Channels:** {', '.join(channels)}")
            
            # Get blacklisted roles
            roles = []
            for role_id in restrictions.get('roles', []):
                role = ctx.guild.get_role(role_id)
                if role:
                    roles.append(role.mention)
                else:
                    roles.append(f"<@&{role_id}> (deleted)")
            
            if roles:
                restriction_parts.append(f"**Roles:** {', '.join(roles)}")
            
            # Get blacklisted users
            users = []
            for user_id in restrictions.get('users', []):
                user = ctx.guild.get_member(user_id)
                if user:
                    users.append(user.mention)
                else:
                    users.append(f"<@{user_id}> (left server)")
            
            if users:
                restriction_parts.append(f"**Users:** {', '.join(users)}")
            
            embed.add_field(
                name=f"🚫 {command}",
                value="\n".join(restriction_parts) if restriction_parts else "No restrictions",
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def blacklist_channel(self, ctx, channel: nextcord.TextChannel, command: str):
        """Blacklist a command for a specific channel"""
        if not await self._validate_command(command):
            await ctx.send(f"❌ Command `{command}` not found")
            return
        
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist:
            blacklist[command] = {'channels': [], 'roles': [], 'users': []}
        
        if channel.id in blacklist[command]['channels']:
            await ctx.send(f"❌ Command `{command}` is already blacklisted for {channel.mention}")
            return
        
        if len(blacklist[command]['channels']) >= LIMITS['max_blacklist_per_command']:
            await ctx.send(f"❌ Maximum {LIMITS['max_blacklist_per_command']} blacklists per command")
            return
        
        blacklist[command]['channels'].append(channel.id)
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Added",
            description=f"Command `{command}` is now blacklisted for {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklisted for channel {channel.id} in guild {ctx.guild.id}")

    async def blacklist_role(self, ctx, role: nextcord.Role, command: str):
        """Blacklist a command for a specific role"""
        if not await self._validate_command(command):
            await ctx.send(f"❌ Command `{command}` not found")
            return
        
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist:
            blacklist[command] = {'channels': [], 'roles': [], 'users': []}
        
        if role.id in blacklist[command]['roles']:
            await ctx.send(f"❌ Command `{command}` is already blacklisted for {role.mention}")
            return
        
        if len(blacklist[command]['roles']) >= LIMITS['max_blacklist_per_command']:
            await ctx.send(f"❌ Maximum {LIMITS['max_blacklist_per_command']} blacklists per command")
            return
        
        blacklist[command]['roles'].append(role.id)
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Added",
            description=f"Command `{command}` is now blacklisted for {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklisted for role {role.id} in guild {ctx.guild.id}")

    async def blacklist_user(self, ctx, user: nextcord.Member, command: str):
        """Blacklist a command for a specific user"""
        if not await self._validate_command(command):
            await ctx.send(f"❌ Command `{command}` not found")
            return
        
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist:
            blacklist[command] = {'channels': [], 'roles': [], 'users': []}
        
        if user.id in blacklist[command]['users']:
            await ctx.send(f"❌ Command `{command}` is already blacklisted for {user.mention}")
            return
        
        if len(blacklist[command]['users']) >= LIMITS['max_blacklist_per_command']:
            await ctx.send(f"❌ Maximum {LIMITS['max_blacklist_per_command']} blacklists per command")
            return
        
        blacklist[command]['users'].append(user.id)
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Added",
            description=f"Command `{command}` is now blacklisted for {user.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklisted for user {user.id} in guild {ctx.guild.id}")

    async def remove_blacklist_channel(self, ctx, channel: nextcord.TextChannel, command: str):
        """Remove channel blacklist for a command"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist or channel.id not in blacklist[command]['channels']:
            await ctx.send(f"❌ Command `{command}` is not blacklisted for {channel.mention}")
            return
        
        blacklist[command]['channels'].remove(channel.id)
        
        # Clean up empty entries
        if not any(blacklist[command].values()):
            del blacklist[command]
        
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Removed",
            description=f"Command `{command}` blacklist removed for {channel.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklist removed for channel {channel.id} in guild {ctx.guild.id}")

    async def remove_blacklist_role(self, ctx, role: nextcord.Role, command: str):
        """Remove role blacklist for a command"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist or role.id not in blacklist[command]['roles']:
            await ctx.send(f"❌ Command `{command}` is not blacklisted for {role.mention}")
            return
        
        blacklist[command]['roles'].remove(role.id)
        
        # Clean up empty entries
        if not any(blacklist[command].values()):
            del blacklist[command]
        
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Removed",
            description=f"Command `{command}` blacklist removed for {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklist removed for role {role.id} in guild {ctx.guild.id}")

    async def remove_blacklist_user(self, ctx, user: nextcord.Member, command: str):
        """Remove user blacklist for a command"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        if command not in blacklist or user.id not in blacklist[command]['users']:
            await ctx.send(f"❌ Command `{command}` is not blacklisted for {user.mention}")
            return
        
        blacklist[command]['users'].remove(user.id)
        
        # Clean up empty entries
        if not any(blacklist[command].values()):
            del blacklist[command]
        
        await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
        
        embed = nextcord.Embed(
            title="✅ Blacklist Removed",
            description=f"Command `{command}` blacklist removed for {user.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Command '{command}' blacklist removed for user {user.id} in guild {ctx.guild.id}")

    async def is_blacklisted(self, ctx, command_name: str) -> bool:
        """Check if command is blacklisted for the current context"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        # If command is not blacklisted, it's allowed
        if command_name not in blacklist:
            return False
        
        restrictions = blacklist[command_name]
        
        # Check channel blacklist
        if ctx.channel.id in restrictions.get('channels', []):
            return True
        
        # Check user blacklist
        if ctx.author.id in restrictions.get('users', []):
            return True
        
        # Check role blacklist
        user_role_ids = [role.id for role in ctx.author.roles]
        blacklisted_roles = restrictions.get('roles', [])
        
        if any(role_id in blacklisted_roles for role_id in user_role_ids):
            return True
        
        return False

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
