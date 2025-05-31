import discord
import json
import random
import time
import sys
import os
import asyncio
import aiohttp
import traceback
from discord.ext import commands, tasks
from typing import Dict, List, Tuple
from os import system
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

# config
with open("data/config.json", "r") as f:
    config = json.load(f)

dev = config.get('DEV', False)  # Check if running in development mode

# List of guilds that have access to all features
MAIN_GUILD_IDS = [
    1259717095382319215,  # Main server
    1299747094449623111,  # South Bronx
    1142088882222022786   # Long Island
]

# setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.reactions = True

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
        self.guild_list = []  # Add this line to store guild IDs

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

    @tasks.loop(seconds=30)
    async def update_stats(self):
        """Update bot stats"""
        # Remove web interface stats update
        try:
            stats = {
                'server_count': len(self.guilds),
                'user_count': sum(g.member_count for g in self.guilds),
                'uptime': int(time.time() - self.start_time),
                'latency': round(self.latency * 1000, 2),
                'guilds': [str(g.id) for g in self.guilds],
                'shard_count': self.shard_count,
                'shard_stats': {
                    str(shard_id): {
                        'status': 'online',
                        'latency': shard.latency * 1000,
                        'guild_count': len([g for g in self.guilds if (g.id >> 22) % self.shard_count == shard_id]),
                        'uptime': int(time.time() - self.start_time)
                    }
                    for shard_id, shard in enumerate(self.shards.values())
                }
            }
            # Store stats locally
            with open('data/stats.json', 'w') as f:
                json.dump(stats, f, indent=2)
            
            # Send stats to both prod and dev environments
            async with aiohttp.ClientSession() as session:
                endpoints = {
                    'prod': 'https://bronxbot.onrender.com/api/stats',
                    'dev': 'http://localhost:5000/api/stats'
                }
                
                for env, url in endpoints.items():
                    try:
                        async with session.post(url, json=stats) as resp:
                            result = await resp.text()
                            if resp.status == 200:
                                logging.info(f"[{env.upper()}] Stats updated successfully: {result}")
                            else:
                                logging.error(f"[{env.upper()}] Failed to update stats: {resp.status} - {result}")
                                
                    except Exception as e:
                        logging.error(f"[{env.upper()}] Failed to update stats: {e}")
        except Exception as e:
            logging.error(f"Error updating stats: {e}")

    @update_stats.before_loop
    async def before_update_stats(self):
        """Wait until the bot is ready before starting the stats update loop"""
        await self.wait_until_ready()

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


bot = BronxBot(command_prefix='.', intents=intents, shard_count=2, case_insensitive=True)
bot.remove_command('help')

# loading config
COG_DATA = {
    "cogs": {
        "cogs.admin.Admin": "warning",
        "cogs.misc.Cypher": "cog", 
        "cogs.misc.MathRace": "cog", 
        "cogs.misc.TicTacToe": "cog",
        "cogs.bronx.Stats": "other", 
        "cogs.bronx.VoteBans": "other", 
        "cogs.bronx.Welcoming": "other",
        "cogs.unique.Multiplayer": "fun", 
        "cogs.Fun": "fun",
        "cogs.Giveaway": "fun",
        "cogs.unique.SyncRoles": "success", 
        "cogs.Help": "success", 
        "cogs.ModMail": "success", 
        "cogs.Utility": "cog",
        # cogs.unique.economy is now split into multiple cogs
        "cogs.economy.Economy": "success",
        "cogs.economy.Fishing": "success",
        "cogs.economy.Shop": "success",
        "cogs.economy.Trading": "success",
        "cogs.economy.Gambling": "success",
    },
    "colors": {
        "error": "\033[31m",      # Red
        "success": "\033[32m",    # Green
        "warning": "\033[33m",    # Yellow
        "info": "\033[34m",       # Blue
        "default": "\033[37m",    # White
        "disabled": "\033[90m",   # Bright Black (Gray)
        "fun": "\033[35m",        # Magenta
        "cog": "\033[36m",        # Cyan
        "other": "\033[94m"       # Bright Blue
    }
}

