import nextcord
import random
import json
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import db

logger = CogLogger('Welcoming')

def load_welcome_data():
    with open('data/welcome.json', 'r') as f:
        return json.load(f)

WELCOME_DATA = load_welcome_data()

def welcome_embed(member):
    # Get a random character key from the dictionary
    character_name = random.choice(list(WELCOME_DATA["characters"].keys()))
    character = WELCOME_DATA["characters"][character_name]
    character_url = character['image']
    
    return nextcord.Embed(
        description=f"\"{random.choice(character['messages'])}\"\n\n[main](https://discord.gg/furryporn) • [backup](https://discord.gg/W563EnFwed) • [appeal](https://discord.gg/6Th9dsw6rM)",
        color=nextcord.Color.random()
    ).set_author(
        name=character_name,  # Use the character name directly
        icon_url=character_url,
        url="https://discord.gg/6Th9dsw6rM"
    ).set_footer(text="click name to appeal if banned")

class Welcoming(commands.Cog):
    """Welcoming and stats tracking for new and leaving members."""
    def __init__(self, bot):
        self.bot = bot
        self.main_guilds = getattr(self.bot, "MAIN_GUILD_IDS", [])

    async def cog_check(self, ctx):
        """Check if the guild has permission to use this cog's commands."""
        return ctx.guild and ctx.guild.id in self.main_guilds

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id not in self.main_guilds:
            return

        # Load welcome channel from environment or use default
        import os
        welcome_channel = int(os.getenv('WELCOME_CHANNEL', '1378156495144751147'))

        logger.info(f"[+] Member joined: {member} in guild {member.guild.id}")

        greetings = ["hi", "yo", "hola", "bonjour", "hhhjhhhiiiiii", "haiiiiii :3", "haaaaaaaiiiiiii", "hello", "hhiihihihiihihi"]
        emoji = random.choice(member.guild.emojis) if member.guild.emojis else ""
        if member.guild.id == 1259717095382319215:
            channel = member.guild.get_channel(welcome_channel)
            if channel:
                await channel.send(f"{member.mention} {random.choice(greetings)} {emoji}")
            embed = welcome_embed(member)
            try:
                await member.send(embed=embed)
            except nextcord.Forbidden:
                logger.warning(f"Could not DM {member} (forbidden).")
            try:
                await db.store_stats(member.guild.id, "gained")
            except Exception as e:
                logger.error(f"Failed to store join stats: {e}")

    @commands.command()
    async def welcometest(self, ctx):
        """Test the welcome embed in your DMs."""
        try:
            await ctx.author.send(embed=welcome_embed(ctx.author))
            await ctx.reply("Check your DMs for the welcome message!")
        except nextcord.Forbidden:
            await ctx.reply("Couldn't DM you! Please enable DMs from server members.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id not in self.main_guilds:
            return
        logger.info(f"[-] Member left: {member} in guild {member.guild.id}")
        if member.guild.id == 1259717095382319215:
            try:
                await db.store_stats(member.guild.id, "lost")
            except Exception as e:
                logger.error(f"Failed to store leave stats: {e}")

async def setup(bot):
    try:
        bot.add_cog(Welcoming(bot))
    except Exception as e:
        logger.error(f"Failed to load Welcoming cog: {e}")
        raise e
