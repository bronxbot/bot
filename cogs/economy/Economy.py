"""
Economy System Compatibility Shim
This file maintains backwards compatibility while loading the modular economy system.
"""

# Import the modular economy system
from .economy import Economy

async def setup(bot):
    """Setup function for the economy cog"""
    bot.add_cog(Economy(bot))