class CogLoader:
    @staticmethod
    def get_color_escape(color_name: str) -> str:
        return COG_DATA['colors'].get(color_name, COG_DATA['colors']['default'])

    @classmethod
    async def load_extension_safe(cls, bot: BronxBot, cog: str) -> Tuple[bool, str, float]:
        """Safely load an extension and return status, error (if any), and load time"""
        start = time.time()
        try:
            await bot.load_extension(cog)
            return True, "", time.time() - start
        except Exception as e:
            tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            return False, tb, time.time() - start

    @classmethod
    async def load_all_cogs(cls, bot: BronxBot) -> Tuple[int, int]:
        """Load all cogs and display results grouped by type"""
        results = []
        errors = []

        print(f"{cls.get_color_escape('info')}=== COG LOADING STATUS ===\033[0m".center(100))
        
        cog_groups = {}
        for cog, cog_type in COG_DATA["cogs"].items():
            if cog_type not in cog_groups:
                cog_groups[cog_type] = []
            cog_groups[cog_type].append(cog)

        for cog_type in sorted(cog_groups.keys()):
            cog_results = []
            
            for cog in cog_groups[cog_type]:
                success, error, load_time = await cls.load_extension_safe(bot, cog)
                
                status = "LOADED" if success else "ERROR"
                color = cls.get_color_escape('success' if success else 'error')
                cog_color = cls.get_color_escape(cog_type)
                
                line = f"[bronxbot] {cog_color}{cog:<24}\033[0m : {color}{status}\033[0m ({load_time:.2f}s)"
                cog_results.append(line)
                
                if not success:
                    errors.append((cog, error))
            
            print('\n'.join(cog_results))
            print()

        # summary
        success_count = len(COG_DATA["cogs"]) - len(errors)
        total = len(COG_DATA["cogs"])
        
        print(f"{cls.get_color_escape('success' if not errors else 'warning')}[SUMMARY] Loaded {success_count}/{total} cogs ({len(errors)} errors)\033[0m")
        
        # detailed error report if needed
        if errors:
            print("\nDetailed error report:")
            for cog, error in errors:
                print(f"\n{cls.get_color_escape('error')}[ERROR] {cog}:\033[0m")
                print(f"{error.strip()}")
        
        return success_count, len(errors)

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

    guild_cache_start = time.time()
    # Build guild cache
    for guild in bot.guilds:
        await guild.chunk()
    bot.boot_metrics['guild_cache_time'] = time.time() - guild_cache_start
    
    # Update presence
    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.playing,
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
            
            embed = discord.Embed(
                description=boot_info,
                color=discord.Color.green()
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
    
    activity = discord.Activity(
        type=discord.ActivityType.playing,
        name=f"with {len(bot.guilds)} servers | .help"
    )
    await bot.change_presence(activity=activity)

@bot.event
async def on_guild_join(guild):
    """Send welcome message when bot joins a new guild"""
    # Find first available channel
    channel = None
    for ch in guild.text_channels:
        try:
            if ch.permissions_for(guild.me).send_messages:
                channel = ch
                break
        except discord.HTTPException:
            continue
    
    if not channel:
        return

    embed = discord.Embed(
        description=(
            f"Thanks for adding me! 👋\n\n"
            "**What I can do:**\n"
            "• Customizable welcome messages\n"
            "• Economy & *Fake* Gambling\n"
            "• Basic utility commands (!help)\n"
            "• Fun commands and games\n"
            "• Moderation tools\n\n"
            "*The bot is still in active development, so feel free to suggest new features!*\n\n"
           
            "• Use .help to see available commands\n"
            "• Use .help <command> for detailed info\n"
            "• Join the [support server](https://discord.gg/furryporn)\n\n"
            "Have fun! 🎉"
        ),
        color=discord.Color.blue()
    )
    
    embed.set_thumbnail(url=bot.user.avatar.url)
    embed.set_footer(text="made with 💜 by ks.net", icon_url=bot.user.avatar.url)
    
    try:
        await channel.send(embed=embed)
    except discord.HTTPException as e:
        print(f"Failed to send welcome message in {guild.name}: {e}")

@bot.event
async def on_command_error(ctx: commands.Context, error: Exception):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.NotOwner):
        embed = discord.Embed(
            title="Error",
            description="❌ This command can only be used by the bot owner.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, commands.MissingPermissions):
        perms = ', '.join(error.missing_permissions)
        embed = discord.Embed(
            title="Error",
            description=f"❌ You need the following permissions: `{perms}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, commands.BotMissingPermissions):
        perms = ', '.join(error.missing_permissions)
        embed = discord.Embed(
            title="Error",
            description=f"❌ I need the following permissions: `{perms}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="Error",
            description=f"❌ Missing required argument: `{error.param.name}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed, delete_after=10)
    elif isinstance(error, commands.CommandOnCooldown):
        embed = discord.Embed(
            title="Cooldown",
            description=f"⏰ Try again in {error.retry_after:.2f}s",
            color=discord.Color.gold()
        )
        await ctx.send(embed=embed, delete_after=5)
    else:
        print(f"Unhandled error in {ctx.command}: {error}")
        traceback.print_exception(type(error), error, error.__traceback__)

@bot.command(name="restart", aliases=["reboot"])
@commands.is_owner()
async def restart(ctx):
    """Restart the bot"""
    embed = discord.Embed(
        description="🔄 Restarting bot...",
        color=discord.Color.orange()
    )
    msg = await ctx.reply(embed=embed)
    
    with open("data/restart_info.json", "w") as f:
        json.dump({
            "channel_id": ctx.channel.id,
            "message_id": msg.id
        }, f)
    
    os.execv(sys.executable, ['python'] + sys.argv)

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
    
    # Print startup info
    logging.info(f"Python version: {platform.python_version()}")
    logging.info(f"Discord.py version: {discord.__version__}")
    logging.info(f"Starting BronxBot with {bot.shard_count} shards")
    
    # Run the Discord bot
    if dev:
        logging.info("Running in development mode")
        system("clear" if os.name == "posix" else "cls")
        if os.name == "posix":
            sys.stdout.write("\x1b]2;BronxBot (DEV)\x07")
        bot.run(config['DEV_TOKEN'], log_handler=None)  # Disable default discord.py logging
    else:
        try:
            system("clear" if os.name == "posix" else "cls")
            if os.name == "posix":
                sys.stdout.write("\x1b]2;BronxBot\x07")
            bot.run(config['TOKEN'], log_handler=None)  # Disable default discord.py logging
        except Exception as e:
            logging.error(f"Failed to start the bot: {e}")
            traceback.print_exc()