import nextcord
from nextcord.ext import commands
import logging

logger = logging.getLogger('SlashCommands')

class SlashCommands(commands.Cog):
    """Slash command management utilities"""
    
    def __init__(self, bot):
        self.bot = bot
        logger.info("SlashCommands cog initialized")

    @commands.command(name='sync_slash', aliases=['sync', 'refresh_slash'])
    @commands.is_owner()
    async def sync_slash_commands(self, ctx, guild_id: int = None):
        """Sync slash commands to a specific guild or globally
        
        Usage:
        - !sync_slash - Sync globally (can take up to 1 hour)
        - !sync_slash 123456789 - Sync to specific guild (instant)
        """
        try:
            if guild_id:
                # Sync to specific guild
                guild = self.bot.get_guild(guild_id)
                if not guild:
                    return await ctx.reply(f"❌ Guild with ID `{guild_id}` not found.")
                
                synced = await self.bot.sync_application_commands(guild_id=guild_id)
                synced_count = len(synced) if synced else 0
                await ctx.reply(f"✅ Synced {synced_count} slash commands to **{guild.name}**!")
                logger.info(f"Synced {synced_count} slash commands to guild {guild.name} ({guild_id})")
            else:
                # Global sync
                await ctx.reply("🔄 Syncing slash commands globally... This may take up to 1 hour to propagate.")
                synced = await self.bot.sync_application_commands()
                synced_count = len(synced) if synced else 0
                await ctx.reply(f"✅ Synced {synced_count} slash commands globally!")
                logger.info(f"Synced {synced_count} slash commands globally")
                
        except Exception as e:
            await ctx.reply(f"❌ Error syncing slash commands: {str(e)}")
            logger.error(f"Error syncing slash commands: {e}")

    @commands.command(name='sync_all_guilds')
    @commands.is_owner()
    async def sync_all_guilds(self, ctx):
        """Sync slash commands to all guilds the bot is in"""
        try:
            await ctx.reply("🔄 Starting to sync slash commands to all guilds...")
            
            synced_count = 0
            failed_count = 0
            
            for guild in self.bot.guilds:
                try:
                    synced = await self.bot.sync_application_commands(guild_id=guild.id)
                    synced_count += 1
                    command_count = len(synced) if synced else 0
                    logger.info(f"Synced {command_count} commands to {guild.name}")
                except Exception as e:
                    failed_count += 1
                    logger.error(f"Failed to sync to {guild.name}: {e}")
            
            await ctx.reply(f"✅ Sync complete! Successfully synced to {synced_count} guilds. Failed: {failed_count}")
            
        except Exception as e:
            await ctx.reply(f"❌ Error during bulk sync: {str(e)}")
            logger.error(f"Error during bulk sync: {e}")

    @nextcord.slash_command(description="Sync slash commands (Owner only)")
    async def sync(self, interaction: nextcord.Interaction, guild_id: str = None):
        """Slash command version of sync"""
        if interaction.user.id not in self.bot.owner_ids:
            return await interaction.response.send_message("❌ Only bot owners can use this command.", ephemeral=True)
        
        try:
            if guild_id:
                try:
                    guild_id_int = int(guild_id)
                    guild = self.bot.get_guild(guild_id_int)
                    if not guild:
                        return await interaction.response.send_message(f"❌ Guild with ID `{guild_id}` not found.", ephemeral=True)
                    
                    synced = await self.bot.sync_application_commands(guild_id=guild_id_int)
                    synced_count = len(synced) if synced else 0
                    await interaction.response.send_message(f"✅ Synced {synced_count} slash commands to **{guild.name}**!", ephemeral=True)
                except ValueError:
                    await interaction.response.send_message("❌ Invalid guild ID format.", ephemeral=True)
            else:
                await interaction.response.send_message("🔄 Syncing slash commands globally... This may take up to 1 hour to propagate.", ephemeral=True)
                synced = await self.bot.sync_application_commands()
                synced_count = len(synced) if synced else 0
                await interaction.followup.send(f"✅ Synced {synced_count} slash commands globally!", ephemeral=True)
                
        except Exception as e:
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ Error syncing slash commands: {str(e)}", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ Error syncing slash commands: {str(e)}", ephemeral=True)

    @commands.command(name='slash_status', aliases=['slash_info'])
    @commands.is_owner()
    async def slash_status(self, ctx):
        """Check the status of slash command registration"""
        try:
            embed = nextcord.Embed(
                title="🔧 Slash Command Status", 
                color=0x2b2d31
            )
            
            # Get application commands
            try:
                # Try to get application commands from the bot
                all_commands = self.bot.get_all_application_commands()
                global_commands = [cmd for cmd in all_commands if cmd.guild_id is None]
                
                embed.add_field(
                    name="📊 Global Commands", 
                    value=f"{len(global_commands)} commands registered globally",
                    inline=False
                )
                
                embed.add_field(
                    name="🔧 Total Commands", 
                    value=f"{len(all_commands)} total slash commands defined",
                    inline=False
                )
            except Exception as e:
                embed.add_field(
                    name="📊 Command Status", 
                    value=f"Unable to fetch command info: {str(e)}",
                    inline=False
                )
            
            # Show some guild info
            guild_count = len(self.bot.guilds)
            embed.add_field(
                name="🏠 Guild Count", 
                value=f"Bot is in {guild_count} guilds",
                inline=True
            )
            
            embed.add_field(
                name="⚡ Quick Sync", 
                value="Use `!sync_slash <guild_id>` for instant guild sync",
                inline=True
            )
            
            embed.add_field(
                name="🌍 Global Sync", 
                value="Use `!sync_slash` for global sync (up to 1 hour)",
                inline=True
            )
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            await ctx.reply(f"❌ Error getting slash command status: {str(e)}")
            logger.error(f"Error getting slash command status: {e}")

    @commands.command(name='sync_here')
    @commands.is_owner()
    async def sync_here(self, ctx):
        """Sync slash commands to the current guild"""
        try:
            if not ctx.guild:
                return await ctx.reply("❌ This command can only be used in a server!")
            
            synced = await self.bot.sync_application_commands(guild_id=ctx.guild.id)
            synced_count = len(synced) if synced else 0
            await ctx.reply(f"✅ Synced {synced_count} slash commands to **{ctx.guild.name}**!")
            logger.info(f"Synced {synced_count} slash commands to guild {ctx.guild.name} ({ctx.guild.id})")
            
        except Exception as e:
            await ctx.reply(f"❌ Error syncing slash commands: {str(e)}")
            logger.error(f"Error syncing slash commands to current guild: {e}")

async def setup(bot):
    cog = SlashCommands(bot)
    bot.add_cog(cog)
    
    # Debug: Check what slash commands are registered
    logger.info("=== SLASH COMMAND DEBUG ===")
    all_commands = bot.get_all_application_commands()
    logger.info(f"Total application commands found: {len(all_commands)}")
    
    for cmd in all_commands:
        guild_info = getattr(cmd, 'guild_ids', 'Global') or 'Global'
        logger.info(f"Command: {cmd.name} | Type: {type(cmd).__name__} | Guild: {guild_info}")
    
    # Also check slash commands specifically
    slash_commands = [cmd for cmd in all_commands if hasattr(cmd, 'callback')]
    logger.info(f"Slash commands found: {len(slash_commands)}")
    logger.info("==============================")
