"""
General Settings Cog
Main cog for general server settings management.
"""

import nextcord
from nextcord.ext import commands
# from nextcord import app_commands  # Not available in nextcord
from typing import Optional, List, Union

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

from .constants import DEFAULT_GUILD_SETTINGS, LIMITS, SETTING_CATEGORIES, PERMISSION_LEVELS
from .prefix_manager import PrefixManager
from .permission_manager import PermissionManager
from .whitelist_manager import WhitelistManager
from .blacklist_manager import BlacklistManager
from .ignore_manager import IgnoreManager
from .general_utils import GeneralUtils

logger = CogLogger('GeneralSettings')

class GeneralSettings(commands.Cog, ErrorHandler):
    """General server configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        
        # Initialize managers
        self.prefix_manager = PrefixManager(bot)
        self.permission_manager = PermissionManager(bot)
        self.whitelist_manager = WhitelistManager(bot)
        self.blacklist_manager = BlacklistManager(bot)
        self.ignore_manager = IgnoreManager(bot)
        self.utils = GeneralUtils(bot)

    @commands.group(name='general', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def general_settings(self, ctx):
        """General server settings management"""
        embed = nextcord.Embed(
            title="🔧 General Server Settings",
            description=(
                "Configure general bot behavior for this server\n\n"
                "**Available Commands:**\n"
                "`general permissions` - Manage who can edit bot settings\n"
                "`general whitelist` - Manage command whitelists\n"
                "`general blacklist` - Manage command blacklists\n"
                "`general ignore` - Manage ignored users/roles\n"
                "`general prefix` - Manage server prefixes\n"
                "`general view` - View current settings"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)

    @general_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_general_settings(self, ctx):
        """View current general settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        
        # Get prefixes
        prefixes = settings.get('prefixes', ['.'])
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        # Get permissions
        perms = settings.get('general_permissions', {})
        manage_roles = [f"<@&{r}>" for r in perms.get('manage_roles', [])]
        manage_users = [f"<@{u}>" for u in perms.get('manage_users', [])]
        
        # Get ignored users/roles
        ignored = settings.get('ignored', {})
        ignored_roles = [f"<@&{r}>" for r in ignored.get('roles', [])]
        ignored_users = [f"<@{u}>" for u in ignored.get('users', [])]
        
        # Get command restrictions
        whitelist = settings.get('command_whitelist', {})
        blacklist = settings.get('command_blacklist', {})
        
        embed = nextcord.Embed(
            title="🔧 General Settings Overview",
            color=0x3498db
        )
        
        embed.add_field(
            name="📌 Prefixes",
            value=f"`{'`, `'.join(prefixes)}`" if prefixes else "None set",
            inline=False
        )
        
        embed.add_field(
            name="👑 Management Permissions",
            value=(
                f"**Roles:** {', '.join(manage_roles) if manage_roles else 'None'}\n"
                f"**Users:** {', '.join(manage_users) if manage_users else 'None'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🚫 Ignored by Bot",
            value=(
                f"**Roles:** {', '.join(ignored_roles) if ignored_roles else 'None'}\n"
                f"**Users:** {', '.join(ignored_users) if ignored_users else 'None'}"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📋 Command Restrictions",
            value=(
                f"**Whitelisted Commands:** {len(whitelist)} configured\n"
                f"**Blacklisted Commands:** {len(blacklist)} configured"
            ),
            inline=False
        )
        
        embed.set_footer(text="Use 'general <category>' to manage specific settings")
        await ctx.send(embed=embed)

    # Delegate to managers for specific functionality
    @general_settings.group(name='prefix')
    @commands.has_permissions(manage_guild=True)
    async def prefix_settings(self, ctx):
        """Server prefix management"""
        if ctx.invoked_subcommand is None:
            await self.prefix_manager.show_prefixes(ctx)

    @prefix_settings.command(name='add')
    async def add_prefix(self, ctx, prefix: str):
        """Add a new server prefix"""
        await self.prefix_manager.add_prefix(ctx, prefix)

    @prefix_settings.command(name='remove')
    async def remove_prefix(self, ctx, prefix: str):
        """Remove a server prefix"""
        await self.prefix_manager.remove_prefix(ctx, prefix)

    @prefix_settings.command(name='list')
    async def list_prefixes(self, ctx):
        """List all server prefixes"""
        await self.prefix_manager.list_prefixes(ctx)

    @general_settings.group(name='permissions')
    @commands.has_permissions(manage_guild=True)
    async def permission_settings(self, ctx):
        """Permission management for bot settings"""
        if ctx.invoked_subcommand is None:
            await self.permission_manager.show_permissions(ctx)

    @permission_settings.command(name='view')
    async def view_permissions(self, ctx):
        """View current permission settings"""
        await self.permission_manager.view_permissions(ctx)

    @permission_settings.group(name='add')
    async def add_permission(self, ctx):
        """Add permission for a role or user"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `role` or `user`")

    @add_permission.command(name='role')
    async def add_role_permission(self, ctx, role: nextcord.Role):
        """Add a role to settings management permissions"""
        await self.permission_manager.add_role_permission(ctx, role)

    @add_permission.command(name='user')
    async def add_user_permission(self, ctx, user: nextcord.Member):
        """Add a user to settings management permissions"""
        await self.permission_manager.add_user_permission(ctx, user)

    @permission_settings.group(name='remove')
    async def remove_permission(self, ctx):
        """Remove permission for a role or user"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `role` or `user`")

    @remove_permission.command(name='role')
    async def remove_role_permission(self, ctx, role: nextcord.Role):
        """Remove a role from settings management permissions"""
        await self.permission_manager.remove_role_permission(ctx, role)

    @remove_permission.command(name='user')
    async def remove_user_permission(self, ctx, user: nextcord.Member):
        """Remove a user from settings management permissions"""
        await self.permission_manager.remove_user_permission(ctx, user)

    @general_settings.group(name='whitelist')
    @commands.has_permissions(manage_guild=True)
    async def whitelist_settings(self, ctx):
        """Command whitelist management"""
        if ctx.invoked_subcommand is None:
            await self.whitelist_manager.show_whitelist(ctx)

    @whitelist_settings.command(name='view')
    async def view_whitelist(self, ctx):
        """View current whitelist settings"""
        await self.whitelist_manager.view_whitelist(ctx)

    @whitelist_settings.command(name='channel')
    async def whitelist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Whitelist a command for a specific channel"""
        await self.whitelist_manager.whitelist_channel(ctx, channel, command)

    @whitelist_settings.command(name='role')
    async def whitelist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Whitelist a command for a specific role"""
        await self.whitelist_manager.whitelist_role(ctx, role, command)

    @whitelist_settings.group(name='remove')
    async def remove_whitelist(self, ctx):
        """Remove whitelist entries"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `channel`, `role`, or `user`")

    @remove_whitelist.command(name='channel')
    async def remove_whitelist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Remove channel whitelist for a command"""
        await self.whitelist_manager.remove_whitelist_channel(ctx, channel, command)

    @remove_whitelist.command(name='role')
    async def remove_whitelist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Remove role whitelist for a command"""
        await self.whitelist_manager.remove_whitelist_role(ctx, role, command)

    @general_settings.group(name='blacklist')
    @commands.has_permissions(manage_guild=True)
    async def blacklist_settings(self, ctx):
        """Command blacklist management"""
        if ctx.invoked_subcommand is None:
            await self.blacklist_manager.show_blacklist(ctx)

    @blacklist_settings.command(name='view')
    async def view_blacklist(self, ctx):
        """View current blacklist settings"""
        await self.blacklist_manager.view_blacklist(ctx)

    @blacklist_settings.command(name='channel')
    async def blacklist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Blacklist a command for a specific channel"""
        await self.blacklist_manager.blacklist_channel(ctx, channel, command)

    @blacklist_settings.command(name='role')
    async def blacklist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Blacklist a command for a specific role"""
        await self.blacklist_manager.blacklist_role(ctx, role, command)

    @blacklist_settings.command(name='user')
    async def blacklist_user(self, ctx, user: nextcord.Member, *, command: str):
        """Blacklist a command for a specific user"""
        await self.blacklist_manager.blacklist_user(ctx, user, command)

    @blacklist_settings.group(name='remove')
    async def remove_blacklist(self, ctx):
        """Remove blacklist entries"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `channel`, `role`, or `user`")

    @remove_blacklist.command(name='channel')
    async def remove_blacklist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Remove channel blacklist for a command"""
        await self.blacklist_manager.remove_blacklist_channel(ctx, channel, command)

    @remove_blacklist.command(name='role')
    async def remove_blacklist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Remove role blacklist for a command"""
        await self.blacklist_manager.remove_blacklist_role(ctx, role, command)

    @remove_blacklist.command(name='user')
    async def remove_blacklist_user(self, ctx, user: nextcord.Member, *, command: str):
        """Remove user blacklist for a command"""
        await self.blacklist_manager.remove_blacklist_user(ctx, user, command)

    @general_settings.group(name='ignore')
    @commands.has_permissions(manage_guild=True)
    async def ignore_settings(self, ctx):
        """Ignore management - users/roles to ignore completely"""
        if ctx.invoked_subcommand is None:
            await self.ignore_manager.show_ignored(ctx)

    @ignore_settings.command(name='view')
    async def view_ignored(self, ctx):
        """View currently ignored users and roles"""
        await self.ignore_manager.view_ignored(ctx)

    @ignore_settings.group(name='add')
    async def add_ignore(self, ctx):
        """Add users or roles to ignore list"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `role` or `user`")

    @add_ignore.command(name='role')
    async def add_ignore_role(self, ctx, role: nextcord.Role):
        """Add a role to the ignore list"""
        await self.ignore_manager.add_ignore_role(ctx, role)

    @add_ignore.command(name='user')
    async def add_ignore_user(self, ctx, user: nextcord.Member):
        """Add a user to the ignore list"""
        await self.ignore_manager.add_ignore_user(ctx, user)

    @ignore_settings.group(name='remove')
    async def remove_ignore(self, ctx):
        """Remove users or roles from ignore list"""
        if ctx.invoked_subcommand is None:
            await ctx.send("Please specify `role` or `user`")

    @remove_ignore.command(name='role')
    async def remove_ignore_role(self, ctx, role: nextcord.Role):
        """Remove a role from the ignore list"""
        await self.ignore_manager.remove_ignore_role(ctx, role)

    @remove_ignore.command(name='user')
    async def remove_ignore_user(self, ctx, user: nextcord.Member):
        """Remove a user from the ignore list"""
        await self.ignore_manager.remove_ignore_user(ctx, user)

    # Utility methods for other cogs to use
    async def is_command_allowed(self, ctx, command_name: str) -> bool:
        """Check if a command is allowed in the current context"""
        return await self.utils.is_command_allowed(ctx, command_name)

    async def cog_command_error(self, ctx, error):
        """Handle cog-specific errors"""
        await self.handle_error(ctx, error, "general settings")

async def setup(bot):
    bot.add_cog(GeneralSettings(bot))
