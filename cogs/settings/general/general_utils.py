"""
General Utilities
Utility functions for the general settings system.
"""

import nextcord
from nextcord.ext import commands
from typing import Dict, List, Set

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger

logger = CogLogger('GeneralUtils')

class GeneralUtils:
    """Utility functions for general settings"""
    
    def __init__(self, bot):
        self.bot = bot

    async def is_command_allowed(self, ctx, command_name: str) -> bool:
        """
        Comprehensive check if a command is allowed in the current context.
        Checks ignore, blacklist, and whitelist settings.
        """
        
        # First check if user/context is ignored
        if await self._is_ignored(ctx):
            return False
        
        # Then check blacklist
        if await self._is_blacklisted(ctx, command_name):
            return False
        
        # Finally check whitelist
        if not await self._is_whitelisted(ctx, command_name):
            return False
        
        return True

    async def _is_ignored(self, ctx) -> bool:
        """Check if user/context should be ignored"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        
        # Check if user is directly ignored
        if ctx.author.id in ignored.get('users', []):
            return True
        
        # Check if user has an ignored role
        user_role_ids = [role.id for role in ctx.author.roles]
        ignored_roles = ignored.get('roles', [])
        
        return any(role_id in ignored_roles for role_id in user_role_ids)

    async def _is_blacklisted(self, ctx, command_name: str) -> bool:
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

    async def _is_whitelisted(self, ctx, command_name: str) -> bool:
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

    async def validate_command_name(self, command_name: str) -> bool:
        """Validate that a command exists"""
        all_commands = set()
        
        # Get all regular commands
        for command in self.bot.commands:
            all_commands.add(command.name)
            if hasattr(command, 'aliases'):
                all_commands.update(command.aliases)
            
            # Add subcommands for groups
            if hasattr(command, 'commands'):
                for subcommand in command.commands:
                    all_commands.add(f"{command.name} {subcommand.name}")
                    if hasattr(subcommand, 'aliases'):
                        for alias in subcommand.aliases:
                            all_commands.add(f"{command.name} {alias}")
        
        # Also include qualified names from cogs
        for cog in self.bot.cogs.values():
            for command in cog.get_commands():
                all_commands.add(command.qualified_name)
                
                # Add aliases with qualified names
                if hasattr(command, 'aliases'):
                    parent = command.parent.qualified_name if command.parent else ""
                    for alias in command.aliases:
                        qualified_alias = f"{parent} {alias}".strip()
                        all_commands.add(qualified_alias)
        
        return command_name in all_commands

    async def get_all_command_names(self) -> Set[str]:
        """Get all available command names"""
        all_commands = set()
        
        # Get all regular commands
        for command in self.bot.commands:
            all_commands.add(command.name)
            if hasattr(command, 'aliases'):
                all_commands.update(command.aliases)
            
            # Add subcommands for groups
            if hasattr(command, 'commands'):
                for subcommand in command.commands:
                    all_commands.add(f"{command.name} {subcommand.name}")
                    if hasattr(subcommand, 'aliases'):
                        for alias in subcommand.aliases:
                            all_commands.add(f"{command.name} {alias}")
        
        # Also include qualified names from cogs
        for cog in self.bot.cogs.values():
            for command in cog.get_commands():
                all_commands.add(command.qualified_name)
        
        return all_commands

    async def get_guild_statistics(self, guild_id: int) -> Dict[str, int]:
        """Get statistics about general settings for a guild"""
        settings = await db.get_guild_settings(guild_id)
        
        # Count various settings
        stats = {
            'prefixes': len(settings.get('prefixes', [])),
            'manage_roles': len(settings.get('general_permissions', {}).get('manage_roles', [])),
            'manage_users': len(settings.get('general_permissions', {}).get('manage_users', [])),
            'whitelisted_commands': len(settings.get('command_whitelist', {})),
            'blacklisted_commands': len(settings.get('command_blacklist', {})),
            'ignored_users': len(settings.get('ignored', {}).get('users', [])),
            'ignored_roles': len(settings.get('ignored', {}).get('roles', []))
        }
        
        return stats

    async def cleanup_deleted_entities(self, guild_id: int, guild: nextcord.Guild):
        """Clean up references to deleted roles/channels/users"""
        settings = await db.get_guild_settings(guild_id)
        updated = False
        
        # Clean up permission roles
        perms = settings.get('general_permissions', {})
        if 'manage_roles' in perms:
            valid_roles = [role_id for role_id in perms['manage_roles'] if guild.get_role(role_id)]
            if len(valid_roles) != len(perms['manage_roles']):
                perms['manage_roles'] = valid_roles
                settings['general_permissions'] = perms
                updated = True
        
        # Clean up ignored roles
        ignored = settings.get('ignored', {})
        if 'roles' in ignored:
            valid_roles = [role_id for role_id in ignored['roles'] if guild.get_role(role_id)]
            if len(valid_roles) != len(ignored['roles']):
                ignored['roles'] = valid_roles
                settings['ignored'] = ignored
                updated = True
        
        # Clean up whitelist/blacklist channels and roles
        for list_type in ['command_whitelist', 'command_blacklist']:
            if list_type in settings:
                for command, restrictions in settings[list_type].items():
                    if 'channels' in restrictions:
                        valid_channels = [ch_id for ch_id in restrictions['channels'] if guild.get_channel(ch_id)]
                        if len(valid_channels) != len(restrictions['channels']):
                            restrictions['channels'] = valid_channels
                            updated = True
                    
                    if 'roles' in restrictions:
                        valid_roles = [role_id for role_id in restrictions['roles'] if guild.get_role(role_id)]
                        if len(valid_roles) != len(restrictions['roles']):
                            restrictions['roles'] = valid_roles
                            updated = True
        
        if updated:
            await db.update_guild_settings(guild_id, settings)
            logger.info(f"Cleaned up deleted entities for guild {guild_id}")
        
        return updated

    def format_permissions_help(self) -> nextcord.Embed:
        """Create help embed for permissions"""
        embed = nextcord.Embed(
            title="🔧 General Settings Help",
            description="Comprehensive guide to general server settings",
            color=0x3498db
        )
        
        embed.add_field(
            name="📌 Prefixes",
            value=(
                "• Set custom prefixes for bot commands\n"
                "• Maximum 5 prefixes, 5 characters each\n"
                "• Cannot remove the last prefix"
            ),
            inline=False
        )
        
        embed.add_field(
            name="👑 Permissions",
            value=(
                "• Control who can manage bot settings\n"
                "• Add roles or users to management list\n"
                "• Server admins always have access"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Whitelist vs 🚫 Blacklist",
            value=(
                "• **Whitelist**: ONLY specified channels/roles can use command\n"
                "• **Blacklist**: Specified channels/roles/users CANNOT use command\n"
                "• Whitelist takes precedence over blacklist"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🙈 Ignore List",
            value=(
                "• Completely ignore users or roles\n"
                "• Ignored entities cannot use ANY bot commands\n"
                "• Useful for bots or troublesome users"
            ),
            inline=False
        )
        
        return embed
