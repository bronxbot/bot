# Moderation Settings
# Handles auto-moderation, punishment settings, and moderation configuration

import nextcord
from nextcord.ext import commands
from typing import Optional, List, Dict, Union
import json
import asyncio
from utils.db import db
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('ModerationSettings')

class ModerationSettings(commands.Cog, ErrorHandler):
    """Moderation configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='moderation', aliases=['mod'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def moderation_settings(self, ctx):
        """Moderation settings management"""
        embed = nextcord.Embed(
            title="🛡️ Moderation Settings",
            description=(
                "Configure moderation and auto-mod settings for this server\n\n"
                "**Available Commands:**\n"
                "`moderation automod` - Configure auto-moderation settings\n"
                "`moderation punishment` - Configure punishment escalation\n"
                "`moderation view` - View current moderation settings\n"
                "`moderation reset` - Reset all moderation settings"
            ),
            color=0xe74c3c
        )
        await ctx.send(embed=embed)

    @moderation_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_moderation_settings(self, ctx):
        """View current moderation settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        mod_settings = settings.get('moderation', {})
        
        embed = nextcord.Embed(
            title="🛡️ Moderation Settings Overview",
            color=0xe74c3c
        )
        
        # Auto-mod settings
        automod = mod_settings.get('automod', {})
        enabled_features = []
        if automod.get('anti_spam', {}).get('enabled', False):
            enabled_features.append("Anti-Spam")
        if automod.get('anti_mention', {}).get('enabled', False):
            enabled_features.append("Anti-Mass Mention")
        if automod.get('anti_caps', {}).get('enabled', False):
            enabled_features.append("Anti-Caps")
        if automod.get('anti_links', {}).get('enabled', False):
            enabled_features.append("Anti-Links")
        if automod.get('auto_delete', {}).get('enabled', False):
            enabled_features.append("Auto-Delete")
        
        embed.add_field(
            name="🤖 Auto-Moderation",
            value=f"**Active Features:** {', '.join(enabled_features) if enabled_features else 'None'}\n"
                  f"Use `moderation automod` to configure",
            inline=False
        )
        
        # Punishment settings
        punishment = mod_settings.get('punishment', {})
        warn_limits = punishment.get('warn_limits', {})
        
        embed.add_field(
            name="⚖️ Punishment System",
            value=(
                f"**Warn Limits:**\n"
                f"• {warn_limits.get('mute', 3)} warns → Mute\n"
                f"• {warn_limits.get('kick', 5)} warns → Kick\n"
                f"• {warn_limits.get('ban', 7)} warns → Ban\n"
                f"Use `moderation punishment` to configure"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Auto-Moderation Settings
    @moderation_settings.group(name='automod', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def automod_settings(self, ctx):
        """Configure auto-moderation settings"""
        embed = nextcord.Embed(
            title="🤖 Auto-Moderation Settings",
            description="Configure automatic moderation features",
            color=0xe74c3c
        )
        embed.add_field(
            name="Available Features",
            value=(
                "`automod spam` - Anti-spam configuration\n"
                "`automod mentions` - Anti-mass mention settings\n"
                "`automod caps` - Anti-caps lock settings\n"
                "`automod links` - Link filtering settings\n"
                "`automod delete` - Auto-delete settings\n"
                "`automod view` - View current auto-mod settings"
            ),
            inline=False
        )
        embed.add_field(
            name="⚠️ Note",
            value="Auto-moderation features are currently in development.\nBasic spam detection is available, advanced features coming soon!",
            inline=False
        )
        await ctx.send(embed=embed)

    @automod_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_automod(self, ctx):
        """View current auto-moderation settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        automod = settings.get('moderation', {}).get('automod', {})
        
        embed = nextcord.Embed(
            title="🤖 Auto-Moderation Configuration",
            color=0xe74c3c
        )
        
        # Anti-spam settings
        spam_settings = automod.get('anti_spam', {})
        embed.add_field(
            name="📨 Anti-Spam",
            value=(
                f"**Enabled:** {'✅' if spam_settings.get('enabled', False) else '❌'}\n"
                f"**Max Messages:** {spam_settings.get('max_messages', 5)} per {spam_settings.get('time_window', 5)}s\n"
                f"**Action:** {spam_settings.get('action', 'warn').title()}\n"
                f"**Delete Messages:** {'✅' if spam_settings.get('delete_messages', True) else '❌'}"
            ),
            inline=True
        )
        
        # Anti-mention settings
        mention_settings = automod.get('anti_mention', {})
        embed.add_field(
            name="📢 Anti-Mass Mention",
            value=(
                f"**Enabled:** {'✅' if mention_settings.get('enabled', False) else '❌'}\n"
                f"**Max Mentions:** {mention_settings.get('max_mentions', 8)}\n"
                f"**Action:** {mention_settings.get('action', 'warn').title()}\n"
                f"**Delete Message:** {'✅' if mention_settings.get('delete_message', True) else '❌'}"
            ),
            inline=True
        )
        
        # Anti-caps settings
        caps_settings = automod.get('anti_caps', {})
        embed.add_field(
            name="🔠 Anti-Caps",
            value=(
                f"**Enabled:** {'✅' if caps_settings.get('enabled', False) else '❌'}\n"
                f"**Max Caps %:** {caps_settings.get('max_caps_percent', 70)}%\n"
                f"**Min Length:** {caps_settings.get('min_length', 10)} chars\n"
                f"**Action:** {caps_settings.get('action', 'warn').title()}"
            ),
            inline=True
        )
        
        # Link filtering settings
        link_settings = automod.get('anti_links', {})
        embed.add_field(
            name="🔗 Link Filtering",
            value=(
                f"**Enabled:** {'✅' if link_settings.get('enabled', False) else '❌'}\n"
                f"**Block Invites:** {'✅' if link_settings.get('block_invites', True) else '❌'}\n"
                f"**Block Suspicious:** {'✅' if link_settings.get('block_suspicious', False) else '❌'}\n"
                f"**Action:** {link_settings.get('action', 'delete').title()}"
            ),
            inline=True
        )
        
        # Auto-delete settings
        delete_settings = automod.get('auto_delete', {})
        embed.add_field(
            name="🗑️ Auto-Delete",
            value=(
                f"**Enabled:** {'✅' if delete_settings.get('enabled', False) else '❌'}\n"
                f"**Delete Images:** {'✅' if delete_settings.get('delete_images', False) else '❌'}\n"
                f"**Delete Links:** {'✅' if delete_settings.get('delete_links', False) else '❌'}\n"
                f"**Timeout:** {delete_settings.get('timeout', 0)}s"
            ),
            inline=True
        )
        
        await ctx.send(embed=embed)

    @automod_settings.command(name='spam')
    @commands.has_permissions(manage_guild=True)
    async def configure_antispam(self, ctx, enabled: bool = None, max_messages: int = None, time_window: int = None, action: str = None):
        """Configure anti-spam settings
        
        Usage: automod spam [enabled] [max_messages] [time_window] [action]
        Actions: warn, mute, kick, ban
        """
        settings = await db.get_guild_settings(ctx.guild.id)
        mod_settings = settings.get('moderation', {})
        automod = mod_settings.get('automod', {})
        spam_settings = automod.get('anti_spam', {})
        
        if all(param is None for param in [enabled, max_messages, time_window, action]):
            # Show current settings
            embed = nextcord.Embed(
                title="📨 Anti-Spam Configuration",
                color=0xe74c3c
            )
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**Enabled:** {'✅' if spam_settings.get('enabled', False) else '❌'}\n"
                    f"**Max Messages:** {spam_settings.get('max_messages', 5)}\n"
                    f"**Time Window:** {spam_settings.get('time_window', 5)} seconds\n"
                    f"**Action:** {spam_settings.get('action', 'warn').title()}\n"
                    f"**Delete Messages:** {'✅' if spam_settings.get('delete_messages', True) else '❌'}"
                ),
                inline=False
            )
            embed.add_field(
                name="Usage",
                value="`automod spam <enabled> [max_messages] [time_window] [action]`\n"
                      "Example: `automod spam True 3 5 mute`",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        # Update settings
        if enabled is not None:
            spam_settings['enabled'] = enabled
        if max_messages is not None:
            if max_messages < 1 or max_messages > 20:
                return await ctx.send("❌ Max messages must be between 1 and 20!")
            spam_settings['max_messages'] = max_messages
        if time_window is not None:
            if time_window < 1 or time_window > 60:
                return await ctx.send("❌ Time window must be between 1 and 60 seconds!")
            spam_settings['time_window'] = time_window
        if action is not None:
            valid_actions = ['warn', 'mute', 'kick', 'ban']
            if action.lower() not in valid_actions:
                return await ctx.send(f"❌ Invalid action! Valid actions: {', '.join(valid_actions)}")
            spam_settings['action'] = action.lower()
        
        # Save settings
        automod['anti_spam'] = spam_settings
        mod_settings['automod'] = automod
        await db.update_guild_settings(ctx.guild.id, {'moderation': mod_settings})
        
        embed = nextcord.Embed(
            title="✅ Anti-Spam Updated",
            description="Anti-spam settings have been updated successfully!",
            color=0x2ecc71
        )
        embed.add_field(
            name="New Settings",
            value=(
                f"**Enabled:** {'✅' if spam_settings.get('enabled', False) else '❌'}\n"
                f"**Max Messages:** {spam_settings.get('max_messages', 5)}\n"
                f"**Time Window:** {spam_settings.get('time_window', 5)} seconds\n"
                f"**Action:** {spam_settings.get('action', 'warn').title()}"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @automod_settings.command(name='mentions')
    @commands.has_permissions(manage_guild=True)
    async def configure_mentions(self, ctx, enabled: bool = None, max_mentions: int = None, action: str = None):
        """Configure anti-mass mention settings
        
        Usage: automod mentions [enabled] [max_mentions] [action]
        """
        settings = await db.get_guild_settings(ctx.guild.id)
        mod_settings = settings.get('moderation', {})
        automod = mod_settings.get('automod', {})
        mention_settings = automod.get('anti_mention', {})
        
        if all(param is None for param in [enabled, max_mentions, action]):
            # Show current settings
            embed = nextcord.Embed(
                title="📢 Anti-Mass Mention Configuration",
                color=0xe74c3c
            )
            embed.add_field(
                name="Current Settings",
                value=(
                    f"**Enabled:** {'✅' if mention_settings.get('enabled', False) else '❌'}\n"
                    f"**Max Mentions:** {mention_settings.get('max_mentions', 8)}\n"
                    f"**Action:** {mention_settings.get('action', 'warn').title()}\n"
                    f"**Delete Message:** {'✅' if mention_settings.get('delete_message', True) else '❌'}"
                ),
                inline=False
            )
            embed.add_field(
                name="Usage",
                value="`automod mentions <enabled> [max_mentions] [action]`\n"
                      "Example: `automod mentions True 5 mute`",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        # Update settings
        if enabled is not None:
            mention_settings['enabled'] = enabled
        if max_mentions is not None:
            if max_mentions < 1 or max_mentions > 20:
                return await ctx.send("❌ Max mentions must be between 1 and 20!")
            mention_settings['max_mentions'] = max_mentions
        if action is not None:
            valid_actions = ['warn', 'mute', 'kick', 'ban']
            if action.lower() not in valid_actions:
                return await ctx.send(f"❌ Invalid action! Valid actions: {', '.join(valid_actions)}")
            mention_settings['action'] = action.lower()
        
        # Save settings
        automod['anti_mention'] = mention_settings
        mod_settings['automod'] = automod
        await db.update_guild_settings(ctx.guild.id, {'moderation': mod_settings})
        
        embed = nextcord.Embed(
            title="✅ Anti-Mass Mention Updated",
            description="Anti-mass mention settings have been updated successfully!",
            color=0x2ecc71
        )
        embed.add_field(
            name="New Settings",
            value=(
                f"**Enabled:** {'✅' if mention_settings.get('enabled', False) else '❌'}\n"
                f"**Max Mentions:** {mention_settings.get('max_mentions', 8)}\n"
                f"**Action:** {mention_settings.get('action', 'warn').title()}"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    # Punishment Settings
    @moderation_settings.group(name='punishment', aliases=['punish'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def punishment_settings(self, ctx):
        """Configure punishment escalation settings"""
        embed = nextcord.Embed(
            title="⚖️ Punishment System",
            description="Configure automatic punishment escalation based on warnings",
            color=0xe74c3c
        )
        embed.add_field(
            name="Commands",
            value=(
                "`punishment limits` - Set warning limits for actions\n"
                "`punishment actions` - Configure punishment actions\n"
                "`punishment view` - View current punishment settings\n"
                "`punishment reset` - Reset punishment settings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @punishment_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_punishment(self, ctx):
        """View current punishment settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        punishment = settings.get('moderation', {}).get('punishment', {})
        
        warn_limits = punishment.get('warn_limits', {
            'mute': 3,
            'kick': 5, 
            'ban': 7
        })
        
        actions = punishment.get('actions', {
            'mute': {'duration': 3600, 'enabled': True},
            'kick': {'enabled': True},
            'ban': {'enabled': True, 'delete_days': 1}
        })
        
        embed = nextcord.Embed(
            title="⚖️ Punishment System Configuration",
            color=0xe74c3c
        )
        
        embed.add_field(
            name="📊 Warning Limits",
            value=(
                f"**{warn_limits.get('mute', 3)} warns** → Mute\n"
                f"**{warn_limits.get('kick', 5)} warns** → Kick\n"
                f"**{warn_limits.get('ban', 7)} warns** → Ban"
            ),
            inline=True
        )
        
        mute_action = actions.get('mute', {})
        kick_action = actions.get('kick', {})
        ban_action = actions.get('ban', {})
        
        embed.add_field(
            name="⚡ Actions",
            value=(
                f"**Mute:** {'✅' if mute_action.get('enabled', True) else '❌'} "
                f"({mute_action.get('duration', 3600)}s)\n"
                f"**Kick:** {'✅' if kick_action.get('enabled', True) else '❌'}\n"
                f"**Ban:** {'✅' if ban_action.get('enabled', True) else '❌'} "
                f"(del {ban_action.get('delete_days', 1)}d)"
            ),
            inline=True
        )
        
        await ctx.send(embed=embed)

    @punishment_settings.command(name='limits')
    @commands.has_permissions(manage_guild=True)
    async def set_punishment_limits(self, ctx, mute: int = None, kick: int = None, ban: int = None):
        """Set warning limits for punishment actions
        
        Usage: punishment limits [mute_warns] [kick_warns] [ban_warns]
        """
        settings = await db.get_guild_settings(ctx.guild.id)
        mod_settings = settings.get('moderation', {})
        punishment = mod_settings.get('punishment', {})
        warn_limits = punishment.get('warn_limits', {
            'mute': 3,
            'kick': 5,
            'ban': 7
        })
        
        if all(param is None for param in [mute, kick, ban]):
            embed = nextcord.Embed(
                title="📊 Current Warning Limits",
                color=0xe74c3c
            )
            embed.add_field(
                name="Limits",
                value=(
                    f"**Mute:** {warn_limits.get('mute', 3)} warnings\n"
                    f"**Kick:** {warn_limits.get('kick', 5)} warnings\n"
                    f"**Ban:** {warn_limits.get('ban', 7)} warnings"
                ),
                inline=False
            )
            embed.add_field(
                name="Usage",
                value="`punishment limits <mute_warns> <kick_warns> <ban_warns>`\n"
                      "Example: `punishment limits 3 5 7`",
                inline=False
            )
            return await ctx.send(embed=embed)
        
        # Validate inputs
        if mute is not None:
            if mute < 1 or mute > 20:
                return await ctx.send("❌ Mute warning limit must be between 1 and 20!")
            warn_limits['mute'] = mute
        
        if kick is not None:
            if kick < 1 or kick > 20:
                return await ctx.send("❌ Kick warning limit must be between 1 and 20!")
            warn_limits['kick'] = kick
        
        if ban is not None:
            if ban < 1 or ban > 20:
                return await ctx.send("❌ Ban warning limit must be between 1 and 20!")
            warn_limits['ban'] = ban
        
        # Ensure logical progression
        if warn_limits['mute'] >= warn_limits['kick']:
            return await ctx.send("❌ Mute limit must be less than kick limit!")
        if warn_limits['kick'] >= warn_limits['ban']:
            return await ctx.send("❌ Kick limit must be less than ban limit!")
        
        # Save settings
        punishment['warn_limits'] = warn_limits
        mod_settings['punishment'] = punishment
        await db.update_guild_settings(ctx.guild.id, {'moderation': mod_settings})
        
        embed = nextcord.Embed(
            title="✅ Warning Limits Updated",
            description="Punishment warning limits have been updated!",
            color=0x2ecc71
        )
        embed.add_field(
            name="New Limits",
            value=(
                f"**Mute:** {warn_limits['mute']} warnings\n"
                f"**Kick:** {warn_limits['kick']} warnings\n"
                f"**Ban:** {warn_limits['ban']} warnings"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @moderation_settings.command(name='reset')
    @commands.has_permissions(manage_guild=True)
    async def reset_moderation(self, ctx):
        """Reset all moderation settings to defaults"""
        embed = nextcord.Embed(
            title="⚠️ Reset Moderation Settings",
            description="Are you sure you want to reset ALL moderation settings to defaults?\nThis action cannot be undone!",
            color=0xff9500
        )
        
        view = ConfirmView()
        message = await ctx.send(embed=embed, view=view)
        await view.wait()
        
        if view.value:
            # Reset to defaults
            default_settings = {
                'automod': {
                    'anti_spam': {'enabled': False, 'max_messages': 5, 'time_window': 5, 'action': 'warn'},
                    'anti_mention': {'enabled': False, 'max_mentions': 8, 'action': 'warn'},
                    'anti_caps': {'enabled': False, 'max_caps_percent': 70, 'min_length': 10, 'action': 'warn'},
                    'anti_links': {'enabled': False, 'block_invites': True, 'action': 'delete'},
                    'auto_delete': {'enabled': False, 'timeout': 0}
                },
                'punishment': {
                    'warn_limits': {'mute': 3, 'kick': 5, 'ban': 7},
                    'actions': {
                        'mute': {'duration': 3600, 'enabled': True},
                        'kick': {'enabled': True},
                        'ban': {'enabled': True, 'delete_days': 1}
                    }
                }
            }
            
            await db.update_guild_settings(ctx.guild.id, {'moderation': default_settings})
            
            embed = nextcord.Embed(
                title="✅ Moderation Settings Reset",
                description="All moderation settings have been reset to defaults.",
                color=0x2ecc71
            )
            await message.edit(embed=embed, view=None)
        else:
            embed = nextcord.Embed(
                title="❌ Reset Cancelled",
                description="Moderation settings were not reset.",
                color=0x95a5a6
            )
            await message.edit(embed=embed, view=None)

    async def check_automod(self, message: nextcord.Message) -> bool:
        """Check if message triggers auto-moderation"""
        if not message.guild or message.author.bot:
            return True
        
        settings = await db.get_guild_settings(message.guild.id)
        automod = settings.get('moderation', {}).get('automod', {})
        
        # Check spam
        if automod.get('anti_spam', {}).get('enabled', False):
            if await self._check_spam(message, automod['anti_spam']):
                return False
        
        # Check mass mentions
        if automod.get('anti_mention', {}).get('enabled', False):
            if await self._check_mass_mentions(message, automod['anti_mention']):
                return False
        
        # Check caps
        if automod.get('anti_caps', {}).get('enabled', False):
            if await self._check_caps(message, automod['anti_caps']):
                return False
        
        # Check links
        if automod.get('anti_links', {}).get('enabled', False):
            if await self._check_links(message, automod['anti_links']):
                return False
        
        return True

    async def _check_spam(self, message: nextcord.Message, settings: dict) -> bool:
        """Check for spam and take action if needed"""
        # This would implement spam detection logic
        # For now, return False (no spam detected)
        return False

    async def _check_mass_mentions(self, message: nextcord.Message, settings: dict) -> bool:
        """Check for mass mentions and take action if needed"""
        max_mentions = settings.get('max_mentions', 8)
        total_mentions = len(message.mentions) + len(message.role_mentions)
        
        if total_mentions >= max_mentions:
            action = settings.get('action', 'warn')
            delete_message = settings.get('delete_message', True)
            
            if delete_message:
                try:
                    await message.delete()
                except nextcord.HTTPException:
                    pass
            
            # Take action based on settings
            await self._take_action(message.author, message.guild, action, f"Mass mentions ({total_mentions} mentions)")
            return True
        
        return False

    async def _check_caps(self, message: nextcord.Message, settings: dict) -> bool:
        """Check for excessive caps and take action if needed"""
        content = message.content
        min_length = settings.get('min_length', 10)
        max_caps_percent = settings.get('max_caps_percent', 70)
        
        if len(content) < min_length:
            return False
        
        caps_count = sum(1 for c in content if c.isupper())
        caps_percent = (caps_count / len(content)) * 100
        
        if caps_percent >= max_caps_percent:
            action = settings.get('action', 'warn')
            
            try:
                await message.delete()
            except nextcord.HTTPException:
                pass
            
            await self._take_action(message.author, message.guild, action, f"Excessive caps ({caps_percent:.1f}%)")
            return True
        
        return False

    async def _check_links(self, message: nextcord.Message, settings: dict) -> bool:
        """Check for unwanted links and take action if needed"""
        content = message.content.lower()
        
        # Check for Discord invites
        if settings.get('block_invites', True):
            invite_patterns = ['discord.gg/', 'discord.com/invite/', 'discordapp.com/invite/']
            if any(pattern in content for pattern in invite_patterns):
                action = settings.get('action', 'delete')
                
                try:
                    await message.delete()
                except nextcord.HTTPException:
                    pass
                
                if action != 'delete':
                    await self._take_action(message.author, message.guild, action, "Discord invite link")
                return True
        
        return False

    async def _take_action(self, user: nextcord.Member, guild: nextcord.Guild, action: str, reason: str):
        """Take moderation action against a user"""
        try:
            if action == 'warn':
                # This would integrate with a warning system
                pass
            elif action == 'mute':
                # This would implement muting
                pass
            elif action == 'kick':
                await user.kick(reason=f"Auto-mod: {reason}")
            elif action == 'ban':
                await user.ban(reason=f"Auto-mod: {reason}", delete_message_days=1)
        except nextcord.HTTPException as e:
            logger.error(f"Failed to take action {action} against {user}: {e}")

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "moderation settings")

class ConfirmView(nextcord.ui.View):
    def __init__(self):
        super().__init__(timeout=30)
        self.value = None

    @nextcord.ui.button(label='Confirm', style=nextcord.ButtonStyle.danger)
    async def confirm(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        self.value = True
        self.stop()

    @nextcord.ui.button(label='Cancel', style=nextcord.ButtonStyle.secondary)
    async def cancel(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        self.value = False
        self.stop()

async def setup(bot):
    bot.add_cog(ModerationSettings(bot))
