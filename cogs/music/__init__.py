"""
Music cog package for BronxBot
Handles all music-related functionality including playback, queue management, and audio controls.
Main music system now uses robust alternative methods to bypass YouTube restrictions.
"""

from .core import MusicCore
from .queue import MusicQueue
from .controls import MusicControls
from .alt_player import AlternativeMusicPlayer

__all__ = ['MusicCore', 'MusicQueue', 'MusicControls', 'AlternativeMusicPlayer']

async def setup(bot):
    """Setup function to load all music cogs - Alternative player is now primary"""
    # Load core music functionality first
    bot.add_cog(MusicCore(bot))
    
    # Load queue management
    bot.add_cog(MusicQueue(bot))
    
    # Load music controls
    bot.add_cog(MusicControls(bot))
    
    # Load alternative music player (main implementation)
    bot.add_cog(AlternativeMusicPlayer(bot))
    
    print("[Music] 🎵 All music modules loaded successfully with robust YouTube access")
