# Welcome Settings
# Handles welcome messages, auto-roles, and new member configuration

import nextcord
from nextcord.ext import commands
from typing import Optional, List, Dict, Union
import json
import re
import asyncio
from datetime import datetime, timedelta
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('WelcomeSettings')

# Comprehensive list of supported variables for welcome messages
WELCOME_VARIABLES = {
    # User variables
    '{user}': 'Mentions the user (@User)',
    '{user.name}': 'User\'s display name',
    '{user.username}': 'User\'s username',
    '{user.discriminator}': 'User\'s discriminator (#1234)',
    '{user.id}': 'User\'s ID',
    '{user.mention}': 'Mentions the user (@User)',
    '{user.avatar}': 'User\'s avatar URL',
    '{user.created_at}': 'When the user account was created',
    '{user.created_at.date}': 'Account creation date only',
    '{user.created_at.time}': 'Account creation time only',
    '{user.age}': 'Account age (e.g., "5 days old")',
    
    # Server variables
    '{server}': 'Server name',
    '{server.name}': 'Server name',
    '{server.id}': 'Server ID',
    '{server.member_count}': 'Current member count',
    '{server.members}': 'Current member count',
    '{server.owner}': 'Server owner mention',
    '{server.owner.name}': 'Server owner name',
    '{server.created_at}': 'When server was created',
    '{server.created_at.date}': 'Server creation date only',
    '{server.icon}': 'Server icon URL',
    '{server.boost_level}': 'Server boost level',
    '{server.boost_count}': 'Number of boosts',
    
    # Member-specific variables
    '{member.number}': 'What number member this user is (e.g., "1,234th")',
    '{member.position}': 'Member position number',
    '{member.joined_at}': 'When member joined the server',
    '{member.joined_at.date}': 'Join date only',
    '{member.joined_at.time}': 'Join time only',
    
    # Count variables
    '{count}': 'Current member count',
    '{count.ordinal}': 'Member count with ordinal (e.g., "1,234th")',
    '{count.bots}': 'Number of bots in server',
    '{count.humans}': 'Number of humans in server',
    '{count.online}': 'Number of online members',
    
    # Time variables
    '{time}': 'Current time',
    '{time.date}': 'Current date only',
    '{time.time}': 'Current time only',
    '{time.timestamp}': 'Unix timestamp',
    '{date}': 'Current date',
    '{timestamp}': 'Discord timestamp',
    
    # Random variables
    '{random.number}': 'Random number 1-100',
    '{random.emoji}': 'Random emoji from server',
    '{random.color}': 'Random color hex code',
    
    # Custom variables (can be set per server)
    '{custom.welcome_role}': 'Custom welcome role mention',
    '{custom.rules_channel}': 'Custom rules channel mention',
    '{custom.general_channel}': 'Custom general channel mention',
}

