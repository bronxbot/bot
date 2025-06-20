import nextcord
from nextcord.ext import commands, tasks
import json
from pathlib import Path
from datetime import datetime, timedelta
import asyncio
from collections import defaultdict
from cogs.logging.logger import CogLogger

logger = CogLogger('VoteBans')

class VoteBans(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.main_guilds = self.bot.MAIN_GUILD_IDS
        self.vote_channel_id = 1367979611748696284
        self.staff_role_id = 1259728436377817100
        self.required_votes = 25
        self.ban_threshold = 15
        self.timeout_duration = timedelta(days=7)
        self.data_path = Path("data/votebans.json")
        self.vote_data = self.load_data()
        
        # Enhanced rate limiting and caching
        self.message_edit_queue = asyncio.Queue()
        self.last_edit_time = {}
        self.edit_cooldown = 5.0  # Increased from 2.0 to 5.0 seconds
        self.reaction_cache = defaultdict(dict)  # message_id: {emoji: [user_ids]}
        self.last_reaction_check = {}
        
        # Background task management with scalability integration
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """Start background tasks with scalability integration"""
        # Check if scalability manager is available
        if hasattr(self.bot, 'scalability_manager') and self.bot.scalability_manager:
            # Let scalability manager handle this
            logger.info("Using scalability manager for background task management")
        else:
            # Fallback to traditional approach
            self.bot.loop.create_task(self.process_message_edits())
            self.verify_reactions.start()
    
    def cog_unload(self):
        self.verify_reactions.cancel()
    
    @tasks.loop(minutes=5)  # Reduced from 30 seconds to 5 minutes
    async def verify_reactions(self):
        """Efficiently verify reactions with caching and batching"""
        logger.debug("Running optimized reaction verification...")
        
        # Process in batches to avoid rate limits
        active_votes = [v for v in self.vote_data.values() if not v.get("completed", True)]
        for i in range(0, len(active_votes), 5):  # Process 5 votes at a time
            batch = active_votes[i:i+5]
            await self._process_batch(batch)
            await asyncio.sleep(10)  # Space out batches
    
    async def _process_batch(self, batch):
        """Process a batch of votes efficiently"""
        for vote_info in batch:
            try:
                message_id = vote_info["message_id"]
                channel_id = vote_info["channel_id"]
                
                # Check if we recently processed this message
                if self.last_reaction_check.get(message_id, 0) > datetime.now().timestamp() - 300:
                    continue
                
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    continue
                    
                message = await self.safe_fetch_message(channel, message_id)
                if not message:
                    vote_info["completed"] = True
                    continue
                
                # Get reactions efficiently
                yes_reaction = next((r for r in message.reactions if str(r.emoji) == "✅"), None)
                no_reaction = next((r for r in message.reactions if str(r.emoji) == "❌"), None)
                
                # Update cache
                cache_entry = {}
                if yes_reaction:
                    cache_entry["✅"] = [user.id async for user in yes_reaction.users() if not user.bot]
                if no_reaction:
                    cache_entry["❌"] = [user.id async for user in no_reaction.users() if not user.bot]
                self.reaction_cache[message_id] = cache_entry
                
                # Update stored votes if different
                current_yes = set(cache_entry.get("✅", []))
                current_no = set(cache_entry.get("❌", []))
                stored_yes = set(vote_info["votes"]["✅"])
                stored_no = set(vote_info["votes"]["❌"])
                
                if current_yes != stored_yes or current_no != stored_no:
                    vote_info["votes"]["✅"] = list(current_yes)
                    vote_info["votes"]["❌"] = list(current_no)
                    
                    total_votes = len(current_yes) + len(current_no)
                    if total_votes >= self.required_votes:
                        await self.complete_vote(str(vote_info["user_id"]), message)
                    else:
                        await self.queue_message_edit(message_id, channel_id, 
                                                   await self.create_vote_embed(vote_info))
                
                self.last_reaction_check[message_id] = datetime.now().timestamp()
                
            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                continue

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        """Handle reaction adds with cache support"""
        if not await self.should_process_reaction(payload):
            return
            
        emoji = str(payload.emoji)
        message_id = payload.message_id
        
        # Update cache immediately
        if message_id in self.reaction_cache:
            if emoji in self.reaction_cache[message_id]:
                if payload.user_id not in self.reaction_cache[message_id][emoji]:
                    self.reaction_cache[message_id][emoji].append(payload.user_id)
            else:
                self.reaction_cache[message_id][emoji] = [payload.user_id]
        
        await self.process_reaction_change(payload, added=True)

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload):
        """Handle reaction removes with cache support"""
        if not await self.should_process_reaction(payload):
            return
            
        emoji = str(payload.emoji)
        message_id = payload.message_id
        
        # Update cache immediately
        if message_id in self.reaction_cache and emoji in self.reaction_cache[message_id]:
            if payload.user_id in self.reaction_cache[message_id][emoji]:
                self.reaction_cache[message_id][emoji].remove(payload.user_id)
        
        await self.process_reaction_change(payload, added=False)

    async def should_process_reaction(self, payload):
        """Check if we should process this reaction event"""
        if payload.guild_id not in self.main_guilds:
            return False
        if payload.user_id == self.bot.user.id:
            return False
            
        # Find the vote
        vote_info = next((v for v in self.vote_data.values() 
                         if v.get("message_id") == payload.message_id), None)
        
        if not vote_info or vote_info.get("completed", True):
            return False
            
        return str(payload.emoji) in ["✅", "❌"]

    async def process_reaction_change(self, payload, added):
        """Process reaction changes efficiently"""
        emoji = str(payload.emoji)
        opposite = "❌" if emoji == "✅" else "✅"
        message_id = payload.message_id
        
        # Find the vote
        user_id_str, vote_info = next(((k, v) for k, v in self.vote_data.items() 
                                     if v.get("message_id") == message_id), (None, None))
        if not vote_info:
            return
            
        # Update vote counts
        if added:
            if payload.user_id in vote_info["votes"][opposite]:
                vote_info["votes"][opposite].remove(payload.user_id)
            if payload.user_id not in vote_info["votes"][emoji]:
                vote_info["votes"][emoji].append(payload.user_id)
        else:
            if payload.user_id in vote_info["votes"][emoji]:
                vote_info["votes"][emoji].remove(payload.user_id)
        
        self.save_data()
        
        # Get channel and message from cache if possible
        channel = self.bot.get_channel(payload.channel_id)
        if not channel:
            return
            
        # Update embed
        await self.queue_message_edit(message_id, payload.channel_id, 
                                   await self.create_vote_embed(vote_info))
        
        # Check completion
        total_votes = len(vote_info["votes"]["✅"]) + len(vote_info["votes"]["❌"])
        if total_votes >= self.required_votes:
            message = await self.safe_fetch_message(channel, message_id)
            if message:
                await self.complete_vote(user_id_str, message)

    async def create_vote_embed(self, vote_info):
        """Create an embed from vote info (reused from your original code)"""
        user = self.bot.get_user(vote_info["user_id"])
        user_name = user.display_name if user else f"User {vote_info['user_id']}"
        
        yes_votes = len(vote_info["votes"]["✅"])
        no_votes = len(vote_info["votes"]["❌"])
        
        embed = nextcord.Embed(
            title=f"Vote Ban: {user_name}",
            description=(
                f"**Reason:** {vote_info['reason']}\n\n"
                f"Vote ✅ to ban ({yes_votes}), ❌ to keep ({no_votes})\n"
                f"{self.required_votes} votes needed to decide"
            ),
            color=nextcord.Colour.random(),
            timestamp=datetime.now()
        )
        
        if user and user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        # Add advocates if any
        advocate_text = []
        for advocate_id, advocate_data in vote_info.get("advocates", {}).items():
            try:
                timestamp = int(datetime.fromisoformat(advocate_data['timestamp']).timestamp())
                advocate_text.append(
                    f"• **{advocate_data['username']}** - \"{advocate_data['reason']}\" "
                    f"(<t:{timestamp}:R>)"
                )
            except (ValueError, KeyError):
                advocate_text.append(f"• **{advocate_data.get('username', 'Unknown')}** - \"{advocate_data.get('reason', 'No reason')}\"")

        if advocate_text:
            embed.add_field(name="Advocates", value="\n".join(advocate_text[:10]), inline=False)
        
        return embed
        
    def load_data(self):
        try:
            with open(self.data_path) as f:
                data = json.load(f)
                # Backwards compatibility: support old format
                if "votes" in data and isinstance(data["votes"], dict):
                    new_data = {}
                    for vote_id, vote_info in data["votes"].items():
                        user_id = str(vote_info["user_id"])
                        new_data[user_id] = {
                            "user_id": vote_info["user_id"],
                            "initiator": vote_info["initiator"],
                            "message_id": vote_info["message_id"],
                            "channel_id": vote_info["channel_id"],
                            "jump_url": vote_info.get("jump_url", ""),
                            "reason": vote_info["reason"],
                            "votes": vote_info["votes"],
                            "advocates": vote_info.get("advocates", {}),
                            "completed": vote_info["completed"]
                        }
                    return new_data
                # Newer structure is just vote_data directly
                return data
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load vote data: {e}")
            return {}
    
    def save_data(self):
        try:
            self.data_path.parent.mkdir(exist_ok=True)
            with open(self.data_path, "w") as f:
                json.dump(self.vote_data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save vote data: {e}")

    async def process_message_edits(self):
        """Process message edits with rate limiting to avoid API limits"""
        while True:
            try:
                message_id, embed_data = await self.message_edit_queue.get()
                
                # Check if we need to wait due to rate limiting
                current_time = asyncio.get_event_loop().time()
                if message_id in self.last_edit_time:
                    time_since_last = current_time - self.last_edit_time[message_id]
                    if time_since_last < self.edit_cooldown:
                        await asyncio.sleep(self.edit_cooldown - time_since_last)
                
                # Attempt to edit the message
                try:
                    channel = self.bot.get_channel(embed_data['channel_id'])
                    if channel:
                        message = await channel.fetch_message(message_id)
                        await message.edit(embed=embed_data['embed'])
                        self.last_edit_time[message_id] = asyncio.get_event_loop().time()
                except nextcord.NotFound:
                    logger.warning(f"Message {message_id} not found for editing")
                    # Clean up vote data for missing messages
                    self.cleanup_missing_vote(message_id)
                except nextcord.HTTPException as e:
                    logger.error(f"HTTP error editing message {message_id}: {e}")
                    # Wait longer on HTTP errors
                    await asyncio.sleep(5)
                except Exception as e:
                    logger.error(f"Unexpected error editing message {message_id}: {e}")
                
            except Exception as e:
                logger.error(f"Error in message edit processor: {e}")
                await asyncio.sleep(1)

    def cleanup_missing_vote(self, message_id):
        """Remove vote data for messages that no longer exist"""
        for user_id, vote_data in list(self.vote_data.items()):
            if vote_data.get("message_id") == message_id:
                logger.info(f"Cleaning up vote data for missing message {message_id}")
                vote_data["completed"] = True
                self.save_data()
                break

    async def queue_message_edit(self, message_id, channel_id, embed):
        """Queue a message edit to avoid rate limits"""
        await self.message_edit_queue.put((message_id, {
            'channel_id': channel_id,
            'embed': embed
        }))

    async def is_staff(self, member):
        """Check if member has staff role"""
        if not member:
            return False
        staff_role = member.guild.get_role(self.staff_role_id)
        return staff_role in member.roles if staff_role else False

    async def safe_fetch_message(self, channel, message_id):
        """Safely fetch a message with error handling"""
        try:
            return await channel.fetch_message(message_id)
        except nextcord.NotFound:
            logger.warning(f"Message {message_id} not found")
            return None
        except nextcord.Forbidden:
            logger.error(f"No permission to fetch message {message_id}")
            return None
        except nextcord.HTTPException as e:
            logger.error(f"HTTP error fetching message {message_id}: {e}")
            return None

    async def cog_check(self, ctx):
        """Check if the guild has permission to use this cog's commands"""
        return ctx.guild.id in self.main_guilds

    @commands.command(name="vban", aliases=["voteban", "kill", "vb", "ban"])
    async def voteban(self, ctx, user: nextcord.Member=None, *, reason="No reason provided"):
        if not user:
            embed = nextcord.Embed(
                title="Vote Ban",
                description=f"""
                **Usage:**
                `{ctx.prefix}vban <user> <reason>`
                > *vb, voteban, vote, kill, ban, vban*
                
                **Example:**
                `{ctx.prefix}vban ks.net gay`
                `{ctx.prefix}vban @ks.net gay`
                `{ctx.prefix}vban 814226043924643880 still gay`
                """,
                color=nextcord.Colour.random(),
                timestamp=datetime.now()
            )
            return await ctx.send(embed=embed)

        # Validation checks
        if user.id == ctx.author.id:
            return await ctx.send("You can't vote ban yourself!", delete_after=10)
            
        if await self.is_staff(user) or await self.is_staff(ctx.author):
            return await ctx.send("You can't vote ban (or vote as) a staff member!", delete_after=10)
            
        if user.bot:
            return await ctx.send("You can't vote ban bots!", delete_after=10)

        # Check reason length
        if len(reason) < 10:
            return await ctx.send("Reason must be at least 10 characters long!", delete_after=10)
        elif len(reason) > 250:
            return await ctx.send("Reason must be less than 250 characters long!", delete_after=10)

        user_id_str = str(user.id)

        # If vote already exists, update advocates
        if user_id_str in self.vote_data and not self.vote_data[user_id_str].get("completed", True):
            existing_vote = self.vote_data[user_id_str]

            # Add advocate
            existing_vote["advocates"][str(ctx.author.id)] = {
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "username": ctx.author.name
            }

            # Update embed with new advocate list
            embed = nextcord.Embed(
                title=f"Vote Ban: {user.display_name}",
                description=f"**Reason:** {existing_vote['reason']}\n\nVote ✅ to ban, ❌ to keep\n{self.required_votes} votes needed to decide",
                color=nextcord.Colour.random(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.set_footer(text=f"Started by {ctx.author.display_name}")

            # Add advocates field
            advocate_text = []
            for advocate_id, advocate_data in existing_vote["advocates"].items():
                try:
                    timestamp = int(datetime.fromisoformat(advocate_data['timestamp']).timestamp())
                    advocate_text.append(
                        f"• **{advocate_data['username']}** - \"{advocate_data['reason']}\" "
                        f"(<t:{timestamp}:R>)"
                    )
                except (ValueError, KeyError):
                    advocate_text.append(f"• **{advocate_data.get('username', 'Unknown')}** - \"{advocate_data.get('reason', 'No reason')}\"")

            if advocate_text:
                embed.add_field(
                    name="Advocates",
                    value="\n".join(advocate_text[:10]),  # Limit to prevent embed size issues
                    inline=False
                )

            # Queue the message edit
            await self.queue_message_edit(
                existing_vote["message_id"], 
                existing_vote["channel_id"], 
                embed
            )
            
            self.save_data()

            return await ctx.send(
                f"You've been added as an advocate for {user.mention}'s vote ban.\n"
                f"Vote here: {existing_vote['jump_url']}"
            )

        # Create a new vote embed
        embed = nextcord.Embed(
            title=f"Vote Ban: {user.display_name}",
            description=f"**Reason:** {reason}\n\nVote ✅ to ban, ❌ to keep\n{self.required_votes} votes needed to decide",
            color=nextcord.Colour.random(),
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        embed.set_footer(text=f"Started by {ctx.author.display_name}")

        # Send embed to vote channel
        vote_channel = self.bot.get_channel(self.vote_channel_id)
        if not vote_channel:
            return await ctx.send("Vote channel not found!", delete_after=10)

        try:
            vote_msg = await vote_channel.send(embed=embed)
            await vote_msg.add_reaction("✅")
            await vote_msg.add_reaction("❌")
        except nextcord.HTTPException as e:
            logger.error(f"Failed to send vote message: {e}")
            return await ctx.send("Failed to create vote! Please try again later.", delete_after=10)

        # Store vote data
        self.vote_data[user_id_str] = {
            "user_id": user.id,
            "initiator": ctx.author.id,
            "message_id": vote_msg.id,
            "channel_id": vote_channel.id,
            "jump_url": vote_msg.jump_url,
            "reason": reason,
            "votes": {"✅": [], "❌": []},
            "advocates": {
                str(ctx.author.id): {
                    "reason": reason,
                    "timestamp": datetime.now().isoformat(),
                    "username": ctx.author.name
                }
            },
            "completed": False
        }

        self.save_data()

        await ctx.send(
            f"Vote started for {user.mention}!\n"
            f"Vote here: {vote_msg.jump_url}"
        )

    @commands.Cog.listener()
    async def on_ready(self):
        """Restore vote embeds on bot restart"""
        logger.info("Restoring vote embeds...")
        restored_count = 0
        
        for user_id, vote in list(self.vote_data.items()):
            if not vote.get("completed", True):
                try:
                    channel = self.bot.get_channel(vote["channel_id"])
                    if not channel:
                        logger.warning(f"Vote channel {vote['channel_id']} not found, marking vote as completed")
                        vote["completed"] = True
                        continue

                    message = await self.safe_fetch_message(channel, vote["message_id"])
                    if not message:
                        logger.warning(f"Vote message {vote['message_id']} not found, marking vote as completed")
                        vote["completed"] = True
                        continue

                    # Rebuild embed with current data
                    user = self.bot.get_user(vote["user_id"])
                    user_name = user.display_name if user else f"User {vote['user_id']}"
                    
                    embed = nextcord.Embed(
                        title=f"Vote Ban: {user_name}",
                        description=f"**Reason:** {vote['reason']}\n\nVote ✅ to ban, ❌ to keep\n{self.required_votes} votes needed to decide",
                        color=nextcord.Colour.random(),
                        timestamp=datetime.now()
                    )
                    
                    if user and user.avatar:
                        embed.set_thumbnail(url=user.avatar.url)
                    
                    # Add advocate information
                    advocate_text = []
                    for advocate_id, advocate_data in vote.get("advocates", {}).items():
                        try:
                            timestamp = int(datetime.fromisoformat(advocate_data['timestamp']).timestamp())
                            advocate_text.append(
                                f"• **{advocate_data['username']}** - \"{advocate_data['reason']}\" "
                                f"(<t:{timestamp}:R>)"
                            )
                        except (ValueError, KeyError):
                            advocate_text.append(f"• **{advocate_data.get('username', 'Unknown')}** - \"{advocate_data.get('reason', 'No reason')}\"")

                    if advocate_text:
                        embed.add_field(name="Advocates", value="\n".join(advocate_text[:10]), inline=False)

                    await self.queue_message_edit(vote["message_id"], vote["channel_id"], embed)
                    restored_count += 1
                    
                except Exception as e:
                    logger.error(f"Failed to restore vote message {vote.get('message_id', 'unknown')}: {e}")
                    vote["completed"] = True

        if restored_count > 0:
            self.save_data()
            logger.info(f"Restored {restored_count} vote embeds")

    async def update_vote_embed(self, vote_info, message):
        """Update vote embed with current vote counts"""
        yes_votes = len(vote_info["votes"]["✅"])
        no_votes = len(vote_info["votes"]["❌"])
        
        # Get user info
        user = self.bot.get_user(vote_info["user_id"])
        user_name = user.display_name if user else f"User {vote_info['user_id']}"
        
        embed = nextcord.Embed(
            title=f"Vote Ban: {user_name}",
            description=(
                f"**Reason:** {vote_info['reason']}\n\n"
                f"Vote ✅ to ban ({yes_votes}), ❌ to keep ({no_votes})\n"
                f"{self.required_votes} votes needed to decide"
            ),
            color=nextcord.Colour.random(),
            timestamp=datetime.now()
        )
        
        if user and user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        # Add advocates if any
        advocate_text = []
        for advocate_id, advocate_data in vote_info.get("advocates", {}).items():
            try:
                timestamp = int(datetime.fromisoformat(advocate_data['timestamp']).timestamp())
                advocate_text.append(
                    f"• **{advocate_data['username']}** - \"{advocate_data['reason']}\" "
                    f"(<t:{timestamp}:R>)"
                )
            except (ValueError, KeyError):
                advocate_text.append(f"• **{advocate_data.get('username', 'Unknown')}** - \"{advocate_data.get('reason', 'No reason')}\"")

        if advocate_text:
            embed.add_field(name="Advocates", value="\n".join(advocate_text[:10]), inline=False)
        
        await self.queue_message_edit(message.id, message.channel.id, embed)

    async def complete_vote(self, user_id_str, message):
        """Complete a vote and apply the result"""
        vote_info = self.vote_data[user_id_str]
        vote_info["completed"] = True
        self.save_data()
        
        yes_votes = len(vote_info["votes"]["✅"])
        no_votes = len(vote_info["votes"]["❌"])
        advocate_bonus = len(vote_info.get("advocates", {})) * 3
        total_score = yes_votes - no_votes + advocate_bonus
        
        guild = message.guild
        target_user = guild.get_member(int(user_id_str))
        
        # Build final embed
        user = self.bot.get_user(vote_info["user_id"])
        user_name = user.display_name if user else f"User {vote_info['user_id']}"
        
        embed = nextcord.Embed(
            title=f"Vote Ban Complete: {user_name}",
            description=(
                f"**Reason:** {vote_info['reason']}\n\n"
                f"**Voting Complete!**\n"
                f"✅ {yes_votes} votes | ❌ {no_votes} votes\n"
                f"Advocate bonus: +{advocate_bonus}\n"
                f"**Final Score:** {total_score}\n\n"
            ),
            timestamp=datetime.now()
        )
        
        if user and user.avatar:
            embed.set_thumbnail(url=user.avatar.url)
        
        if total_score >= self.ban_threshold:
            if target_user:
                try:
                    await target_user.timeout(self.timeout_duration, reason=f"Vote ban result: {vote_info['reason']}")
                    embed.description += f"**Result:** {target_user.mention} has been timed out for 1 week!"
                    embed.color = 0xff0000
                    logger.info(f"Successfully timed out user {target_user} (ID: {target_user.id})")
                except nextcord.Forbidden:
                    embed.description += "**Result:** Failed to timeout user (missing permissions)"
                    embed.color = 0xffff00
                    logger.error(f"Missing permissions to timeout user {target_user}")
                except nextcord.HTTPException as e:
                    embed.description += f"**Result:** Error timing out user: {e}"
                    embed.color = 0xffff00
                    logger.error(f"HTTP error timing out user {target_user}: {e}")
            else:
                embed.description += "**Result:** User not found in server"
                embed.color = 0xffff00
                logger.warning(f"User {user_id_str} not found in server for timeout")
        else:
            embed.description += "**Result:** User will not be banned (score below threshold)"
            embed.color = 0x00ff00
        
        try:
            await message.edit(embed=embed)
            await message.clear_reactions()
        except nextcord.HTTPException as e:
            logger.error(f"Failed to update completed vote message: {e}")
    
    @commands.command(name="votestats", aliases=["vs"])
    async def vote_stats(self, ctx, user: nextcord.Member = None):
        if not user:
            return await ctx.send("Please specify a user to check stats for.", delete_after=10)
            
        user_id_str = str(user.id)
        embed = nextcord.Embed(
            title=f"Vote Stats for {user.display_name}",
            color=0x7289da
        )
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
        
        if user_id_str in self.vote_data:
            vote_info = self.vote_data[user_id_str]
            
            # Show current vote status if active
            if not vote_info.get("completed", True):
                yes_votes = len(vote_info["votes"]["✅"])
                no_votes = len(vote_info["votes"]["❌"])
                embed.add_field(
                    name="Current Vote",
                    value=f"✅ {yes_votes} | ❌ {no_votes}\n"
                         f"Needs {self.required_votes} total votes\n"
                         f"[Jump to Vote]({vote_info['jump_url']})",
                    inline=False
                )
            
            # Show advocates
            if vote_info.get("advocates", {}):
                advocate_text = []
                for advocate_id, advocate_data in vote_info["advocates"].items():
                    try:
                        timestamp = int(datetime.fromisoformat(advocate_data['timestamp']).timestamp())
                        advocate_text.append(
                            f"• **{advocate_data['username']}** - \"{advocate_data['reason']}\" "
                            f"(<t:{timestamp}:R>)"
                        )
                    except (ValueError, KeyError):
                        advocate_text.append(f"• **{advocate_data.get('username', 'Unknown')}** - \"{advocate_data.get('reason', 'No reason')}\"")
                
                if advocate_text:
                    embed.add_field(
                        name="Advocates",
                        value="\n".join(advocate_text[:10]),
                        inline=False
                    )
        else:
            embed.description = "No vote history found for this user."
        
        await ctx.send(embed=embed)

    @commands.command(name="clearvotes", hidden=True)
    @commands.has_permissions(administrator=True)
    async def clear_completed_votes(self, ctx):
        """Clean up completed votes (admin only)"""
        before_count = len(self.vote_data)
        self.vote_data = {k: v for k, v in self.vote_data.items() if not v.get("completed", True)}
        after_count = len(self.vote_data)
        cleaned = before_count - after_count
        
        self.save_data()
        await ctx.send(f"Cleaned up {cleaned} completed votes. {after_count} active votes remaining.")

async def setup(bot):
    try:
        bot.add_cog(VoteBans(bot))
    except Exception as e:
        logger.error(f"Failed to load VoteBans cog: {e}")
        raise e