# Gambling Module Init
# Main coordinator for all gambling games

from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from cogs.logging.stats_logger import StatsLogger
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from utils.safe_reply import safe_reply
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
import nextcord
import asyncio
import time
import functools
from typing import Optional, List, Dict
from datetime import datetime, timedelta

# Import all gambling modules
from .card_games import CardGames
from .chance_games import ChanceGames
from .special_games import SpecialGames
from .plinko import Plinko

class MultiplierConverter(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            # Remove 'x' suffix if present and convert to float
            if argument.endswith('x'):
                argument = argument[:-1]
            return float(argument)
        except ValueError:
            raise commands.BadArgument("Multiplier must be a number (like 1.1 or 1.5x)")

def requires_tos():
    """Decorator to ensure user has accepted ToS before using gambling commands"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            if not await check_tos_acceptance(ctx.author.id):
                await prompt_tos_acceptance(ctx)
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator

class Gambling(commands.Cog):
    """Main gambling coordinator that loads all gambling sub-modules"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        
        # Enhanced rate limiting for message edits
        self.message_edit_queue = asyncio.Queue()
        self.edit_cooldown = 3.0  # 3 second cooldown between edits
        self.last_edit_time = {}
        
        # Start message edit processor
        self.bot.loop.create_task(self.process_message_edits())
        self.bot.loop.create_task(self.cleanup_active_games())
        
        self.logger.info("Gambling coordinator initialized")
    
    async def cog_check(self, ctx):
        """Global check for gambling commands"""
        # Ensure user exists in database by getting their wallet balance
        # This will automatically create the user if they don't exist due to upsert=True
        await db.get_wallet_balance(ctx.author.id)
        
        # Check cooldowns, ToS, etc here if needed
        return True
    
    async def process_message_edits(self):
        """Process queued message edits with rate limiting"""
        while True:
            try:
                edit_data = await self.message_edit_queue.get()
                current_time = time.time()
                message_id = edit_data['message_id']
                
                # Check if enough time has passed since last edit for this message
                if message_id in self.last_edit_time:
                    time_diff = current_time - self.last_edit_time[message_id]
                    if time_diff < self.edit_cooldown:
                        await asyncio.sleep(self.edit_cooldown - time_diff)
                
                # Perform the edit
                try:
                    await edit_data['message'].edit(embed=edit_data['embed'])
                    self.last_edit_time[message_id] = time.time()
                except nextcord.NotFound:
                    # Message was deleted, remove from tracking
                    if message_id in self.last_edit_time:
                        del self.last_edit_time[message_id]
                except Exception as e:
                    self.logger.error(f"Error editing message {message_id}: {e}")
                
                # Mark task as done
                self.message_edit_queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error in message edit processor: {e}")
                await asyncio.sleep(1)

    async def queue_message_edit(self, message, embed):
        """Queue a message edit for rate-limited processing"""
        edit_data = {
            'message': message,
            'embed': embed,
            'message_id': message.id,
            'timestamp': time.time()
        }
        await self.message_edit_queue.put(edit_data)

    async def cleanup_active_games(self):
        """Clear active games queue every 15 minutes to prevent stuck games"""
        while True:
            try:
                await asyncio.sleep(900)  # 15 minutes = 900 seconds
                
                if self.active_games:
                    cleared_count = len(self.active_games)
                    self.active_games.clear()
                    self.logger.info(f"Cleared {cleared_count:,} stuck active games")
                    
            except Exception as e:
                self.logger.error(f"Error in active games cleanup: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retrying

async def setup(bot):
    # Load all gambling modules
    bot.add_cog(CardGames(bot))
    bot.add_cog(ChanceGames(bot)) 
    bot.add_cog(SpecialGames(bot))
    bot.add_cog(Plinko(bot))
    bot.add_cog(Gambling(bot))
