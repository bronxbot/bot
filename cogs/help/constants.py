# Help System Constants
# Contains constants and configuration for the help system

import json

# Load bot configuration from environment variables
import os
try:
    BOT_ADMINS = os.getenv('DISCORD_BOT_OWNER_IDS', '').split(',') if os.getenv('DISCORD_BOT_OWNER_IDS') else ['814226043924643880']
    # Convert to integers
    BOT_ADMINS = [int(admin_id.strip()) for admin_id in BOT_ADMINS if admin_id.strip()]
except (ValueError, AttributeError):
    BOT_ADMINS = [814226043924643880]  # Fallback admin ID

# Help system configuration
HELP_CONFIG = {
    'timeout': 180,  # View timeout in seconds
    'commands_per_page': 15,  # Commands per embed field
    'search_results_limit': 20,  # Maximum search results
    'cogs_per_select': 23,  # Cogs per select menu (leaving room for overview/more)
    'description_max_length': 100,  # Maximum description length
}

# Category mappings for cogs
COG_CATEGORIES = {
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

# Pretty name mappings for cogs
COG_DISPLAY_NAMES = {
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

# Admin-only cogs
ADMIN_ONLY_COGS = {'Admin', 'Performance', 'SyncRoles', 'Stats'}

# Hidden cogs that should never appear in help
HIDDEN_COGS = {'ErrorHandler', 'Logger', 'CommandTracker'}

# Colors for embeds
COLORS = {
    'primary': 0x2b2d31,
    'success': 0x00ff00,
    'warning': 0xffff00,
    'error': 0xff0000,
    'info': 0x0099ff
}

# Emojis
EMOJIS = {
    'overview': '📋',
    'search': '🔍',
    'home': '🏠',
    'previous': '◀️',
    'next': '▶️',
    'close': '❌',
    'category': '🗂️',
    'command': '📋',
    'group': '🗂️',
    'subcommand': '🔧',
    'alias': '🔄',
    'cooldown': '⏱️',
    'permissions': '🔒',
    'more': '➡️',
    'back': '⬅️'
}
