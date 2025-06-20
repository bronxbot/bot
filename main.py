# Note: Had to do SO many workarounds for circular imports, the code was all jumbled so modularization at this point was almost impossible, barely managed it

# Way better looking imports
from imports import *
from bronxbot import bot, BronxBot, additional_stats_update, reset_daily_stats, stats_tracker, config, dev  # gotta import separate classes outside of imports.py to avoid circular imports
from cogInfo import CogLoader
from botEvents.onReady import *
from botEvents.onCommand import *
from botEvents.onMessage import *
from misc._commands import setup
from misc.blacklist import blacklist_check

setup(bot)

if os.path.exists("data/restart_info.json"):
    try:
        with open("data/restart_info.json", "r") as f:
            restart_info = json.load(f)
            bot.restart_channel = restart_info["channel_id"]
            bot.restart_message = restart_info["message_id"]
        os.remove("data/restart_info.json")
    except Exception as e:
        print(f"Failed to load restart info: {e}")

if __name__ == "__main__":
    import platform
    
    # Set logging level to reduce verbosity
    logging.getLogger('nextcord.gateway').setLevel(logging.WARNING)
    logging.getLogger('nextcord.client').setLevel(logging.WARNING)
    logging.getLogger('nextcord.http').setLevel(logging.WARNING)
    
    # Print startup info
    logging.info(f"Python version: {platform.python_version()}")
    logging.info(f"Nextcord version: {nextcord.__version__}")
    logging.info(f"Starting BronxBot with {bot.shard_count} shards")
    
    # Run the Discord bot
    if dev:
        logging.info("Running in development mode")
        system("clear" if os.name == "posix" else "cls")
        if os.name == "posix":
            sys.stdout.write("\x1b]2;BronxBot (DEV)\x07")
        bot.run(config['DEV_TOKEN'])  # Run with dev token
    else:
        try:
            system("clear" if os.name == "posix" else "cls")
            if os.name == "posix":
                sys.stdout.write("\x1b]2;BronxBot\x07")
            bot.run(config['TOKEN'])  # Run with production token
        except Exception as e:
            logging.error(f"Failed to start the bot: {e}")
            traceback.print_exc()
