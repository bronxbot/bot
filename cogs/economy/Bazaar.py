"""
Bazaar System Compatibility Shim
This file maintains backwards compatibility while loading the modular bazaar system.
"""

# Import the modular bazaar system
from .bazaar import Bazaar

async def setup(bot):
    """Setup function for the bazaar cog"""
    bot.add_cog(Bazaar(bot))
