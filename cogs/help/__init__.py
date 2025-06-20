# Help System Module
# Modular help system for BronxBot

from .help_cog import Help

async def setup(bot):
    """Setup function for the Help cog"""
    bot.add_cog(Help(bot))
