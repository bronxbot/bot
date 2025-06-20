"""
Ignore Manager
Handles ignore functionality for users and roles.
"""

import nextcord
from nextcord.ext import commands
from typing import List

from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from .constants import LIMITS

logger = CogLogger('IgnoreManager')

class IgnoreManager:
    """Manages ignore settings for users and roles"""
    
    def __init__(self, bot):
        self.bot = bot

    async def show_ignored(self, ctx):
        """Show ignore management interface"""
        embed = nextcord.Embed(
            title="🙈 Ignore Management",
            description=(
                "Manage ignored users and roles - bot will completely ignore them\n\n"
                "**Available Commands:**\n"
                "`general ignore view` - View currently ignored users/roles\n"
                "`general ignore add role <role>` - Add role to ignore list\n"
                "`general ignore add user <user>` - Add user to ignore list\n"
                "`general ignore remove role <role>` - Remove role from ignore list\n"
                "`general ignore remove user <user>` - Remove user from ignore list"
            ),
            color=0x95a5a6
        )
        embed.set_footer(text="Ignored users/roles cannot use ANY bot commands")
        await ctx.send(embed=embed)

    async def view_ignored(self, ctx):
        """View currently ignored users and roles"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        
        ignored_roles = ignored.get('roles', [])
        ignored_users = ignored.get('users', [])
        
        embed = nextcord.Embed(
            title="🙈 Ignored Users and Roles",
            color=0x95a5a6
        )
        
        # Show ignored roles
        if ignored_roles:
            role_list = []
            for role_id in ignored_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(f"• {role.mention}")
                else:
                    role_list.append(f"• <@&{role_id}> (deleted)")
            
            embed.add_field(
                name=f"🎭 Ignored Roles ({len(ignored_roles)}/{LIMITS['max_ignored_roles']})",
                value="\n".join(role_list),
                inline=False
            )
        else:
            embed.add_field(
                name=f"🎭 Ignored Roles (0/{LIMITS['max_ignored_roles']})",
                value="None configured",
                inline=False
            )
        
        # Show ignored users
        if ignored_users:
            user_list = []
            for user_id in ignored_users:
                user = ctx.guild.get_member(user_id)
                if user:
                    user_list.append(f"• {user.mention}")
                else:
                    user_list.append(f"• <@{user_id}> (left server)")
            
            embed.add_field(
                name=f"👤 Ignored Users ({len(ignored_users)}/{LIMITS['max_ignored_users']})",
                value="\n".join(user_list),
                inline=False
            )
        else:
            embed.add_field(
                name=f"👤 Ignored Users (0/{LIMITS['max_ignored_users']})",
                value="None configured",
                inline=False
            )
        
        embed.set_footer(text="Ignored users/roles cannot use any bot commands")
        await ctx.send(embed=embed)

    async def add_ignore_role(self, ctx, role: nextcord.Role):
        """Add a role to the ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {'roles': [], 'users': []})
        
        if role.id in ignored['roles']:
            await ctx.send(f"❌ Role {role.mention} is already ignored")
            return
        
        if len(ignored['roles']) >= LIMITS['max_ignored_roles']:
            await ctx.send(f"❌ Maximum {LIMITS['max_ignored_roles']} ignored roles allowed")
            return
        
        ignored['roles'].append(role.id)
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ Role Ignored",
            description=f"Role {role.mention} is now ignored by the bot",
            color=0x2ecc71
        )
        embed.set_footer(text="Members with this role cannot use any bot commands")
        await ctx.send(embed=embed)
        logger.info(f"Role {role.id} ({role.name}) added to ignore list in guild {ctx.guild.id}")

    async def add_ignore_user(self, ctx, user: nextcord.Member):
        """Add a user to the ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {'roles': [], 'users': []})
        
        if user.id in ignored['users']:
            await ctx.send(f"❌ User {user.mention} is already ignored")
            return
        
        if len(ignored['users']) >= LIMITS['max_ignored_users']:
            await ctx.send(f"❌ Maximum {LIMITS['max_ignored_users']} ignored users allowed")
            return
        
        ignored['users'].append(user.id)
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ User Ignored",
            description=f"User {user.mention} is now ignored by the bot",
            color=0x2ecc71
        )
        embed.set_footer(text="This user cannot use any bot commands")
        await ctx.send(embed=embed)
        logger.info(f"User {user.id} ({user.name}) added to ignore list in guild {ctx.guild.id}")

    async def remove_ignore_role(self, ctx, role: nextcord.Role):
        """Remove a role from the ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {'roles': [], 'users': []})
        
        if role.id not in ignored['roles']:
            await ctx.send(f"❌ Role {role.mention} is not ignored")
            return
        
        ignored['roles'].remove(role.id)
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ Role Un-ignored",
            description=f"Role {role.mention} is no longer ignored by the bot",
            color=0x2ecc71
        )
        embed.set_footer(text="Members with this role can now use bot commands")
        await ctx.send(embed=embed)
        logger.info(f"Role {role.id} ({role.name}) removed from ignore list in guild {ctx.guild.id}")

    async def remove_ignore_user(self, ctx, user: nextcord.Member):
        """Remove a user from the ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {'roles': [], 'users': []})
        
        if user.id not in ignored['users']:
            await ctx.send(f"❌ User {user.mention} is not ignored")
            return
        
        ignored['users'].remove(user.id)
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ User Un-ignored",
            description=f"User {user.mention} is no longer ignored by the bot",
            color=0x2ecc71
        )
        embed.set_footer(text="This user can now use bot commands")
        await ctx.send(embed=embed)
        logger.info(f"User {user.id} ({user.name}) removed from ignore list in guild {ctx.guild.id}")

    async def is_ignored(self, ctx) -> bool:
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

    async def get_ignored_stats(self, guild_id: int) -> dict:
        """Get statistics about ignored users and roles"""
        settings = await db.get_guild_settings(guild_id)
        ignored = settings.get('ignored', {})
        
        return {
            'ignored_users': len(ignored.get('users', [])),
            'ignored_roles': len(ignored.get('roles', [])),
            'max_users': LIMITS['max_ignored_users'],
            'max_roles': LIMITS['max_ignored_roles']
        }
