"""
Work System Compatibility Shim
This file maintains backwards compatibility while loading the modular work system.
"""

# Import the modular work system
from .work import Work

async def setup(bot):
    """Setup function for the work cog"""
    bot.add_cog(Work(bot))
