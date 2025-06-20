"""
Permission Manager
Handles permission management for bot settings.
"""

import nextcord
from nextcord.ext import commands
from typing import List, Dict

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from .constants import PERMISSION_LEVELS

logger = CogLogger('PermissionManager')

class PermissionManager:
    """Manages permission settings for bot configuration"""
    
    def __init__(self, bot):
        self.bot = bot

    async def show_permissions(self, ctx):
        """Show permission management interface"""
        embed = nextcord.Embed(
            title="👑 Permission Management",
            description=(
                "Configure who can manage bot settings\n\n"
                "**Available Commands:**\n"
                "`general permissions view` - View current permissions\n"
                "`general permissions add role <role>` - Add role permission\n"
                "`general permissions add user <user>` - Add user permission\n"
                "`general permissions remove role <role>` - Remove role permission\n"
                "`general permissions remove user <user>` - Remove user permission"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)

    async def view_permissions(self, ctx):
        """View current permission settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        
        manage_roles = perms.get('manage_roles', [])
        manage_users = perms.get('manage_users', [])
        
        embed = nextcord.Embed(
            title="👑 Settings Management Permissions",
            color=0x3498db
        )
        
        # Show roles with permissions
        if manage_roles:
            role_list = []
            for role_id in manage_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• <@&{role_id}> (deleted)")
            
            embed.add_field(
                name="🎭 Authorized Roles",
                value="\n".join(role_list),
                inline=False
            )
        else:
            embed.add_field(
                name="🎭 Authorized Roles",
                value="None configured",
                inline=False
            )
        
        # Show users with permissions
        if manage_users:
            user_list = []
            for user_id in manage_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    user_list.append(f"• {user.mention}")
                else:
                    user_list.append(f"• <@{user_id}> (left server)")
            
            embed.add_field(
                name="👤 Authorized Users",
                value="\n".join(user_list),
                inline=False
            )
        else:
            embed.add_field(
                name="👤 Authorized Users",
                value="None configured",
                inline=False
            )
        
        embed.set_footer(text="Note: Server admins and owners always have access")
        await ctx.send(embed=embed)

    async def add_role_permission(self, ctx, role: nextcord.Role):
        """Add a role to settings management permissions"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_roles = perms.get('manage_roles', [])
        
        if role.id in manage_roles:
            await ctx.send(f"❌ Role {role.mention} already has settings management permissions")
            return
        
        manage_roles.append(role.id)
        perms['manage_roles'] = manage_roles
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Added",
            description=f"Role {role.mention} can now manage bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Role {role.id} ({role.name}) granted settings permissions in guild {ctx.guild.id}")

    async def add_user_permission(self, ctx, user: nextcord.Member):
        """Add a user to settings management permissions"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_users = perms.get('manage_users', [])
        
        if user.id in manage_users:
            await ctx.send(f"❌ User {user.mention} already has settings management permissions")
            return
        
        manage_users.append(user.id)
        perms['manage_users'] = manage_users
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Added",
            description=f"User {user.mention} can now manage bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"User {user.id} ({user.name}) granted settings permissions in guild {ctx.guild.id}")

    async def remove_role_permission(self, ctx, role: nextcord.Role):
        """Remove a role from settings management permissions"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_roles = perms.get('manage_roles', [])
        
        if role.id not in manage_roles:
            await ctx.send(f"❌ Role {role.mention} doesn't have settings management permissions")
            return
        
        manage_roles.remove(role.id)
        perms['manage_roles'] = manage_roles
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Removed",
            description=f"Role {role.mention} can no longer manage bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"Role {role.id} ({role.name}) settings permissions revoked in guild {ctx.guild.id}")

    async def remove_user_permission(self, ctx, user: nextcord.Member):
        """Remove a user from settings management permissions"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_users = perms.get('manage_users', [])
        
        if user.id not in manage_users:
            await ctx.send(f"❌ User {user.mention} doesn't have settings management permissions")
            return
        
        manage_users.remove(user.id)
        perms['manage_users'] = manage_users
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Removed",
            description=f"User {user.mention} can no longer manage bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)
        logger.info(f"User {user.id} ({user.name}) settings permissions revoked in guild {ctx.guild.id}")

    async def has_settings_permissions(self, ctx) -> bool:
        """Check if user has permission to manage settings"""
        # Server owner and administrators always have access
        if ctx.author.id == ctx.guild.owner_id or ctx.author.guild_permissions.administrator:
            return True
        
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        
        # Check user permissions
        if ctx.author.id in perms.get('manage_users', []):
            return True
        
        # Check role permissions
        user_role_ids = [role.id for role in ctx.author.roles]
        manage_roles = perms.get('manage_roles', [])
        
        return any(role_id in manage_roles for role_id in user_role_ids)
