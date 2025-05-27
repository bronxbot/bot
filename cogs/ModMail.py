import discord
from discord.ext import commands
import logging
import json
import os
import random
import sys
from utils.error_handler import ErrorHandler

with open("data/config.json", "r") as f:
    config = json.load(f)

class ModMail(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.staff_channel_id = 1259717946947670099
        self.data_file = "data/modmail.json"
        self.allowed_guilds = [1259717095382319215, 1299747094449623111, 1142088882222022786]
        
        # Ensure data directory exists
        os.makedirs("data", exist_ok=True)
        
        # Simple logger setup - avoid complex custom logger for now
        self.logger = logging.getLogger(f"ModMail")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.active_tickets = self.load_data()
        self.logger.info("ModMail cog initialized")
    
    def load_data(self):
        """Load active tickets from JSON file"""
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    # Convert thread IDs to integers (JSON stores them as strings)
                    return {k: int(v) for k, v in data.items()}
            return {}
        except Exception as e:
            self.logger.error(f"Failed to load modmail data: {e}")
            return {}
    
    def save_data(self):
        """Save active tickets to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.active_tickets, f)
        except Exception as e:
            self.logger.error(f"Failed to save modmail data: {e}")
    
    @commands.Cog.listener()
    async def on_ready(self):
        self.logger.info(f"ModMail cog ready. Logged in as {self.bot.user}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return
        if message.author.bot:
            return
        
        # Handle DM messages
        if isinstance(message.channel, discord.DMChannel):
            if str(message.author.id) not in self.active_tickets:
                # Check for a simple "help" message
                if message.content.lower().strip() == "help":
                    if not await self.can_use_modmail(message.author):
                        embed = discord.Embed(
                            description="Sorry, ModMail is only available to members of our servers.",
                            color=discord.Color.red()
                        )
                    else:
                        embed = discord.Embed(
                            description="To create a modmail ticket, send a message containing your issue.\nExample: `I need help with...`",
                            color=discord.Color.blue()
                        )
                    await message.author.send(embed=embed)
                else:
                    await self.create_new_modmail(message)
            else:
                await self.forward_to_thread(message)
        
        # Handle staff replies in threads
        elif (isinstance(message.channel, discord.Thread) and 
              message.channel.parent_id == self.staff_channel_id and
              not message.author.bot) and message.content[0] != ".":
            await self.handle_staff_reply(message)
        
        # Handle message stats for specific guilds
        elif message.guild and message.guild.id in self.allowed_guilds:
            await self.update_message_stats(message)
    
    
    async def update_message_stats(self, message):
        """Update message statistics"""
        try:
            os.makedirs("data", exist_ok=True)
            stats_file = "data/stats.json"
            
            # Load existing data or create new structure
            if os.path.exists(stats_file):
                with open(stats_file, "r") as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Ensure required structures exist
            if "stats" not in data:
                data["stats"] = {}
            if "guilds" not in data:
                data["guilds"] = []
            
            # Initialize guild stats if not exists
            guild_id = str(message.guild.id)
            if guild_id not in data["stats"]:
                data["stats"][guild_id] = {
                    "messages": 0,
                    "name": message.guild.name,
                    "last_message": discord.utils.utcnow().isoformat()
                }
            
            # Update message count and last message time
            data["stats"][guild_id]["messages"] += 1
            data["stats"][guild_id]["last_message"] = discord.utils.utcnow().isoformat()
            
            # Ensure guild is in guilds list
            if guild_id not in data["guilds"]:
                data["guilds"].append(guild_id)
            
            # Save the updated data
            with open(stats_file, "w") as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            self.logger.error(f"Failed to update stats for guild {message.guild.id}: {e}")
    
    async def can_use_modmail(self, user: discord.User) -> bool:
        """Check if user is in any of the allowed guilds"""
        for guild_id in self.allowed_guilds:
            guild = self.bot.get_guild(guild_id)
            if guild and guild.get_member(user.id):
                return True
        return False
    
    async def create_new_modmail(self, user_message):
        """Create a new modmail thread for a user's DM"""
        try:
            # Check if user is allowed to use modmail
            if not await self.can_use_modmail(user_message.author):
                embed = discord.Embed(
                    title="Access Denied",
                    description="You must be a member of one of our servers to use ModMail.",
                    color=discord.Color.red()
                )
                await user_message.author.send(embed=embed)
                return

            staff_channel = self.bot.get_channel(self.staff_channel_id)
            if staff_channel is None:
                self.logger.error(f"Staff channel {self.staff_channel_id} not found!")
                return
            
            # Check if user already has an active ticket
            if str(user_message.author.id) in self.active_tickets:
                return
            
            embed = discord.Embed(
                title=f"New Modmail from {user_message.author}",
                description=user_message.content,
                color=0x00ff00
            )
            
            # Handle avatar URL safely
            if user_message.author.avatar:
                embed.set_thumbnail(url=user_message.author.avatar.url)
            
            embed.add_field(name="User ID", value=str(user_message.author.id), inline=False)
            embed.add_field(name="Account Created", value=user_message.author.created_at.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
            
            staff_msg = await staff_channel.send(embed=embed)
            thread = await staff_msg.create_thread(
                name=f"Modmail {user_message.author}",
                auto_archive_duration=1440
            )
            
            # Save thread ID and send confirmation
            self.active_tickets[str(user_message.author.id)] = thread.id
            self.save_data()  # Make sure to save after updating
            
            user_embed = discord.Embed(
                title="Modmail Received",
                description="Your message has been received by our staff team. "
                            "Please wait for a response. You can send additional "
                            "messages in this DM and they will be forwarded.",
                color=0x00ff00
            )
            await user_message.author.send(embed=user_embed)
            self.logger.info(f"Created new modmail for {user_message.author}")
            
        except Exception as e:
            self.logger.error(f"Failed to create modmail: {e}")
            try:
                await user_message.author.send("Failed to create your modmail ticket. Please try again later.")
            except:
                pass
    
    async def forward_to_thread(self, user_message):
        """Forward subsequent DMs to the existing thread"""
        thread_id = self.active_tickets.get(str(user_message.author.id))
        if not thread_id:
            self.logger.error(f"No thread ID found for user {user_message.author.id}")
            return
            
        try:
            thread = await self.bot.fetch_channel(thread_id)
            if thread is None:
                self.logger.error(f"Thread {thread_id} not found!")
                del self.active_tickets[str(user_message.author.id)]
                self.save_data()
                return
                
            embed = discord.Embed(
                description=user_message.content,
                color=0x7289da,
                timestamp=user_message.created_at
            )
            
            # Handle avatar URL safely
            avatar_url = None
            if user_message.author.avatar:
                avatar_url = user_message.author.avatar.url
            
            embed.set_author(name=str(user_message.author), icon_url=avatar_url)
            
            if user_message.attachments:
                attachment_urls = []
                for attachment in user_message.attachments:
                    attachment_urls.append(f"[{attachment.filename}]({attachment.url})")
                embed.add_field(name="Attachments", value="\n".join(attachment_urls), inline=False)
            
            msg = await thread.send(embed=embed)
            await msg.add_reaction("✅")
            
        except discord.NotFound:
            self.logger.error(f"Thread {thread_id} not found (404)")
            del self.active_tickets[str(user_message.author.id)]
            self.save_data()
            try:
                await user_message.author.send("Your previous modmail thread was not found. A new one will be created if you send another message.")
            except:
                pass
        except Exception as e:
            self.logger.error(f"Failed to forward message: {e}")
            try:
                await user_message.author.send("Failed to forward your message to staff. Please try again later.")
            except:
                pass
    
    async def handle_staff_reply(self, staff_message):
        """Handle staff replies in modmail threads"""
        try:
            if staff_message.content.startswith("!"):
                return
            
            # Staff roles mapping
            staffroles = {
                "owner": 1281553341100457995,
                "co-owner": 1262995584231669770,
                "admin": 1292612655261155428,
                "head mod": 1259718732163321906,
                "mod": 1266510089683079330,
                "trial mod": 1259718795556028446,
                "helper": 1362671155730972733,
                "staff": 1259728436377817100
            }
            
            staffrank = None
            author_role_ids = {role.id for role in staff_message.author.roles}
            
            for role_name, role_id in staffroles.items():
                if role_id in author_role_ids:
                    staffrank = role_name
                    break
            
            if not staffrank:
                return

            # Find the user for this thread
            user_id = None
            for uid, tid in self.active_tickets.items():
                if tid == staff_message.channel.id:
                    user_id = int(uid)
                    break
            
            if not user_id:
                return
                
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            embed = discord.Embed(
                description=staff_message.content,
                color=0x7289da,
                timestamp=staff_message.created_at
            )
            
            # Handle avatar URL safely
            avatar_url = None
            if staff_message.author.avatar:
                avatar_url = staff_message.author.avatar.url
            
            embed.set_author(
                name=f"{staff_message.author} ({staffrank.capitalize()})",
                icon_url=avatar_url
            )
            
            if staff_message.attachments:
                attachment_urls = []
                for attachment in staff_message.attachments:
                    attachment_urls.append(f"[{attachment.filename}]({attachment.url})")
                embed.add_field(name="Attachments", value="\n".join(attachment_urls), inline=False)
            
            await user.send(embed=embed)
            await staff_message.add_reaction("✅")
            
        except discord.Forbidden:
            await staff_message.add_reaction("❌")
            await staff_message.channel.send("Failed to send message to user (user has DMs disabled)")
        except Exception as e:
            self.logger.error(f"Failed to handle staff reply: {e}")
            await staff_message.add_reaction("❌")
            await staff_message.channel.send(f"Failed to send message to user: {str(e)}")
    
    @commands.command(name="open", aliases=["openmail", "openmodmail", "omm", "mods"])
    async def open_modmail(self, ctx, *, message=None):
        """Open a new modmail thread"""
        # Check if user is allowed to use modmail
        if not await self.can_use_modmail(ctx.author):
            await ctx.reply("You must be a member of one of our servers to use ModMail.")
            return

        if not message or len(message) < 15:
            return await ctx.reply("Please give a reason to open a new modmail thread. Don't spam it please.")
        
        # Check if user already has an active ticket
        if str(ctx.author.id) in self.active_tickets:
            try:
                thread = await self.bot.fetch_channel(self.active_tickets[str(ctx.author.id)])
                return await ctx.reply(f"You already have an active ticket! {thread.jump_url}")
            except:
                # Clean up invalid ticket
                del self.active_tickets[str(ctx.author.id)]
                self.save_data()
        
        # Create mock message and proceed
        class MockMessage:
            def __init__(self, author, content):
                self.author = author
                self.content = content
                self.created_at = discord.utils.utcnow()
        
        mock_message = MockMessage(ctx.author, message)
        await self.create_new_modmail(mock_message)
        await ctx.message.add_reaction("✅")

    @commands.command(name="close", aliases=["closemail", "closemodmail", "cmm"])
    @commands.has_permissions(manage_messages=True)
    async def close_modmail(self, ctx):
        """Close the current modmail thread"""
        try:
            if not isinstance(ctx.channel, discord.Thread):
                await ctx.send("This command can only be used in modmail threads")
                return
                
            user_id = None
            for uid, tid in self.active_tickets.items():
                if tid == ctx.channel.id:
                    user_id = uid
                    break
            
            if user_id:
                user = self.bot.get_user(int(user_id))
                if user:
                    try:
                        embed = discord.Embed(
                            title="Modmail Closed",
                            description="This modmail ticket has been closed by staff. "
                                      "If you have further questions, please open a new one.",
                            color=0xff0000
                        )
                        await user.send(embed=embed)
                    except discord.HTTPException:
                        pass
                
                del self.active_tickets[user_id]
                self.save_data()
            
            # Try to edit the original embed color to red
            try:
                parent_channel = self.bot.get_channel(ctx.channel.parent_id)
                if parent_channel:
                    starter_message = await parent_channel.fetch_message(ctx.channel.id)
                    if starter_message and starter_message.embeds:
                        original_embed = starter_message.embeds[0]
                        edited_embed = discord.Embed.from_dict(original_embed.to_dict())
                        edited_embed.color = 0xff0000
                        await starter_message.edit(embed=edited_embed)
            except Exception as e:
                self.logger.error(f"Failed to edit original embed: {e}")
            
            await ctx.send("Closing this modmail ticket...")
            await ctx.channel.edit(archived=True, locked=True)
            
        except Exception as e:
            self.logger.error(f"Failed to close modmail: {e}")
            await ctx.send(f"Failed to close modmail: {e}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if ctx.command and ctx.command.cog_name == self.__class__.__name__:
            await self.handle_error(ctx, error)

async def setup(bot):
    """Setup function for the cog"""
    try:
        await bot.add_cog(ModMail(bot))
    except Exception as e:
        print(f"Failed to load ModMail cog: {e}")
        raise