# Music Settings
# Handles music bot configuration, playlists, and music permissions

import nextcord
from nextcord.ext import commands
from typing import Optional, List, Dict, Union
import json
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('MusicSettings')

class MusicSettings(commands.Cog, ErrorHandler):
    """Music configuration settings"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(name='music', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def music_settings(self, ctx):
        """Music settings management"""
        embed = nextcord.Embed(
            title="🎵 Music Settings",
            description=(
                "Configure music bot settings for this server\n\n"
                "**Available Commands:**\n"
                "`music playlists` - Manage server playlists\n"
                "`music permissions` - Configure music permissions\n"
                "`music channels` - Set allowed music channels\n"
                "`music view` - View current music settings\n"
                "`music reset` - Reset all music settings"
            ),
            color=0x9b59b6
        )
        await ctx.send(embed=embed)

    @music_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_music_settings(self, ctx):
        """View current music settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        
        embed = nextcord.Embed(
            title="🎵 Music Settings Overview",
            color=0x9b59b6
        )
        
        # General settings
        general = music_settings.get('general', {})
        embed.add_field(
            name="⚙️ General Settings",
            value=(
                f"**Music Enabled:** {'✅' if general.get('enabled', True) else '❌'}\n"
                f"**Auto-Leave:** {'✅' if general.get('auto_leave', True) else '❌'}\n"
                f"**Auto-Leave Timeout:** {general.get('auto_leave_timeout', 300)}s\n"
                f"**Max Queue Size:** {general.get('max_queue_size', 100)}"
            ),
            inline=False
        )
        
        # Permissions
        permissions = music_settings.get('permissions', {})
        embed.add_field(
            name="🔐 Permissions",
            value=(
                f"**DJ Roles:** {len(permissions.get('dj_roles', []))} roles\n"
                f"**Skip Votes Required:** {permissions.get('skip_votes_required', 2)}\n"
                f"**Skip Ratio:** {permissions.get('skip_ratio', 0.5)}\n"
                f"Use `music permissions view` for details"
            ),
            inline=False
        )
        
        # Playlists
        playlists = music_settings.get('playlists', [])
        embed.add_field(
            name="📋 Playlists",
            value=(
                f"**Server Playlists:** {len(playlists)} playlists\n"
                f"Use `music playlists view` for details"
            ),
            inline=False
        )
        
        # Channels
        channels = music_settings.get('channels', {})
        allowed_channels = channels.get('allowed_channels', [])
        embed.add_field(
            name="📺 Channel Settings",
            value=(
                f"**Allowed Channels:** {len(allowed_channels) if allowed_channels else 'All channels'}\n"
                f"**Music Channel Only:** {'✅' if channels.get('music_channel_only', False) else '❌'}"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    # Playlist Management
    @music_settings.group(name='playlists', aliases=['playlist'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def playlist_settings(self, ctx):
        """Manage server playlists"""
        embed = nextcord.Embed(
            title="📋 Playlist Management",
            description="Manage server music playlists",
            color=0x9b59b6
        )
        embed.add_field(
            name="Commands",
            value=(
                "`playlists view` - View all server playlists\n"
                "`playlists create <name>` - Create a new playlist\n"
                "`playlists delete <name>` - Delete a playlist\n"
                "`playlists add <playlist> <url>` - Add song to playlist\n"
                "`playlists remove <playlist> <index>` - Remove song from playlist\n"
                "`playlists info <name>` - View playlist details"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @playlist_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_playlists(self, ctx):
        """View all server playlists"""
        settings = await db.get_guild_settings(ctx.guild.id)
        playlists = settings.get('music', {}).get('playlists', [])
        
        embed = nextcord.Embed(
            title="📋 Server Playlists",
            color=0x9b59b6
        )
        
        if not playlists:
            embed.description = "No playlists created yet.\nUse `music playlists create <name>` to create one!"
            return await ctx.send(embed=embed)
        
        for playlist in playlists:
            embed.add_field(
                name=f"🎵 {playlist['name']}",
                value=(
                    f"**Songs:** {len(playlist.get('songs', []))}\n"
                    f"**Created by:** <@{playlist.get('created_by', 'Unknown')}>\n"
                    f"**Created:** {playlist.get('created_at', 'Unknown')[:10]}"
                ),
                inline=True
            )
        
        embed.set_footer(text=f"Total playlists: {len(playlists)}")
        await ctx.send(embed=embed)

    @playlist_settings.command(name='create')
    @commands.has_permissions(manage_guild=True)
    async def create_playlist(self, ctx, *, name: str):
        """Create a new server playlist"""
        if len(name) > 50:
            return await ctx.send("❌ Playlist name cannot be longer than 50 characters!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        playlists = music_settings.get('playlists', [])
        
        # Check if playlist already exists
        if any(p['name'].lower() == name.lower() for p in playlists):
            return await ctx.send(f"❌ A playlist named '{name}' already exists!")
        
        # Create new playlist
        new_playlist = {
            'name': name,
            'songs': [],
            'created_by': ctx.author.id,
            'created_at': ctx.message.created_at.isoformat(),
            'description': ""
        }
        
        playlists.append(new_playlist)
        music_settings['playlists'] = playlists
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ Playlist Created",
            description=f"Successfully created playlist **{name}**!",
            color=0x2ecc71
        )
        embed.add_field(
            name="Next Steps",
            value=f"• Add songs: `music playlists add {name} <youtube_url>`\n"
                  f"• View playlist: `music playlists info {name}`",
            inline=False
        )
        await ctx.send(embed=embed)

    @playlist_settings.command(name='delete')
    @commands.has_permissions(manage_guild=True)
    async def delete_playlist(self, ctx, *, name: str):
        """Delete a server playlist"""
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        playlists = music_settings.get('playlists', [])
        
        # Find playlist
        playlist_to_delete = None
        for playlist in playlists:
            if playlist['name'].lower() == name.lower():
                playlist_to_delete = playlist
                break
        
        if not playlist_to_delete:
            return await ctx.send(f"❌ No playlist named '{name}' found!")
        
        playlists.remove(playlist_to_delete)
        music_settings['playlists'] = playlists
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ Playlist Deleted",
            description=f"Successfully deleted playlist **{name}**!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @playlist_settings.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_to_playlist(self, ctx, playlist_name: str, *, url: str):
        """Add a song to a playlist"""
        # Basic URL validation
        if not any(domain in url.lower() for domain in ['youtube.com', 'youtu.be', 'spotify.com']):
            return await ctx.send("❌ Please provide a valid YouTube or Spotify URL!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        playlists = music_settings.get('playlists', [])
        
        # Find playlist
        target_playlist = None
        for playlist in playlists:
            if playlist['name'].lower() == playlist_name.lower():
                target_playlist = playlist
                break
        
        if not target_playlist:
            return await ctx.send(f"❌ No playlist named '{playlist_name}' found!")
        
        # Add song to playlist
        song_data = {
            'url': url,
            'added_by': ctx.author.id,
            'added_at': ctx.message.created_at.isoformat(),
            'title': 'Unknown Title',  # Would be fetched from YouTube API in real implementation
            'duration': 0
        }
        
        target_playlist['songs'].append(song_data)
        music_settings['playlists'] = playlists
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ Song Added to Playlist",
            description=f"Added song to playlist **{playlist_name}**!",
            color=0x2ecc71
        )
        embed.add_field(
            name="Song Details",
            value=f"**URL:** {url}\n**Added by:** {ctx.author.mention}",
            inline=False
        )
        embed.set_footer(text=f"Playlist now has {len(target_playlist['songs'])} songs")
        await ctx.send(embed=embed)

    @playlist_settings.command(name='info')
    @commands.has_permissions(manage_guild=True)
    async def playlist_info(self, ctx, *, name: str):
        """View detailed information about a playlist"""
        settings = await db.get_guild_settings(ctx.guild.id)
        playlists = settings.get('music', {}).get('playlists', [])
        
        # Find playlist
        target_playlist = None
        for playlist in playlists:
            if playlist['name'].lower() == name.lower():
                target_playlist = playlist
                break
        
        if not target_playlist:
            return await ctx.send(f"❌ No playlist named '{name}' found!")
        
        embed = nextcord.Embed(
            title=f"📋 Playlist: {target_playlist['name']}",
            color=0x9b59b6
        )
        
        embed.add_field(
            name="📊 Statistics",
            value=(
                f"**Songs:** {len(target_playlist.get('songs', []))}\n"
                f"**Created by:** <@{target_playlist.get('created_by', 'Unknown')}>\n"
                f"**Created:** {target_playlist.get('created_at', 'Unknown')[:10]}"
            ),
            inline=False
        )
        
        # Show first 10 songs
        songs = target_playlist.get('songs', [])
        if songs:
            song_list = []
            for i, song in enumerate(songs[:10], 1):
                song_list.append(f"{i}. {song.get('title', 'Unknown')} - <@{song.get('added_by', 'Unknown')}>")
            
            embed.add_field(
                name="🎵 Songs (First 10)",
                value='\n'.join(song_list) if song_list else "No songs",
                inline=False
            )
            
            if len(songs) > 10:
                embed.set_footer(text=f"... and {len(songs) - 10} more songs")
        
        await ctx.send(embed=embed)

    # Permission Management
    @music_settings.group(name='permissions', aliases=['perms'], invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def music_permissions(self, ctx):
        """Configure music permissions"""
        embed = nextcord.Embed(
            title="🔐 Music Permissions",
            description="Configure who can control music playback",
            color=0x9b59b6
        )
        embed.add_field(
            name="Commands",
            value=(
                "`permissions view` - View current permissions\n"
                "`permissions dj add <role>` - Add DJ role\n"
                "`permissions dj remove <role>` - Remove DJ role\n"
                "`permissions skip <votes>` - Set skip vote requirement\n"
                "`permissions ratio <ratio>` - Set skip vote ratio"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @music_permissions.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_music_permissions(self, ctx):
        """View current music permissions"""
        settings = await db.get_guild_settings(ctx.guild.id)
        permissions = settings.get('music', {}).get('permissions', {})
        
        embed = nextcord.Embed(
            title="🔐 Music Permissions Configuration",
            color=0x9b59b6
        )
        
        # DJ Roles
        dj_roles = permissions.get('dj_roles', [])
        if dj_roles:
            role_list = []
            for role_id in dj_roles:
                role = ctx.guild.get_role(role_id)
                if role:
                    role_list.append(role.mention)
                else:
                    role_list.append(f"<@&{role_id}> (Deleted)")
            
            embed.add_field(
                name="👑 DJ Roles",
                value='\n'.join(role_list),
                inline=False
            )
        else:
            embed.add_field(
                name="👑 DJ Roles",
                value="No DJ roles configured (anyone can control music)",
                inline=False
            )
        
        # Skip settings
        embed.add_field(
            name="⏭️ Skip Settings",
            value=(
                f"**Votes Required:** {permissions.get('skip_votes_required', 2)}\n"
                f"**Skip Ratio:** {permissions.get('skip_ratio', 0.5)} ({int(permissions.get('skip_ratio', 0.5) * 100)}%)\n"
                f"**DJ Skip Override:** {'✅' if permissions.get('dj_skip_override', True) else '❌'}"
            ),
            inline=False
        )
        
        # Other permissions
        embed.add_field(
            name="🎛️ Other Permissions",
            value=(
                f"**Anyone Can Queue:** {'✅' if permissions.get('anyone_can_queue', True) else '❌'}\n"
                f"**Anyone Can Skip:** {'✅' if permissions.get('anyone_can_skip', False) else '❌'}\n"
                f"**Max User Queue:** {permissions.get('max_user_queue', 10)}"
            ),
            inline=False
        )
        
        await ctx.send(embed=embed)

    @music_permissions.group(name='dj', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def dj_management(self, ctx):
        """Manage DJ roles"""
        embed = nextcord.Embed(
            title="👑 DJ Role Management",
            description="DJ roles have special permissions for music control",
            color=0x9b59b6
        )
        embed.add_field(
            name="DJ Permissions",
            value=(
                "• Skip songs without voting\n"
                "• Clear the queue\n"
                "• Control volume\n"
                "• Force disconnect\n"
                "• Manage playlists"
            ),
            inline=False
        )
        embed.add_field(
            name="Commands",
            value=(
                "`dj add <role>` - Add a DJ role\n"
                "`dj remove <role>` - Remove a DJ role\n"
                "`dj list` - List current DJ roles"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @dj_management.command(name='add')
    @commands.has_permissions(manage_guild=True)
    async def add_dj_role(self, ctx, role: nextcord.Role):
        """Add a DJ role"""
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        permissions = music_settings.get('permissions', {})
        dj_roles = permissions.get('dj_roles', [])
        
        if role.id in dj_roles:
            return await ctx.send(f"❌ {role.mention} is already a DJ role!")
        
        dj_roles.append(role.id)
        permissions['dj_roles'] = dj_roles
        music_settings['permissions'] = permissions
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ DJ Role Added",
            description=f"Added {role.mention} as a DJ role!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @dj_management.command(name='remove')
    @commands.has_permissions(manage_guild=True)
    async def remove_dj_role(self, ctx, role: nextcord.Role):
        """Remove a DJ role"""
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        permissions = music_settings.get('permissions', {})
        dj_roles = permissions.get('dj_roles', [])
        
        if role.id not in dj_roles:
            return await ctx.send(f"❌ {role.mention} is not a DJ role!")
        
        dj_roles.remove(role.id)
        permissions['dj_roles'] = dj_roles
        music_settings['permissions'] = permissions
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ DJ Role Removed",
            description=f"Removed {role.mention} from DJ roles!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    @music_permissions.command(name='skip')
    @commands.has_permissions(manage_guild=True)
    async def set_skip_votes(self, ctx, votes: int):
        """Set required number of votes to skip a song"""
        if votes < 1 or votes > 20:
            return await ctx.send("❌ Skip votes must be between 1 and 20!")
        
        settings = await db.get_guild_settings(ctx.guild.id)
        music_settings = settings.get('music', {})
        permissions = music_settings.get('permissions', {})
        
        permissions['skip_votes_required'] = votes
        music_settings['permissions'] = permissions
        await db.update_guild_settings(ctx.guild.id, {'music': music_settings})
        
        embed = nextcord.Embed(
            title="✅ Skip Votes Updated",
            description=f"Skip votes required set to {votes}!",
            color=0x2ecc71
        )
        await ctx.send(embed=embed)

    # Channel Management
    @music_settings.group(name='channels', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def channel_settings(self, ctx):
        """Configure music channel settings"""
        embed = nextcord.Embed(
            title="📺 Music Channel Settings",
            description="Configure which channels can use music commands",
            color=0x9b59b6
        )
        embed.add_field(
            name="Commands",
            value=(
                "`channels view` - View current channel settings\n"
                "`channels add <channel>` - Allow music in channel\n"
                "`channels remove <channel>` - Disallow music in channel\n"
                "`channels clear` - Allow music in all channels\n"
                "`channels restrict` - Toggle music channel restriction"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @channel_settings.command(name='view')
    @commands.has_permissions(manage_guild=True)
    async def view_channel_settings(self, ctx):
        """View current channel settings"""
        settings = await db.get_guild_settings(ctx.guild.id)
        channels = settings.get('music', {}).get('channels', {})
        
        allowed_channels = channels.get('allowed_channels', [])
        music_channel_only = channels.get('music_channel_only', False)
        
        embed = nextcord.Embed(
            title="📺 Music Channel Configuration",
            color=0x9b59b6
        )
        
        if music_channel_only and allowed_channels:
            channel_list = []
            for channel_id in allowed_channels:
                channel = ctx.guild.get_channel(channel_id)
                if channel:
                    channel_list.append(channel.mention)
                else:
                    channel_list.append(f"<#{channel_id}> (Deleted)")
            
            embed.add_field(
                name="✅ Allowed Music Channels",
                value='\n'.join(channel_list),
                inline=False
            )
        else:
            embed.add_field(
                name="🌐 Channel Access",
                value="Music commands are allowed in all channels",
                inline=False
            )
        
        embed.add_field(
            name="⚙️ Settings",
            value=f"**Restrict to Specific Channels:** {'✅' if music_channel_only else '❌'}",
            inline=False
        )
        
        await ctx.send(embed=embed)

    def has_music_permissions(self, member: nextcord.Member, guild_settings: dict) -> bool:
        """Check if a member has music permissions"""
        # Server administrators always have permission
        if member.guild_permissions.manage_guild or member.guild_permissions.administrator:
            return True
        
        # Check DJ roles
        permissions = guild_settings.get('music', {}).get('permissions', {})
        dj_roles = permissions.get('dj_roles', [])
        
        member_role_ids = [role.id for role in member.roles]
        return any(role_id in dj_roles for role_id in member_role_ids)

    def can_use_music_in_channel(self, channel: nextcord.TextChannel, guild_settings: dict) -> bool:
        """Check if music commands can be used in a channel"""
        channels = guild_settings.get('music', {}).get('channels', {})
        
        # If no restrictions, allow all channels
        if not channels.get('music_channel_only', False):
            return True
        
        # Check if channel is in allowed list
        allowed_channels = channels.get('allowed_channels', [])
        return channel.id in allowed_channels

    async def cog_command_error(self, ctx, error):
        """Handle errors in this cog"""
        await self.handle_error(ctx, error, "music settings")

async def setup(bot):
    bot.add_cog(MusicSettings(bot))
