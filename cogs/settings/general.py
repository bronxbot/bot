"""
COMPATIBILITY SHIM - This file has been modularized
The new modular general settings system is located in cogs/settings/general/
This shim provides backwards compatibility for imports.

Original file backed up as: general.py.backup
"""

# Import the modularized version
from .general.general_cog import GeneralSettings

# Re-export for compatibility
__all__ = ['GeneralSettings']

# Async setup function for the cog
async def setup(bot):
    """Set up the General Settings cog"""
    bot.add_cog(GeneralSettings(bot))
