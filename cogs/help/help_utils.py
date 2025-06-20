import nextcord
from nextcord.ext import commands
from typing import List, Tuple, Dict, Any
import re

class HelpUtils:
    """Utility functions for the help system"""
    
    def __init__(self, bot):
        self.bot = bot

    def categorize_cog(self, cog_name: str) -> str:
        """Determine which category a cog belongs to"""
        categories = {
            'Economy': ['Economy', 'Work', 'Shop', 'Bazaar', 'Giveaway', 'Trading'],
            'Fun & Games': ['Fun', 'Text', 'MathRace', 'TicTacToe', 'Multiplayer', 'Cypher'],
            'Music': ['Music', 'MusicControls', 'MusicPlayer', 'MusicQueue'],
            'Moderation': ['Moderation', 'VoteBans', 'AutoMod'],
            'Utility': ['Utility', 'Help', 'Stats', 'Status'],
            'Economy - Fishing': ['FishingCore', 'FishingStats', 'FishingSelling', 'FishingInventory', 'AutoFishing'],
            'Economy - Gambling': ['Gambling', 'CardGames', 'ChanceGames', 'SpecialGames', 'Plinko'],
            'Settings': ['ServerSettings', 'GeneralSettings', 'ModerationSettings', 'WelcomeSettings', 'LoggingSettings', 'EconomySettings', 'MusicSettings'],
            'Admin': ['Admin', 'Performance', 'SyncRoles'],
            'Special': ['AI', 'Welcoming', 'Reminders', 'SetupWizard', 'ModMail']
        }
        
        for category, cogs in categories.items():
            if cog_name in cogs:
                return category
        
        return 'Other'

    def should_show_cog(self, cog_name: str, user_id: int) -> bool:
        """Determine if a cog should be shown to the user"""
        BOT_ADMINS = [814226043924643880]  # Add your admin IDs
        
        # Admin-only cogs
        admin_only = {'Admin', 'Performance', 'SyncRoles', 'Stats'}
        if cog_name in admin_only and user_id not in BOT_ADMINS:
            return False
        
        # Hidden cogs
        hidden = {'ErrorHandler', 'Logger', 'CommandTracker'}
        if cog_name in hidden:
            return False
        
        return True

    def prettify_cog_name(self, cog_name: str) -> str:
        """Convert cog names to prettier display names"""
        name_mappings = {
            'Economy': '💰 Economy',
            'Work': '💼 Work & Jobs',
            'Shop': '🛍️ Shop',
            'Bazaar': '🏪 Bazaar',
            'Trading': '🤝 Trading',
            'Giveaway': '🎁 Giveaways',
            'FishingCore': '🎣 Fishing',
            'FishingStats': '📊 Fishing Stats',
            'FishingSelling': '💰 Fish Market',
            'FishingInventory': '🎒 Fishing Gear',
            'AutoFishing': '🤖 Auto Fishing',
            'Gambling': '🎰 Gambling',
            'CardGames': '🃏 Card Games',
            'ChanceGames': '🎲 Chance Games',
            'SpecialGames': '🎪 Special Games',
            'Plinko': '🏀 Plinko',
            'Fun': '🎮 Fun Commands',
            'Text': '📝 Text Tools',
            'MathRace': '🧮 Math Race',
            'TicTacToe': '⭕ Tic Tac Toe',
            'Multiplayer': '👥 Multiplayer Games',
            'Cypher': '🔐 Encryption',
            'Music': '🎵 Music Player',
            'MusicControls': '🎛️ Music Controls',
            'MusicPlayer': '▶️ Music Playback',
            'MusicQueue': '📝 Music Queue',
            'Moderation': '🛡️ Moderation',
            'VoteBans': '🗳️ Vote Bans',
            'AutoMod': '🤖 Auto Moderation',
            'Utility': '🔧 Utility',
            'Help': '❓ Help System',
            'Stats': '📈 Statistics',
            'Status': '📊 Bot Status',
            'ServerSettings': '⚙️ Server Settings',
            'GeneralSettings': '🔧 General Settings',
            'ModerationSettings': '🛡️ Moderation Settings',
            'WelcomeSettings': '👋 Welcome Settings',
            'LoggingSettings': '📝 Logging Settings',
            'EconomySettings': '💰 Economy Settings',
            'MusicSettings': '🎵 Music Settings',
            'Admin': '👑 Admin Tools',
            'Performance': '⚡ Performance',
            'SyncRoles': '🔄 Role Sync',
            'AI': '🤖 AI Chat',
            'Welcoming': '👋 Welcome System',
            'Reminders': '⏰ Reminders',
            'SetupWizard': '🧙 Setup Wizard',
            'ModMail': '📨 ModMail'
        }
        
        return name_mappings.get(cog_name, f"📁 {cog_name}")

    def get_command_signature(self, command: commands.Command) -> str:
        """Get a formatted command signature"""
        if isinstance(command, commands.Group):
            return f"{command.name} <subcommand>"
        else:
            return f"{command.name} {command.signature}".strip()

    def format_command_help(self, command: commands.Command) -> str:
        """Format command help text with proper truncation"""
        help_text = command.help or "No description available"
        
        # Truncate if too long
        if len(help_text) > 100:
            help_text = help_text[:97] + "..."
        
        return help_text

    def search_commands(self, query: str, user_id: int = None) -> List[Tuple[commands.Command, str]]:
        """Search for commands matching the query"""
        results = []
        query_lower = query.lower()
        
        for command in self.bot.commands:
            # Check if cog should be shown
            if command.cog and not self.should_show_cog(command.cog.__class__.__name__, user_id or 0):
                continue
            
            # Search in command name
            if query_lower in command.name.lower():
                results.append((command, "name"))
                continue
            
            # Search in aliases
            if hasattr(command, 'aliases'):
                for alias in command.aliases:
                    if query_lower in alias.lower():
                        results.append((command, "alias"))
                        break
                else:
                    # Search in help text
                    if command.help and query_lower in command.help.lower():
                        results.append((command, "description"))
                        continue
            
            # Search in subcommands for groups
            if isinstance(command, commands.Group):
                for subcommand in command.commands:
                    if query_lower in subcommand.name.lower():
                        results.append((subcommand, "subcommand"))
                    elif subcommand.help and query_lower in subcommand.help.lower():
                        results.append((subcommand, "description"))
        
        # Remove duplicates and limit results
        seen = set()
        unique_results = []
        for cmd, match_type in results:
            if cmd.qualified_name not in seen:
                seen.add(cmd.qualified_name)
                unique_results.append((cmd, match_type))
        
        return unique_results[:20]  # Limit to 20 results

    def get_all_visible_cogs(self, user_id: int) -> Dict[str, Any]:
        """Get all cogs that should be visible to the user"""
        visible_cogs = {}
        
        for cog_name, cog in self.bot.cogs.items():
            if self.should_show_cog(cog_name, user_id):
                visible_cogs[cog_name] = cog
        
        return visible_cogs

    def group_cogs_by_category(self, cogs: Dict[str, Any]) -> Dict[str, List[str]]:
        """Group cogs by their categories"""
        categories = {}
        
        for cog_name in cogs.keys():
            category = self.categorize_cog(cog_name)
            if category not in categories:
                categories[category] = []
            categories[category].append(cog_name)
        
        return categories
