import nextcord
from nextcord.ext import commands
from typing import List, Dict, Any
from .help_utils import HelpUtils

class HelpPaginator(nextcord.ui.View):
    """Interactive paginator for help system with dropdown navigation"""
    
    def __init__(self, pages: List[nextcord.Embed], author: nextcord.Member, cog_page_map: Dict[str, int], timeout=180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.author = author
        self.current_page = 0
        self.message = None
        self.cog_page_map = cog_page_map
        self.current_select_page = 0
        self.utils = HelpUtils(None)  # Will be set when we have bot reference
        
        # Group cogs into chunks for select menus (24 per select, leaving room for overview)
        self.cog_groups = []
        cog_items = list(cog_page_map.items())
        
        # Split cogs into groups of max 23 (leaving room for "Overview" and "More...")
        chunk_size = 23
        for i in range(0, len(cog_items), chunk_size):
            chunk = cog_items[i:i + chunk_size]
            self.cog_groups.append(chunk)
        
        # Initialize the select menus
        self._setup_select_menus()
        
        # Update button states
        self.update_buttons()

    async def start(self, ctx: commands.Context):
        """Start the paginator"""
        if not self.pages:
            await ctx.reply("❌ No help pages available.")
            return
        
        # Set bot reference for utils
        self.utils.bot = ctx.bot
        
        embed = self.pages[self.current_page]
        self.message = await ctx.reply(embed=embed, view=self)

    def _setup_select_menus(self):
        """Setup select menus based on current select page"""
        # Clear existing select menus
        for item in self.children[:]:
            if isinstance(item, nextcord.ui.Select):
                self.remove_item(item)
        
        if not self.cog_groups:
            return
        
        # Add main category select
        select = nextcord.ui.Select(
            placeholder="🗂️ Choose a category...",
            custom_id="category_select",
            row=0
        )
        
        # Add overview option
        select.add_option(
            label="📋 Overview",
            value="overview",
            description="Main help page with navigation info",
            emoji="📋"
        )
        
        # Add cogs from current group
        current_group = self.cog_groups[self.current_select_page] if self.cog_groups else []
        
        for cog_name, page_index in current_group:
            if self.utils.bot:
                pretty_name = self.utils.prettify_cog_name(cog_name)
                # Extract emoji and clean name
                if pretty_name.startswith(('💰', '💼', '🛍️', '🏪', '🤝', '🎁', '🎣', '📊', '🎒', '🤖', '🎰', '🃏', '🎲', '🎪', '🏀')):
                    emoji = pretty_name.split()[0]
                    clean_name = pretty_name[2:].strip()  # Remove emoji and space
                else:
                    emoji = "📁"
                    clean_name = pretty_name
                
                # Limit description length
                description = f"Commands for {clean_name}"
                if len(description) > 100:
                    description = description[:97] + "..."
                
                select.add_option(
                    label=clean_name[:25],  # Discord limit
                    value=cog_name,
                    description=description,
                    emoji=emoji
                )
        
        # Add "More..." option if there are more groups
        if len(self.cog_groups) > 1:
            if self.current_select_page < len(self.cog_groups) - 1:
                select.add_option(
                    label="More Categories...",
                    value="more_categories",
                    description="View more category options",
                    emoji="➡️"
                )
            elif self.current_select_page > 0:
                select.add_option(
                    label="Previous Categories...",
                    value="prev_categories", 
                    description="View previous category options",
                    emoji="⬅️"
                )
        
        self.add_item(select)
        
        # Set the callback for the select
        select.callback = self.category_select_callback

    async def category_select_callback(self, interaction: nextcord.Interaction):
        """Handle category selection"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        # Get the select component that triggered this
        select = None
        for item in self.children:
            if isinstance(item, nextcord.ui.Select) and item.custom_id == "category_select":
                select = item
                break
        
        if not select or not select.values:
            await interaction.response.defer()
            return
        
        value = select.values[0]
        
        if value == "overview":
            self.current_page = 0
        elif value == "more_categories":
            self.current_select_page = min(self.current_select_page + 1, len(self.cog_groups) - 1)
            self._setup_select_menus()
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            return
        elif value == "prev_categories":
            self.current_select_page = max(self.current_select_page - 1, 0)
            self._setup_select_menus()
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
            return
        elif value in self.cog_page_map:
            self.current_page = self.cog_page_map[value]
        
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @nextcord.ui.button(label="◀️ Previous", style=nextcord.ButtonStyle.gray, row=1)
    async def previous_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Go to previous page"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        if self.current_page > 0:
            self.current_page -= 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.defer()

    @nextcord.ui.button(label="🏠 Home", style=nextcord.ButtonStyle.primary, row=1)
    async def home_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Go to overview page"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        self.current_page = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @nextcord.ui.button(label="Next ▶️", style=nextcord.ButtonStyle.gray, row=1)
    async def next_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Go to next page"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            self.update_buttons()
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.defer()

    @nextcord.ui.button(label="🔍 Search", style=nextcord.ButtonStyle.green, row=1)
    async def search_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Open search modal"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        modal = SearchModal(self.utils, interaction.user)
        await interaction.response.send_modal(modal)

    @nextcord.ui.button(label="❌ Close", style=nextcord.ButtonStyle.red, row=1)
    async def close_button(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Close the help menu"""
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("❌ This help menu is not for you!", ephemeral=True)
            return
        
        self.stop()
        await interaction.response.edit_message(view=None)

    def update_buttons(self):
        """Update button states based on current page"""
        # Update page indicator in home button
        home_button = None
        prev_button = None
        next_button = None
        
        for item in self.children:
            if isinstance(item, nextcord.ui.Button):
                if "Previous" in item.label:
                    prev_button = item
                elif "Home" in item.label:
                    home_button = item
                elif "Next" in item.label:
                    next_button = item
        
        if home_button:
            home_button.label = f"🏠 Home ({self.current_page + 1}/{len(self.pages)})"
        
        if prev_button:
            prev_button.disabled = self.current_page <= 0
        
        if next_button:
            next_button.disabled = self.current_page >= len(self.pages) - 1

    async def on_timeout(self):
        """Handle timeout"""
        if self.message:
            try:
                await self.message.edit(view=None)
            except nextcord.NotFound:
                pass


class SearchModal(nextcord.ui.Modal):
    """Modal for searching commands"""
    
    def __init__(self, utils: HelpUtils, user: nextcord.Member):
        super().__init__(title="🔍 Search Commands")
        self.utils = utils
        self.user = user
    
    search_query = nextcord.ui.TextInput(
        label="Search Query",
        placeholder="Enter command name, alias, or description...",
        max_length=100,
        required=True
    )
    
    async def on_submit(self, interaction: nextcord.Interaction):
        """Handle search submission"""
        query = self.search_query.value.strip()
        
        if not query:
            await interaction.response.send_message("❌ Please enter a search query!", ephemeral=True)
            return
        
        # Perform the actual search
        results = self.utils.search_commands(query, self.user.id)
        
        if not results:
            await interaction.response.send_message(
                f"❌ No commands found matching `{query}`\n"
                "Try a different search term or use broader keywords.",
                ephemeral=True
            )
            return
        
        # Create search results embed
        embed = nextcord.Embed(
            title=f"🔍 Search Results for '{query}'",
            color=0x00ff00
        )
        
        # Group results by match type
        name_matches = []
        alias_matches = []
        desc_matches = []
        
        for command, match_type in results:
            if match_type == "name":
                name_matches.append(command)
            elif match_type == "alias":
                alias_matches.append(command)
            else:
                desc_matches.append(command)
        
        # Add fields for different match types
        if name_matches:
            name_list = []
            for cmd in name_matches[:5]:  # Limit to 5 per category
                help_text = cmd.help or "No description"
                if len(help_text) > 60:
                    help_text = help_text[:57] + "..."
                name_list.append(f"**`.{cmd.qualified_name}`** - {help_text}")
            embed.add_field(
                name="📌 Name Matches",
                value="\n".join(name_list),
                inline=False
            )
        
        if alias_matches:
            alias_list = []
            for cmd in alias_matches[:3]:  # Limit to 3 per category
                help_text = cmd.help or "No description"
                if len(help_text) > 60:
                    help_text = help_text[:57] + "..."
                alias_list.append(f"**`.{cmd.qualified_name}`** - {help_text}")
            embed.add_field(
                name="🏷️ Alias Matches",
                value="\n".join(alias_list),
                inline=False
            )
        
        if desc_matches:
            desc_list = []
            for cmd in desc_matches[:3]:  # Limit to 3 per category  
                help_text = cmd.help or "No description"
                if len(help_text) > 60:
                    help_text = help_text[:57] + "..."
                desc_list.append(f"**`.{cmd.qualified_name}`** - {help_text}")
            embed.add_field(
                name="📝 Description Matches",
                value="\n".join(desc_list),
                inline=False
            )
        
        embed.set_footer(text=f"Found {len(results)} total matches • Use .help <command> for details")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
