from nextcord.ext import commands
from cogs.logging.logger import CogLogger
from cogs.logging.stats_logger import StatsLogger
from utils.db import AsyncDatabase
db = AsyncDatabase.get_instance()
from utils.safe_reply import safe_reply
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance
import nextcord
import random
import asyncio
import time
import functools
from typing import Optional, List, Dict
from datetime import datetime, timedelta

class MultiplierConverter(commands.Converter):
    async def convert(self, ctx, argument):
        try:
            # Remove 'x' suffix if present and convert to float
            if argument.endswith('x'):
                argument = argument[:-1]
            return float(argument)
        except ValueError:
            raise commands.BadArgument("Multiplier must be a number (like 1.1 or 1.5x)")

def requires_tos():
    """Decorator to ensure user has accepted ToS before using gambling commands"""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, ctx, *args, **kwargs):
            if not await check_tos_acceptance(ctx.author.id):
                await prompt_tos_acceptance(ctx)
                return
            return await func(self, ctx, *args, **kwargs)
        return wrapper
    return decorator

class SpecialGames(commands.Cog):
    """Special gambling games with unique mechanics"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        

        
        # Roulette wheel configuration
        self.roulette_wheel = [
            (0, "green"), (32, "red"), (15, "black"), (19, "red"), (4, "black"), (21, "red"), (2, "black"), 
            (25, "red"), (17, "black"), (34, "red"), (6, "black"), (27, "red"), (13, "black"), (36, "red"), 
            (11, "black"), (30, "red"), (8, "black"), (23, "red"), (10, "black"), (5, "red"), (24, "black"), 
            (16, "red"), (33, "black"), (1, "red"), (20, "black"), (14, "red"), (31, "black"), (9, "red"), 
            (22, "black"), (18, "red"), (29, "black"), (7, "red"), (28, "black"), (12, "red"), (35, "black"), 
            (3, "red"), (26, "black")
        ]
        
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
    
    async def cog_check(self, ctx):
        """Global check for gambling commands"""
        if ctx.channel.id in self.blocked_channels:
            await ctx.reply("❌ Gambling commands are not allowed in this channel!")
            return False
        return True
    

    
    async def _parse_bet(self, bet_str: str, wallet: int) -> int:
        """Parse bet string (all, half, percentage, or number)"""
        try:
            if bet_str.lower() == "all":
                return wallet
            elif bet_str.lower() == "half":
                return int(wallet / 2)
            elif bet_str.endswith("%"):
                percentage = float(bet_str[:-1])
                if percentage < 0 or percentage > 100:
                    return None
                return int(wallet * (percentage / 100))
            else:
                return int(bet_str.replace(",", ""))
        except (ValueError, TypeError):
            return None

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    @requires_tos()
    async def crash(self, ctx, bet: str, auto_cashout: MultiplierConverter = None):
        """Bet on a multiplier that can crash at any moment
        
        Usage: `.crash <bet> [auto_cashout]`
        Examples: `.crash 1000`, `.crash all 1.5x`, `.crash 500 2.0`
        
        Auto-cashout must be at least 1.35x if specified.
        """
        if ctx.author.id in self.active_games:
            return await ctx.reply("❌ You already have an active game!")

        if auto_cashout and (auto_cashout < 1.35 or auto_cashout < 0):
            return await ctx.reply("❌ Auto-cashout must be greater than 1.35x!")
            
        self.active_games.add(ctx.author.id)
        
        try:
            # Parse bet amount
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_bet = await self._parse_bet(bet, wallet)
            
            if not parsed_bet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ Invalid bet amount!")

            if parsed_bet <= 0:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ Bet amount must be greater than 0!")

            if parsed_bet > wallet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ You don't have enough money for that bet!")
                
            # Deduct bet immediately
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            self.stats_logger.log_command_usage("crash")
            
            # Create crash game
            view = self._crash_view(ctx.author.id, parsed_bet, wallet - parsed_bet)
            embed = self._crash_embed(ctx.author.name, 1.0, parsed_bet, wallet - parsed_bet, False)
            
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            
            # Start crash sequence
            await self._run_crash_game(ctx, view, parsed_bet, wallet - parsed_bet, auto_cashout)
            
        except Exception as e:
            self.logger.error(f"Crash error: {e}")
            if ctx.author.id in self.active_games:
                self.active_games.remove(ctx.author.id)
            await ctx.send("❌ An error occurred while starting the game.")

    async def _run_crash_game(self, ctx, view, bet: int, current_balance: int, auto_cashout: float = None):
        """Run the crash game sequence with exact crash points"""
        multiplier = 1.0
        increment = 0.1
        crash_point = random.uniform(1.1, 2.0)  # Determine crash point first

        # 1 in 1000 chance for a big multiplier
        if random.random() < 0.001:
            crash_point = random.uniform(10.0, 1000000.0)
        
        while True:
            # First check if we've reached crash point
            if multiplier >= crash_point:
                # Crashed exactly at crash_point
                embed = self._crash_embed(
                    ctx.author.name,
                    crash_point,
                    bet,
                    current_balance,
                    True,
                    f"💥 Crashed at {crash_point:.2f}x!"
                )
                self.active_games.remove(ctx.author.id)
                return await view.message.edit(embed=embed, view=None)
                
            # Then check for cashout (only possible if we haven't crashed yet)
            if view.cashed_out or (auto_cashout and multiplier >= auto_cashout):
                cashout_value = view.current_multiplier if view.cashed_out else auto_cashout
                winnings = int(bet * cashout_value)
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                
                # Calculate how close they were to crashing
                percent_to_crash = (cashout_value / crash_point) * 100
                closeness = f"{percent_to_crash:.0f}% to crash point"
                
                status_msg = (f"💰 Cashed out at {cashout_value:.2f}x!" if view.cashed_out 
                            else f"🔄 Auto-cashed out at {auto_cashout:.2f}x!")
                
                embed = self._crash_embed(
                    ctx.author.name,
                    cashout_value,
                    bet,
                    current_balance + winnings,
                    True,
                    f"{status_msg}\n\n"
                    f"💡 Game would have crashed at {crash_point:.2f}x ({closeness})"
                )
                self.active_games.remove(ctx.author.id)
                return await view.message.edit(embed=embed, view=None)
                
            # Update multiplier (but never beyond crash_point)
            multiplier = min(multiplier + increment, crash_point)
            increment = max(0.01, increment * 0.99)
            view.current_multiplier = multiplier
            
            # Update display
            embed = self._crash_embed(ctx.author.name, multiplier, bet, current_balance, False)
            try:
                await view.message.edit(embed=embed)
            except nextcord.NotFound:
                self.active_games.remove(ctx.author.id)
                return
                
            await asyncio.sleep(0.75)

    def _crash_view(self, user_id: int, bet: int, current_balance: int):
        """Create the crash game view with cashout button"""
        view = nextcord.ui.View(timeout=30.0)
        view.cashed_out = False
        view.cashout_multiplier = 1.0
        view.current_multiplier = 1.0  # Track current multiplier
        
        async def cashout_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            view.cashed_out = True
            view.cashout_multiplier = view.current_multiplier  # Use the tracked multiplier
            await interaction.response.defer()
        
        cashout_button = nextcord.ui.Button(label="Cash Out", style=nextcord.ButtonStyle.green)
        cashout_button.callback = cashout_callback
        view.add_item(cashout_button)
        
        return view

    def _crash_embed(self, author: str, multiplier: float, bet: int, balance: int, game_over: bool, status: str = None):
        """Create a crash game embed"""
        color = 0x2ecc71 if not game_over else 0xe74c3c
        title = f"{author.capitalize()}'s 🚀 Crash Game" if not game_over else "💥 Game Over"
        
        embed = nextcord.Embed(title=title, color=color)
        
        if status:
            embed.description = f"**{status}**"
        
        embed.add_field(
            name="Current Multiplier",
            value=f"**{multiplier:.2f}x**",
            inline=True
        )
        
        embed.add_field(
            name="Potential Win",
            value=f"**{int(bet * multiplier):,}** {self.currency}",
            inline=True
        )
        
        embed.add_field(
            name="Your Balance",
            value=f"**{balance:,}** {self.currency}",
            inline=True
        )
        
        if not game_over:
            embed.set_footer(text="Cash out before the game crashes!")
        
        return embed

    @commands.command(aliases=['rlt'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @requires_tos()
    async def roulette(self, ctx, bet: str = None, choice: str = None):
        """Play roulette - bet on numbers, colors, or odd/even
        
        Usage: `.roulette <bet> <choice>`
        Examples: `.roulette 1000 red`, `.roulette all 17`, `.roulette 500 odd`
        
        Betting options:
        - Numbers (0-36): 15:1 payout
        - red/black: 1.8:1 payout
        - odd/even: 1.8:1 payout
        - green (0): 15:1 payout
        """
        if not bet or not choice:
            embed = nextcord.Embed(
                title="🎰 Roulette",
                description="**Betting Options:**\n"
                          "• Numbers `0-36` - **15:1 payout**\n"
                          "• `red` or `black` - 1.8:1 payout\n"
                          "• `odd` or `even` - 1.8:1 payout\n"
                          "• `green` (0) - **15:1 payout**\n\n"
                          f"**Usage:** `{ctx.prefix}roulette <bet> <choice>`\n"
                          f"**Example:** `{ctx.prefix}roulette 1000 red`",
                color=0x9b59b6
            )
            return await ctx.reply(embed=embed)
            
        try:
            # Parse bet amount
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_bet = await self._parse_bet(bet, wallet)
            
            if not parsed_bet:
                return await ctx.reply("❌ Invalid bet amount!")
                
            if parsed_bet <= 0:
                return await ctx.reply("❌ Bet amount must be greater than 0!")

            if parsed_bet > wallet:
                return await ctx.reply("❌ You don't have enough money for that bet!")
            
            # Validate choice
            choice = choice.lower()
            valid_numbers = [str(i) for i in range(37)]
            valid_colors = ["red", "black", "green"]
            valid_types = ["odd", "even"]
            
            if choice not in valid_numbers + valid_colors + valid_types:
                return await ctx.reply("❌ Invalid choice! Must be a number (0-36), color (red/black/green), or type (odd/even)")
            
            # Deduct bet
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            self.stats_logger.log_command_usage("roulette")
            
            # Spin the wheel
            winning_number, winning_color = random.choice(self.roulette_wheel)
            
            # Check win conditions
            win = False
            multiplier = 0
            bet_name = choice
            
            if choice.isdigit():
                # Number bet
                if int(choice) == winning_number:
                    win = True
                    multiplier = 15
                    bet_name = f"Number {choice}"
            elif choice in ["red", "black", "green"]:
                # Color bet
                if choice == winning_color:
                    win = True
                    multiplier = 15 if choice == "green" else 1.8
                    bet_name = f"{choice.title()} color"
            elif choice in ["odd", "even"]:
                # Odd/even bet
                if winning_number != 0:
                    if (choice == "odd" and winning_number % 2 == 1) or (choice == "even" and winning_number % 2 == 0):
                        win = True
                        multiplier = 1.8
                        bet_name = f"{choice.title()} numbers"
            
            # Calculate winnings
            if win:
                winnings = int(parsed_bet * multiplier)
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                outcome = f"**You won {winnings:,}** {self.currency}! ({multiplier}x payout)"
                result_color = 0x2ecc71
                self.stats_logger.log_economy_transaction(ctx.author.id, "roulette", winnings, True)
            else:
                winnings = 0
                outcome = f"**You lost {parsed_bet:,}** {self.currency}!"
                result_color = 0xe74c3c
                self.stats_logger.log_economy_transaction(ctx.author.id, "roulette", parsed_bet, False)
            
            # Send initial spinning message
            spinning_embed = nextcord.Embed(
                title="🎰 Roulette (REBALANCED)",
                description="🎲 **The wheel is spinning...**",
                color=0x9b59b6
            )
            message = await ctx.reply(embed=spinning_embed)
            
            # Wait for suspense
            await asyncio.sleep(2)
            
            # Show result
            embed = nextcord.Embed(
                title=f"🎰 {'You Win!' if win else 'You Lose!'}",
                description=f"**Winning Number:** "
                        f"**{winning_number} {winning_color.title()}**\n\n"
                        f"**Your bet:** {bet_name}\n"
                        f"**Bet amount:** {parsed_bet:,} {self.currency}\n"
                        f"**Multiplier:** {multiplier}x\n\n"
                        f"{outcome}",
                color=result_color
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{wallet - parsed_bet + winnings:,}** {self.currency}",
                inline=True
            )
            
            if win:
                embed.add_field(
                    name="⚠️ Economy Rebalance",
                    value="All payouts heavily reduced to combat inflation",
                    inline=True
                )
            
            # Add different emojis based on result
            if win:
                embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/160/twitter/259/party-popper_1f389.png")
            else:
                embed.set_thumbnail(url="https://emojipedia-us.s3.dualstack.us-west-1.amazonaws.com/thumbs/160/twitter/259/pensive-face_1f614.png")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Roulette error: {e}")
            await ctx.reply("❌ An error occurred while processing your bet.")

    @commands.command(aliases=['bomb_activate'])
    @commands.cooldown(1, 300, commands.BucketType.guild)
    @requires_tos()
    async def bomb(self, ctx, channel: nextcord.TextChannel = None, amount: int = 1000):
        """Start a money bomb in a channel
        
        Usage: `.bomb [channel] [amount]`
        Examples: `.bomb #general 5000`, `.bomb 10000`
        
        Anyone who talks during the bomb has a 50% chance of losing money.
        You get up to 2x your investment back based on victims.
        """
        if not channel:
            channel = ctx.channel
            
        # Check permissions
        if not channel.permissions_for(ctx.guild.me).send_messages:
            embed = nextcord.Embed(
                color=0xFF0000,
                description=f"{ctx.author.mention}, I don't have permission to send messages in {channel.mention}!"
            )
            return await ctx.send(embed=embed)
        
        # Amount validation
        amount = max(1000, min(1000000, amount))  # Clamp between 1k-1M
        wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        
        if wallet < amount:
            embed = nextcord.Embed(
                color=0xFF0000,
                description=f"💸 {ctx.author.mention} You need **{amount:,}** {self.currency} (You have: {wallet:,})"
            )
            return await ctx.send(embed=embed)
        
        # Calculate duration (linear scaling, max 10min at 1M)
        base_duration = 60  # 1 minute at 1k coins
        max_duration = 600  # 10 minutes at 1M coins
        duration = min(max_duration, base_duration * (amount / 1000))
        
        # Deduct bomb cost
        await db.update_wallet(ctx.author.id, -amount, ctx.guild.id)
        
        # Bomb activation embed
        bomb_embed = nextcord.Embed(
            title="💣 **DYNAMIC MONEY BOMB** 💣",
            color=0xFF5733,
            description=(
                f"**Investor:** {ctx.author.mention}\n"
                f"**Investment:** {amount:,} {self.currency}\n"
                f"**Duration:** {int(duration)} seconds\n\n"
                "🚨 **ANY MESSAGE HAS 50% CHANCE TO EXPLODE** 💥\n"
                f"💰 **Potential Payout:** Up to {amount*2:,} {self.currency}"
            )
        )
        bomb_msg = await channel.send(embed=bomb_embed)
        
        # Game tracking
        victims = {}
        first_time_victims = set()
        bomber_bank = 0
        end_time = datetime.now() + timedelta(seconds=duration)
        
        def is_bomb_active():
            return datetime.now() < end_time
            
        # Real-time duration updater
        async def update_timer():
            while is_bomb_active():
                time_left = max(0, (end_time - datetime.now()).total_seconds())
                if time_left % 30 == 0 or time_left <= 10:  # Update every 30s or last 10s
                    await bomb_msg.edit(embed=bomb_embed.set_footer(
                        text=f"⏰ Time remaining: {int(time_left)} seconds | Current victims: {len(victims)}"
                    ))
                await asyncio.sleep(1)
        
        timer_task = self.bot.loop.create_task(update_timer())
        
        # Main game loop
        try:
            while is_bomb_active():
                try:
                    msg = await self.bot.wait_for(
                        'message',
                        check=lambda m: (
                            m.channel == channel and
                            not m.author.bot and
                            m.author != ctx.author and
                            is_bomb_active()
                        ),
                        timeout=0.5
                    )
                    
                    if random.random() < 0.5:
                        # Scale loss with investment (40-75 at 1k, up to 400-750 at 1M)
                        loss_multiplier = min(10, amount / 1000)
                        amount_lost = random.randint(
                            int(40 * loss_multiplier),
                            int(75 * loss_multiplier)
                        )
                        
                        # Take money from victim
                        await db.update_wallet(msg.author.id, -amount_lost, ctx.guild.id)
                        victims[msg.author.id] = victims.get(msg.author.id, 0) + amount_lost
                        bomber_bank += amount_lost
                        
                        if msg.author.id not in first_time_victims:
                            first_time_victims.add(msg.author.id)
                            await msg.add_reaction('💥')
                            await msg.add_reaction('💸')
                            
                except asyncio.TimeoutError:
                    continue
                    
        finally:
            timer_task.cancel()
        
        # Payout calculation (up to 2x investment)
        payout = min(amount*2, bomber_bank)
        await db.update_bank(ctx.author.id, payout, ctx.guild.id)
        
        # Results embed
        result_embed = nextcord.Embed(
            title=f"💥 **BOMB COMPLETED** 💥",
            color=0xFFA500,
            description=(
                f"**Investment:** {amount:,} {self.currency}\n"
                f"**Duration:** {int(duration)} seconds\n"
                f"**Total Payout:** {payout:,} {self.currency}\n"
                f"**ROI:** {((payout/amount)*100)-100:.1f}%\n\n"
                f"**Next Upgrade:** {int(amount*1.5):,} {self.currency} = {min(720, int(duration*1.5))} seconds"
            )
        )
        
        if victims:
            top_victims = sorted(victims.items(), key=lambda x: x[1], reverse=True)[:5]
            result_embed.add_field(
                name="🔥 Top Victims",
                value="\n".join(
                    f"{self.bot.get_user(vid).mention} ─ **{amt:,}** {self.currency}"
                    for vid, amt in top_victims
                ),
                inline=False
            )
        else:
            result_embed.add_field(
                name="Result",
                value="💨 No victims were caught!",
                inline=False
            )
        
        await channel.send(embed=result_embed)

async def setup(bot):
    bot.add_cog(SpecialGames(bot))
