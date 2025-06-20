import nextcord
from nextcord.ext import commands
import traceback
from cogs.logging.logger import CogLogger

class ErrorHandler:
    """Base class for error handling in cogs"""
    
    def __init__(self):
        self.logger = CogLogger(self.__class__.__name__)

    async def handle_error(self, ctx, error, command_name=None):
        """Common error handling logic for all cogs"""
        # Get error context
        command = command_name or ctx.command.qualified_name if ctx.command else "Unknown"
        author = f"{ctx.author} ({ctx.author.id})"
        guild = f"{ctx.guild} ({ctx.guild.id})" if ctx.guild else "DM"
        
        # Generate error trace
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

        # Handle common error types
        try:
            if isinstance(error, commands.MissingPermissions):
                await ctx.reply(f"❌ You need {', '.join(error.missing_permissions)} permission(s) to use this command!")
                
            elif isinstance(error, commands.BotMissingPermissions):
                await ctx.reply("❌ I don't have the required permissions for this command!")
                
            elif isinstance(error, commands.BadArgument):
                await ctx.reply(f"❌ Invalid argument provided: {str(error)}")
                
            elif isinstance(error, commands.DisabledCommand):
                await ctx.reply("❌ This command is currently disabled")
                
            elif isinstance(error, commands.NoPrivateMessage):
                await ctx.reply("❌ This command cannot be used in DMs")
                
            elif isinstance(error, commands.CheckFailure):
                await ctx.reply("❌ You don't meet the requirements to use this command")
                
            else:
                pass
                
        except Exception as e:
            self.logger.error(f"Error handling error: {e}")
            
        return error_id
