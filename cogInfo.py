from bronxbot import *
# loading config
COG_DATA = {
    "cogs": {
        "cogs.admin.Admin": "warning",
        "cogs.admin.Performance": "warning",  # Add performance monitoring
        "cogs.misc.Cypher": "cog", 
        "cogs.misc.MathRace": "cog", 
        "cogs.misc.TicTacToe": "cog",
        "cogs.Stats": "other", 
        "cogs.bronx.AI": "other",
        "cogs.bronx.VoteBans": "other", 
        "cogs.bronx.Welcoming": "other",
        "cogs.unique.Multiplayer": "fun", 
        "cogs.fun.Fun": "fun",
        "cogs.fun.Text": "fun",
        "cogs.unique.SyncRoles": "success",        "cogs.Help": "success", 
        "cogs.ModMail": "success", 
        "cogs.Reminders": "success",
        "cogs.Utility": "cog",
        "cogs.economy.Economy": "success",
        "cogs.economy.fishing": "success",
        "cogs.economy.fishing.AutoFishing": "success",
        "cogs.economy.Shop": "success",
        "cogs.economy.Giveaway": "success",
        "cogs.economy.Trading": "success",
        "cogs.economy.Gambling": "success",
        "cogs.economy.Work": "success",
        "cogs.economy.Bazaar": "success",
        "cogs.settings.general": "success",
        "cogs.settings.moderation": "success", 
        "cogs.settings.economy": "success",
        "cogs.settings.music": "success",
        "cogs.settings.welcome": "success",
        "cogs.settings.logging": "success",
        "cogs.Error": "success",
        "cogs.music": "fun",
        #"cogs.Security": "success", disabled for now
        #"cogs.LastFm": "disabled",  disabled for now
    },
    "colors": {
        "error": "\033[31m",      # Red
        "success": "\033[32m",    # Green
        "warning": "\033[33m",    # Yellow
        "info": "\033[34m",       # Blue
        "default": "\033[37m",    # White
        "disabled": "\033[90m",   # Bright Black (Gray)
        "fun": "\033[35m",        # Magenta
        "cog": "\033[36m",        # Cyan
        "other": "\033[94m"       # Bright Blue
    }
}

class CogLoader:
    @staticmethod
    def get_color_escape(color_name: str) -> str:
        return COG_DATA['colors'].get(color_name, COG_DATA['colors']['default'])

    @classmethod
    async def load_extension_safe(cls, bot: BronxBot, cog: str) -> Tuple[bool, str, float]:
        """Safely load an extension and return status, error (if any), and load time"""
        start = time.time()
        try:
            await bot.load_extension(cog)
            return True, "", time.time() - start
        except Exception as e:
            tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
            return False, tb, time.time() - start

    @classmethod
    async def load_all_cogs(cls, bot: BronxBot) -> Tuple[int, int]:
        """Load all cogs and display results grouped by type"""
        results = []
        errors = []

        print(f"{cls.get_color_escape('info')}=== COG LOADING STATUS ===\033[0m".center(100))
        
        cog_groups = {}
        for cog, cog_type in COG_DATA["cogs"].items():
            if cog_type not in cog_groups:
                cog_groups[cog_type] = []
            cog_groups[cog_type].append(cog)

        for cog_type in sorted(cog_groups.keys()):
            cog_results = []
            
            for cog in cog_groups[cog_type]:
                success, error, load_time = await cls.load_extension_safe(bot, cog)
                
                status = "LOADED" if success else "ERROR"
                color = cls.get_color_escape('success' if success else 'error')
                cog_color = cls.get_color_escape(cog_type)
                
                line = f"[bronxbot] {cog_color}{cog:<24}\033[0m : {color}{status}\033[0m ({load_time:.2f}s)"
                cog_results.append(line)
                
                if not success:
                    errors.append((cog, error))
            
            print('\n'.join(cog_results))
            print()

        # summary
        success_count = len(COG_DATA["cogs"]) - len(errors)
        total = len(COG_DATA["cogs"])
        
        print(f"{cls.get_color_escape('success' if not errors else 'warning')}[SUMMARY] Loaded {success_count}/{total} cogs ({len(errors)} errors)\033[0m")
        
        # detailed error report if needed
        if errors:
            print("\nDetailed error report:")
            for cog, error in errors:
                print(f"\n{cls.get_color_escape('error')}[ERROR] {cog}:\033[0m")
                print(f"{error.strip()}")
        
        return success_count, len(errors)
