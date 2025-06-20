import nextcord
from nextcord.ext import commands
from typing import List, Tuple, Dict, Any, Union
from .help_utils import HelpUtils

class HelpFormatter:
    """Handles formatting of help embeds and pages"""
    
    def __init__(self, bot):
        self.bot = bot
        self.utils = HelpUtils(bot)

    def create_overview_embed(self) -> nextcord.Embed:
        """Create the main overview embed"""
        embed = nextcord.Embed(
            title="🤖 BronxBot Help",
            description=(
                "Welcome to BronxBot! Use the dropdown menu below to explore different categories.\n\n"
                "**Quick Navigation:**\n"
                "• Use the dropdown to browse categories\n"
                "• Use `.help <command>` for specific command info\n"
                "• Use `.help search <query>` to search commands\n\n"
                "**Examples:**\n"
                "• `.help balance` - Get help for balance command\n"
                "• `.help Economy` - Browse economy commands\n"
                "• `.help search fish` - Search for fishing commands"
            ),
            color=0x2b2d31
        )
        
        # Add category overview
        visible_cogs = self.utils.get_all_visible_cogs(0)  # Get all cogs for overview
        categories = self.utils.group_cogs_by_category(visible_cogs)
        
        category_text = ""
        for category, cog_list in categories.items():
            category_text += f"**{category}** ({len(cog_list)} modules)\n"
        
        embed.add_field(
            name="📂 Available Categories",
            value=category_text or "No categories available",
            inline=False
        )
        
        embed.add_field(
            name="🔗 Useful Links",
            value=(
                "[Invite Bot](https://discord.com/api/oauth2/authorize?client_id={}&permissions=8&scope=bot) • "
                "[Support Server](https://discord.gg/bronx) • "
                "[Documentation](https://docs.bronxbot.xyz)"
            ).format(self.bot.user.id),
            inline=False
        )
        
        embed.set_footer(text="Use the dropdown menu below to navigate categories")
        embed.set_thumbnail(url=self.bot.user.display_avatar.url)
        
        return embed

    def create_command_embed(self, command: commands.Command) -> nextcord.Embed:
        """Create an embed for a specific command"""
        embed = nextcord.Embed(
            title=f"📋 Command: {command.qualified_name}",
            color=0x2b2d31
        )
        
        # Command description
        description = command.help or "No description available"
        embed.description = description
        
        # Usage
        signature = self.utils.get_command_signature(command)
        embed.add_field(
            name="📝 Usage",
            value=f"`.{signature}`",
            inline=False
        )
        
        # Aliases
        if hasattr(command, 'aliases') and command.aliases:
            aliases = ", ".join([f"`.{alias}`" for alias in command.aliases])
            embed.add_field(
                name="🔄 Aliases",
                value=aliases,
                inline=False
            )
        
        # Cooldown
        if command._buckets and command._buckets._cooldown:
            cooldown = command._buckets._cooldown
            embed.add_field(
                name="⏱️ Cooldown",
                value=f"{cooldown.rate} uses per {cooldown.per} seconds",
                inline=True
            )
        
        # Permissions
        if command.checks:
            perms = []
            for check in command.checks:
                if hasattr(check, '__name__'):
                    if 'admin' in check.__name__.lower():
                        perms.append("Administrator")
                    elif 'owner' in check.__name__.lower():
                        perms.append("Bot Owner")
                    elif 'manage' in check.__name__.lower():
                        perms.append("Manage Permissions")
            
            if perms:
                embed.add_field(
                    name="🔒 Required Permissions",
                    value=", ".join(perms),
                    inline=True
                )
        
        # Category
        if command.cog:
            category = self.utils.categorize_cog(command.cog.__class__.__name__)
            embed.add_field(
                name="📂 Category",
                value=category,
                inline=True
            )
        
        # Subcommands for groups
        if isinstance(command, commands.Group) and command.commands:
            subcommands = []
            for subcmd in sorted(command.commands, key=lambda x: x.name):
                subcommands.append(f"`.{subcmd.qualified_name}` - {self.utils.format_command_help(subcmd)}")
            
            if subcommands:
                # Split into multiple fields if too many subcommands
                chunk_size = 10
                for i in range(0, len(subcommands), chunk_size):
                    chunk = subcommands[i:i + chunk_size]
                    field_name = "🔧 Subcommands" if i == 0 else f"🔧 Subcommands (continued {i//chunk_size + 1})"
                    embed.add_field(
                        name=field_name,
                        value="\n".join(chunk),
                        inline=False
                    )
        
        embed.set_footer(text="Use .help <command> for more specific help")
        
        return embed

    def create_cog_embed(self, cog: commands.Cog) -> nextcord.Embed:
        """Create an embed for a specific cog"""
        cog_name = cog.__class__.__name__
        pretty_name = self.utils.prettify_cog_name(cog_name)
        
        embed = nextcord.Embed(
            title=f"{pretty_name}",
            description=cog.__doc__ or f"Commands for {pretty_name}",
            color=0x2b2d31
        )
        
        # Get commands for this cog
        commands_list = []
        group_commands = []
        
        for command in sorted(cog.get_commands(), key=lambda x: x.name):
            if isinstance(command, commands.Group):
                group_commands.append(command)
            else:
                commands_list.append(command)
        
        # Regular commands
        if commands_list:
            command_text = []
            for cmd in commands_list:
                signature = self.utils.get_command_signature(cmd)
                help_text = self.utils.format_command_help(cmd)
                command_text.append(f"`.{signature}` - {help_text}")
            
            # Split into multiple fields if too many commands
            chunk_size = 15
            for i in range(0, len(command_text), chunk_size):
                chunk = command_text[i:i + chunk_size]
                field_name = "📋 Commands" if i == 0 else f"📋 Commands (continued {i//chunk_size + 1})"
                embed.add_field(
                    name=field_name,
                    value="\n".join(chunk),
                    inline=False
                )
        
        # Group commands
        if group_commands:
            group_text = []
            for group in group_commands:
                signature = self.utils.get_command_signature(group)
                help_text = self.utils.format_command_help(group)
                subcommand_count = len(group.commands)
                group_text.append(f"`.{signature}` - {help_text} ({subcommand_count} subcommands)")
            
            embed.add_field(
                name="🗂️ Command Groups",
                value="\n".join(group_text),
                inline=False
            )
        
        # Category info
        category = self.utils.categorize_cog(cog_name)
        embed.add_field(
            name="📂 Category",
            value=category,
            inline=True
        )
        
        # Command count
        total_commands = len(commands_list) + sum(len(g.commands) for g in group_commands)
        embed.add_field(
            name="📊 Total Commands",
            value=str(total_commands),
            inline=True
        )
        
        embed.set_footer(text="Use .help <command> for detailed command information")
        
        return embed

    def create_search_results_embed(self, query: str, results: List[Tuple[commands.Command, str]]) -> nextcord.Embed:
        """Create an embed showing search results"""
        embed = nextcord.Embed(
            title=f"🔍 Search Results for '{query}'",
            description=f"Found {len(results)} matching commands:",
            color=0x2b2d31
        )
        
        # Group results by match type
        by_name = []
        by_alias = []
        by_description = []
        by_subcommand = []
        
        for command, match_type in results:
            signature = self.utils.get_command_signature(command)
            help_text = self.utils.format_command_help(command)
            
            result_line = f"`.{signature}` - {help_text}"
            
            if match_type == "name":
                by_name.append(result_line)
            elif match_type == "alias":
                by_alias.append(result_line)
            elif match_type == "description":
                by_description.append(result_line)
            elif match_type == "subcommand":
                by_subcommand.append(result_line)
        
        # Add results to embed
        if by_name:
            embed.add_field(
                name="📝 Exact Name Matches",
                value="\n".join(by_name[:10]),  # Limit to prevent embed overflow
                inline=False
            )
        
        if by_alias:
            embed.add_field(
                name="🔄 Alias Matches",
                value="\n".join(by_alias[:5]),
                inline=False
            )
        
        if by_subcommand:
            embed.add_field(
                name="🗂️ Subcommand Matches",
                value="\n".join(by_subcommand[:5]),
                inline=False
            )
        
        if by_description:
            embed.add_field(
                name="📋 Description Matches",
                value="\n".join(by_description[:5]),
                inline=False
            )
        
        embed.set_footer(text="Use .help <command> for detailed information about any command")
        
        return embed

    def create_all_pages(self) -> Tuple[List[nextcord.Embed], Dict[str, int]]:
        """Create all help pages and return cog page mapping"""
        pages = []
        cog_page_map = {}
        
        # Add overview page
        pages.append(self.create_overview_embed())
        
        # Get visible cogs
        visible_cogs = self.utils.get_all_visible_cogs(0)
        
        # Create pages for each cog
        for cog_name, cog in visible_cogs.items():
            cog_page_map[cog_name] = len(pages)
            pages.append(self.create_cog_embed(cog))
        
        return pages, cog_page_map

    def create_cog_pages(self, cog: commands.Cog) -> Tuple[List[nextcord.Embed], Dict[str, int]]:
        """Create pages for a specific cog"""
        pages = []
        cog_page_map = {}
        
        # Add the cog page
        cog_name = cog.__class__.__name__
        cog_page_map[cog_name] = 0
        pages.append(self.create_cog_embed(cog))
        
        return pages, cog_page_map
