# Main Fishing Module Loader
# Loads all fishing sub-modules and provides initialization

from nextcord.ext import commands
from cogs.logging.logger import CogLogger

class FishingMain(commands.Cog, name="Fishing"):
    """Main fishing module that coordinates all fishing functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger("FishingMain")
        
    @commands.command(name="fishing_reload", hidden=True)
    @commands.is_owner()
    async def reload_fishing_modules(self, ctx):
        """Reload all fishing modules - Owner only"""
        try:
            modules = [
                'cogs.economy.fishing.fishing_core',
                'cogs.economy.fishing.fishing_inventory', 
                'cogs.economy.fishing.fishing_selling',
                'cogs.economy.fishing.fishing_stats'
            ]
            
            for module in modules:
                try:
                    await self.bot.reload_extension(module)
                    self.logger.info(f"Reloaded {module}")
                except Exception as e:
                    self.logger.error(f"Failed to reload {module}: {e}")
                    return await ctx.reply(f"❌ Failed to reload {module}: {e}")
            
            await ctx.reply("✅ All fishing modules reloaded successfully!")
            
        except Exception as e:
            self.logger.error(f"Failed to reload fishing modules: {e}")
            await ctx.reply("❌ Failed to reload fishing modules!")

async def setup(bot):
    """Setup function to load all fishing modules"""
    
    # Load all fishing sub-modules
    fishing_modules = [
        'cogs.economy.fishing.fishing_core',
        'cogs.economy.fishing.fishing_inventory',
        'cogs.economy.fishing.fishing_selling', 
        'cogs.economy.fishing.fishing_stats'
    ]
    
    for module in fishing_modules:
        try:
            bot.load_extension(module)
            print(f"✅ Loaded fishing module: {module}")
        except Exception as e:
            print(f"❌ Failed to load fishing module {module}: {e}")
            raise e
    
    # Load the main coordinator
    bot.add_cog(FishingMain(bot))
    print("✅ Loaded fishing main coordinator")
