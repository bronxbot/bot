import nextcord
import random
import json
import logging
import re
from uuid import uuid4
from nextcord.ext import commands, tasks
from nextcord.utils import utcnow
from cogs.logging.logger import CogLogger
from utils.db import db
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
from utils.amount_parser import parse_amount

class Giveaway(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.bot.launch_time = utcnow()
        self.active_giveaways: dict[str, dict] = {}
        self.check_giveaways.start()
        self.logger.info("Giveaway cog initialized")

    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        # Check if user has accepted ToS
        if not await check_tos_acceptance(ctx.author.id):
            await prompt_tos_acceptance(ctx)
            return False
        return True

    def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.check_giveaways.cancel()

    @tasks.loop(seconds=30)
    async def check_giveaways(self):
        """Check for expired giveaways every 30 seconds"""
        try:
            current_time = utcnow()
            expired_giveaways = [
                gid for gid, data in self.active_giveaways.items()
                if current_time >= data['end_time']
            ]
            for giveaway_id in expired_giveaways:
                await self.end_giveaway(giveaway_id)
        except Exception as e:
            self.logger.error(f"Error checking giveaways: {e}")

    @check_giveaways.before_loop
    async def before_check_giveaways(self):
        await self.bot.wait_until_ready()

    async def get_server_balance(self, guild_id: int) -> int:
        """Get the server's giveaway balance"""
        try:
            settings = await db.get_guild_settings(guild_id)
            return settings.get('server_balance', 0)
        except Exception as e:
            self.logger.error(f"Error getting server balance: {e}")
            return 0

    async def update_server_balance(self, guild_id: int, amount: int) -> bool:
        """Update the server's giveaway balance"""
        try:
            current_balance = await self.get_server_balance(guild_id)
            new_balance = current_balance + amount
            if new_balance < 0:
                return False
            return await db.update_guild_settings(guild_id, {'server_balance': new_balance})
        except Exception as e:
            self.logger.error(f"Error updating server balance: {e}")
            return False

    async def get_multiplier_info(self, user_id: int) -> dict:
        """Get active multipliers for a user"""
        try:
            # Integrate with your potion/buff system here
            return {'multiplier': 1.0, 'description': 'No active multipliers'}
        except Exception as e:
            self.logger.error(f"Error getting multiplier info: {e}")
            return {'multiplier': 1.0, 'description': 'Error getting multipliers'}

    @commands.group(name='giveaway', aliases=['gw'], invoke_without_command=True)
    async def giveaway_group(self, ctx: commands.Context):
        """Giveaway command group"""
        embed = nextcord.Embed(
            title="🎉 Giveaway Commands",
            description="Available giveaway commands:",
            color=nextcord.Color.gold()
        )
        embed.add_field(
            name="**User Commands**",
            value=(
                "`.giveaway donate <amount>` - Donate to server balance\n"
                "`.giveaway balance` - Check server balance\n"
                "`.giveaway list` - View active giveaways\n"
                "*Supports: 1k, 1.5m, 2b, 50%, all, half*"
            ),
            inline=False
        )
        embed.add_field(
            name="**Admin Commands**",
            value=(
                "`.giveaway create <amount> <duration> [description]` - Create giveaway\n"
                "`.giveaway end <giveaway_id>` - End giveaway early"
            ),
            inline=False
        )
        embed.add_field(
            name="**Examples**",
            value=(
                "`.giveaway donate 1000` - Donate 1000 coins\n"
                "`.giveaway donate 1.5m` - Donate 1.5 million\n"
                "`.giveaway donate 2b` - Donate 2 billion\n"
                "`.giveaway create 5000 1h Epic Giveaway!` - Create 1 hour giveaway"
            ),
            inline=False
        )
        await ctx.send(embed=embed)

    @giveaway_group.command(name='donate')
    async def donate_to_server(self, ctx: commands.Context, *, amount_str: str):
        """Donate money to the server giveaway balance"""
        wallet_balance = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        
        # Parse the amount using the enhanced parser
        amount, error = parse_amount(amount_str, wallet_balance, context="wallet")
        if error:
            await ctx.reply(f"❌ {error}")
            return
        
        if amount <= 0:
            await ctx.reply("❌ Amount must be positive!")
            return

        if wallet_balance < amount:
            await ctx.reply(f"❌ Insufficient funds! You have {wallet_balance:,} coins but need {amount:,}.")
            return

        multiplier_info = await self.get_multiplier_info(ctx.author.id)
        multiplier = multiplier_info['multiplier']
        boosted_amount = int(amount * multiplier)

        if not await db.update_wallet(ctx.author.id, -amount, ctx.guild.id):
            await ctx.reply("❌ Failed to deduct donation from your wallet!")
            return

        if not await self.update_server_balance(ctx.guild.id, boosted_amount):
            await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
            await ctx.reply("❌ Failed to update server balance!")
            return

        await db.store_stats(ctx.guild.id, "donated")

        if ctx.guild.id == 1259717095382319215:
            role = nextcord.utils.get(ctx.guild.roles, id=1261514786311766106)
            if role:
                try:
                    await ctx.author.add_roles(role)
                except Exception as e:
                    self.logger.error(f"Error assigning role: {e}")
                    await ctx.reply("❌ Failed to assign the donor role!")

        embed = nextcord.Embed(
            title="💝 Donation Successful!",
            description=f"{ctx.author.mention} donated **{amount:,}** coins to the server giveaway balance!",
            color=nextcord.Color.green()
        )
        if multiplier > 1.0:
            embed.add_field(
                name="🚀 Multiplier Applied!",
                value=f"**{multiplier}x** multiplier active!\nActual donation: **{boosted_amount:,}** coins",
                inline=False
            )
            embed.add_field(
                name="Multiplier Source",
                value=multiplier_info['description'],
                inline=False
            )

        server_balance = await self.get_server_balance(ctx.guild.id)
        embed.add_field(
            name="💰 New Server Balance",
            value=f"**{server_balance:,}** coins",
            inline=True
        )
        embed.set_footer(text=f"Thank you for contributing to {ctx.guild.name}!")
        await ctx.send(embed=embed)

    @giveaway_group.command(name='balance', aliases=['bal'])
    async def server_balance(self, ctx):
        """Check the server's giveaway balance"""
        balance = await self.get_server_balance(ctx.guild.id)
        
        embed = nextcord.Embed(
            title="💰 Server Giveaway Balance",
            description=f"**{balance:,}** coins available for giveaways",
            color=nextcord.Color.blue()
        )
        embed.set_footer(text=f"Use '.giveaway donate <amount>' to contribute!")
        await ctx.send(embed=embed)

    @giveaway_group.command(name='create')
    @commands.has_permissions(manage_guild=True)
    async def create_giveaway(self, ctx: commands.Context, amount: int, duration: str, *, description: str = "Amazing Giveaway!"):
        """Create a new giveaway"""
        if amount <= 0:
            await ctx.reply("❌ Giveaway amount must be positive!")
            return

        server_balance = await self.get_server_balance(ctx.guild.id)
        if server_balance < amount:
            await ctx.reply(f"❌ Insufficient server balance! Available: {server_balance:,}, needed: {amount:,}")
            return

        try:
            duration_seconds = self.parse_duration(duration)
            if duration_seconds < 60:
                await ctx.reply("❌ Minimum giveaway duration is 1 minute!")
                return
            if duration_seconds > 7 * 24 * 3600:
                await ctx.reply("❌ Maximum giveaway duration is 7 days!")
                return
        except ValueError:
            await ctx.reply("❌ Invalid duration format! Use formats like: 1h, 30m, 2d, 1h30m")
            return

        if not await self.update_server_balance(ctx.guild.id, -amount):
            await ctx.reply("❌ Failed to deduct from server balance!")
            return

        end_time = utcnow() + nextcord.utils.timedelta(seconds=duration_seconds)
        giveaway_id = str(uuid4())

        embed = nextcord.Embed(
            title="🎉 GIVEAWAY 🎉",
            description=description,
            color=nextcord.Color.gold()
        )
        embed.add_field(
            name="💰 Prize",
            value=f"**{amount:,}** coins",
            inline=True
        )
        embed.add_field(
            name="⏰ Ends",
            value=f"<t:{int(end_time.timestamp())}:R>",
            inline=True
        )
        embed.add_field(
            name="🎯 How to Enter",
            value="React with 🎉 to enter!",
            inline=False
        )
        embed.set_footer(text=f"Giveaway ID: {giveaway_id}")

        giveaway_msg = await ctx.send(embed=embed)
        await giveaway_msg.add_reaction("🎉")

        self.active_giveaways[giveaway_id] = {
            'guild_id': ctx.guild.id,
            'channel_id': ctx.channel.id,
            'message_id': giveaway_msg.id,
            'amount': amount,
            'description': description,
            'end_time': end_time,
            'host_id': ctx.author.id,
            'participants': []
        }

        await db.update_guild_settings(
            ctx.guild.id,
            {f'giveaway_{giveaway_id}': self.active_giveaways[giveaway_id]}
        )

        await ctx.send(f"✅ Giveaway created successfully! ID: `{giveaway_id}`")

    @giveaway_group.command(name='end')
    @commands.has_permissions(manage_guild=True)
    async def end_giveaway_command(self, ctx, giveaway_id: str=None):
        """End a giveaway early"""
        if giveaway_id is None:
            embed = nextcord.Embed(
                title="End Giveaway",
                description="❌ Please provide the giveaway ID to end.",
                color=nextcord.Color.red()
            )
            return await ctx.send(embed=embed)
        if giveaway_id not in self.active_giveaways:
            await ctx.reply("❌ Giveaway not found!")
            return

        await self.end_giveaway(giveaway_id)
        await ctx.send("✅ Giveaway ended successfully!")

    @giveaway_group.command(name='list')
    async def list_giveaways(self, ctx):
        """List active giveaways"""
        guild_giveaways = {
            gw_id: gw_data for gw_id, gw_data in self.active_giveaways.items()
            if gw_data['guild_id'] == ctx.guild.id
        }

        if not guild_giveaways:
            embed = nextcord.Embed(
                title="🎉 Active Giveaways",
                description="No active giveaways in this server.",
                color=nextcord.Color.blue()
            )
        else:
            embed = nextcord.Embed(
                title="🎉 Active Giveaways",
                color=nextcord.Color.gold()
            )
            for gw_id, gw_data in guild_giveaways.items():
                embed.add_field(
                    name=f"**{gw_data['description']}**",
                    value=(
                        f"💰 Prize: **{gw_data['amount']:,}** coins\n"
                        f"⏰ Ends: <t:{int(gw_data['end_time'].timestamp())}:R>\n"
                        f"🆔 ID: `{gw_id}`"
                    ),
                    inline=False
                )

        await ctx.send(embed=embed)

    async def end_giveaway(self, giveaway_id: str):
        """End a giveaway and pick winners"""
        if giveaway_id not in self.active_giveaways:
            return

        giveaway_data = self.active_giveaways[giveaway_id]
        
        try:
            # Get the giveaway message
            guild = self.bot.get_guild(giveaway_data['guild_id'])
            if not guild:
                return

            channel = guild.get_channel(giveaway_data['channel_id'])
            if not channel:
                return

            try:
                message = await channel.fetch_message(giveaway_data['message_id'])
            except nextcord.NotFound:
                # Message was deleted
                del self.active_giveaways[giveaway_id]
                return

            # Get participants from reactions
            participants = []
            participant_ids = set()  # Use a set locally to track unique participants
            for reaction in message.reactions:
                if str(reaction.emoji) == "🎉":
                    async for user in reaction.users():
                        if not user.bot and user.id != giveaway_data['host_id'] and user.id not in participant_ids:
                            participants.append(user)
                            participant_ids.add(user.id)

            # Pick winner
            embed = nextcord.Embed(
                title="🎉 GIVEAWAY ENDED 🎉",
                description=giveaway_data['description'],
                color=nextcord.Color.red()
            )

            if not participants:
                embed.add_field(
                    name="😢 No Winner",
                    value="No valid participants found!",
                    inline=False
                )
                # Refund server balance
                await self.update_server_balance(giveaway_data['guild_id'], giveaway_data['amount'])
                embed.add_field(
                    name="💰 Refund",
                    value=f"{giveaway_data['amount']:,} coins refunded to server balance",
                    inline=False
                )
            else:
                winner = random.choice(participants)
                
                # Award prize to winner
                await db.update_wallet(winner.id, giveaway_data['amount'], giveaway_data['guild_id'])
                
                embed.add_field(
                    name="🏆 Winner",
                    value=f"Congratulations {winner.mention}!",
                    inline=False
                )
                embed.add_field(
                    name="💰 Prize",
                    value=f"**{giveaway_data['amount']:,}** coins",
                    inline=True
                )
                embed.add_field(
                    name="👥 Participants",
                    value=f"**{len(participants)}** entries",
                    inline=True
                )

                # Store stats
                await db.store_stats(giveaway_data['guild_id'], "giveaway_won")

            # Update the original message
            await message.edit(embed=embed)
            await message.clear_reactions()

            # Send winner announcement
            if participants:
                await channel.send(f"🎉 Congratulations {winner.mention}! You won **{giveaway_data['amount']:,}** coins!")

        except Exception as e:
            self.logger.error(f"Error ending giveaway {giveaway_id}: {e}")
        finally:
            # Clean up
            if giveaway_id in self.active_giveaways:
                del self.active_giveaways[giveaway_id]

    def parse_duration(self, duration_str: str) -> int:
        """Parse duration string into seconds. Supports 1h30m, 2d, etc."""
        pattern = re.compile(r'(\d+)([smhd])')
        matches = pattern.findall(duration_str.lower().replace(' ', ''))
        if not matches:
            raise ValueError("Invalid duration format")
        total_seconds = 0
        for value, unit in matches:
            value = int(value)
            if unit == 's':
                total_seconds += value
            elif unit == 'm':
                total_seconds += value * 60
            elif unit == 'h':
                total_seconds += value * 3600
            elif unit == 'd':
                total_seconds += value * 86400
        return total_seconds

    async def handle_error(self, ctx: commands.Context, error: Exception, command_name: str = ""):
        """Generic error handler for giveaway commands"""
        self.logger.error(f"Error in {command_name}: {error}")
        await ctx.reply("❌ An unexpected error occurred. Please try again later.")

    @donate_to_server.error
    async def donate_error(self, ctx, error):
        """Handle donate command errors"""
        if isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Please provide a valid amount to donate!")
        else:
            await self.handle_error(ctx, error, "donate")

    @create_giveaway.error
    async def create_giveaway_error(self, ctx, error):
        """Handle create giveaway command errors"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ You don't have permission to create giveaways!")
        elif isinstance(error, commands.BadArgument):
            await ctx.reply("❌ Invalid giveaway parameters! Usage: `.giveaway create <amount> <duration> [description]`")
        else:
            await self.handle_error(ctx, error, "create_giveaway")

    @end_giveaway_command.error
    async def end_giveaway_error(self, ctx, error):
        """Handle end giveaway command errors"""
        if isinstance(error, commands.MissingPermissions):
            await ctx.reply("❌ You don't have permission to end giveaways!")
        else:
            await self.handle_error(ctx, error, "end_giveaway")

async def setup(bot):
    logger = CogLogger("Giveaway")
    try:
        bot.add_cog(Giveaway(bot))
        logger.info("Giveaway cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load Giveaway cog: {e}")
        raise