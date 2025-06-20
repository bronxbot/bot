"""
Trading System Compatibility Shim
This file maintains backwards compatibility while loading the modular trading system.
"""

# Import the modular trading system
from .trading import Trading

async def setup(bot):
    """Setup function for the trading cog"""
    bot.add_cog(Trading(bot))
