# General Server Settings
# Handles permissions, command restrictions, and user/role management

import nextcord
from nextcord.ext import commands
# from nextcord import app_commands  # Not available in nextcord
from typing import Optional, List, Union
import json
from utils.db import db
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('GeneralSettings')

class GeneralSettings(commands.Cog, ErrorHandler):
    """General server configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='general', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def general_settings(self, ctx):
        """General server settings management"""
        embed = nextcord.Embed(
            title="🔧 General Server Settings",
            description=(
                "Configure general bot behavior for this server\n\n"
                "**Available Commands:**\n"
                f"`{ctx.prefix}general permissions` - Manage who can edit bot settings\n"
                f"`{ctx.prefix}general whitelist` - Manage command whitelists\n"
                f"`{ctx.prefix}general blacklist` - Manage command blacklists\n"
                f"`{ctx.prefix}general ignore` - Manage ignored users/roles\n"
                f"`{ctx.prefix}general prefix` - Manage server prefixes\n"
                f"`{ctx.prefix}general view` - View current settings"
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
                f"**Blacklisted Commands:** {len(blacklist)} configured\n"
                f"Use `general whitelist view` or `general blacklist view` for details"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Prefix Management
    @general_settings.group(name='prefix', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def prefix_settings(self, ctx):
        """Manage server prefixes"""
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get('prefixes', ['.'])
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        embed = nextcord.Embed(
            title="📌 Server Prefixes",
            description=f"Current prefixes: `{'`, `'.join(prefixes)}`",
            color=0x3498db
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}prefix add <prefix>` - Add a new prefix\n"
                f"`{ctx.prefix}prefix remove <prefix>` - Remove a prefix\n"
                f"`{ctx.prefix}prefix list` - List all prefixes"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @prefix_settings.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_prefix(self, ctx, prefix: str):
        """Add a new prefix to the server"""
        if len(prefix) > 5:
            return await ctx.send("❌ Prefix cannot be longer than 5 characters!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get('prefixes', ['.'])
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        if prefix in prefixes:
            return await ctx.send(f"❌ Prefix `{prefix}` is already set!")
        
        if len(prefixes) >= 5:
            return await ctx.send("❌ Maximum of 5 prefixes allowed per server!")
        
        prefixes.append(prefix)
        await db.update_guild_settings(ctx.guild.id, {'prefixes': prefixes})
        
        embed = nextcord.Embed(
            title="✅ Prefix Added",
            description=f"Added prefix: `{prefix}`\nCurrent prefixes: `{'`, `'.join(prefixes)}`",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @prefix_settings.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_prefix(self, ctx, prefix: str):
        """Remove a prefix from the server"""
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get('prefixes', ['.'])
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        if prefix not in prefixes:
            return await ctx.send(f"❌ Prefix `{prefix}` is not set!")
        
        if len(prefixes) <= 1:
            return await ctx.send("❌ Cannot remove the last prefix! Add another prefix first.")
        
        prefixes.remove(prefix)
        await db.update_guild_settings(ctx.guild.id, {'prefixes': prefixes})
        
        embed = nextcord.Embed(
            title="✅ Prefix Removed",
            description=f"Removed prefix: `{prefix}`\nCurrent prefixes: `{'`, `'.join(prefixes)}`",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @prefix_settings.command(name='list')
    @commands.has_permissions(manage_guild=True)
    async def list_prefixes(self, ctx):
        """List all server prefixes"""
        settings = await db.get_guild_settings(ctx.guild.id)
        prefixes = settings.get('prefixes', ['.'])
        if isinstance(prefixes, str):
            prefixes = [prefixes]
        
        embed = nextcord.Embed(
            title="📌 Server Prefixes",
            description=f"Current prefixes: `{'`, `'.join(prefixes)}`",
            color=0x3498db
        )
        await ctx.send(embed=embed)

    # Permission Management
    @general_settings.group(name='permissions', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def permission_settings(self, ctx):
        """Manage who can edit bot settings"""
        embed = nextcord.Embed(
            title="👑 Permission Management",
            description="Configure who can modify bot settings",
            color=0x3498db
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}permissions add role <role>` - Allow role to edit settings\n"
                f"`{ctx.prefix}permissions add user <user>` - Allow user to edit settings\n"
                f"`{ctx.prefix}permissions remove role <role>` - Remove role permissions\n"
                f"`{ctx.prefix}permissions remove user <user>` - Remove user permissions\n"
                f"`{ctx.prefix}permissions view` - View current permissions"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @permission_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_permissions(self, ctx):
        """View current permission settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        
        manage_roles = perms.get('manage_roles', [])
        manage_users = perms.get('manage_users', [])
        
        embed = nextcord.Embed(
            title="👑 Current Permissions",
            color=0x3498db
        )
        
        role_list = []
        for role_id in manage_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                role_list.append(f"<@&{role_id}> ({role.name})")
            else:
                role_list.append(f"<@&{role_id}> (Deleted Role)")
        
        user_list = []
        for user_id in manage_users:
            try:
                user = await self.bot.fetch_user(user_id)
                user_list.append(f"<@{user_id}> ({user.name})")
            except:
                user_list.append(f"<@{user_id}> (Unknown User)")
        
        embed.add_field(
            name="👥 Roles with Settings Access",
            value='\n'.join(role_list) if role_list else "None",
            inline=False
        )
        
        embed.add_field(
            name="👤 Users with Settings Access",
            value='\n'.join(user_list) if user_list else "None",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @permission_settings.group(name='add', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def add_permission(self, ctx):
        """Add permission to role or user"""
        await ctx.send("❌ Please specify `role` or `user`. Example: `permissions add role @ModeratorRole`")

    @add_permission.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def add_role_permission(self, ctx, role: nextcord.Role):
        """Add role permission to edit settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_roles = perms.get('manage_roles', [])
        
        if role.id in manage_roles:
            return await ctx.send(f"❌ Role {role.mention} already has settings permissions!")
        
        manage_roles.append(role.id)
        perms['manage_roles'] = manage_roles
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Added",
            description=f"Role {role.mention} can now edit bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @add_permission.command(name='user')
    @commands.has_permissions(manage_guild=True)
    async def add_user_permission(self, ctx, user: nextcord.Member):
        """Add user permission to edit settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_users = perms.get('manage_users', [])
        
        if user.id in manage_users:
            return await ctx.send(f"❌ User {user.mention} already has settings permissions!")
        
        manage_users.append(user.id)
        perms['manage_users'] = manage_users
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Added",
            description=f"User {user.mention} can now edit bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @permission_settings.group(name='remove', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def remove_permission(self, ctx):
        """Remove permission from role or user"""
        await ctx.send("❌ Please specify `role` or `user`. Example: `permissions remove role @ModeratorRole`")

    @remove_permission.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def remove_role_permission(self, ctx, role: nextcord.Role):
        """Remove role permission to edit settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_roles = perms.get('manage_roles', [])
        
        if role.id not in manage_roles:
            return await ctx.send(f"❌ Role {role.mention} doesn't have settings permissions!")
        
        manage_roles.remove(role.id)
        perms['manage_roles'] = manage_roles
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Removed",
            description=f"Role {role.mention} can no longer edit bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @remove_permission.command(name='user')
    @commands.has_permissions(manage_guild=True)
    async def remove_user_permission(self, ctx, user: nextcord.Member):
        """Remove user permission to edit settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        perms = settings.get('general_permissions', {})
        manage_users = perms.get('manage_users', [])
        
        if user.id not in manage_users:
            return await ctx.send(f"❌ User {user.mention} doesn't have settings permissions!")
        
        manage_users.remove(user.id)
        perms['manage_users'] = manage_users
        await db.update_guild_settings(ctx.guild.id, {'general_permissions': perms})
        
        embed = nextcord.Embed(
            title="✅ Permission Removed",
            description=f"User {user.mention} can no longer edit bot settings",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    # Command Whitelist Management
    @general_settings.group(name='whitelist', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def whitelist_settings(self, ctx):
        """Manage command whitelists"""
        embed = nextcord.Embed(
            title="✅ Command Whitelist Management",
            description="Configure which commands are allowed in channels/roles",
            color=0x2ecc71
        )
        embed.add_field(
            name="Commands",
            value=(
                "`whitelist channel <channel> <command>` - Whitelist command in channel\n"
                "`whitelist role <role> <command>` - Whitelist command for role\n"
                "`whitelist remove channel <channel> <command>` - Remove whitelist\n"
                "`whitelist remove role <role> <command>` - Remove role whitelist\n"
                "`whitelist view` - View current whitelists"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @whitelist_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_whitelist(self, ctx):
        """View current command whitelists"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        
        embed = nextcord.Embed(
            title="✅ Command Whitelists",
            color=0x2ecc71
        )
        
        if not whitelist:
            embed.description = "No command whitelists configured"
            return await ctx.send(embed=embed)
        
        # Channel whitelists
        channel_whitelist = whitelist.get('channels', {})
        if channel_whitelist:
            channel_text = []
            for channel_id, commands in channel_whitelist.items():
                channel = ctx.guild.get_channel(int(channel_id))
                channel_name = channel.mention if channel else f"#{channel_id} (Deleted)"
                channel_text.append(f"{channel_name}: `{', '.join(commands)}`")
            
            embed.add_field(
                name="📺 Channel Whitelists",
                value='\n'.join(channel_text),
                inline=False
            )
        
        # Role whitelists
        role_whitelist = whitelist.get('roles', {})
        if role_whitelist:
            role_text = []
            for role_id, commands in role_whitelist.items():
                role = ctx.guild.get_role(int(role_id))
                role_name = role.mention if role else f"@{role_id} (Deleted)"
                role_text.append(f"{role_name}: `{', '.join(commands)}`")
            
            embed.add_field(
                name="👥 Role Whitelists",
                value='\n'.join(role_text),
                inline=False
            )
        
        await ctx.send(embed=embed)

    @whitelist_settings.command(name='channel')
    @commands.has_permissions(manage_guild=True)
    async def whitelist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Whitelist a command in a specific channel"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        channel_whitelist = whitelist.get('channels', {})
        
        channel_id = str(channel.id)
        if channel_id not in channel_whitelist:
            channel_whitelist[channel_id] = []
        
        if command not in channel_whitelist[channel_id]:
            channel_whitelist[channel_id].append(command)
            whitelist['channels'] = channel_whitelist
            await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
            
            embed = nextcord.Embed(
                title="✅ Command Whitelisted",
                description=f"Command `{command}` is now whitelisted in {channel.mention}",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `{command}` is already whitelisted in {channel.mention}")

    @whitelist_settings.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def whitelist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Whitelist a command for a specific role"""
        settings = await db.get_guild_settings(ctx.guild.id)
        whitelist = settings.get('command_whitelist', {})
        role_whitelist = whitelist.get('roles', {})
        
        role_id = str(role.id)
        if role_id not in role_whitelist:
            role_whitelist[role_id] = []
        
        if command not in role_whitelist[role_id]:
            role_whitelist[role_id].append(command)
            whitelist['roles'] = role_whitelist
            await db.update_guild_settings(ctx.guild.id, {'command_whitelist': whitelist})
            
            embed = nextcord.Embed(
                title="✅ Command Whitelisted",
                description=f"Command `{command}` is now whitelisted for {role.mention}",
                color=0x2ecc71
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `{command}` is already whitelisted for {role.mention}")

    # Command Blacklist Management  
    @general_settings.group(name='blacklist', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def blacklist_settings(self, ctx):
        """Manage command blacklists"""
        embed = nextcord.Embed(
            title="❌ Command Blacklist Management",
            description="Configure which commands are blocked in channels/roles",
            color=0xe74c3c
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}blacklist channel <channel> <command>` - Blacklist command in channel\n"
                f"`{ctx.prefix}blacklist role <role> <command>` - Blacklist command for role\n"
                f"`{ctx.prefix}blacklist user <user> <command>` - Blacklist command for user\n"
                f"`{ctx.prefix}blacklist remove channel <channel> <command>` - Remove blacklist\n"
                f"`{ctx.prefix}blacklist remove role <role> <command>` - Remove role blacklist\n"
                f"`{ctx.prefix}blacklist remove user <user> <command>` - Remove user blacklist\n"
                f"`{ctx.prefix}blacklist view` - View current blacklists"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @blacklist_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_blacklist(self, ctx):
        """View current command blacklists"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        
        embed = nextcord.Embed(
            title="❌ Command Blacklists",
            color=0xe74c3c
        )
        
        if not blacklist:
            embed.description = "No command blacklists configured"
            return await ctx.send(embed=embed)
        
        # Channel blacklists
        channel_blacklist = blacklist.get('channels', {})
        if channel_blacklist:
            channel_text = []
            for channel_id, commands in channel_blacklist.items():
                channel = ctx.guild.get_channel(int(channel_id))
                channel_name = channel.mention if channel else f"#{channel_id} (Deleted)"
                channel_text.append(f"{channel_name}: `{', '.join(commands)}`")
            
            embed.add_field(
                name="📺 Channel Blacklists",
                value='\n'.join(channel_text),
                inline=False
            )
        
        # Role blacklists
        role_blacklist = blacklist.get('roles', {})
        if role_blacklist:
            role_text = []
            for role_id, commands in role_blacklist.items():
                role = ctx.guild.get_role(int(role_id))
                role_name = role.mention if role else f"@{role_id} (Deleted)"
                role_text.append(f"{role_name}: `{', '.join(commands)}`")
            
            embed.add_field(
                name="👥 Role Blacklists",
                value='\n'.join(role_text),
                inline=False
            )
        
        # User blacklists
        user_blacklist = blacklist.get('users', {})
        if user_blacklist:
            user_text = []
            for user_id, commands in user_blacklist.items():
                try:
                    user = await self.bot.fetch_user(int(user_id))
                    user_name = user.mention
                except:
                    user_name = f"<@{user_id}> (Unknown)"
                user_text.append(f"{user_name}: `{', '.join(commands)}`")
            
            embed.add_field(
                name="👤 User Blacklists",
                value='\n'.join(user_text),
                inline=False
            )
        
        await ctx.send(embed=embed)

    @blacklist_settings.command(name='channel')
    @commands.has_permissions(manage_guild=True)
    async def blacklist_channel(self, ctx, channel: nextcord.TextChannel, *, command: str):
        """Blacklist a command in a specific channel"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        channel_blacklist = blacklist.get('channels', {})
        
        channel_id = str(channel.id)
        if channel_id not in channel_blacklist:
            channel_blacklist[channel_id] = []
        
        if command not in channel_blacklist[channel_id]:
            channel_blacklist[channel_id].append(command)
            blacklist['channels'] = channel_blacklist
            await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
            
            embed = nextcord.Embed(
                title="❌ Command Blacklisted",
                description=f"Command `{command}` is now blacklisted in {channel.mention}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `{command}` is already blacklisted in {channel.mention}")

    @blacklist_settings.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def blacklist_role(self, ctx, role: nextcord.Role, *, command: str):
        """Blacklist a command for a specific role"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        role_blacklist = blacklist.get('roles', {})
        
        role_id = str(role.id)
        if role_id not in role_blacklist:
            role_blacklist[role_id] = []
        
        if command not in role_blacklist[role_id]:
            role_blacklist[role_id].append(command)
            blacklist['roles'] = role_blacklist
            await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
            
            embed = nextcord.Embed(
                title="❌ Command Blacklisted",
                description=f"Command `{command}` is now blacklisted for {role.mention}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `{command}` is already blacklisted for {role.mention}")

    @blacklist_settings.command(name='user')
    @commands.has_permissions(manage_guild=True)
    async def blacklist_user(self, ctx, user: nextcord.Member, *, command: str):
        """Blacklist a command for a specific user"""
        settings = await db.get_guild_settings(ctx.guild.id)
        blacklist = settings.get('command_blacklist', {})
        user_blacklist = blacklist.get('users', {})
        
        user_id = str(user.id)
        if user_id not in user_blacklist:
            user_blacklist[user_id] = []
        
        if command not in user_blacklist[user_id]:
            user_blacklist[user_id].append(command)
            blacklist['users'] = user_blacklist
            await db.update_guild_settings(ctx.guild.id, {'command_blacklist': blacklist})
            
            embed = nextcord.Embed(
                title="❌ Command Blacklisted",
                description=f"Command `{command}` is now blacklisted for {user.mention}",
                color=0xe74c3c
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Command `{command}` is already blacklisted for {user.mention}")

    # Ignore Management
    @general_settings.group(name='ignore', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def ignore_settings(self, ctx):
        """Manage ignored users/roles"""
        embed = nextcord.Embed(
            title="🚫 Ignore Management",
            description="Configure which users/roles the bot ignores completely",
            color=0x95a5a6
        )
        embed.add_field(
            name="Commands",
            value=(
                f"`{ctx.prefix}ignore add role <role>` - Ignore all commands from role\n"
                f"`{ctx.prefix}ignore add user <user>` - Ignore all commands from user\n"
                f"`{ctx.prefix}ignore remove role <role>` - Stop ignoring role\n"
                f"`{ctx.prefix}ignore remove user <user>` - Stop ignoring user\n"
                f"`{ctx.prefix}ignore view` - View currently ignored users/roles"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @ignore_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_ignored(self, ctx):
        """View currently ignored users/roles"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        
        ignored_roles = ignored.get('roles', [])
        ignored_users = ignored.get('users', [])
        
        embed = nextcord.Embed(
            title="🚫 Currently Ignored",
            color=0x95a5a6
        )
        
        role_list = []
        for role_id in ignored_roles:
            role = ctx.guild.get_role(role_id)
            if role:
                role_list.append(f"<@&{role_id}> ({role.name})")
            else:
                role_list.append(f"<@&{role_id}> (Deleted Role)")
        
        user_list = []
        for user_id in ignored_users:
            try:
                user = await self.bot.fetch_user(user_id)
                user_list.append(f"<@{user_id}> ({user.name})")
            except:
                user_list.append(f"<@{user_id}> (Unknown User)")
        
        embed.add_field(
            name="👥 Ignored Roles",
            value='\n'.join(role_list) if role_list else "None",
            inline=False
        )
        
        embed.add_field(
            name="👤 Ignored Users",
            value='\n'.join(user_list) if user_list else "None",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @ignore_settings.group(name='add', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def add_ignore(self, ctx):
        """Add user/role to ignore list"""
        await ctx.send("❌ Please specify `role` or `user`. Example: `ignore add role @SpamRole`")

    @add_ignore.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def add_ignore_role(self, ctx, role: nextcord.Role):
        """Add role to ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        ignored_roles = ignored.get('roles', [])
        
        if role.id in ignored_roles:
            return await ctx.send(f"❌ Role {role.mention} is already ignored!")
        
        ignored_roles.append(role.id)
        ignored['roles'] = ignored_roles
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ Role Ignored",
            description=f"Bot will now ignore all commands from {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @add_ignore.command(name='user')
    @commands.has_permissions(manage_guild=True)
    async def add_ignore_user(self, ctx, user: nextcord.Member):
        """Add user to ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        ignored_users = ignored.get('users', [])
        
        if user.id in ignored_users:
            return await ctx.send(f"❌ User {user.mention} is already ignored!")
        
        ignored_users.append(user.id)
        ignored['users'] = ignored_users
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ User Ignored",
            description=f"Bot will now ignore all commands from {user.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @ignore_settings.group(name='remove', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def remove_ignore(self, ctx):
        """Remove user/role from ignore list"""
        await ctx.send("❌ Please specify `role` or `user`. Example: `ignore remove role @SpamRole`")

    @remove_ignore.command(name='role')
    @commands.has_permissions(manage_guild=True)
    async def remove_ignore_role(self, ctx, role: nextcord.Role):
        """Remove role from ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        ignored_roles = ignored.get('roles', [])
        
        if role.id not in ignored_roles:
            return await ctx.send(f"❌ Role {role.mention} is not ignored!")
        
        ignored_roles.remove(role.id)
        ignored['roles'] = ignored_roles
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ Role Un-ignored",
            description=f"Bot will now respond to commands from {role.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @remove_ignore.command(name='user')
    @commands.has_permissions(manage_guild=True)
    async def remove_ignore_user(self, ctx, user: nextcord.Member):
        """Remove user from ignore list"""
        settings = await db.get_guild_settings(ctx.guild.id)
        ignored = settings.get('ignored', {})
        ignored_users = ignored.get('users', [])
        
        if user.id not in ignored_users:
            return await ctx.send(f"❌ User {user.mention} is not ignored!")
        
        ignored_users.remove(user.id)
        ignored['users'] = ignored_users
        await db.update_guild_settings(ctx.guild.id, {'ignored': ignored})
        
        embed = nextcord.Embed(
            title="✅ User Un-ignored",
            description=f"Bot will now respond to commands from {user.mention}",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    def can_manage_settings(self, user: nextcord.Member, guild_settings: dict) -> bool:
        """Check if user can manage settings"""
        # Owner and manage_guild permission always can
        if user.guild_permissions.manage_guild or user.guild_permissions.administrator:
            return True
        
        # Check custom permissions
        perms = guild_settings.get('general_permissions', {})
        
        # Check if user is specifically allowed
        if user.id in perms.get('manage_users', []):
            return True
        
        # Check if any of user's roles are allowed
        user_role_ids = [role.id for role in user.roles]
        allowed_roles = perms.get('manage_roles', [])
        if any(role_id in allowed_roles for role_id in user_role_ids):
            return True
        
        return False

    async def is_command_allowed(self, ctx, command_name: str) -> bool:
        """Check if a command is allowed based on whitelist/blacklist settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        
        # Check if user/role is ignored
        ignored = settings.get('ignored', {})
        if ctx.author.id in ignored.get('users', []):
            return False
        
        user_role_ids = [role.id for role in ctx.author.roles]
        if any(role_id in ignored.get('roles', []) for role_id in user_role_ids):
            return False
        
        # Check blacklists first (they take precedence)
        blacklist = settings.get('command_blacklist', {})
        
        # User blacklist
        user_blacklist = blacklist.get('users', {}).get(str(ctx.author.id), [])
        if command_name in user_blacklist:
            return False
        
        # Role blacklist
        role_blacklist = blacklist.get('roles', {})
        for role_id in user_role_ids:
            if command_name in role_blacklist.get(str(role_id), []):
                return False
        
        # Channel blacklist
        channel_blacklist = blacklist.get('channels', {}).get(str(ctx.channel.id), [])
        if command_name in channel_blacklist:
            return False
        
        # Check whitelists (if any exist, command must be whitelisted)
        whitelist = settings.get('command_whitelist', {})
        
        # If no whitelists exist, allow command
        if not any(whitelist.values()):
            return True
        
        # Check channel whitelist
        channel_whitelist = whitelist.get('channels', {}).get(str(ctx.channel.id), [])
        if command_name in channel_whitelist:
            return True
        
        # Check role whitelist
        role_whitelist = whitelist.get('roles', {})
        for role_id in user_role_ids:
            if command_name in role_whitelist.get(str(role_id), []):
                return True
        
        # If whitelists exist but command not found, deny
        return False

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "general settings")

async def setup(bot):
    bot.add_cog(GeneralSettings(bot))
