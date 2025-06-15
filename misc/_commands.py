import discord
from discord.ext import commands
from utils.error_handler import ErrorHandler
from cogs.logging.logger import CogLogger

def setup(bot): # setup function like this every time you make a standalone command
    @bot.command(name="settings", case_insensitive = True)
    @commands.has_permissions(manage_guild=True)
    async def settings(ctx):
        """Command used to access all settings categories."""
        embed = discord.Embed(
            title="🔧 Settings",
            description=(
                "Access all settings for the bot\n\n"
                "**Available Commands:**\n"
                "`.general` - General settings\n"
                "`.moderation` - Moderation settings\n"
                "`.logging` - Logging settings\n"
                "`.music` - Music settings\n"
                "`.economy` - Economy settings\n"
                "`.welcome` - Welcome settings\n"
            ),
            color=0x3498db
        )
        await ctx.send(embed=embed)
    @bot.command(name="test", case_insensitive=True)
    @commands.has_permissions(manage_guild=True)
    async def test(ctx):
        """Test command(NOT FOR USERS)"""
        message = discord.message(
            message=("hi")
        )
        await ctx.send(message=message)

