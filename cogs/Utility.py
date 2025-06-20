import nextcord
import random
import json
import datetime
import asyncio
import ast
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from typing import Optional
from utils.error_handler import ErrorHandler
from utils.restart_manager import RestartConfirmView

class AdminRoleSelect(nextcord.ui.Select):
    """Select menu for admin roles"""
    def __init__(self, admin_roles, page=0):
        self.admin_roles = admin_roles
        self.page = page
        
        # Calculate which roles to show (24 per page)
        start_idx = page * 24
        end_idx = min(start_idx + 24, len(admin_roles))
        current_roles = admin_roles[start_idx:end_idx]
        
        options = []
        for role in current_roles:
            member_count = len(role.members)
            bot_count = len([m for m in role.members if m.bot])
            human_count = member_count - bot_count
            
            description = f"👥 {human_count} users, 🤖 {bot_count} bots"
            if len(description) > 100:
                description = description[:97] + "..."
            
            options.append(nextcord.SelectOption(
                label=role.name[:100],  # Discord limit
                value=str(role.id),
                description=description,
                emoji="🛡️"
            ))
        
        super().__init__(
            placeholder=f"Select an admin role (Page {page + 1})",
            options=options,
            min_values=1,
            max_values=1
        )
    
    async def callback(self, interaction: nextcord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message("❌ Role not found!", ephemeral=True)
            return
        
        # Get the current filter from the view
        view = self.view
        filter_type = view.current_filter
        
        members = []
        if filter_type == "bots":
            members = [m for m in role.members if m.bot]
        elif filter_type == "users":
            members = [m for m in role.members if not m.bot]
        else:  # all
            members = role.members
        
        if not members:
            member_type = {"bots": "bots", "users": "users", "all": "members"}[filter_type]
            await interaction.response.send_message(f"❌ No {member_type} found in {role.mention}!", ephemeral=True)
            return
        
        # Create embed for role members
        embed = nextcord.Embed(
            title=f"🛡️ {role.name}",
            color=role.color or nextcord.Color.blue(),
            description=f"Showing {filter_type} with administrator permissions"
        )
        
        # Add members in chunks
        member_list = []
        for i, member in enumerate(members[:20]):  # Limit to 20 to avoid embed limits
            status_emoji = "🤖" if member.bot else "👤"
            member_list.append(f"{status_emoji} {member.display_name}")
        
        if len(members) > 20:
            member_list.append(f"... and {len(members) - 20} more")
        
        embed.add_field(
            name=f"Members ({len(members)})",
            value="\n".join(member_list) if member_list else "None",
            inline=False
        )
        
        embed.set_footer(text=f"Role ID: {role.id}")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

class AdminView(nextcord.ui.View):
    """View for admin listing with filters and role selection"""
    def __init__(self, ctx):
        super().__init__(timeout=300)
        self.ctx = ctx
        self.current_filter = "all"  # all, bots, users
        self.role_page = 0
        
        # Get admin roles
        self.admin_roles = [
            role for role in ctx.guild.roles 
            if role.permissions.administrator and role != ctx.guild.default_role and len(role.members) > 0
        ]
        self.admin_roles.sort(key=lambda r: len(r.members), reverse=True)
        
        self.update_components()
    
    def update_components(self):
        """Update view components based on current state"""
        self.clear_items()
        
        # Filter buttons
        self.add_item(FilterButton("👥 Users", "users", self.current_filter == "users"))
        self.add_item(FilterButton("🤖 Bots", "bots", self.current_filter == "bots"))  
        self.add_item(FilterButton("🌐 All", "all", self.current_filter == "all"))
        
        # Role select menu (if there are admin roles)
        if self.admin_roles:
            self.add_item(AdminRoleSelect(self.admin_roles, self.role_page))
            
            # Next page button for roles (if needed)
            total_pages = (len(self.admin_roles) + 23) // 24  # 24 roles per page
            if total_pages > 1:
                self.add_item(RolePageButton(self.role_page, total_pages))
    
    async def create_embed(self):
        """Create the main embed showing admin overview"""
        # Get all members with admin permissions
        all_admins = []
        for member in self.ctx.guild.members:
            admin_roles = [role for role in member.roles if role.permissions.administrator and role != self.ctx.guild.default_role]
            if admin_roles:
                all_admins.append((member, admin_roles))
        
        # Filter based on current selection
        if self.current_filter == "bots":
            filtered_admins = [(m, r) for m, r in all_admins if m.bot]
        elif self.current_filter == "users":
            filtered_admins = [(m, r) for m, r in all_admins if not m.bot]
        else:  # all
            filtered_admins = all_admins
        
        embed = nextcord.Embed(
            title="🛡️ Server Administrators",
            color=nextcord.Color.blue(),
            description=f"Showing **{self.current_filter}** with administrator permissions"
        )
        
        if not filtered_admins:
            embed.add_field(
                name="No Results",
                value=f"No {self.current_filter} found with administrator permissions",
                inline=False
            )
        else:
            # Show overview stats
            total_users = len([m for m, r in all_admins if not m.bot])
            total_bots = len([m for m, r in all_admins if m.bot])
            
            embed.add_field(
                name="📊 Overview",
                value=f"👥 **{total_users}** users\n🤖 **{total_bots}** bots\n🌐 **{len(all_admins)}** total",
                inline=True
            )
            
            embed.add_field(
                name="🛡️ Admin Roles",
                value=f"**{len(self.admin_roles)}** roles with admin permissions",
                inline=True
            )
            
            # List filtered admins (limited to avoid embed limits)
            admin_list = []
            for i, (member, roles) in enumerate(filtered_admins[:15]):  # Limit to 15
                status_emoji = "🤖" if member.bot else "👤"
                role_names = [role.name for role in roles[:3]]  # Show max 3 roles
                if len(roles) > 3:
                    role_names.append(f"+{len(roles) - 3} more")
                
                admin_list.append(f"{status_emoji} **{member.display_name}**\n└ {', '.join(role_names)}")
            
            if len(filtered_admins) > 15:
                admin_list.append(f"... and **{len(filtered_admins) - 15}** more")
            
            embed.add_field(
                name=f"{self.current_filter.title()} with Admin Permissions ({len(filtered_admins)})",
                value="\n".join(admin_list) if admin_list else "None",
                inline=False
            )
        
        embed.set_footer(text="Use the buttons below to filter results or select a role for details")
        return embed
    
    async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
        """Check if user can use this view"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message("❌ You cannot use this menu!", ephemeral=True)
            return False
        return True

class FilterButton(nextcord.ui.Button):
    """Button for filtering admin list"""
    def __init__(self, label: str, filter_type: str, is_active: bool):
        style = nextcord.ButtonStyle.primary if is_active else nextcord.ButtonStyle.secondary
        super().__init__(label=label, style=style)
        self.filter_type = filter_type
    
    async def callback(self, interaction: nextcord.Interaction):
        view = self.view
        view.current_filter = self.filter_type
        view.update_components()
        
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class RolePageButton(nextcord.ui.Button):
    """Button for navigating role pages"""
    def __init__(self, current_page: int, total_pages: int):
        self.current_page = current_page
        self.total_pages = total_pages
        
        if current_page < total_pages - 1:
            label = f"Role Page {current_page + 2}/{total_pages}"
            emoji = "▶️"
        else:
            label = f"Role Page 1/{total_pages}"
            emoji = "◀️"
        
        super().__init__(label=label, emoji=emoji, style=nextcord.ButtonStyle.secondary)
    
    async def callback(self, interaction: nextcord.Interaction):
        view = self.view
        
        if self.current_page < self.total_pages - 1:
            view.role_page += 1
        else:
            view.role_page = 0
        
        view.update_components()
        embed = await view.create_embed()
        await interaction.response.edit_message(embed=embed, view=view)

class Utility(commands.Cog, ErrorHandler):
    """Utility commands for server management and fun."""

    # --- Snipe Command ---
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.bot.launch_time = datetime.datetime.now()
        self.logger.info("Utility cog initialized")
        
        # Initialize instance variables
        self.afk_users = {}
        self.last_deleted = {}  # {guild_id: {channel_id: (message, deleted_at)}}

    @commands.command(name="ping", aliases=["pong"])
    async def ping(self, ctx):
        """Show bot latency."""
        latency = round(self.bot.latency * 1000)
        self.logger.debug(f"Ping command used by {ctx.author} - {latency}ms")
        await ctx.send(f"`{latency}ms`")

    @commands.command(aliases=['av'])
    async def avatar(self, ctx, user: nextcord.Member = None):
        """Show a user's avatar."""
        user = user or ctx.author
        self.logger.info(f"Avatar requested for {user.display_name}")
        embed = nextcord.Embed(title=f"{user.display_name}'s Avatar", color=user.color)
        embed.set_image(url=user.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.command(name='cleanup', aliases=['cu'])
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def cleanup(self, ctx, limit: Optional[int] = 100):
        """Deletes all command messages and bot messages in the channel"""
        
        # Check if limit is reasonable
        if limit > 1000:
            return await ctx.send("Please specify a limit of 1000 or less for safety reasons.")
        
        def is_target(m):
            # Match messages that start with the prefix or are from any bot
            return m.content.startswith(ctx.prefix) or m.author.bot
        
        # For older versions of nextcord.py (1.x)
        try:
            deleted = await ctx.channel.purge(limit=limit, check=is_target, before=ctx.message)
        except Exception as e:
            return await ctx.send(f"An error occurred: {e}")
        
        # Send confirmation and delete it after 5 seconds
        await ctx.message.delete()
        msg = await ctx.send(f"Deleted {len(deleted)} messages (commands and bot messages).")
        await msg.delete(delay=5)
        
        # Try to delete the original command message
        try:
            await ctx.message.delete()
        except:
            pass

    @commands.command(aliases=['si'])
    async def serverinfo(self, ctx):
        guild = ctx.guild
        
        embed = nextcord.Embed(
            description=(f"**{guild.name}**\n\n"
                      f"Members: `{guild.member_count}`\n"
                      f"Owner: `{guild.owner.display_name}`\n"
                    f"*Verification Level: `{guild.verification_level}`*\n"
                    f"Boosts: `{guild.premium_subscription_count}`\n"
                    f"Boost Level: `{guild.premium_tier}`\n"
                      f"Created: `{guild.created_at.strftime('%Y-%m-%d')}`\n"
                      f"Roles: `{len(guild.roles)}`\n"
                      f"Channels: `{len(guild.channels)}`"
                        f"\n\n**Channels:**\n"
                            f"Voice Channels: `{len(guild.voice_channels)}`\n"
                            f"Text Channels: `{len(guild.text_channels)}`"
                        f"\n\n**Emojis:**\n"
                            f"Custom Emojis: `{len(guild.emojis)}`\n"
                            f"Animated Emojis: `{len([e for e in guild.emojis if e.animated])}`"),
            color=0x2b2d31,
            timestamp=datetime.datetime.now()
        )
        embed.set_thumbnail(url=guild.icon.url if guild.icon else self.bot.user.avatar.url)
        embed.set_image(url=guild.banner.url if guild.banner else "")
        embed.set_footer(text=f"ID: {guild.id}")
        if guild.description:
            embed.description += f"\n\n**Description:** {guild.description}"
        if guild.system_channel:
            embed.add_field(name="System Channel", value=guild.system_channel.mention, inline=False)
        if guild.rules_channel:
            embed.add_field(name="Rules Channel", value=guild.rules_channel.mention, inline=False)
        await ctx.reply(embed=embed)

    @commands.command(aliases=['ui'])
    async def userinfo(self, ctx, user: nextcord.Member = None):
        user = user or ctx.author
        
        embed = nextcord.Embed(
            description=(f"**{user.display_name}**\n\n"
                      f"Joined: `{user.joined_at.strftime('%Y-%m-%d')}`\n"
                      f"Registered: `{user.created_at.strftime('%Y-%m-%d')}`\n"
                        f"Nickname: `{user.nick}`\n"
                        f"Status: `{user.status}`\n"
                        f"Roles: `{len(user.roles)}`\n"
                        f"\n**Roles:**\n"
                            f"{', '.join(role.name for role in user.roles if role.name != '@everyone') or 'None'}\n"
                        f"\n**Top Role:**\n"
                            f"{user.top_role.name if user.top_role.name != '@everyone' else 'None'}\n"
                        f"\n**Account Created:**\n"
                            f"`{user.created_at.strftime('%Y-%m-%d')}`\n"
                        f"**Joined Server:**\n"
                            f"`{user.joined_at.strftime('%Y-%m-%d')}`"
                        f"\n**Presence:**\n"
                            f"`{user.activity.name if user.activity else 'None'}`\n"
                            f"**Voice State:**\n"
                                f"`{f'Connected in {user.voice.channel.mention}' if user.voice else 'Not Connected'}`\n"),
            color=user.color or 0x2b2d31
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_author(name=str(user), icon_url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id}")
        if user.banner:
            embed.set_image(url=user.banner.url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=["ask", "yn", "yesno"])
    async def poll(self, ctx, *, question):
        embed = nextcord.Embed(
            description=f"❓ {question}\n\n✅ Yes | ❌ No",
            color=0x2b2d31
        )
        msg = await ctx.send(embed=embed)
        await msg.add_reaction('✅')
        await msg.add_reaction('❌')

    @commands.command(aliases=['calc'])
    async def calculate(self, ctx, *, expression):
        """Evaluate a math expression (basic operations only)."""
        try:
            allowed_chars = set('0123456789+-*/().,% ')
            if not all(c in allowed_chars for c in expression):
                self.logger.warning(f"Potentially unsafe expression: {expression}")
                return await ctx.reply("```only basic math operations allowed```")
            # Use ast.literal_eval for safety
            result = eval(expression, {"__builtins__": None}, {})
            self.logger.debug(f"Calculation: {expression} = {result}")
            await ctx.reply(f"```{expression} = {result}```")
        except Exception as e:
            self.logger.warning(f"Invalid expression: {expression} - {str(e)}")
            await ctx.reply("```invalid expression```")
    
    @commands.command()
    async def uptime(self, ctx):
        """show bot uptime"""
        delta = datetime.datetime.now() - self.bot.launch_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        self.logger.debug(f"Uptime requested: {days}d {hours}h {minutes}m {seconds}s")
        embed = nextcord.Embed(description=f"```{days} days, {hours} hours, {minutes} minutes, {seconds} seconds```", color=0x2b2d31)
        await ctx.reply(embed=embed)

    @commands.command(aliases=['time'])
    async def timestamp(self, ctx, style: str = 'f'):
        """generate discord timestamps"""
        valid = ['t', 'T', 'd', 'D', 'f', 'F', 'R']
        if style not in valid:
            self.logger.warning(f"Invalid timestamp style: {style}")
            return await ctx.reply(f"```invalid style. choose from: {', '.join(valid)}```")
        now = int(datetime.datetime.now().timestamp())
        self.logger.debug(f"Generated timestamp style {style} for {ctx.author}")
        await ctx.reply(f"```<t:{now}:{style}> → <t:{now}:{style}>```\n`copy-paste the gray part`")

    @commands.command(aliases=['timeleft'])
    async def countdown(self, ctx, future_time: str):
        """calculate time remaining"""
        try:
            target = datetime.datetime.strptime(future_time, "%Y-%m-%d")
            delta = target - datetime.datetime.now()
            self.logger.info(f"Countdown calculated: {delta.days} days remaining")
            await ctx.reply(f"```{delta.days} days remaining```")
        except ValueError:
            self.logger.warning(f"Invalid date format: {future_time}")
            await ctx.reply("```invalid format. use YYYY-MM-DD```")
        except Exception as e:
            self.logger.error(f"Countdown error: {str(e)}", exc_info=True)
            await ctx.reply(f"```{e}```")
    
    @commands.command(aliases=['shorten'])
    async def tinyurl(self, ctx, *, url: str):
        """Shorten a URL using TinyURL."""
        if not url.startswith(('http://', 'https://')):
            url = f'https://{url}'
        self.logger.debug(f"URL shortening requested for: {url}")

        if not hasattr(self.bot, 'session'):
            return await ctx.reply("```URL shortening unavailable (no session)```")

        try:
            async with self.bot.session.get(f"https://tinyurl.com/api-create.php?url={url}") as resp:
                result = await resp.text()
                self.logger.debug(f"URL shortened to: {result}")
                await ctx.reply(f"```{result}```")
        except Exception as e:
            self.logger.error(f"URL shortening failed: {str(e)}")
            await ctx.reply("```URL shortening failed```")

    @commands.command()
    async def lottery(self, ctx, max_num: int = 100, picks: int = 6):
        """generate lottery numbers"""
        if picks > max_num:
            self.logger.warning(f"Invalid lottery params: picks={picks} > max={max_num}")
            return await ctx.reply("```picks cannot exceed max number```")
        nums = random.sample(range(1, max_num+1), picks)
        self.logger.debug(f"Generated lottery numbers: {nums}")
        await ctx.reply(f"```{' '.join(map(str, sorted(nums)))}```")

    @commands.command(aliases=['color'])
    async def hexcolor(self, ctx, hex_code: str=None):
        """show a color preview"""
        if not hex_code:
            hex_code = "%06x" % random.randint(0, 0xFFFFFF)
        else:
            hex_code = hex_code.strip('#')
            if len(hex_code) not in (3, 6):
                self.logger.warning(f"Invalid hex code: {hex_code}")
                return await ctx.reply("```invalid hex code```")
            self.logger.debug(f"Color preview generated for: #{hex_code}")
        url = f"https://singlecolorimage.com/get/{hex_code}/200x200"
        embed = nextcord.Embed(color=int(hex_code.ljust(6, '0'), 16))
        embed.set_image(url=url)
        await ctx.reply(embed=embed)

    @commands.command(aliases=['steal', 'stl', 'addemoji'])
    @commands.has_permissions(manage_emojis=True)
    async def emojisteal(self, ctx, emoji: nextcord.PartialEmoji):
        """add an emoji to this server"""
        self.logger.info(f"Emoji steal attempted: {emoji.name}")
        
        # Check if bot has aiohttp session
        if not hasattr(self.bot, 'session'):
            return await ctx.reply("```emoji stealing unavailable```")
            
        try:
            async with self.bot.session.get(emoji.url) as resp:
                if resp.status != 200:
                    self.logger.error(f"Failed to download emoji: {emoji.url}")
                    return await ctx.reply("```failed to download emoji```")
                data = await resp.read()
            
            added = await ctx.guild.create_custom_emoji(
                name=emoji.name,
                image=data
            )
            self.logger.info(f"Emoji added: {added}")
            await ctx.reply(f"```added emoji: {added}```")
        except Exception as e:
            self.logger.error(f"Emoji add failed: {str(e)}", exc_info=True)
            await ctx.reply("```missing permissions or slot full```")

    @commands.command(aliases=['firstmsg'])
    async def firstmessage(self, ctx, channel: nextcord.TextChannel = None):
        """Fetch a channel's first message."""
        channel = channel or ctx.channel
        self.logger.debug(f"First message requested in #{channel.name}")
        try:
            async for msg in channel.history(limit=1, oldest_first=True):
                return await ctx.reply(f"```first message in #{channel.name}```\n{msg.jump_url}")
            await ctx.reply(f"```No messages found in #{channel.name}```")
        except Exception as e:
            self.logger.error(f"Failed to fetch first message: {e}")
            await ctx.reply("```Failed to fetch first message```")

    @commands.command(aliases=['remindme_old', 'remind_old'])
    async def reminder_old(self, ctx, time: str=None, *, message: str="You asked me to remind you, but didnt give me a reason."):
        """Legacy reminder command (use new .remind command for better features)"""
        embed = nextcord.Embed(
            title="⏰ Legacy Reminder Disabled",
            description=(
                "This legacy reminder command has been replaced with a better version!\n\n"
                "**Use the new reminder system:**\n"
                "• `.remind <time> <message>` - Set a reminder\n"
                "• `.myreminders` - View your reminders\n"
                "• `.cancelreminder <number>` - Cancel a reminder\n\n"
                "**New features:**\n"
                "• Persistent reminders (survive bot restarts)\n"
                "• Up to 2 years duration\n"
                "• Flexible time formats (1Y 6M 2d 5h 30m)\n"
                "• Better time parsing"
            ),
            color=0x2b2d31
        )
        await ctx.reply(embed=embed)

    @commands.command()
    async def multipoll(self, ctx, question: str, *options):
        """Create a poll with multiple options. Example: .multipoll "Favorite?" "Red" "Blue" "Green" """
        if len(options) < 2 or len(options) > 10:
            return await ctx.reply("You need 2-10 options.")
        emojis = ['1️⃣','2️⃣','3️⃣','4️⃣','5️⃣','6️⃣','7️⃣','8️⃣','9️⃣','🔟']
        desc = "\n".join(f"{emojis[i]} {opt}" for i, opt in enumerate(options))
        embed = nextcord.Embed(title=question, description=desc, color=0x2b2d31)
        msg = await ctx.send(embed=embed)
        for i in range(len(options)):
            await msg.add_reaction(emojis[i])

    @commands.command()
    async def roleinfo(self, ctx, *, role: nextcord.Role):
        """Show info about a role."""
        embed = nextcord.Embed(
            title=f"Role: {role.name}",
            color=role.color
        )
        embed.add_field(name="ID", value=role.id)
        embed.add_field(name="Members", value=len(role.members))
        embed.add_field(name="Mentionable", value=role.mentionable)
        embed.add_field(name="Hoisted", value=role.hoist)
        embed.add_field(name="Position", value=role.position)
        embed.add_field(name="Created", value=role.created_at.strftime('%Y-%m-%d'))
        embed.set_footer(text=f"Color: {role.color}")
        await ctx.reply(embed=embed)

    @commands.command()
    async def banner(self, ctx, user: nextcord.Member = None):
        """Show a user's banner."""
        user = user or ctx.author
        user = await ctx.guild.fetch_member(user.id)
        banner = user.banner
        if banner:
            embed = nextcord.Embed(title=f"{user.display_name}'s Banner", color=user.color)
            embed.set_image(url=banner.url)
            await ctx.reply(embed=embed)
        else:
            await ctx.reply("User has no banner.")

    @commands.command()
    async def emojiinfo(self, ctx, emoji: nextcord.PartialEmoji):
        """Show info about a custom emoji."""
        embed = nextcord.Embed(title=f"Emoji: {emoji.name}", color=0x2b2d31)
        embed.add_field(name="ID", value=emoji.id)
        embed.add_field(name="Animated", value=emoji.animated)
        embed.add_field(name="URL", value=emoji.url)
        embed.set_image(url=emoji.url)
        await ctx.reply(embed=embed)

    @commands.command()
    async def servericon(self, ctx):
        """Get the server's icon."""
        if ctx.guild.icon:
            await ctx.reply(ctx.guild.icon.url)
        else:
            await ctx.reply("This server has no icon.")

    @commands.command()
    async def serverbanner(self, ctx):
        """Get the server's banner."""
        if ctx.guild.banner:
            await ctx.reply(ctx.guild.banner.url)
        else:
            await ctx.reply("This server has no banner.")

    # --- AFK System ---

    @commands.command()
    async def afk(self, ctx, *, reason="AFK"):
        """Set your AFK status."""
        self.afk_users[ctx.author.id] = reason
        await ctx.reply(f"{ctx.author.mention} is now AFK: {reason}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return
        # Remove AFK if user sends a message
        if message.author.id in self.afk_users:
            del self.afk_users[message.author.id]
            try:
                await message.reply("Welcome back! Removed your AFK.")
            except Exception:
                pass
        # Notify if mentioning AFK users
        for user_id in self.afk_users:
            if f"<@{user_id}>" in message.content or f"<@!{user_id}>" in message.content:
                reason = self.afk_users[user_id]
                await message.channel.send(f"<@{user_id}> is AFK: {reason}")
                break

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if message.guild:
            guild_id = message.guild.id
            channel_id = message.channel.id
            if guild_id not in self.last_deleted:
                self.last_deleted[guild_id] = {}
            self.last_deleted[guild_id][channel_id] = (message, datetime.datetime.now())

    @commands.command()
    async def admins(self, ctx):
        """List all server admins with interactive filters and role details.
        
        Features:
        • Filter by users, bots, or all members
        • Browse admin roles with member counts
        • View detailed role member lists
        • Paginated role selection (24 roles per page)
        """
        view = AdminView(ctx)
        embed = await view.create_embed()
        await ctx.reply(embed=embed, view=view)

    @commands.command()
    async def snipe(self, ctx):
        """Show the last deleted message in this channel (within 1 hour)."""
        guild_id = ctx.guild.id
        channel_id = ctx.channel.id
        entry = self.last_deleted.get(guild_id, {}).get(channel_id)
        if entry:
            msg, deleted_at = entry
            # Only show if deleted within the last hour
            if (datetime.datetime.now() - deleted_at).total_seconds() <= 3600:
                embed = nextcord.Embed(description=msg.content, color=0x2b2d31)
                embed.set_author(name=str(msg.author), icon_url=msg.author.display_avatar.url)
                embed.timestamp = msg.created_at
                await ctx.reply(embed=embed)
                return
        await ctx.reply("Nothing to snipe in the past hour!")

    @commands.command()
    async def botinfo(self, ctx):
        """Show bot statistics and info."""
        delta = datetime.datetime.now() - self.bot.launch_time
        total_seconds = int(delta.total_seconds())
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days} days, {hours} hours, {minutes} minutes, {seconds} seconds"

        embed = nextcord.Embed(
            title="Bot Info",
            color=0x2b2d31,
            description=f"Uptime: {uptime_str}"
        )
        embed.add_field(name="Servers", value=len(self.bot.guilds))
        embed.add_field(name="Users", value=len(set(self.bot.get_all_members())))
        embed.add_field(name="Commands", value=len(self.bot.commands))
        embed.set_footer(text=f"ID: {self.bot.user.id}")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        await ctx.reply(embed=embed)

    @commands.Cog.listener() 
    async def on_command_error(self, ctx, error):
        if ctx.command and ctx.command.cog_name == self.__class__.__name__:
            await self.handle_error(ctx, error)

    def get_command_help(self) -> list[nextcord.Embed]:
        """Get paginated help embeds for this cog"""
        pages = []
        
        # Server Info Commands Page
        info_embed = nextcord.Embed(
            title="🔧 Utility Commands - Information",
            color=nextcord.Color.blue()
        )
        info_commands = ['serverinfo', 'userinfo', 'avatar', 'uptime']
        for cmd_name in info_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                info_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(info_embed)

        # Time Commands Page
        time_embed = nextcord.Embed(
            title="🔧 Utility Commands - Time",
            color=nextcord.Color.blue()
        )
        time_commands = ['timestamp', 'countdown', 'uptime']
        for cmd_name in time_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                time_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(time_embed)

        # Misc Utility Commands Page
        misc_embed = nextcord.Embed(
            title="🔧 Utility Commands - Miscellaneous",
            color=nextcord.Color.blue()
        )
        misc_commands = ['ping', 'calculate', 'tinyurl', 'hexcolor']
        for cmd_name in misc_commands:
            cmd = self.bot.get_command(cmd_name)
            if cmd:
                misc_embed.add_field(
                    name=f"{cmd.name} {cmd.signature}",
                    value=cmd.help or "No description",
                    inline=False
                )
        pages.append(misc_embed)

        return pages

    @commands.command(name='botrestart', aliases=['reboot'])
    @commands.is_owner()
    async def restart(self, ctx):
        """Smart bot restart that waits for optimal conditions (renamed from restart for music priority)"""
        await self._smart_restart(ctx)

    async def _smart_restart(self, ctx):
        """Perform intelligent restart with activity checking"""
        try:
            # Check for active games and activities
            blocking_activities = await self._check_blocking_activities()
            
            if not blocking_activities:
                # Safe to restart immediately
                embed = nextcord.Embed(
                    title="🔄 Restarting Bot",
                    description="No active games detected. Restarting now...",
                    color=nextcord.Color.green()
                )
                await ctx.reply(embed=embed)
                
                # Give a moment for the message to send
                await asyncio.sleep(2)
                await self._perform_restart()
                return
            
            # Calculate estimated wait time
            estimated_wait = await self._estimate_wait_time(blocking_activities)
            
            # Show blocking activities and estimated time
            embed = nextcord.Embed(
                title="⏳ Restart Delayed",
                description="Bot will restart when activities complete",
                color=nextcord.Color.orange()
            )
            
            # List blocking activities
            activities_text = ""
            for activity in blocking_activities:
                activities_text += f"• {activity['type']}: {activity['description']}\n"
            
            embed.add_field(
                name="🎮 Active Games/Activities",
                value=activities_text,
                inline=False
            )
            
            embed.add_field(
                name="⏰ Estimated Wait Time",
                value=f"Approximately {estimated_wait} minutes",
                inline=True
            )
            
            embed.add_field(
                name="🔄 Auto-Restart",
                value="Bot will restart automatically when safe",
                inline=True
            )
            
            embed.set_footer(text="Use 'restart force' to override (not recommended)")
            
            message = await ctx.reply(embed=embed)
            
            # Start monitoring for restart opportunity
            await self._monitor_for_restart(ctx, message)
            
        except Exception as e:
            self.logger.error(f"Smart restart error: {e}")
            await ctx.reply("❌ Error during restart process")

    async def _check_blocking_activities(self):
        """Check for activities that should block restart"""
        blocking_activities = []
        
        try:
            # Check gambling games
            gambling_cog = self.bot.get_cog("Gambling")
            if gambling_cog and hasattr(gambling_cog, 'active_games'):
                if gambling_cog.active_games:
                    blocking_activities.append({
                        'type': 'Gambling Games',
                        'description': f"{len(gambling_cog.active_games)} active gambling games",
                        'count': len(gambling_cog.active_games)
                    })
            
            # Check multiplayer games
            multiplayer_cog = self.bot.get_cog("Multiplayer")
            if multiplayer_cog and hasattr(multiplayer_cog, 'active_games'):
                if multiplayer_cog.active_games:
                    blocking_activities.append({
                        'type': 'Multiplayer Games',
                        'description': f"{len(multiplayer_cog.active_games)} active multiplayer games",
                        'count': len(multiplayer_cog.active_games)
                    })
            
            # Check vote bans
            voteban_cog = self.bot.get_cog("VoteBans")
            if voteban_cog and hasattr(voteban_cog, 'vote_data'):
                active_votes = sum(1 for vote in voteban_cog.vote_data.values() 
                                 if not vote.get("completed", True))
                if active_votes > 0:
                    blocking_activities.append({
                        'type': 'Vote Bans',
                        'description': f"{active_votes} active vote ban(s)",
                        'count': active_votes
                    })
            
            # Check giveaways
            giveaway_cog = self.bot.get_cog("Giveaway")
            if giveaway_cog and hasattr(giveaway_cog, 'active_giveaways'):
                if giveaway_cog.active_giveaways:
                    blocking_activities.append({
                        'type': 'Giveaways',
                        'description': f"{len(giveaway_cog.active_giveaways)} active giveaway(s)",
                        'count': len(giveaway_cog.active_giveaways)
                    })
            
            # Check critical background tasks
            critical_tasks = await self._check_critical_tasks()
            if critical_tasks:
                blocking_activities.append({
                    'type': 'Background Tasks',
                    'description': f"{len(critical_tasks)} critical tasks running",
                    'count': len(critical_tasks)
                })
            
        except Exception as e:
            self.logger.error(f"Error checking blocking activities: {e}")
        
        return blocking_activities

    async def _check_critical_tasks(self):
        """Check for critical background tasks that shouldn't be interrupted"""
        critical_tasks = []
        
        try:
            # Check for active loops in cogs
            for cog_name, cog in self.bot.cogs.items():
                # Check for running tasks/loops
                if hasattr(cog, 'check_giveaways') and not cog.check_giveaways.is_running():
                    continue
                elif hasattr(cog, 'verify_reactions') and cog.verify_reactions.is_running():
                    critical_tasks.append(f"{cog_name} - Reaction Verification")
                elif hasattr(cog, 'reset_bazaar') and cog.reset_bazaar.is_running():
                    critical_tasks.append(f"{cog_name} - Bazaar Reset")
                elif hasattr(cog, 'process_message_edits'):
                    # Check if there are pending edits
                    if hasattr(cog, 'message_edit_queue') and not cog.message_edit_queue.empty():
                        critical_tasks.append(f"{cog_name} - Message Edit Queue")
        
        except Exception as e:
            self.logger.error(f"Error checking critical tasks: {e}")
        
        return critical_tasks

    async def _estimate_wait_time(self, blocking_activities):
        """Estimate how long until restart conditions are met"""
        max_wait = 0
        
        for activity in blocking_activities:
            activity_type = activity['type']
            count = activity.get('count', 1)
            
            if activity_type == 'Gambling Games':
                # Most gambling games finish within 5 minutes
                max_wait = max(max_wait, 5)
            elif activity_type == 'Multiplayer Games':
                # Multiplayer games can take 10-15 minutes
                max_wait = max(max_wait, 15)
            elif activity_type == 'Vote Bans':
                # Vote bans can take a while if not enough votes
                max_wait = max(max_wait, 30)
            elif activity_type == 'Giveaways':
                # Check actual giveaway end times if possible
                giveaway_cog = self.bot.get_cog("Giveaway")
                if giveaway_cog and hasattr(giveaway_cog, 'active_giveaways'):
                    try:
                        from datetime import datetime
                        now = datetime.now()
                        max_giveaway_wait = 0
                        
                        for giveaway in giveaway_cog.active_giveaways.values():
                            if 'end_time' in giveaway:
                                end_time = giveaway['end_time']
                                if hasattr(end_time, 'timestamp'):
                                    wait_minutes = (end_time - now).total_seconds() / 60
                                    max_giveaway_wait = max(max_giveaway_wait, wait_minutes)
                        
                        max_wait = max(max_wait, max_giveaway_wait)
                    except:
                        max_wait = max(max_wait, 60)  # Fallback
            elif activity_type == 'Background Tasks':
                # Background tasks usually finish quickly
                max_wait = max(max_wait, 2)
        
        return max(1, int(max_wait))  # At least 1 minute

    async def _monitor_for_restart(self, ctx, status_message):
        """Monitor activities and restart when safe"""
        check_interval = 30  # Check every 30 seconds
        max_wait_time = 3600  # Maximum 1 hour wait
        elapsed_time = 0
        
        while elapsed_time < max_wait_time:
            await asyncio.sleep(check_interval)
            elapsed_time += check_interval
            
            # Check if conditions are now safe
            blocking_activities = await self._check_blocking_activities()
            
            if not blocking_activities:
                # Conditions are now safe - restart
                embed = nextcord.Embed(
                    title="🔄 Restarting Bot",
                    description="All activities completed. Restarting now...",
                    color=nextcord.Color.green()
                )
                embed.add_field(
                    name="⏰ Wait Time",
                    value=f"Waited {elapsed_time // 60} minutes {elapsed_time % 60} seconds",
                    inline=True
                )
                
                try:
                    await status_message.edit(embed=embed)
                except:
                    await ctx.send(embed=embed)
                
                await asyncio.sleep(2)
                await self._perform_restart()
                return
            
            # Update status every 5 minutes
            if elapsed_time % 300 == 0:  # Every 5 minutes
                try:
                    updated_wait = await self._estimate_wait_time(blocking_activities)
                    
                    embed = nextcord.Embed(
                        title="⏳ Still Waiting to Restart",
                        description="Monitoring activities for safe restart window",
                        color=nextcord.Color.orange()
                    )
                    
                    activities_text = ""
                    for activity in blocking_activities:
                        activities_text += f"• {activity['type']}: {activity['description']}\n"
                    
                    embed.add_field(
                        name="🎮 Remaining Activities",
                        value=activities_text,
                        inline=False
                    )
                    
                    embed.add_field(
                        name="⏰ Elapsed Time",
                        value=f"{elapsed_time // 60} minutes",
                        inline=True
                    )
                    
                    embed.add_field(
                        name="📊 Estimated Remaining",
                        value=f"~{updated_wait} minutes",
                        inline=True
                    )
                    
                    await status_message.edit(embed=embed)
                except Exception as e:
                    self.logger.error(f"Error updating restart status: {e}")
        
        # Timeout reached
        embed = nextcord.Embed(
            title="⚠️ Restart Timeout",
            description="Maximum wait time exceeded. Consider using 'restart force'",
            color=nextcord.Color.red()
        )
        embed.add_field(
            name="⏰ Total Wait Time",
            value="1 hour (maximum)",
            inline=True
        )
        
        try:
            await status_message.edit(embed=embed)
        except:
            await ctx.send(embed=embed)

    async def _perform_restart(self):
        """Actually restart the bot"""
        try:
            self.logger.info("Performing bot restart...")
            
            # Close background tasks gracefully
            await self._graceful_shutdown()
            
            # Restart the bot
            import os
            import sys
            os.execv(sys.executable, ['python'] + sys.argv)
            
        except Exception as e:
            self.logger.error(f"Restart failed: {e}")

    async def _graceful_shutdown(self):
        """Gracefully shutdown background tasks"""
        try:
            # Stop all running tasks in cogs
            for cog_name, cog in self.bot.cogs.items():
                if hasattr(cog, 'cog_unload'):
                    try:
                        cog.cog_unload()
                    except Exception as e:
                        self.logger.warning(f"Error unloading {cog_name}: {e}")
            
            # Close aiohttp session if it exists
            if hasattr(self.bot, 'session') and self.bot.session:
                await self.bot.session.close()
                
        except Exception as e:
            self.logger.error(f"Error during graceful shutdown: {e}")

    @commands.command()
    @commands.is_owner()
    async def restart_force(self, ctx):
        """Force restart immediately (not recommended during active games)"""
        embed = nextcord.Embed(
            title="⚠️ Force Restart",
            description="This will restart immediately, potentially disrupting active games!",
            color=nextcord.Color.red()
        )
        
        view = RestartConfirmView(self, ctx)
        await ctx.reply(embed=embed, view=view)

    @commands.command(name="quickhelp", aliases=['qh', 'info'])
    async def quickhelp(self, ctx):
        """Quick help command with essential information"""
        embed = nextcord.Embed(
            title="🤖 BronxBot Quick Help",
            description="Essential commands and information",
            color=0x2b2d31
        )
        
        embed.add_field(
            name="📋 Basic Commands",
            value=(
                "`!help` - Full help menu\n"
                "`!ping` - Check bot latency\n"
                "`!avatar` - Show user avatar\n"
                "`!balance` - Check economy balance"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎮 Economy",
            value=(
                "`!work` - Earn money\n"
                "`!daily` - Daily rewards\n"
                "`!shop` - Browse shop\n"
                "`!fish` - Go fishing"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎵 Music",
            value=(
                "`!play <song>` - Play music\n"
                "`!queue` - Show queue\n"
                "`!skip` - Skip current song\n"
                "`!stop` - Stop playback"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🔗 Links",
            value=(
                f"[Invite Bot](https://discord.com/api/oauth2/authorize?client_id={self.bot.user.id}&permissions=8&scope=bot)\n"
                "[Support Server](https://discord.gg/bronx)\n"
                "Use `!help` for complete command list"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"BronxBot • {len(self.bot.guilds)} servers")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        await ctx.reply(embed=embed)
        self.logger.info(f"Quick help shown to {ctx.author}")

    @commands.command(name="sync_commands", aliases=['synchere', 'refresh'])
    @commands.has_permissions(administrator=True)
    async def sync_commands_here(self, ctx):
        """Sync slash commands to this server (Admin only)"""
        if not ctx.guild:
            return await ctx.reply("❌ This command can only be used in a server!")
        
        # Check if user is bot owner or has admin perms
        if ctx.author.id not in self.bot.owner_ids and not ctx.author.guild_permissions.administrator:
            return await ctx.reply("❌ You need Administrator permissions to use this command!")
        
        try:
            # Send initial message
            msg = await ctx.reply("🔄 Syncing slash commands to this server...")
            
            # Debug: Check commands before sync
            all_commands = self.bot.get_all_application_commands()
            self.logger.info(f"About to sync to guild {ctx.guild.id}")
            self.logger.info(f"Available commands before sync: {len(all_commands)}")
            for cmd in all_commands:
                guild_info = getattr(cmd, 'guild_ids', None) or 'Global'
                self.logger.info(f"  - {cmd.name} (Guild: {guild_info})")
            
            # Sync commands
            synced = await self.bot.sync_application_commands(guild_id=ctx.guild.id)
            synced_count = len(synced) if synced else 0
            
            self.logger.info(f"Sync result type: {type(synced)}")
            self.logger.info(f"Sync result: {synced}")
            self.logger.info(f"Synced count: {synced_count}")
            
            # Update message with result
            embed = nextcord.Embed(
                title="✅ Slash Commands Synced!",
                description=f"Successfully synced **{synced_count}** slash commands to **{ctx.guild.name}**",
                color=0x00ff00
            )
            embed.add_field(
                name="ℹ️ Note", 
                value="Slash commands should now be available in this server!",
                inline=False
            )
            embed.set_footer(text="Changes are instant for guild-specific syncs")
            
            await msg.edit(content=None, embed=embed)
            self.logger.info(f"Synced {synced_count} slash commands to guild {ctx.guild.name} ({ctx.guild.id}) by {ctx.author}")
            
        except Exception as e:
            await ctx.reply(f"❌ Error syncing slash commands: {str(e)}")
            self.logger.error(f"Error syncing slash commands to guild: {e}")

    @commands.command(name="commands", aliases=['cmdlist', 'textcommands'])
    async def list_commands(self, ctx):
        """Show a list of available text commands"""
        embed = nextcord.Embed(
            title="📝 Text Commands",
            description="List of available prefix commands",
            color=0x2b2d31
        )
        
        # Get all commands and organize by cog
        cog_commands = {}
        for command in self.bot.commands:
            if command.hidden:
                continue
                
            cog_name = command.cog.qualified_name if command.cog else "No Category"
            if cog_name not in cog_commands:
                cog_commands[cog_name] = []
            cog_commands[cog_name].append(f"`{command.name}`")
        
        # Add fields for each cog (limit to important ones)
        important_cogs = [
            "Utility", "Economy", "Help", "Music", "Fun", 
            "Moderation", "Admin", "Gambling", "Trading"
        ]
        
        for cog_name in important_cogs:
            if cog_name in cog_commands:
                commands_list = cog_commands[cog_name][:10]  # Limit to 10 commands
                if len(cog_commands[cog_name]) > 10:
                    commands_list.append("...")
                
                embed.add_field(
                    name=f"🔧 {cog_name}",
                    value=" ".join(commands_list) if commands_list else "None",
                    inline=True
                )
        
        embed.add_field(
            name="ℹ️ Usage",
            value=(
                f"Use `{ctx.prefix}help <command>` for detailed help\n"
                f"Use `{ctx.prefix}help` for the full interactive help menu"
            ),
            inline=False
        )
        
        embed.set_footer(text=f"Prefix: {ctx.prefix} • Use /help for slash commands")
        
        await ctx.reply(embed=embed)
        self.logger.info(f"Command list shown to {ctx.author}")

async def setup(bot):
    logger = CogLogger("Utility")
    try:
        bot.add_cog(Utility(bot))
    except Exception as e:
        logger.error(f"Failed to load Utility cog: {e}")
        raise
