from bronxbot import *
from cogInfo import CogLoader

@bot.event
async def on_ready():
    """Called when the bot is ready"""
    logging.info(f"Bot ready as {bot.user.name} ({bot.user.id})")
    
    # Load all cogs using CogLoader
    try:
        logging.info("Loading cogs...")
        success_count, error_count = await CogLoader.load_all_cogs(bot)
        logging.info(f"Loaded {success_count} cogs with {error_count} errors")
        
    except Exception as e:
        logging.error(f"Error during cog loading: {e}")
        traceback.print_exc()
    
    # Start the stats update loop after cogs are loaded
    if not hasattr(bot, 'update_stats'):
        logging.error("update_stats task not found")
        return
    if not bot.update_stats.is_running():
        bot.update_stats.start()
        logging.info("Started stats update loop")

    # Start command usage tracker auto-save
    try:
        usage_tracker.start_auto_save()
        logging.info("Started command usage tracker auto-save")
    except Exception as e:
        logging.error(f"Failed to start command usage tracker: {e}")

    # Initialize scalability manager
    try:
        bot.scalability_manager = await initialize_scalability(bot)
        logging.info("Scalability manager initialized successfully")
    except Exception as e:
        logging.warning(f"Scalability manager initialization failed: {e}")
        bot.scalability_manager = None

    # Load additional cogs manually
    try:
        # Load TOS handler
        bot.load_extension('utils.tos_handler')
        logging.info("TOS handler loaded successfully")
        
        # Load Setup wizard
        bot.load_extension('cogs.setup.SetupWizard') 
        logging.info("Setup wizard loaded successfully")
        
        # Load SlashCommandManager
        bot.load_extension('cogs.utility.SlashCommandManager')
        logging.info("SlashCommandManager loaded successfully")
        
        # Load SlashCommands cog
        bot.load_extension('cogs.admin.SlashCommands')
        logging.info("SlashCommands cog loaded successfully")
    except Exception as e:
        logging.error(f"Failed to load additional cogs: {e}")

    # Auto-sync slash commands for main guilds
    try:
        if hasattr(bot, 'MAIN_GUILD_IDS'):
            for guild_id in bot.MAIN_GUILD_IDS:
                try:
                    synced = await bot.sync_application_commands(guild_id=guild_id)
                    guild = bot.get_guild(guild_id)
                    guild_name = guild.name if guild else f"ID:{guild_id}"
                    logging.info(f"Auto-synced {len(synced)} slash commands to {guild_name}")
                except Exception as e:
                    logging.warning(f"Failed to auto-sync slash commands to guild {guild_id}: {e}")
        else:
            logging.info("No MAIN_GUILD_IDS found, skipping auto-sync")
    except Exception as e:
        logging.error(f"Error during auto-sync of slash commands: {e}")

    # Initialize database and clean up corrupted inventory data
    try:
        from utils.db import db
        await db.ensure_connected()
        logging.info("Database connection established")
        
        # Run inventory cleanup on startup to remove corrupted data
        cleaned_count = await db.cleanup_corrupted_inventory()
        if cleaned_count > 0:
            logging.info(f"Cleaned up {cleaned_count} corrupted inventory items on startup")
        else:
            logging.info("No corrupted inventory items found during startup cleanup")
    except ImportError:
        logging.warning("Database module not available, skipping database initialization")
    except Exception as e:
        logging.error(f"Failed to initialize database or cleanup inventory: {e}")

    guild_cache_start = time.time()
    # Build guild cache
    for guild in bot.guilds:
        await guild.chunk()
    bot.boot_metrics['guild_cache_time'] = time.time() - guild_cache_start
    
    # Update presence
    await bot.change_presence(
        activity=nextcord.Activity(
            type=nextcord.ActivityType.playing,
            name=f"with {len(bot.guilds)} servers | .help"
        )
    )
    
    if bot.restart_channel and bot.restart_message:
        try:
            channel = await bot.fetch_channel(bot.restart_channel)
            message = await channel.fetch_message(bot.restart_message)
            
            bot.boot_metrics['total_boot_time'] = time.time() - bot.boot_metrics['start_time']
            bot.boot_metrics['ready_time'] = time.time() - bot.start_time
            bot.boot_metrics['total_cog_load_time'] = sum(bot.cog_load_times.values())
            
            boot_info = (
                f"✅ Boot completed in `{bot.boot_metrics['total_boot_time']:.2f}s`\n\n"
                f"**Boot Metrics:**\n"
                f"• Config Load: `{bot.boot_metrics['config_load_time']:.2f}s`\n"
                f"• Guild Cache: `{bot.boot_metrics['guild_cache_time']:.2f}s`\n"
                f"• Total Cog Load: `{bot.boot_metrics['total_cog_load_time']:.2f}s`\n"
                f"• Ready Time: `{bot.boot_metrics['ready_time']:.2f}s`\n\n"
                f"**Individual Cog Load Times:**\n" + 
                "\n".join([f"• `{cog.split('.')[-1]}: {time:.2f}s`" 
                          for cog, time in sorted(bot.cog_load_times.items())])
            )
            
            embed = nextcord.Embed(
                description=boot_info,
                color=nextcord.Color.green()
            )
            await message.edit(embed=embed)
        except Exception as e:
            print(f"Failed to update restart message: {e}")

    """success, errors = await CogLoader.load_all_cogs(bot)
    status_msg = (
        f"[?] Logged in as {bot.user.name} (ID: {bot.user.id})\n"
        f"[!] Shards: {bot.shard_count}, Latency: {round(bot.latency * 1000, 2)}ms\n"
        f"[+] Cogs: {success} loaded, {errors} errors"
    )
    print(status_msg)"""
    
    activity = nextcord.Activity(
        type=nextcord.ActivityType.playing,
        name=f"with {len(bot.guilds)} servers | .help"
    )
    await bot.change_presence(activity=activity)
    
    # Start additional stats tracker
    if not additional_stats_update.is_running():
        additional_stats_update.start()
        logging.info("Started additional stats update loop")
    
    if not reset_daily_stats.is_running():
        reset_daily_stats.start()
        logging.info("Started daily stats reset loop")
        
    # Debug: Check slash commands after everything is fully loaded
    await asyncio.sleep(2)  # Give a moment for all initializations to complete
    logging.info("=== FINAL SLASH COMMAND CHECK ===")
    all_commands = bot.get_all_application_commands()
    logging.info(f"Total application commands registered: {len(all_commands)}")
    
    for cmd in all_commands:
        guild_info = getattr(cmd, 'guild_ids', None) or 'Global'
        logging.info(f"• {cmd.name} (Type: {type(cmd).__name__}, Guild: {guild_info})")
    
    if not all_commands:
        logging.warning("No application commands found! This might be why sync shows 0 commands.")
    logging.info("=====================================")