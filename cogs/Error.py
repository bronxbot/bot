import nextcord
from nextcord.ext import commands
from cogs.logging.logger import CogLogger
import traceback

logger = CogLogger('Error')

class Error(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger('Error')
        
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error handler for all command errors"""
        
        if isinstance(error, commands.CommandNotFound):
            # Ignore command not found errors
            return
            
        # Get command info for logging
        command = ctx.command.qualified_name if ctx.command else "unknown"
        author = f"{ctx.author} ({ctx.author.id})"
        guild = f"{ctx.guild} ({ctx.guild.id})" if ctx.guild else "DM"
        
        # Generate full traceback
        error_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        error_id = hex(abs(hash(str(error))))[-6:]
        
        # Log the error
        self.logger.error(
            f"Command error in {command} (ID: {error_id}):\n"
            f"User: {author}\n" 
            f"Guild: {guild}\n"
            f"Error: {str(error)}\n"
            f"Traceback:\n{error_trace}"
        )

        # Handle specific error types with user-friendly messages
        try:
            if isinstance(error, commands.MissingPermissions):
                perms = ', '.join(error.missing_permissions)
                embed = nextcord.Embed(
                    title="❌ Missing Permissions",
                    description=f"You need the following permissions: `{perms}`",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.BotMissingPermissions):
                perms = ', '.join(error.missing_permissions)
                embed = nextcord.Embed(
                    title="❌ Bot Missing Permissions",
                    description=f"I need the following permissions: `{perms}`",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.NotOwner):
                embed = nextcord.Embed(
                    title="❌ Access Denied",
                    description="This command can only be used by the bot owner.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.MissingRequiredArgument):
                embed = nextcord.Embed(
                    title="❌ Missing Argument",
                    description=f"Missing required argument: `{error.param.name}`\n"
                               f"Use `{ctx.prefix}help {command}` for usage information.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=15)
                
            elif isinstance(error, commands.BadArgument):
                embed = nextcord.Embed(
                    title="❌ Invalid Argument",
                    description=f"Invalid argument provided: {str(error)}\n"
                               f"Use `{ctx.prefix}help {command}` for usage information.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=15)
                
            elif isinstance(error, commands.CommandOnCooldown):
                embed = nextcord.Embed(
                    title="⏰ Command on Cooldown",
                    description=f"Try again in {error.retry_after:.1f}s",
                    color=nextcord.Color.gold()
                )
                await ctx.reply(embed=embed, delete_after=5)
                
            elif isinstance(error, commands.DisabledCommand):
                embed = nextcord.Embed(
                    title="❌ Command Disabled",
                    description="This command is currently disabled.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.NoPrivateMessage):
                embed = nextcord.Embed(
                    title="❌ Server Only",
                    description="This command cannot be used in direct messages.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            elif isinstance(error, commands.CheckFailure):
                embed = nextcord.Embed(
                    title="❌ Check Failed",
                    description="You don't meet the requirements to use this command.",
                    color=nextcord.Color.red()
                )
                await ctx.reply(embed=embed, delete_after=10)
                
            else:
                # Unhandled error occurred
                embed = nextcord.Embed(
                    title="❌ Unexpected Error",
                    description=f"An unexpected error occurred! Error ID: `{error_id}`\n"
                               "This has been logged and will be investigated.",
                    color=nextcord.Color.dark_red()
                )
                await ctx.reply(embed=embed, delete_after=30)
                
        except Exception as handling_error:
            # Error occurred while handling the original error
            self.logger.error(f"Error while handling error {error_id}: {handling_error}")
            try:
                await ctx.reply(f"❌ Multiple errors occurred! Error ID: `{error_id}`")
            except Exception as reply_error:
                self.logger.error(f"Failed to send error message: {reply_error}")
                pass  # Give up if we can't even send a basic message

async def setup(bot):
    try:
        bot.add_cog(Error(bot))
        logger.info("Error handling cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Error cog: {e}")
        raise
