from imports import *
from stats import StatsTracker
import math
# Note: bronxbot.py has most necessary imports for main & related files, so import bronxbot.py if you're too lazy to import everything

# Need to import specific functions for some odd reason

# Put BronxBot in a separate class, modularization and ease of use

# List of guilds that have access to all features
MAIN_GUILD_IDS = [
    1259717095382319215,  # Main server
    1299747094449623111,  # South Bronx
    1142088882222022786   # Long Island
]

class BronxBot(commands.AutoShardedBot):
    def __init__(self, *args, **kwargs):
        self.boot_metrics = {
            'start_time': time.time(),
            'config_load_time': 0,
            'cog_load_times': {},
            'total_cog_load_time': 0,
            'guild_cache_time': 0,
            'total_boot_time': 0,
            'ready_time': 0
        }
        
        config_start = time.time()
        super().__init__(*args, **kwargs)
        self.boot_metrics['config_load_time'] = time.time() - config_start
        
        self.start_time = time.time()
        self.cog_load_times = {}
        self.restart_channel = None
        self.restart_message = None
        self.MAIN_GUILD_IDS = MAIN_GUILD_IDS
        self.guild_list = []
        self.stats_tracker = None  # Will be initialized later

    async def load_cog_with_timing(self, cog_name: str) -> Tuple[bool, float]:
        """Load a cog and measure its loading time"""
        start_time = time.time()
        try:
            await self.load_extension(cog_name)
            load_time = time.time() - start_time
            self.cog_load_times[cog_name] = load_time
            return True, load_time
        except Exception as e:
            load_time = time.time() - start_time
            self.cog_load_times[cog_name] = load_time
            return False, load_time

    @tasks.loop(minutes=5)  # Check every 5 minutes, no need to do it as frequently as stats
    async def update_guilds(self):
        """Update guild list for the web interface"""
        try:
            self.guild_list = [str(g.id) for g in self.guilds]
            
            async with aiohttp.ClientSession() as session:
                async with session.post('https://bronxbot.onrender.com/api/stats', 
                                      json={'guilds': self.guild_list}) as resp:
                    if resp.status != 200:
                        print(f"Failed to update guild list: {resp.status}")
        except Exception as e:
            print(f"Error updating guild list: {e}")

    @update_guilds.before_loop
    async def before_update_guilds(self):
        await self.wait_until_ready()

    async def send_realtime_command_update(self, command_name: str, user_id: int, guild_id: int = None, execution_time: float = 0, error: bool = False):
        """Send real-time command update to dashboard"""
        try:
            update_data = {
                'type': 'command_update',
                'command': command_name,
                'user_id': str(user_id),
                'guild_id': str(guild_id) if guild_id else None,
                'execution_time': execution_time,
                'error': error,
                'timestamp': time.time()
            }
            
            dashboard_urls = ['https://bronxbot.onrender.com/api/realtime'] if not dev else ['http://localhost:5000/api/realtime']
            
            async with aiohttp.ClientSession() as session:
                for url in dashboard_urls:
                    try:
                        async with session.post(url, json=update_data, timeout=5) as resp:
                            if resp.status == 200:
                                logging.debug("Real-time command update sent successfully")
                                break
                    except Exception as e:
                        logging.debug(f"Failed to send real-time update to {url}: {e}")
        except Exception as e:
            logging.debug(f"Error sending real-time command update: {e}")

    async def close(self):
        """Gracefully close bot connections"""
        logging.info("Shutting down bot...")
        
        # Stop background tasks
        if hasattr(self, 'update_stats') and self.update_stats.is_running():
            self.update_stats.stop()
            logging.info("Stopped stats update loop")
        
        if hasattr(self, 'update_guilds') and self.update_guilds.is_running():
            self.update_guilds.stop()
            logging.info("Stopped guild update loop")
        
        # Stop additional stats tasks
        try:
            if additional_stats_update.is_running():
                additional_stats_update.stop()
                logging.info("Stopped additional stats update loop")
        except:
            pass
            
        try:
            if reset_daily_stats.is_running():
                reset_daily_stats.stop()
                logging.info("Stopped daily stats reset loop")
        except:
            pass
        
        # Shutdown scalability manager
        if hasattr(self, 'scalability_manager') and self.scalability_manager:
            await self.scalability_manager.shutdown()
            logging.info("Scalability manager shutdown complete")
        
        # Close database connections (only if db module exists)
        try:
            from utils.db import async_db
            if hasattr(async_db, '_client') and async_db._client:
                async_db._client.close()
                logging.info("Closed database connections")
        except ImportError:
            logging.debug("Database module not available, skipping cleanup")
        except Exception as e:
            logging.error(f"Error closing database: {e}")
        
        # Close aiohttp sessions and other resources
        await super().close()
        logging.info("Bot shutdown complete")

# setup
intents = discord.Intents.all()
intents.message_content = True

with open("data/config.json", "r") as f:
    config = json.load(f)

dev = config.get('DEV', False)

bot = BronxBot(
    command_prefix='.',
    intents=intents,
    shard_count=math.ceil(config["GUILD_COUNT"]/20),
    case_insensitive=True,
    application_id=config["CLIENT_ID"]
)
bot.remove_command('help')

@tasks.loop(minutes=10)  # Send additional stats every 10 minutes
async def additional_stats_update():
    """Send additional stats updates to dashboard"""
    try:
        if hasattr(bot, 'stats_tracker'):
            await bot.stats_tracker.send_stats()
            logging.debug("Additional stats update sent successfully")
    except Exception as e:
        logging.error(f"Error in additional stats update: {e}")

@additional_stats_update.before_loop
async def before_additional_stats_update():
    """Wait until the bot is ready before starting additional stats updates"""
    await bot.wait_until_ready()

@tasks.loop(hours=24)
async def reset_daily_stats():
    try:
        bot.stats_tracker.daily_commands = 0
        logging.info("Daily stats reset completed")
    except Exception as e:
        logging.error(f"Error resetting daily stats: {e}")

# Export objects needed by main.py
additional_stats_update = additional_stats_update
reset_daily_stats = reset_daily_stats
stats_tracker = bot.stats_tracker