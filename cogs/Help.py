import discord
import json
import math
from discord.ext import commands
from cogs.logging.logger import CogLogger
from utils.error_handler import ErrorHandler
from typing import Dict, List, Union, Optional

logger = CogLogger('Help')
with open('data/config.json', 'r') as f:
    data = json.load(f)
BOT_ADMINS = data['OWNER_IDS']

class HierarchicalHelpView(discord.ui.View):
    def __init__(self, bot, author, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.author = author
        self.message = None
        
        # Navigation state
        self.current_level = "main"  # main -> category -> subcategory -> commands
        self.current_category = None
        self.current_subcategory = None
        self.current_page = 0
        self.pages_per_level = {}
        
        # Data structure
        self.help_data = self._build_help_structure()
        
        # Update interface
        self._update_components()
    
    def _build_help_structure(self):
        """Build the hierarchical help structure from bot cogs"""
        structure = {
            'Economy': {
                'emoji': '💰',
                'description': 'Economy, work, trading, and money systems',
                'subcategories': {
                    'Core': ['Economy', 'Work'],
                    'Trading': ['Trading', 'Shop', 'Bazaar'],
                    'Games': ['Gambling'],
                    'Events': ['Giveaway'],
                    'Fishing': ['fishing']  # This maps to the fishing folder
                }
            },
            'Fun & Games': {
                'emoji': '🎮',
                'description': 'Entertainment, games, and fun activities',
                'subcategories': {
                    'Text Games': ['Text', 'Cypher', 'MathRace'],
                    'Interactive': ['Fun', 'TicTacToe'],
                    'Multiplayer': ['Multiplayer']
                }
            },
            'Utility & Tools': {
                'emoji': '🔧',
                'description': 'Server utilities and helpful tools',
                'subcategories': {
                    'General': ['Utility', 'Reminders'],
                    'Information': ['Status', 'Stats'],
                    'Communication': ['ModMail']
                }
            },
            'Moderation': {
                'emoji': '🛡️',
                'description': 'Server management and moderation tools',
                'subcategories': {
                    'Core': ['Moderation'],
                    'Community': ['VoteBans', 'Welcoming'],
                    'Admin': ['Admin']
                }
            },
            'Music': {
                'emoji': '🎵',
                'description': 'Music playback and audio features',
                'subcategories': {
                    'Player': ['music']  # This maps to the music folder
                }
            },
            'Settings': {
                'emoji': '⚙️',
                'description': 'Bot configuration and server settings',
                'subcategories': {
                    'General': ['general'],
                    'Features': ['moderation', 'economy', 'music', 'welcome', 'logging']
                }
            },
            'AI & Automation': {
                'emoji': '🤖', 
                'description': 'AI integration and automated features',
                'subcategories': {
                    'AI Chat': ['AI'],
                    'Auto Features': ['AutoFishing']
                }
            }
        }
        return structure
    
    def _get_commands_for_cog(self, cog_name_or_path: str) -> List[commands.Command]:
        """Get commands from a cog name or module path"""
        commands_list = []
        
        # Handle folder-based cogs (like fishing, music, settings)
        if cog_name_or_path in ['fishing', 'music', 'general', 'moderation', 'economy', 'welcome', 'logging']:
            # Get all cogs that start with this path
            for cog_name, cog in self.bot.cogs.items():
                module_path = cog.__module__.lower()
                if cog_name_or_path in module_path:
                    commands_list.extend([cmd for cmd in cog.get_commands() if not cmd.hidden])
        else:
            # Handle direct cog names
            cog = self.bot.get_cog(cog_name_or_path)
            if cog:
                commands_list.extend([cmd for cmd in cog.get_commands() if not cmd.hidden])
        
        return sorted(commands_list, key=lambda x: x.name)
    
    def _update_components(self):
        """Update all UI components based on current state"""
        self.clear_items()
        
        if self.current_level == "main":
            self._add_main_components()
        elif self.current_level == "category":
            self._add_category_components()
        elif self.current_level == "subcategory":
            self._add_subcategory_components()
        elif self.current_level == "commands":
            self._add_commands_components()
    
    def _add_main_components(self):
        """Add components for main category selection"""
        # Category select (Row 1)
        category_select = discord.ui.Select(
            placeholder="🏠 Choose a category...",
            custom_id="category_select",
            row=0
        )
        
        for cat_name, cat_info in self.help_data.items():
            category_select.add_option(
                label=cat_name,
                value=cat_name,
                description=cat_info['description'][:100],
                emoji=cat_info['emoji']
            )
        
        category_select.callback = self._category_selected
        self.add_item(category_select)
        
        # Quick access buttons (Row 2)
        self.add_item(discord.ui.Button(
            label="🔗 Invite", style=discord.ButtonStyle.link,
            url="https://bronxbot.onrender.com/invite", row=1
        ))
        self.add_item(discord.ui.Button(
            label="💬 Support", style=discord.ButtonStyle.link,
            url="https://discord.gg/jvyYWkj3ts", row=1
        ))
        self.add_item(discord.ui.Button(
            label="🌐 Website", style=discord.ButtonStyle.link,
            url="https://bronxbot.onrender.com", row=1
        ))
        
        # Delete button (Row 2)
        delete_btn = discord.ui.Button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
        delete_btn.callback = self._delete_message
        self.add_item(delete_btn)
    
    def _add_category_components(self):
        """Add components for subcategory selection within a category"""
        cat_info = self.help_data[self.current_category]
        
        # Subcategory select (Row 1)
        if len(cat_info['subcategories']) > 1:
            sub_select = discord.ui.Select(
                placeholder=f"{cat_info['emoji']} Choose a subcategory...",
                custom_id="subcategory_select",
                row=0
            )
            
            for sub_name, cog_list in cat_info['subcategories'].items():
                command_count = sum(len(self._get_commands_for_cog(cog)) for cog in cog_list)
                sub_select.add_option(
                    label=sub_name,
                    value=sub_name,
                    description=f"{command_count} commands available"
                )
            
            sub_select.callback = self._subcategory_selected
            self.add_item(sub_select)
        
        # Navigation buttons (Row 2)
        back_btn = discord.ui.Button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=1)
        back_btn.callback = self._go_back
        self.add_item(back_btn)
        
        # If only one subcategory, show direct access button
        if len(cat_info['subcategories']) == 1:
            sub_name = list(cat_info['subcategories'].keys())[0]
            direct_btn = discord.ui.Button(
                label=f"View {sub_name}", 
                style=discord.ButtonStyle.primary, 
                row=1
            )
            direct_btn.callback = lambda i: self._subcategory_selected_direct(i, sub_name)
            self.add_item(direct_btn)
        
        delete_btn = discord.ui.Button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
        delete_btn.callback = self._delete_message
        self.add_item(delete_btn)
    
    def _add_subcategory_components(self):
        """Add components for command viewing within a subcategory"""
        # Get commands for this subcategory
        cat_info = self.help_data[self.current_category]
        cog_list = cat_info['subcategories'][self.current_subcategory]
        all_commands = []
        
        for cog_name in cog_list:
            all_commands.extend(self._get_commands_for_cog(cog_name))
        
        # Pagination info
        commands_per_page = 8
        total_pages = math.ceil(len(all_commands) / commands_per_page) if all_commands else 1
        
        # Command select for current page (Row 1)
        if all_commands:
            start_idx = self.current_page * commands_per_page
            end_idx = start_idx + commands_per_page
            page_commands = all_commands[start_idx:end_idx]
            
            cmd_select = discord.ui.Select(
                placeholder=f"📋 View command details ({len(all_commands)} total)...",
                custom_id="command_select",
                row=0
            )
            
            for cmd in page_commands:
                usage = f"/{cmd.name} {cmd.signature}".strip()
                description = cmd.help or "No description"
                if len(description) > 100:
                    description = description[:97] + "..."
                
                cmd_select.add_option(
                    label=usage,
                    value=cmd.name,
                    description=description
                )
            
            cmd_select.callback = self._command_selected
            self.add_item(cmd_select)
        
        # Navigation buttons (Row 2)
        back_btn = discord.ui.Button(label="⬅️ Back", style=discord.ButtonStyle.secondary, row=1)
        back_btn.callback = self._go_back
        self.add_item(back_btn)
        
        # Pagination buttons (Row 2)
        if total_pages > 1:
            prev_btn = discord.ui.Button(
                label="◀️", style=discord.ButtonStyle.primary, 
                disabled=(self.current_page == 0), row=1
            )
            prev_btn.callback = self._prev_page
            self.add_item(prev_btn)
            
            page_btn = discord.ui.Button(
                label=f"{self.current_page + 1}/{total_pages}",
                style=discord.ButtonStyle.secondary,
                disabled=True, row=1
            )
            self.add_item(page_btn)
            
            next_btn = discord.ui.Button(
                label="▶️", style=discord.ButtonStyle.primary,
                disabled=(self.current_page >= total_pages - 1), row=1
            )
            next_btn.callback = self._next_page
            self.add_item(next_btn)
        
        delete_btn = discord.ui.Button(label="🗑️", style=discord.ButtonStyle.danger, row=1)
        delete_btn.callback = self._delete_message
        self.add_item(delete_btn)
    
    def _add_commands_components(self):
        """Add components for individual command view"""
        # Navigation buttons (Row 1)
        back_btn = discord.ui.Button(label="⬅️ Back to Commands", style=discord.ButtonStyle.secondary, row=0)
        back_btn.callback = self._go_back
        self.add_item(back_btn)
        
        home_btn = discord.ui.Button(label="🏠 Home", style=discord.ButtonStyle.primary, row=0)
        home_btn.callback = self._go_home
        self.add_item(home_btn)
        
        delete_btn = discord.ui.Button(label="🗑️", style=discord.ButtonStyle.danger, row=0)
        delete_btn.callback = self._delete_message
        self.add_item(delete_btn)
    
    # Callback methods
    async def _category_selected(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        self.current_category = interaction.data['values'][0]
        self.current_level = "category"
        self.current_page = 0
        self._update_components()
        
        embed = self._get_category_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _subcategory_selected(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        self.current_subcategory = interaction.data['values'][0]
        self.current_level = "subcategory"
        self.current_page = 0
        self._update_components()
        
        embed = self._get_subcategory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _subcategory_selected_direct(self, interaction: discord.Interaction, subcategory: str):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        self.current_subcategory = subcategory
        self.current_level = "subcategory"
        self.current_page = 0
        self._update_components()
        
        embed = self._get_subcategory_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _command_selected(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        command_name = interaction.data['values'][0]
        command = self.bot.get_command(command_name)
        
        if command:
            self.current_level = "commands"
            self._update_components()
            
            embed = self._get_command_embed(command)
            await interaction.response.edit_message(embed=embed, view=self)
    
    async def _go_back(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        if self.current_level == "commands":
            self.current_level = "subcategory"
        elif self.current_level == "subcategory":
            self.current_level = "category"
            self.current_subcategory = None
        elif self.current_level == "category":
            self.current_level = "main"
            self.current_category = None
        
        self.current_page = 0
        self._update_components()
        
        embed = self._get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _go_home(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        self.current_level = "main"
        self.current_category = None
        self.current_subcategory = None
        self.current_page = 0
        self._update_components()
        
        embed = self._get_main_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _prev_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        self.current_page = max(0, self.current_page - 1)
        self._update_components()
        
        embed = self._get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _next_page(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("This isn't your help menu!", ephemeral=True)
        
        # Calculate max pages based on current context
        if self.current_level == "subcategory":
            cat_info = self.help_data[self.current_category]
            cog_list = cat_info['subcategories'][self.current_subcategory]
            all_commands = []
            for cog_name in cog_list:
                all_commands.extend(self._get_commands_for_cog(cog_name))
            max_pages = math.ceil(len(all_commands) / 8) if all_commands else 1
            self.current_page = min(max_pages - 1, self.current_page + 1)
        
        self._update_components()
        embed = self._get_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def _delete_message(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            return await interaction.response.send_message("Only the command author can delete this!", ephemeral=True)
        
        await interaction.response.defer()
        if self.message:
            await self.message.delete()
    
    # Embed generation methods
    def _get_current_embed(self):
        """Get embed for current navigation state"""
        if self.current_level == "main":
            return self._get_main_embed()
        elif self.current_level == "category":
            return self._get_category_embed()
        elif self.current_level == "subcategory":
            return self._get_subcategory_embed()
        elif self.current_level == "commands":
            return self._get_main_embed()  # Fallback
    
    def _get_main_embed(self):
        """Get main help embed"""
        total_commands = sum(len([cmd for cmd in cog.get_commands() if not cmd.hidden]) 
                           for cog in self.bot.cogs.values())
        
        embed = discord.Embed(
            title="🏠 Bronx Bot - Help Menu",
            description=(
                f"Welcome to Bronx Bot! Choose a category below to explore {total_commands} available commands.\n\n"
                "**📋 Categories:**"
            ),
            color=0x2b2d31
        )
        
        for cat_name, cat_info in self.help_data.items():
            # Count commands in this category
            cat_commands = 0
            for subcategory, cog_list in cat_info['subcategories'].items():
                for cog_name in cog_list:
                    cat_commands += len(self._get_commands_for_cog(cog_name))
            
            embed.add_field(
                name=f"{cat_info['emoji']} {cat_name}",
                value=f"{cat_info['description']}\n*{cat_commands} commands*",
                inline=True
            )
        
        embed.set_footer(text=f"Use the dropdown menu to navigate • {len(self.bot.guilds)} servers")
        return embed
    
    def _get_category_embed(self):
        """Get category overview embed"""
        cat_info = self.help_data[self.current_category]
        
        embed = discord.Embed(
            title=f"{cat_info['emoji']} {self.current_category}",
            description=cat_info['description'],
            color=0x2b2d31
        )
        
        for sub_name, cog_list in cat_info['subcategories'].items():
            commands_count = sum(len(self._get_commands_for_cog(cog)) for cog in cog_list)
            
            # Get a sample of command names
            sample_commands = []
            for cog_name in cog_list[:2]:  # Limit to first 2 cogs
                sample_commands.extend([cmd.name for cmd in self._get_commands_for_cog(cog_name)[:3]])
            
            value = f"**{commands_count} commands**"
            if sample_commands:
                value += f"\n`{', '.join(sample_commands[:4])}`"
                if len(sample_commands) > 4:
                    value += "..."
            
            embed.add_field(
                name=f"📂 {sub_name}",
                value=value,
                inline=True
            )
        
        embed.set_footer(text="Select a subcategory to view commands")
        return embed
    
    def _get_subcategory_embed(self):
        """Get subcategory commands embed"""
        cat_info = self.help_data[self.current_category]
        cog_list = cat_info['subcategories'][self.current_subcategory]
        
        # Get all commands
        all_commands = []
        for cog_name in cog_list:
            all_commands.extend(self._get_commands_for_cog(cog_name))
        
        # Pagination
        commands_per_page = 8
        total_pages = math.ceil(len(all_commands) / commands_per_page) if all_commands else 1
        start_idx = self.current_page * commands_per_page
        end_idx = start_idx + commands_per_page
        page_commands = all_commands[start_idx:end_idx]
        
        embed = discord.Embed(
            title=f"📋 {self.current_category} → {self.current_subcategory}",
            description=f"Commands in this category (Page {self.current_page + 1}/{total_pages})",
            color=0x2b2d31
        )
        
        if page_commands:
            for cmd in page_commands:
                usage = f"/{cmd.name} {cmd.signature}".strip()
                description = cmd.help or "No description available"
                if len(description) > 150:
                    description = description[:147] + "..."
                
                embed.add_field(
                    name=f"`{usage}`",
                    value=description,
                    inline=False
                )
        else:
            embed.add_field(
                name="No Commands",
                value="No commands found in this category.",
                inline=False
            )
        
        embed.set_footer(text=f"Select a command above for detailed help • {len(all_commands)} total commands")
        return embed
    
    def _get_command_embed(self, command):
        """Get detailed command embed"""
        embed = discord.Embed(
            title=f"📖 Command: {command.name}",
            color=0x2b2d31
        )
        
        # Usage
        usage = f"/{command.name} {command.signature}".strip()
        embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
        
        # Description
        description = command.help or "No description available."
        embed.add_field(name="Description", value=description, inline=False)
        
        # Aliases
        if command.aliases:
            aliases = ", ".join([f"`{alias}`" for alias in command.aliases])
            embed.add_field(name="Aliases", value=aliases, inline=True)
        
        # Category info
        cog_name = command.cog.qualified_name if command.cog else "Unknown"
        embed.add_field(name="Category", value=cog_name, inline=True)
        
        # Subcommands (if it's a group)
        if isinstance(command, commands.Group):
            subcommands = [sub.name for sub in command.commands if not sub.hidden]
            if subcommands:
                sub_list = ", ".join([f"`{sub}`" for sub in subcommands[:10]])
                if len(subcommands) > 10:
                    sub_list += f" and {len(subcommands) - 10} more..."
                embed.add_field(name="Subcommands", value=sub_list, inline=False)
        
        embed.set_footer(text="Use the command exactly as shown in the usage field")
        return embed
    
    async def on_timeout(self):
        """Disable all components when the view times out"""
        for item in self.children:
            item.disabled = True
        
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.NotFound:
                pass


class Help(commands.Cog, ErrorHandler):
    def __init__(self, bot):
        ErrorHandler.__init__(self)
        self.bot = bot
        logger.info("Help cog initialized with hierarchical navigation")

    @commands.command(aliases=['support'])
    async def invite(self, ctx):
        """Get the bot's invite link & support server."""
        await self._send_invite(ctx)
    
    @discord.app_commands.command(name="invite", description="Get the bot's invite link and support server")
    async def invite_slash(self, interaction: discord.Interaction):
        """Get the bot's invite link & support server."""
        await self._send_invite(interaction)

    async def _send_invite(self, ctx_or_interaction):
        """Send invite information"""
        embed = discord.Embed(
            title="invite bronx",
            url="https://bronxbot.onrender.com/invite",
            description="[invite](https://bronxbot.onrender.com/invite) | [support](https://discord.gg/jvyYWkj3ts) | [website](https://bronxbot.onrender.com)",
            color=0x2b2d31
        )
        embed.set_footer(text="thanks for using bronx bot!")
        
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.reply(embed=embed)

    @commands.command(name="help", aliases=["h", "commands"])
    async def help(self, ctx, *, command=None):
        """Show help information for commands"""
        await self._send_help(ctx, command)
    
    @discord.app_commands.command(name="help", description="Show help information for commands")
    @discord.app_commands.describe(command="The command or category to get help for")
    async def help_slash(self, interaction: discord.Interaction, command: str = None):
        """Slash command version of help"""
        await self._send_help(interaction, command)

    async def _send_help(self, ctx_or_interaction, command=None):
        """Unified help logic using hierarchical navigation"""
        author = ctx_or_interaction.user if isinstance(ctx_or_interaction, discord.Interaction) else ctx_or_interaction.author
        
        if command:
            # Help for specific command or cog
            cmd = self.bot.get_command(command.lower())
            cog = self.bot.get_cog(command)
            
            if cmd:
                # Show specific command help
                embed = discord.Embed(
                    title=f"📖 Command: {cmd.name}",
                    color=0x2b2d31
                )
                
                usage = f"/{cmd.name} {cmd.signature}".strip()
                embed.add_field(name="Usage", value=f"`{usage}`", inline=False)
                
                description = cmd.help or "No description available."
                embed.add_field(name="Description", value=description, inline=False)
                
                if cmd.aliases:
                    aliases = ", ".join([f"`{alias}`" for alias in cmd.aliases])
                    embed.add_field(name="Aliases", value=aliases, inline=True)
                
                cog_name = cmd.cog.qualified_name if cmd.cog else "Unknown"
                embed.add_field(name="Category", value=cog_name, inline=True)
                
                if isinstance(cmd, commands.Group):
                    subcommands = [sub.name for sub in cmd.commands if not sub.hidden]
                    if subcommands:
                        sub_list = ", ".join([f"`{sub}`" for sub in subcommands[:10]])
                        if len(subcommands) > 10:
                            sub_list += f" and {len(subcommands) - 10} more..."
                        embed.add_field(name="Subcommands", value=sub_list, inline=False)
                
                embed.set_footer(text="Use the command exactly as shown in the usage field")
                return await self._respond(ctx_or_interaction, embed)
            
            elif cog:
                # Show cog help
                commands_list = [cmd for cmd in cog.get_commands() if not cmd.hidden]
                if not commands_list:
                    embed = discord.Embed(
                        description=f"No commands found in `{cog.qualified_name}`",
                        color=discord.Color.red()
                    )
                    return await self._respond(ctx_or_interaction, embed)
                
                embed = discord.Embed(
                    title=f"📂 {cog.qualified_name} Commands",
                    color=0x2b2d31
                )
                
                for cmd in sorted(commands_list, key=lambda x: x.name)[:10]:  # Limit to 10 commands
                    usage = f"/{cmd.name} {cmd.signature}".strip()
                    description = cmd.help or "No description"
                    if len(description) > 100:
                        description = description[:97] + "..."
                    
                    embed.add_field(
                        name=f"`{usage}`",
                        value=description,
                        inline=False
                    )
                
                if len(commands_list) > 10:
                    embed.add_field(
                        name="More Commands",
                        value=f"And {len(commands_list) - 10} more commands...",
                        inline=False
                    )
                
                embed.set_footer(text=f"{len(commands_list)} commands total")
                return await self._respond(ctx_or_interaction, embed)
            
            else:
                # Command not found
                embed = discord.Embed(
                    description=f"Couldn't find command or category `{command}`",
                    color=discord.Color.red()
                )
                return await self._respond(ctx_or_interaction, embed)
        
        # Show main hierarchical help menu
        view = HierarchicalHelpView(self.bot, author)
        embed = view._get_main_embed()
        
        if isinstance(ctx_or_interaction, discord.Interaction):
            message = await ctx_or_interaction.response.send_message(embed=embed, view=view)
            view.message = await ctx_or_interaction.original_response()
        else:
            message = await ctx_or_interaction.reply(embed=embed, view=view)
            view.message = message

    async def _respond(self, ctx_or_interaction, embed):
        """Respond to either context or interaction"""
        if isinstance(ctx_or_interaction, discord.Interaction):
            await ctx_or_interaction.response.send_message(embed=embed)
        else:
            await ctx_or_interaction.reply(embed=embed)

    @help.error
    async def help_error(self, ctx, error):
        """Handle help command errors"""
        if isinstance(error, commands.CommandNotFound):
            await ctx.reply("❌ Command not found!")
        else:
            await self.handle_error(ctx, error, "help")
    
    @help_slash.error
    async def help_slash_error(self, interaction: discord.Interaction, error):
        logger.error(f"Help slash command error: {error}")
        await interaction.response.send_message("An error occurred with the help command.", ephemeral=True)

    @invite_slash.error
    async def invite_slash_error(self, interaction: discord.Interaction, error):
        logger.error(f"Invite slash command error: {error}")
        await interaction.response.send_message("An error occurred with the invite command.", ephemeral=True)


async def setup(bot):
    try:
        await bot.add_cog(Help(bot))
        await bot.tree.sync()
        logger.info("Help cog loaded with hierarchical navigation system")
    except Exception as e:
        logger.error(f"Failed to load Help cog: {e}")
        raise e