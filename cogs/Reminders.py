import nextcord
from nextcord.ext import commands, tasks
import datetime
import re
from typing import Optional, List, Dict, Any
import asyncio
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from utils.error_handler import ErrorHandler
from cogs.logging.logger import CogLogger


class Reminders(commands.Cog, ErrorHandler):
    """Advanced reminder system with persistent storage and flexible time parsing"""
    
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.check_reminders.start()
        self.logger.info("Reminders cog initialized")
    
    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_reminders.cancel()
    
    @tasks.loop(seconds=30)
    async def check_reminders(self):
        """Check for due reminders every 30 seconds"""
        try:
            if not await db.ensure_connected():
                return
            
            current_time = datetime.datetime.now()
            
            # Get all due reminders
            due_reminders = await db.db.reminders.find({
                "due_time": {"$lte": current_time}
            }).to_list(None)
            
            for reminder in due_reminders:
                await self.send_reminder(reminder)
                
                # Remove the reminder from database
                await db.db.reminders.delete_one({"_id": reminder["_id"]})
                
        except Exception as e:
            self.logger.error(f"Error checking reminders: {e}")
    
    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()
    
    async def send_reminder(self, reminder: dict):
        """Send a reminder to the user"""
        try:
            user_id = reminder["user_id"]
            channel_id = reminder.get("channel_id")
            message = reminder["message"]
            original_time_str = reminder.get("original_time", "")
            
            user = self.bot.get_user(user_id)
            if not user:
                return
            
            embed = nextcord.Embed(
                title="⏰ Reminder",
                description=message,
                color=0x2b2d31,
                timestamp=datetime.datetime.now()
            )
            
            if original_time_str:
                embed.set_footer(text=f"Set {original_time_str} ago")
            
            # Try to send DM first
            try:
                await user.send(embed=embed)
                self.logger.info(f"Sent reminder DM to user {user_id}")
            except nextcord.Forbidden:
                # If DM fails, try to send in original channel
                if channel_id:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        embed.description = f"{user.mention} ⏰ **Reminder:** {message}"
                        await channel.send(embed=embed)
                        self.logger.info(f"Sent reminder in channel {channel_id} for user {user_id}")
                
        except Exception as e:
            self.logger.error(f"Error sending reminder: {e}")
    
    def parse_time_string(self, time_str: str) -> Optional[int]:
        """
        Parse flexible time strings and return total seconds
        Supports formats like:
        - 4 months 15 days
        - 15 days 4 months  
        - 14d 4m
        - 14d5M
        - 2Y 3M 1d 5h 30m
        """
        if not time_str:
            return None
        
        # Clean the input but preserve case for M vs m distinction
        time_str = time_str.strip()
        
        # Define time unit mappings
        units = {
            # Years (case insensitive)
            'y': 365 * 24 * 3600,
            'Y': 365 * 24 * 3600,
            'year': 365 * 24 * 3600,
            'years': 365 * 24 * 3600,
            # Months (capital M only)
            'M': 30 * 24 * 3600,  # Capital M for months
            'month': 30 * 24 * 3600,
            'months': 30 * 24 * 3600,
            # Days (case insensitive)
            'd': 24 * 3600,
            'D': 24 * 3600,
            'day': 24 * 3600,
            'days': 24 * 3600,
            # Hours (case insensitive)
            'h': 3600,
            'H': 3600,
            'hour': 3600,
            'hours': 3600,
            # Minutes (lowercase m only)
            'm': 60,
            'min': 60,
            'mins': 60,
            'minute': 60,
            'minutes': 60,
            # Seconds (case insensitive)
            's': 1,
            'S': 1,
            'sec': 1,
            'secs': 1,
            'second': 1,
            'seconds': 1
        }
        
        total_seconds = 0
        
        # Pattern to match number + unit combinations
        # This handles both spaced (4 months) and non-spaced (14d5M) formats
        pattern = r'(\d+)\s*([a-zA-Z]+)'
        matches = re.findall(pattern, time_str)
        
        if not matches:
            return None
        
        for amount_str, unit in matches:
            try:
                amount = int(amount_str)
                
                # Find matching unit (case sensitive for M vs m)
                if unit in units:
                    total_seconds += amount * units[unit]
                else:
                    # Try case insensitive match for word units (day, hour, etc.)
                    unit_lower = unit.lower()
                    if unit_lower in ['year', 'years', 'month', 'months', 'day', 'days', 
                                    'hour', 'hours', 'minute', 'minutes', 'second', 'seconds',
                                    'min', 'mins', 'sec', 'secs']:
                        total_seconds += amount * units[unit_lower]
                    else:
                        # Unknown unit
                        return None
                        
            except ValueError:
                return None
        
        return total_seconds if total_seconds > 0 else None
    
    def format_time_duration(self, seconds: int) -> str:
        """Format seconds into a human-readable duration"""
        if seconds < 60:
            return f"{seconds} second{'s' if seconds != 1 else ''}"
        
        units = [
            (365 * 24 * 3600, 'year'),
            (30 * 24 * 3600, 'month'),
            (24 * 3600, 'day'),
            (3600, 'hour'),
            (60, 'minute'),
            (1, 'second')
        ]
        
        parts = []
        remaining = seconds
        
        for unit_seconds, unit_name in units:
            if remaining >= unit_seconds:
                count = remaining // unit_seconds
                remaining %= unit_seconds
                parts.append(f"{count} {unit_name}{'s' if count != 1 else ''}")
                
                # Limit to 2 most significant units for readability
                if len(parts) >= 2:
                    break
        
        if len(parts) == 1:
            return parts[0]
        elif len(parts) == 2:
            return f"{parts[0]} and {parts[1]}"
        else:
            return "Invalid duration"
    
    @commands.command(aliases=['remindme', 'reminder'])
    async def remind(self, ctx, *, args: str = None):
        """
        Set a reminder with flexible time formatting.
        
        **Time Formats:**
        • `Y` = years, `M` = months (capital M), `d` = days, `h` = hours, `m` = minutes (lowercase m), `s` = seconds
        • Mix and match: `.remind 2Y 3M 1d 5h 30m Take a break`
        • Flexible order: `.remind 15 days 4 months Go shopping`
        • Compact format: `.remind 14d5M30m Meeting with boss`
        
        **Examples:**
        • `.remind 1h 30m Check the oven`
        • `.remind 2 days 4 hours Call mom`
        • `.remind 1Y 6M Renew passport`
        • `.remind 30m Quick break`
        
        **Important:** Use capital `M` for months, lowercase `m` for minutes!
        """
        if not args:
            embed = nextcord.Embed(
                title="⏰ Reminder Help",
                description=(
                    "**Usage:** `.remind <time> <message>`\n\n"
                    "**Time Units:**\n"
                    "• `Y` = years\n"
                    "• `M` = months (capital M)\n" 
                    "• `d` = days\n"
                    "• `h` = hours\n"
                    "• `m` = minutes (lowercase m)\n"
                    "• `s` = seconds\n\n"
                    "**Examples:**\n"
                    "• `.remind 1h 30m Check the oven`\n"
                    "• `.remind 2 days 4 hours Call mom`\n"
                    "• `.remind 1Y 6M Renew passport`\n"
                    "• `.remind 14d5M Meeting with boss`\n\n"
                    "**Important:** Capital `M` = months, lowercase `m` = minutes!"
                ),
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)
        
        # Split args into time and message parts
        # Try to find where the time specification ends and message begins
        words = args.split()
        time_parts = []
        message_parts = []
        
        # Look for time patterns at the beginning
        for i, word in enumerate(words):
            # Check if this word looks like a time specification
            if re.match(r'^\d+[a-zA-Z]+$', word) or re.match(r'^\d+$', word):
                time_parts.append(word)
            elif word.lower() in ['year', 'years', 'month', 'months', 'day', 'days', 
                                'hour', 'hours', 'minute', 'minutes', 'second', 'seconds']:
                time_parts.append(word)
            else:
                # This doesn't look like time, rest is message
                message_parts = words[i:]
                break
        
        if not time_parts:
            embed = nextcord.Embed(
                description="❌ Please specify a time! Example: `.remind 1h 30m Take a break`",
                color=nextcord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        time_str = " ".join(time_parts)
        message = " ".join(message_parts) if message_parts else "You asked me to remind you, but didn't give me a reason."
        
        # Parse the time
        seconds = self.parse_time_string(time_str)
        if seconds is None:
            embed = nextcord.Embed(
                title="❌ Invalid Time Format",
                description=(
                    "Please use valid time units:\n"
                    "• `Y` = years, `M` = months (capital M), `d` = days\n"
                    "• `h` = hours, `m` = minutes (lowercase m), `s` = seconds\n\n"
                    "**Examples:**\n"
                    "• `1h 30m` • `2 days` • `1Y 6M` • `14d5M`\n\n"
                    "**Remember:** Capital `M` = months, lowercase `m` = minutes!"
                ),
                color=nextcord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Check limits
        if seconds <= 0:
            embed = nextcord.Embed(
                description="❌ Time must be positive!",
                color=nextcord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Maximum 2 years
        max_seconds = 2 * 365 * 24 * 3600  # 2 years
        if seconds > max_seconds:
            embed = nextcord.Embed(
                description="❌ Maximum reminder time is 2 years!",
                color=nextcord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        # Calculate due time
        due_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        
        # Store reminder in database
        reminder_data = {
            "user_id": ctx.author.id,
            "channel_id": ctx.channel.id,
            "message": message,
            "due_time": due_time,
            "created_at": datetime.datetime.now(),
            "original_time": time_str
        }
        
        try:
            if not await db.ensure_connected():
                embed = nextcord.Embed(
                    description="❌ Database connection failed!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            result = await db.db.reminders.insert_one(reminder_data)
            
            if result.inserted_id:
                formatted_duration = self.format_time_duration(seconds)
                
                embed = nextcord.Embed(
                    title="⏰ Reminder Set",
                    description=f"I'll remind you in **{formatted_duration}**: `{message}`",
                    color=nextcord.Color.green(),
                    timestamp=due_time
                )
                embed.set_footer(text="Reminder scheduled for")
                
                await ctx.reply(embed=embed)
                self.logger.info(f"Set reminder for user {ctx.author.id}: {message} in {formatted_duration}")
            else:
                embed = nextcord.Embed(
                    description="❌ Failed to save reminder!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error saving reminder: {e}")
            embed = nextcord.Embed(
                description="❌ An error occurred while saving the reminder!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)
    
    @commands.command(aliases=['reminders'])
    async def myreminders(self, ctx):
        """View your active reminders"""
        try:
            if not await db.ensure_connected():
                embed = nextcord.Embed(
                    description="❌ Database connection failed!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            reminders = await db.db.reminders.find({
                "user_id": ctx.author.id
            }).sort("due_time", 1).to_list(None)
            
            if not reminders:
                embed = nextcord.Embed(
                    title="⏰ Your Reminders",
                    description="You don't have any active reminders.",
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)
            
            embed = nextcord.Embed(
                title="⏰ Your Active Reminders",
                description=f"You have {len(reminders)} active reminder{'s' if len(reminders) != 1 else ''}\n\n*Use the reminder numbers with `.editreminder` or `.cancelreminder`*",
                color=0x2b2d31
            )
            
            current_time = datetime.datetime.now()
            
            for i, reminder in enumerate(reminders[:10], 1):  # Limit to 10 for embed space
                due_time = reminder["due_time"]
                time_left = due_time - current_time
                
                if time_left.total_seconds() > 0:
                    time_left_str = self.format_time_duration(int(time_left.total_seconds()))
                    due_str = f"Due in {time_left_str}"
                else:
                    due_str = "Due now (processing...)"
                
                message = reminder["message"]
                if len(message) > 100:
                    message = message[:97] + "..."
                
                embed.add_field(
                    name=f"Reminder #{i}",
                    value=f"**{message}**\n{due_str}",
                    inline=False
                )
            
            if len(reminders) > 10:
                embed.set_footer(text=f"Showing 10 of {len(reminders)} reminders")
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Error fetching reminders: {e}")
            embed = nextcord.Embed(
                description="❌ An error occurred while fetching reminders!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)
    
    @commands.command(aliases=['delreminder', 'rmreminder'])
    async def cancelreminder(self, ctx, reminder_number: int = None):
        """Cancel a specific reminder by number (use .myreminders to see numbers)"""
        if reminder_number is None:
            embed = nextcord.Embed(
                description="❌ Please specify a reminder number! Use `.myreminders` to see your reminders.",
                color=nextcord.Color.red()
            )
            return await ctx.reply(embed=embed)
        
        try:
            if not await db.ensure_connected():
                embed = nextcord.Embed(
                    description="❌ Database connection failed!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Get user's reminders sorted by due time
            reminders = await db.db.reminders.find({
                "user_id": ctx.author.id
            }).sort("due_time", 1).to_list(None)
            
            if not reminders:
                embed = nextcord.Embed(
                    description="❌ You don't have any active reminders!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            if reminder_number < 1 or reminder_number > len(reminders):
                embed = nextcord.Embed(
                    description=f"❌ Invalid reminder number! You have {len(reminders)} reminder{'s' if len(reminders) != 1 else ''}.",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Get the reminder to delete
            reminder_to_delete = reminders[reminder_number - 1]
            
            # Delete the reminder
            result = await db.db.reminders.delete_one({"_id": reminder_to_delete["_id"]})
            
            if result.deleted_count > 0:
                message = reminder_to_delete["message"]
                if len(message) > 100:
                    message = message[:97] + "..."
                
                embed = nextcord.Embed(
                    title="✅ Reminder Cancelled",
                    description=f"Cancelled reminder: `{message}`",
                    color=nextcord.Color.green()
                )
                await ctx.reply(embed=embed)
                self.logger.info(f"Cancelled reminder for user {ctx.author.id}: {reminder_to_delete['message']}")
            else:
                embed = nextcord.Embed(
                    description="❌ Failed to cancel reminder!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error cancelling reminder: {e}")
            embed = nextcord.Embed(
                description="❌ An error occurred while cancelling the reminder!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)
    
    @commands.command(aliases=['clearreminders'])
    async def cancelallreminders(self, ctx):
        """Cancel all your active reminders"""
        try:
            if not await db.ensure_connected():
                embed = nextcord.Embed(
                    description="❌ Database connection failed!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Count user's reminders first
            count = await db.db.reminders.count_documents({"user_id": ctx.author.id})
            
            if count == 0:
                embed = nextcord.Embed(
                    description="❌ You don't have any active reminders!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Delete all user's reminders
            result = await db.db.reminders.delete_many({"user_id": ctx.author.id})
            
            if result.deleted_count > 0:
                embed = nextcord.Embed(
                    title="✅ All Reminders Cancelled",
                    description=f"Cancelled {result.deleted_count} reminder{'s' if result.deleted_count != 1 else ''}.",
                    color=nextcord.Color.green()
                )
                await ctx.reply(embed=embed)
                self.logger.info(f"Cancelled all {result.deleted_count} reminders for user {ctx.author.id}")
            else:
                embed = nextcord.Embed(
                    description="❌ Failed to cancel reminders!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error cancelling all reminders: {e}")
            embed = nextcord.Embed(
                description="❌ An error occurred while cancelling reminders!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)
    
    @commands.command(aliases=['editreminder', 'modifyreminder'])
    async def edit_reminder(self, ctx, reminder_number: int = None, *, new_args: str = None):
        """
        Edit an existing reminder by number.
        
        **Usage:** `.editreminder <number> <new_time> <new_message>`
        
        **Examples:**
        • `.editreminder 1 2h 30m Updated reminder message`
        • `.editreminder 2 1d Call mom instead of dad`
        
        Use `.myreminders` to see your reminder numbers.
        """
        if reminder_number is None or new_args is None:
            embed = nextcord.Embed(
                title="⏰ Edit Reminder Help",
                description=(
                    "**Usage:** `.editreminder <number> <new_time> <new_message>`\n\n"
                    "**Examples:**\n"
                    "• `.editreminder 1 2h 30m Updated message`\n"
                    "• `.editreminder 2 1d Call mom instead`\n\n"
                    "Use `.myreminders` to see your reminder numbers."
                ),
                color=0x2b2d31
            )
            return await ctx.reply(embed=embed)
        
        try:
            if not await db.ensure_connected():
                embed = nextcord.Embed(
                    description="❌ Database connection failed!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Get user's reminders sorted by due time
            reminders = await db.db.reminders.find({
                "user_id": ctx.author.id
            }).sort("due_time", 1).to_list(None)
            
            if not reminders:
                embed = nextcord.Embed(
                    description="❌ You don't have any active reminders!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            if reminder_number < 1 or reminder_number > len(reminders):
                embed = nextcord.Embed(
                    description=f"❌ Invalid reminder number! You have {len(reminders)} reminder{'s' if len(reminders) != 1 else ''}.",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Get the reminder to edit
            reminder_to_edit = reminders[reminder_number - 1]
            old_message = reminder_to_edit["message"]
            
            # Parse new time and message (same logic as remind command)
            words = new_args.split()
            time_parts = []
            message_parts = []
            
            # Look for time patterns at the beginning
            for i, word in enumerate(words):
                # Check if this word looks like a time specification
                if re.match(r'^\d+[a-zA-Z]+$', word) or re.match(r'^\d+$', word):
                    time_parts.append(word)
                elif word.lower() in ['year', 'years', 'month', 'months', 'day', 'days', 
                                    'hour', 'hours', 'minute', 'minutes', 'second', 'seconds']:
                    time_parts.append(word)
                else:
                    # This doesn't look like time, rest is message
                    message_parts = words[i:]
                    break
            
            if not time_parts:
                embed = nextcord.Embed(
                    description="❌ Please specify a time! Example: `.editreminder 1 1h 30m New message`",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            time_str = " ".join(time_parts)
            new_message = " ".join(message_parts) if message_parts else "You asked me to remind you, but didn't give me a reason."
            
            # Parse the time
            seconds = self.parse_time_string(time_str)
            if seconds is None:
                embed = nextcord.Embed(
                    title="❌ Invalid Time Format",
                    description=(
                        "Please use valid time units:\n"
                        "• `Y` = years, `M` = months (capital M), `d` = days\n"
                        "• `h` = hours, `m` = minutes (lowercase m), `s` = seconds\n\n"
                        "**Examples:**\n"
                        "• `1h 30m` • `2 days` • `1Y 6M` • `14d5M`\n\n"
                        "**Remember:** Capital `M` = months, lowercase `m` = minutes!"
                    ),
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Check limits
            if seconds <= 0:
                embed = nextcord.Embed(
                    description="❌ Time must be positive!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Maximum 2 years
            max_seconds = 2 * 365 * 24 * 3600  # 2 years
            if seconds > max_seconds:
                embed = nextcord.Embed(
                    description="❌ Maximum reminder time is 2 years!",
                    color=nextcord.Color.red()
                )
                return await ctx.reply(embed=embed)
            
            # Calculate new due time
            new_due_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            
            # Update reminder in database
            result = await db.db.reminders.update_one(
                {"_id": reminder_to_edit["_id"]},
                {
                    "$set": {
                        "message": new_message,
                        "due_time": new_due_time,
                        "original_time": time_str,
                        "edited_at": datetime.datetime.now()
                    }
                }
            )
            
            if result.modified_count > 0:
                formatted_duration = self.format_time_duration(seconds)
                
                embed = nextcord.Embed(
                    title="✅ Reminder Updated",
                    description=f"Updated reminder #{reminder_number}",
                    color=nextcord.Color.green(),
                    timestamp=new_due_time
                )
                
                embed.add_field(
                    name="📝 Old Message",
                    value=f"`{old_message[:200]}{'...' if len(old_message) > 200 else ''}`",
                    inline=False
                )
                
                embed.add_field(
                    name="📝 New Message",
                    value=f"`{new_message[:200]}{'...' if len(new_message) > 200 else ''}`",
                    inline=False
                )
                
                embed.add_field(
                    name="⏰ New Schedule",
                    value=f"Due in **{formatted_duration}**",
                    inline=False
                )
                
                embed.set_footer(text="New reminder scheduled for")
                
                await ctx.reply(embed=embed)
                self.logger.info(f"Updated reminder #{reminder_number} for user {ctx.author.id}: '{old_message}' -> '{new_message}' in {formatted_duration}")
            else:
                embed = nextcord.Embed(
                    description="❌ Failed to update reminder!",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed)
                
        except Exception as e:
            self.logger.error(f"Error editing reminder: {e}")
            embed = nextcord.Embed(
                description="❌ An error occurred while editing the reminder!",
                color=nextcord.Color.red()
            )
            await ctx.reply(embed=embed)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if ctx.command and ctx.command.cog_name == self.__class__.__name__:
            await self.handle_error(ctx, error)


async def setup(bot):
    """Setup function for the cog"""
    try:
        bot.add_cog(Reminders(bot))
    except Exception as e:
        print(f"Failed to load Reminders cog: {e}")
        raise