class WelcomeSettings(commands.Cog, ErrorHandler):
    """Welcome configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='welcome', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def welcome_settings(self, ctx):
        """Welcome settings management"""
        embed = nextcord.Embed(
            title="👋 Welcome Settings",
            description=(
                "Configure welcome messages and new member settings\n\n"
                "**Available Commands:**\n"
                "`welcome toggle` - Enable/disable welcome messages\n"
                "`welcome channels` - Manage welcome channels\n"
                "`welcome message` - Configure welcome messages\n"
                "`welcome autoroles` - Manage auto-roles\n"
                "`welcome dm` - Configure DM on join\n"
                "`welcome variables` - View available variables\n"
                "`welcome view` - View current settings"
            ),
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @welcome_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_welcome_settings(self, ctx):
        """View current welcome settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        
        embed = nextcord.Embed(
            title="👋 Welcome Settings Overview",
            color=0x2ecc71
        )
        
        # General settings
        general = welcome_settings.get('general', {})
        embed.add_field(
            name="⚙️ General Settings",
            value=(
                f"**Welcome Enabled:** {'✅' if general.get('enabled', False) else '❌'}\n"
                f"**Welcome Channels:** {len(general.get('channels', []))}\n"
                f"**DM on Join:** {'✅' if general.get('dm_enabled', False) else '❌'}\n"
                f"**Auto-roles:** {len(general.get('auto_roles', []))}"
            ),
            inline=False
        )
        
        # Welcome channels
        channels = general.get('channels', [])
        if channels:
            channel_list = []
            for channel_data in channels:
                channel = ctx.guild.get_channel(channel_data.get('id'))
                channel_name = channel.mention if channel else f"#{channel_data.get('id')} (Deleted)"
                channel_type = channel_data.get('type', 'normal')
                ping_delete = f" (Delete after {channel_data.get('ping_delete_after', 10)}s)" if channel_type == 'ping' else ""
                channel_list.append(f"{channel_name} - {channel_type.title()}{ping_delete}")
            
            embed.add_field(
                name="📺 Welcome Channels",
                value='\n'.join(channel_list[:5]),  # Show first 5
                inline=False
            )
        
        # Auto-roles
        auto_roles = general.get('auto_roles', [])
        if auto_roles:
            role_list = []
            for role_data in auto_roles:
                role = ctx.guild.get_role(role_data.get('id'))
                role_name = role.mention if role else f"<@&{role_data.get('id')}> (Deleted)"
                bot_setting = " (Bots: ✅)" if role_data.get('include_bots', False) else " (Bots: ❌)"
                role_list.append(f"{role_name}{bot_setting}")
            
            embed.add_field(
                name="🎭 Auto-roles",
                value='\n'.join(role_list[:3]),  # Show first 3
                inline=False
            )
        
        await ctx.send(embed=embed)

    @welcome_settings.command(name='toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle_welcome(self, ctx, enabled: bool = None):
        """Toggle welcome messages on/off"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        
        if enabled is None:
            current_status = general.get('enabled', False)
            embed = nextcord.Embed(
                title="👋 Welcome Status",
                color=0x2ecc71
            )
            embed.add_field(
                name="Current Status",
                value=f"Welcome Messages: {'✅ Enabled' if current_status else '❌ Disabled'}",
                inline=False
            )
            embed.add_field(
                name="Usage",
                value="`welcome toggle true` - Enable welcome messages\n"
                      "`welcome toggle false` - Disable welcome messages",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        general['enabled'] = enabled
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        status = "enabled" if enabled else "disabled"
        embed = nextcord.Embed(
            title=f"✅ Welcome Messages {status.title()}",
            description=f"Welcome messages have been {status}!",
            color=0x2ecc71 if enabled else 0x95a5a6
        )
        
        if enabled and not general.get('channels'):
            embed.add_field(
                name="⚠️ Setup Required",
                value="No welcome channels configured! Use `welcome channels add` to set them up.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    # Channel Management
    @welcome_settings.group(name='channels', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def channel_settings(self, ctx):
        """Manage welcome channels"""
        embed = nextcord.Embed(
            title="📺 Welcome Channel Management",
            description="Configure up to 3 welcome channels with different types",
            color=0x2ecc71
        )
        embed.add_field(
            name="Channel Types",
            value=(
                "**Normal:** Standard welcome message\n"
                "**Ping:** Pings user and deletes after timeout\n"
                "**Silent:** Welcome without pinging user"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "`channels add <channel> [type]` - Add welcome channel\n"
                "`channels remove <channel>` - Remove welcome channel\n"
                "`channels list` - List current channels\n"
                "`channels configure <channel>` - Configure channel settings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_welcome_channel(self, ctx, channel: nextcord.TextChannel, channel_type: str = 'normal'):
        """Add a welcome channel"""
        valid_types = ['normal', 'ping', 'silent']
        if channel_type.lower() not in valid_types:
            return await ctx.send(f"❌ Invalid channel type! Valid types: {', '.join(valid_types)}")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        channels = general.get('channels', [])
        
        # Check if channel already added
        if any(ch['id'] == channel.id for ch in channels):
            return await ctx.send(f"❌ {channel.mention} is already a welcome channel!")
        
        # Check limit
        if len(channels) >= 3:
            return await ctx.send("❌ Maximum of 3 welcome channels allowed!")
        
        # Add channel
        channel_data = {
            'id': channel.id,
            'type': channel_type.lower(),
            'message': '',
            'ping_delete_after': 10 if channel_type.lower() == 'ping' else 0
        }
        
        channels.append(channel_data)
        general['channels'] = channels
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Welcome Channel Added",
            description=f"Added {channel.mention} as a {channel_type} welcome channel!",
            color=0x2ecc71
        )
        embed.add_field(
            name="Next Steps",
            value=f"• Configure message: `welcome message set #{channel.name}`\n"
                  f"• View variables: `welcome variables`",
            inline=False
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_welcome_channel(self, ctx, channel: nextcord.TextChannel):
        """Remove a welcome channel"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        channels = general.get('channels', [])
        
        # Find and remove channel
        channel_to_remove = None
        for ch in channels:
            if ch['id'] == channel.id:
                channel_to_remove = ch
                break
        
        if not channel_to_remove:
            return await ctx.send(f"❌ {channel.mention} is not a welcome channel!")
        
        channels.remove(channel_to_remove)
        general['channels'] = channels
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Welcome Channel Removed",
            description=f"Removed {channel.mention} from welcome channels!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='list')
    @commands.has_permissions(manage_guild=True)
    async def list_welcome_channels(self, ctx):
        """List current welcome channels"""
        settings = await db.get_guild_settings(ctx.guild.id)
        channels = settings.get('welcome', {}).get('general', {}).get('channels', [])
        
        embed = nextcord.Embed(
            title="📺 Welcome Channels",
            color=0x2ecc71
        )
        
        if not channels:
            embed.description = "No welcome channels configured.\nUse `welcome channels add` to add some!"
            return await ctx.send(embed=embed)
        
        for i, channel_data in enumerate(channels, 1):
            channel = ctx.guild.get_channel(channel_data['id'])
            channel_name = channel.mention if channel else f"#{channel_data['id']} (Deleted)"
            
            details = [f"Type: {channel_data['type'].title()}"]
            if channel_data['type'] == 'ping':
                details.append(f"Delete after: {channel_data.get('ping_delete_after', 10)}s")
            if channel_data.get('message'):
                details.append("✅ Message configured")
            else:
                details.append("❌ No message set")
            
            embed.add_field(
                name=f"{i}. {channel_name}",
                value='\n'.join(details),
                inline=True
            )
        
        await ctx.send(embed=embed)

    # Message Management
    @welcome_settings.group(name='message', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def message_settings(self, ctx):
        """Configure welcome messages"""
        embed = nextcord.Embed(
            title="💬 Welcome Message Configuration",
            description="Configure custom welcome messages for each channel",
            color=0x2ecc71
        )
        embed.add_field(
            name="Commands",
            value=(
                "`message set <channel>` - Set welcome message for channel\n"
                "`message view <channel>` - View current message\n"
                "`message test <channel>` - Test welcome message\n"
                "`message embed <channel>` - Configure embed message\n"
                "`message variables` - View available variables"
            ),
            inline=False
        )
        embed.add_field(
            name="💡 Tips",
            value=(
                "• Use `{user}` to mention the new member\n"
                "• Use `{server}` for server name\n"
                "• Use `{count}` for member count\n"
                "• Type `welcome variables` for full list"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @message_settings.command(name='set')
    @commands.has_permissions(manage_guild=True)
    async def set_welcome_message(self, ctx, channel: nextcord.TextChannel):
        """Set welcome message for a channel (Interactive)"""
        settings = await db.get_guild_settings(ctx.guild.id)
        channels = settings.get('welcome', {}).get('general', {}).get('channels', [])
        
        # Check if channel is a welcome channel
        channel_data = None
        for ch in channels:
            if ch['id'] == channel.id:
                channel_data = ch
                break
        
        if not channel_data:
            return await ctx.send(f"❌ {channel.mention} is not a welcome channel! Add it first with `welcome channels add`")
        
        embed = nextcord.Embed(
            title="💬 Set Welcome Message",
            description=f"Please enter the welcome message for {channel.mention}",
            color=0x2ecc71
        )
        embed.add_field(
            name="📝 Format Options",
            value=(
                "**Text Message:** Just type your message\n"
                "**Embed Message:** Start with `{embed}` and use embed syntax\n"
                "**Variables:** Use `{user}`, `{server}`, `{count}`, etc."
            ),
            inline=False
        )
        embed.add_field(
            name="Example",
            value="Welcome {user} to {server}! You're our {count.ordinal} member! 🎉",
            inline=False
        )
        embed.set_footer(text="Type 'cancel' to cancel or 'variables' to see all variables")
        
        await ctx.send(embed=embed)
        
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel
        
        try:
            message_response = await self.bot.wait_for('message', check=check, timeout=300)
            
            if message_response.content.lower() == 'cancel':
                return await ctx.send("❌ Welcome message setup cancelled.")
            
            if message_response.content.lower() == 'variables':
                return await self.show_variables(ctx)
            
            # Save the message
            channel_data['message'] = message_response.content
            
            # Update database
            welcome_settings = settings.get('welcome', {})
            general = welcome_settings.get('general', {})
            general['channels'] = channels
            welcome_settings['general'] = general
            await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
            
            embed = nextcord.Embed(
                title="✅ Welcome Message Set",
                description=f"Welcome message for {channel.mention} has been configured!",
                color=0x2ecc71
            )
            embed.add_field(
                name="Message Preview",
                value=message_response.content[:500] + ("..." if len(message_response.content) > 500 else ""),
                inline=False
            )
            embed.add_field(
                name="Test it!",
                value=f"Use `welcome message test #{channel.name}` to test the message",
                inline=False
            )
            await ctx.send(embed=embed)
            
        except asyncio.TimeoutError:
            await ctx.send("❌ Message setup timed out. Please try again.")

    @message_settings.command(name='test')
    @commands.has_permissions(manage_guild=True)
    async def test_welcome_message(self, ctx, channel: nextcord.TextChannel):
        """Test a welcome message"""
        settings = await db.get_guild_settings(ctx.guild.id)
        channels = settings.get('welcome', {}).get('general', {}).get('channels', [])
        
        # Find channel data
        channel_data = None
        for ch in channels:
            if ch['id'] == channel.id:
                channel_data = ch
                break
        
        if not channel_data:
            return await ctx.send(f"❌ {channel.mention} is not a welcome channel!")
        
        message = channel_data.get('message')
        if not message:
            return await ctx.send(f"❌ No welcome message configured for {channel.mention}!")
        
        # Parse the message with the command author as test user
        parsed_message = await self.parse_welcome_message(message, ctx.author, ctx.guild)
        
        embed = nextcord.Embed(
            title="🧪 Welcome Message Test",
            description=f"Here's how the welcome message will look in {channel.mention}:",
            color=0x3498db
        )
        
        if message.startswith('{embed}'):
            # Handle embed message
            try:
                embed_data = self.parse_embed_message(parsed_message)
                test_embed = nextcord.Embed.from_dict(embed_data)
                await ctx.send(embed=embed, view=None)
                await ctx.send(embed=test_embed)
            except Exception as e:
                embed.add_field(
                    name="❌ Embed Error",
                    value=f"There's an error in your embed syntax: {e}",
                    inline=False
                )
                await ctx.send(embed=embed)
        else:
            # Handle text message
            embed.add_field(
                name="📝 Message Preview",
                value=parsed_message,
                inline=False
            )
            await ctx.send(embed=embed)

    @welcome_settings.command(name='variables')
    @commands.has_permissions(manage_guild=True)
    async def show_variables(self, ctx):
        """Show all available welcome message variables"""
        embed = nextcord.Embed(
            title="📋 Welcome Message Variables",
            description="Complete list of variables you can use in welcome messages",
            color=0x3498db
        )
        
        # Group variables by category
        categories = {
            "👤 User Variables": [
                ('{user}', 'Mentions the user'),
                ('{user.name}', 'User\'s display name'),
                ('{user.username}', 'User\'s username'),
                ('{user.id}', 'User\'s ID'),
                ('{user.created_at}', 'Account creation date'),
                ('{user.age}', 'Account age'),
            ],
            "🏰 Server Variables": [
                ('{server}', 'Server name'),
                ('{server.member_count}', 'Member count'),
                ('{server.owner}', 'Server owner mention'),
                ('{server.boost_level}', 'Server boost level'),
            ],
            "📊 Count Variables": [
                ('{count}', 'Current member count'),
                ('{count.ordinal}', 'Member count with ordinal (1st, 2nd, etc.)'),
                ('{count.bots}', 'Number of bots'),
                ('{count.humans}', 'Number of humans'),
            ],
            "⏰ Time Variables": [
                ('{time}', 'Current time'),
                ('{date}', 'Current date'),
                ('{timestamp}', 'Discord timestamp'),
            ],
            "🎲 Random Variables": [
                ('{random.number}', 'Random number 1-100'),
                ('{random.emoji}', 'Random server emoji'),
                ('{random.color}', 'Random color hex'),
            ]
        }
        
        for category, variables in categories.items():
            var_list = '\n'.join([f"`{var}` - {desc}" for var, desc in variables])
            embed.add_field(
                name=category,
                value=var_list,
                inline=False
            )
        
        embed.add_field(
            name="💡 Example Usage",
            value=(
                "Welcome {user} to **{server}**! 🎉\n"
                "You're our {count.ordinal} member!\n"
                "Your account is {user.age} old."
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Auto-roles Management
    @welcome_settings.group(name='autoroles', aliases=['autorole'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def autorole_settings(self, ctx):
        """Manage auto-roles for new members"""
        embed = nextcord.Embed(
            title="🎭 Auto-role Management",
            description="Configure roles that are automatically given to new members",
            color=0x2ecc71
        )
        embed.add_field(
            name="Commands",
            value=(
                "`autoroles add <role>` - Add an auto-role\n"
                "`autoroles remove <role>` - Remove an auto-role\n"
                "`autoroles list` - List current auto-roles\n"
                "`autoroles bots <role> <true/false>` - Toggle bots for role"
            ),
            inline=False
        )
        embed.add_field(
            name="📝 Notes",
            value=(
                "• Maximum 3 auto-roles per server\n"
                "• Bot roles are disabled by default\n"
                "• Roles must be below bot's highest role"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @autorole_settings.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_autorole(self, ctx, role: nextcord.Role, include_bots: bool = False):
        """Add an auto-role for new members"""
        # Check bot permissions
        if role >= ctx.guild.me.top_role:
            return await ctx.send("❌ I cannot assign this role! The role must be below my highest role.")
        
        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("❌ I don't have permission to manage roles!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        auto_roles = general.get('auto_roles', [])
        
        # Check if role already added
        if any(ar['id'] == role.id for ar in auto_roles):
            return await ctx.send(f"❌ {role.mention} is already an auto-role!")
        
        # Check limit
        if len(auto_roles) >= 3:
            return await ctx.send("❌ Maximum of 3 auto-roles allowed!")
        
        # Add role
        role_data = {
            'id': role.id,
            'include_bots': include_bots
        }
        
        auto_roles.append(role_data)
        general['auto_roles'] = auto_roles
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Auto-role Added",
            description=f"Added {role.mention} as an auto-role!",
            color=0x2ecc71
        )
        embed.add_field(
            name="Settings",
            value=f"**Include Bots:** {'✅' if include_bots else '❌'}",
            inline=False
        )
        await ctx.send(embed=embed)

    @autorole_settings.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_autorole(self, ctx, role: nextcord.Role):
        """Remove an auto-role"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        auto_roles = general.get('auto_roles', [])
        
        # Find and remove role
        role_to_remove = None
        for ar in auto_roles:
            if ar['id'] == role.id:
                role_to_remove = ar
                break
        
        if not role_to_remove:
            return await ctx.send(f"❌ {role.mention} is not an auto-role!")
        
        auto_roles.remove(role_to_remove)
        general['auto_roles'] = auto_roles
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        embed = nextcord.Embed(
            title="✅ Auto-role Removed",
            description=f"Removed {role.mention} from auto-roles!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @autorole_settings.command(name='list')
    @commands.has_permissions(manage_guild=True)
    async def list_autoroles(self, ctx):
        """List current auto-roles"""
        settings = await db.get_guild_settings(ctx.guild.id)
        auto_roles = settings.get('welcome', {}).get('general', {}).get('auto_roles', [])
        
        embed = nextcord.Embed(
            title="🎭 Auto-roles",
            color=0x2ecc71
        )
        
        if not auto_roles:
            embed.description = "No auto-roles configured.\nUse `welcome autoroles add` to add some!"
            return await ctx.send(embed=embed)
        
        for i, role_data in enumerate(auto_roles, 1):
            role = ctx.guild.get_role(role_data['id'])
            role_name = role.mention if role else f"<@&{role_data['id']}> (Deleted)"
            
            embed.add_field(
                name=f"{i}. {role_name}",
                value=f"**Include Bots:** {'✅' if role_data.get('include_bots', False) else '❌'}",
                inline=True
            )
        
        await ctx.send(embed=embed)

    # DM Settings
    @welcome_settings.group(name='dm', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def dm_settings(self, ctx):
        """Configure DM on join settings"""
        embed = nextcord.Embed(
            title="📬 DM on Join Settings",
            description="Configure private messages sent to new members",
            color=0x2ecc71
        )
        embed.add_field(
            name="Commands",
            value=(
                "`dm toggle` - Enable/disable DM on join\n"
                "`dm message` - Set DM message\n"
                "`dm test` - Test DM message\n"
                "`dm view` - View current DM settings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @dm_settings.command(name='toggle')
    @commands.has_permissions(manage_guild=True)
    async def toggle_dm(self, ctx, enabled: bool = None):
        """Toggle DM on join"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        
        if enabled is None:
            current_status = general.get('dm_enabled', False)
            embed = nextcord.Embed(
                title="📬 DM on Join Status",
                color=0x2ecc71
            )
            embed.add_field(
                name="Current Status",
                value=f"DM on Join: {'✅ Enabled' if current_status else '❌ Disabled'}",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        general['dm_enabled'] = enabled
        welcome_settings['general'] = general
        await db.update_guild_settings(ctx.guild.id, {'welcome': welcome_settings})
        
        status = "enabled" if enabled else "disabled"
        embed = nextcord.Embed(
            title=f"✅ DM on Join {status.title()}",
            description=f"DM on join has been {status}!",
            color=0x2ecc71 if enabled else 0x95a5a6
        )
        
        if enabled and not general.get('dm_message'):
            embed.add_field(
                name="⚠️ Setup Required",
                value="No DM message configured! Use `welcome dm message` to set it up.",
                inline=False
            )
        
        await ctx.send(embed=embed)

    async def parse_welcome_message(self, message: str, member: nextcord.Member, guild: nextcord.Guild) -> str:
        """Parse welcome message variables"""
        # Create replacements dictionary
        replacements = {
            # User variables
            '{user}': member.mention,
            '{user.name}': member.display_name,
            '{user.username}': member.name,
            '{user.discriminator}': member.discriminator,
            '{user.id}': str(member.id),
            '{user.mention}': member.mention,
            '{user.avatar}': str(member.display_avatar.url),
            '{user.created_at}': member.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            '{user.created_at.date}': member.created_at.strftime('%Y-%m-%d'),
            '{user.created_at.time}': member.created_at.strftime('%H:%M:%S UTC'),
            '{user.age}': self._get_account_age(member.created_at),
            
            # Server variables
            '{server}': guild.name,
            '{server.name}': guild.name,
            '{server.id}': str(guild.id),
            '{server.member_count}': str(guild.member_count),
            '{server.members}': str(guild.member_count),
            '{server.owner}': guild.owner.mention if guild.owner else 'Unknown',
            '{server.owner.name}': guild.owner.display_name if guild.owner else 'Unknown',
            '{server.created_at}': guild.created_at.strftime('%Y-%m-%d %H:%M:%S UTC'),
            '{server.created_at.date}': guild.created_at.strftime('%Y-%m-%d'),
            '{server.icon}': str(guild.icon.url) if guild.icon else 'No icon',
            '{server.boost_level}': str(guild.premium_tier),
            '{server.boost_count}': str(guild.premium_subscription_count or 0),
            
            # Member-specific variables
            '{member.number}': self._get_ordinal(guild.member_count),
            '{member.position}': str(guild.member_count),
            '{member.joined_at}': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            '{member.joined_at.date}': datetime.utcnow().strftime('%Y-%m-%d'),
            '{member.joined_at.time}': datetime.utcnow().strftime('%H:%M:%S UTC'),
            
            # Count variables
            '{count}': str(guild.member_count),
            '{count.ordinal}': self._get_ordinal(guild.member_count),
            '{count.bots}': str(sum(1 for m in guild.members if m.bot)),
            '{count.humans}': str(sum(1 for m in guild.members if not m.bot)),
            '{count.online}': str(sum(1 for m in guild.members if m.status != nextcord.Status.offline)),
            
            # Time variables
            '{time}': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC'),
            '{time.date}': datetime.utcnow().strftime('%Y-%m-%d'),
            '{time.time}': datetime.utcnow().strftime('%H:%M:%S UTC'),
            '{time.timestamp}': str(int(datetime.utcnow().timestamp())),
            '{date}': datetime.utcnow().strftime('%Y-%m-%d'),
            '{timestamp}': f"<t:{int(datetime.utcnow().timestamp())}:F>",
            
            # Random variables
            '{random.number}': str(random.randint(1, 100)),
            '{random.emoji}': str(random.choice(guild.emojis)) if guild.emojis else '😊',
            '{random.color}': f"#{random.randint(0, 0xFFFFFF):06x}",
        }
        
        # Apply replacements
        parsed = message
        for variable, replacement in replacements.items():
            parsed = parsed.replace(variable, replacement)
        
        return parsed

    def _get_account_age(self, created_at: datetime) -> str:
        """Get human-readable account age"""
        age = datetime.utcnow() - created_at
        
        if age.days >= 365:
            years = age.days // 365
            return f"{years} year{'s' if years != 1 else ''} old"
        elif age.days >= 30:
            months = age.days // 30
            return f"{months} month{'s' if months != 1 else ''} old"
        elif age.days >= 1:
            return f"{age.days} day{'s' if age.days != 1 else ''} old"
        else:
            hours = age.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} old"

    def _get_ordinal(self, number: int) -> str:
        """Get ordinal number (1st, 2nd, 3rd, etc.)"""
        if 10 <= number % 100 <= 20:
            suffix = 'th'
        else:
            suffix = {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th')
        return f"{number:,}{suffix}"

    def parse_embed_message(self, message: str) -> dict:
        """Parse embed message syntax"""
        # This would implement the embed parsing logic
        # For now, return a basic embed structure
        return {
            "title": "Welcome!",
            "description": message.replace('{embed}', '').strip(),
            "color": 0x2ecc71
        }

    async def send_welcome_message(self, member: nextcord.Member):
        """Send welcome message when member joins"""
        settings = await db.get_guild_settings(member.guild.id)
        welcome_settings = settings.get('welcome', {})
        general = welcome_settings.get('general', {})
        
        if not general.get('enabled', False):
            return
        
        # Send welcome messages to channels
        channels = general.get('channels', [])
        for channel_data in channels:
            channel = member.guild.get_channel(channel_data['id'])
            if not channel:
                continue
            
            message = channel_data.get('message')
            if not message:
                continue
            
            try:
                parsed_message = await self.parse_welcome_message(message, member, member.guild)
                
                if channel_data['type'] == 'ping':
                    # Send ping message and delete after timeout
                    msg = await channel.send(parsed_message)
                    delete_after = channel_data.get('ping_delete_after', 10)
                    if delete_after > 0:
                        await asyncio.sleep(delete_after)
                        try:
                            await msg.delete()
                        except nextcord.HTTPException:
                            pass
                elif channel_data['type'] == 'silent':
                    # Send without pinging
                    silent_message = parsed_message.replace(member.mention, f"**{member.display_name}**")
                    await channel.send(silent_message)
                else:
                    # Normal welcome message
                    await channel.send(parsed_message)
                    
            except nextcord.HTTPException as e:
                logger.error(f"Failed to send welcome message: {e}")
        
        # Apply auto-roles
        auto_roles = general.get('auto_roles', [])
        for role_data in auto_roles:
            if member.bot and not role_data.get('include_bots', False):
                continue
            
            role = member.guild.get_role(role_data['id'])
            if role and role < member.guild.me.top_role:
                try:
                    await member.add_roles(role, reason="Auto-role on join")
                except nextcord.HTTPException as e:
                    logger.error(f"Failed to add auto-role {role.name}: {e}")
        
        # Send DM if enabled
        if general.get('dm_enabled', False) and general.get('dm_message'):
            try:
                dm_message = await self.parse_welcome_message(general['dm_message'], member, member.guild)
                await member.send(dm_message)
            except nextcord.HTTPException:
                pass  # User might have DMs disabled

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "welcome settings")

async def setup(bot):
    bot.add_cog(WelcomeSettings(bot))
