import nextcord
from nextcord.ext import commands
from utils.db import db
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler

logger = CogLogger('ServerSettings')

# DEPRECATED: This file has been replaced by the modular settings system
# The new system is located in cogs/settings/ with separate modules for:
# - general.py (permissions, prefixes, command restrictions)
# - moderation.py (auto-mod, warnings, punishment settings)
# - economy.py (server economy configuration)
# - music.py (music bot settings)
# - welcome.py (welcome messages, auto-roles)
# - logging.py (event logging configuration)

class ServerSettings(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot

    @commands.group(invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def settings(self, ctx):
        """⚠️ DEPRECATED - Use the new modular settings system"""
        embed = nextcord.Embed(
            title="⚠️ Settings System Updated!",
            description=(
                "The server settings have been upgraded to a comprehensive modular system!\n\n"
                "**New Settings Commands:**\n"
                "🔧 `general` - General server configuration\n"
                "🛡️ `moderation` - Auto-moderation settings\n" 
                "💰 `economy` - Economy configuration\n"
                "🎵 `music` - Music bot settings\n"
                "👋 `welcome` - Welcome system setup\n"
                "📝 `logging` - Event logging configuration\n\n"
                "**Example:** `general view` or `welcome setup`"
            ),
            color=0xe74c3c
        )
        embed.set_footer(text="This old settings command will be removed in a future update.")
        await ctx.send(embed=embed)

    @commands.command(name='oldsettings', hidden=True)
    @commands.has_permissions(manage_guild=True)
    async def old_settings_view(self, ctx):
        """View legacy server settings (for migration purposes)"""
        settings = await db.get_guild_settings(ctx.guild.id)
        
        embed = nextcord.Embed(
            title="Legacy Server Settings (Read-Only)",
            description="This shows your old settings. Use the new modular commands to configure.",
            color=nextcord.Color.orange()
        )
        
        # Prefixes
        prefixes = settings.get("prefixes", ["."])
        embed.add_field(
            name="Prefixes",
            value=", ".join(f"`{p}`" for p in prefixes) + "\n*Use: `general prefix` to manage*",
            inline=False
        )
        
        # Welcome settings
        welcome = settings.get("welcome", {})
        welcome_status = "✅" if welcome.get("enabled") else "❌"
        welcome_channel = f"<#{welcome['channel_id']}>" if welcome.get("channel_id") else "Not set"
        embed.add_field(
            name="Welcome System",
            value=f"Status: {welcome_status}\nChannel: {welcome_channel}\n*Use: `welcome setup` to configure*",
            inline=False
        )
        
        # Moderation settings
        mod = settings.get("moderation", {})
        log_channel = f"<#{mod['log_channel']}>" if mod.get("log_channel") else "Not set"
        mute_role = f"<@&{mod['mute_role']}>" if mod.get("mute_role") else "Not set"
        jail_role = f"<@&{mod['jail_role']}>" if mod.get("jail_role") else "Not set"
        
        embed.add_field(
            name="Moderation",
            value=f"Log Channel: {log_channel}\nMute Role: {mute_role}\nJail Role: {jail_role}\n*Use: `moderation` and `logging` to configure*",
            inline=False
        )
        
        await ctx.send(embed=embed)

    @settings.command()
    @commands.has_permissions(manage_guild=True)
    async def prefix(self, ctx, action: str = None, prefix: str = None):
        """Manage server prefixes"""
        if not action:
            settings = await db.get_guild_settings(ctx.guild.id)
            prefixes = settings.get("prefixes", ["."])
            return await ctx.send(f"Current prefixes: {', '.join(f'`{p}`' for p in prefixes)}")
            
        if action.lower() not in ["add", "remove"]:
            return await ctx.send("Please specify `add` or `remove`")
            
        if not prefix:
            return await ctx.send("Please provide a prefix")
            
        if len(prefix) > 5:
            return await ctx.send("Prefix must be 5 characters or less")
        
        if len(prefixes) <= 1 and action.lower() == "remove":
            return await ctx.send("you cant remove your only prefix!")
            
        if action.lower() == "add":
            await db.add_prefix(ctx.guild.id, prefix)
            await ctx.send(f"Added prefix: `{prefix}`")
        else:
            settings = await db.get_guild_settings(ctx.guild.id)
            if len(settings.get("prefixes", [])) <= 1:
                return await ctx.send("Can't remove last prefix!")
            await db.remove_prefix(ctx.guild.id, prefix)
            await ctx.send(f"Removed prefix: `{prefix}`")

    @settings.group()
    @commands.has_permissions(manage_guild=True)
    async def welcome(self, ctx):
        """Configure welcome messages"""
        if ctx.invoked_subcommand is None:
            settings = await db.get_guild_settings(ctx.guild.id)
            welcome = settings.get("welcome", {})
            
            embed = nextcord.Embed(
                title="Welcome Settings",
                description=f"Status: {'✅' if welcome.get('enabled') else '❌'}",
                color=nextcord.Color.blue()
            )
            
            embed.add_field(
                name="Channel",
                value=f"<#{welcome['channel_id']}>" if welcome.get("channel_id") else "Not set",
                inline=False
            )
            
            if welcome.get("embed_json"):
                embed.add_field(
                    name="Welcome Embed",
                    value="Custom embed configured",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Message",
                    value=f"```{welcome.get('message', 'Not set')}```",
                    inline=False
                )
            
            await ctx.send(embed=embed)

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def embed(self, ctx, *, content: str = None):
        """Set welcome embed using JSON format
        Variables: {user}, {server}, {mention}, {name}, {displayname}, {id}, {created_at}, {joined_at}, {member_count}
        Emojis: Use {emoji:name} for server emojis
        
        Example:
        {
            "author": {
                "name": "Welcome {name}!",
                "icon_url": "{avatar_url}",
                "url": "https://discord.gg/discord"
            },
            "title": "Welcome to {server}",
            "url": "https://your-url.com",
            "description": "{emoji:wave} Hey {mention}!\\nYou are member #{member_count}",
            "color": "0x00ff00",
            "thumbnail": {"url": "{avatar_url}"},
            "image": {"url": "https://your-banner.png"},
            "fields": [
                {
                    "name": "Account Created",
                    "value": "{created_at}",
                    "inline": true
                }
            ],
            "footer": {
                "text": "Joined at {joined_at}",
                "icon_url": "{server_icon}"
            }
        }
        """
        if not content:
            await ctx.send("Please provide embed JSON configuration")
            return

        try:
            import json
            embed_data = json.loads(content)
            # Validate structure
            required_types = {
                "title": str, "description": str, "url": str,
                "color": str, "fields": list, "author": dict,
                "footer": dict, "image": dict, "thumbnail": dict
            }
            
            for key, type_ in required_types.items():
                if key in embed_data and not isinstance(embed_data[key], type_):
                    raise ValueError(f"Invalid type for {key}")
                    
            await db.update_guild_settings(ctx.guild.id, {"welcome.embed_json": embed_data})
            await ctx.send("Welcome embed configuration updated!")
        except Exception as e:
            await ctx.send(f"Error setting embed: {str(e)}")

    @welcome.command()
    @commands.has_permissions(manage_guild=True)
    async def test(self, ctx):
        """Test the welcome message/embed"""
        settings = await db.get_guild_settings(ctx.guild.id)
        welcome = settings.get("welcome", {})
        
        if welcome.get("embed_json"):
            try:
                embed_data = welcome["embed_json"].copy()
                # Get variables
                variables = {
                    "user": ctx.author,
                    "name": ctx.author.name,
                    "displayname": ctx.author.display_name,
                    "mention": ctx.author.mention,
                    "id": str(ctx.author.id),
                    "avatar_url": str(ctx.author.avatar.url) if ctx.author.avatar else None,
                    "server": ctx.guild.name,
                    "server_icon": str(ctx.guild.icon.url) if ctx.guild.icon else None,
                    "member_count": str(ctx.guild.member_count),
                    "created_at": nextcord.utils.format_dt(ctx.author.created_at, style="R"),
                    "joined_at": nextcord.utils.format_dt(ctx.author.joined_at, style="R") if ctx.author.joined_at else "N/A"
                }

                def replace_vars(text):
                    if not isinstance(text, str):
                        return text
                    # Replace variables
                    for key, value in variables.items():
                        text = text.replace(f"{{{key}}}", str(value))
                    # Replace emojis
                    import re
                    emoji_pattern = r'\{emoji:(.*?)\}'
                    for emoji_name in re.findall(emoji_pattern, text):
                        emoji = nextcord.utils.get(ctx.guild.emojis, name=emoji_name)
                        if emoji:
                            text = text.replace(f"{{emoji:{emoji_name}}}", str(emoji))
                    return text

                # Process all embed fields recursively
                def process_dict(d):
                    if isinstance(d, dict):
                        return {k: process_dict(v) for k, v in d.items()}
                    elif isinstance(d, list):
                        return [process_dict(i) for i in d]
                    elif isinstance(d, str):
                        return replace_vars(d)
                    return d

                embed_data = process_dict(embed_data)
                embed = nextcord.Embed.from_dict(embed_data)
                await ctx.send(embed=embed)
            except Exception as e:
                await ctx.send(f"Error displaying embed: {str(e)}")
        else:
            message = welcome.get("message", "Welcome message not set")
            await ctx.send(message.format(
                user=ctx.author.name,
                server=ctx.guild.name,
                mention=ctx.author.mention
            ))

    @welcome.error
    async def welcome_error(self, ctx, error):
        await self.handle_error(ctx, error, "welcome")

    @prefix.error 
    async def prefix_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send("Please provide both an action (add/remove) and a prefix")
        else:
            await self.handle_error(ctx, error, "prefix")

async def setup(bot):
    bot.add_cog(ServerSettings(bot))
