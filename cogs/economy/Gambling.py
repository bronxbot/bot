from discord.ext import commands
from cogs.logging.logger import CogLogger
from cogs.logging.stats_logger import StatsLogger
from utils.db import async_db as db
import discord
import random
import asyncio
from typing import Optional, List, Dict
from datetime import datetime, timedelta

class Gambling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        
        # Card suits and values for blackjack
        self.suits = ["♠", "♥", "♦", "♣"]
        self.values = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        
        # Slot machine symbols with weights
        self.slot_symbols = [
            ("🍒", 30),
            ("🍋", 25),
            ("🍊", 20),
            ("🍇", 15),
            ("🔔", 7),
            ("7️⃣", 3),
            ("💎", 1)
        ]
        
        # Roulette numbers and colors
        self.roulette_numbers = [
            (0, "green"),
            (32, "red"), (15, "black"), (19, "red"), (4, "black"), (21, "red"), (2, "black"), 
            (25, "red"), (17, "black"), (34, "red"), (6, "black"), (27, "red"), (13, "black"), 
            (36, "red"), (11, "black"), (30, "red"), (8, "black"), (23, "red"), (10, "black"), 
            (5, "red"), (24, "black"), (16, "red"), (33, "black"), (1, "red"), (20, "black"), 
            (14, "red"), (31, "black"), (9, "red"), (22, "black"), (18, "red"), (29, "black"), 
            (7, "red"), (28, "black"), (12, "red"), (35, "black"), (3, "red"), (26, "black")
        ]

    @commands.command(aliases=['bj', 'blowjob'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def blackjack(self, ctx, bet: str):
        """Play blackjack against the dealer"""
        if ctx.author.id in self.active_games:
            return await ctx.reply("❌ You already have an active game!")
            
        self.active_games.add(ctx.author.id)
        
        try:
            # Parse bet amount
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_bet = await self._parse_bet(bet, wallet)
            
            if not parsed_bet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ Invalid bet amount!")

            if parsed_bet <= 0:
                return await ctx.reply("❌ Bet amount must be greater than 0!")

            if parsed_bet > wallet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ You don't have enough money for that bet!")
                
            # Initialize game
            dealer_hand = [self._draw_card(), self._draw_card()]
            player_hand = [self._draw_card(), self._draw_card()]
            
            # Check for blackjack
            player_bj = self._check_blackjack(player_hand)
            dealer_bj = self._check_blackjack(dealer_hand)
            
            if player_bj and dealer_bj:
                # Push - return bet
                self.stats_logger.log_command_usage("blackjack")  # Log usage
                self.active_games.remove(ctx.author.id)
                return await ctx.send(embed=self._blackjack_embed(
                    "Push! Both have Blackjack",
                    player_hand,
                    dealer_hand,
                    parsed_bet,
                    0,
                    wallet
                ))
            elif player_bj:
                # Player wins 3:2
                winnings = int(parsed_bet * 1.5)
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                self.stats_logger.log_command_usage("blackjack")  # Log usage
                self.stats_logger.log_economy_transaction(ctx.author.id, "blackjack", winnings, True)  # Log win
                self.active_games.remove(ctx.author.id)
                return await ctx.send(embed=self._blackjack_embed(
                    "Blackjack! You win!",
                    player_hand,
                    dealer_hand,
                    parsed_bet,
                    winnings,
                    wallet + winnings
                ))
            elif dealer_bj:
                # Dealer wins
                await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
                self.stats_logger.log_command_usage("blackjack")  # Log usage
                self.stats_logger.log_economy_transaction(ctx.author.id, "blackjack", parsed_bet, False)  # Log loss
                self.active_games.remove(ctx.author.id)
                return await ctx.send(embed=self._blackjack_embed(
                    "Dealer has Blackjack! You lose!",
                    player_hand,
                    dealer_hand,
                    parsed_bet,
                    -parsed_bet,
                    wallet - parsed_bet
                ))
            
            # Game continues
            view = self._blackjack_view(ctx.author.id, parsed_bet, player_hand, dealer_hand, wallet)
            embed = self._blackjack_embed(
                "Your turn - Hit or Stand?",
                player_hand,
                [dealer_hand[0], "❓"],
                parsed_bet,
                0,
                wallet
            )
            
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            
        except Exception as e:
            self.logger.error(f"Blackjack error: {e}")
            if ctx.author.id in self.active_games:
                self.active_games.remove(ctx.author.id)
            await ctx.reply("❌ An error occurred while starting the game.")

    def _blackjack_view(self, user_id: int, bet: int, player_hand: list, dealer_hand: list, wallet: int):
        """Create the blackjack game view with buttons"""
        view = discord.ui.View(timeout=60.0)
        
        async def hit_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Draw new card
            player_hand.append(self._draw_card())
            
            # Check for bust
            player_total = self._hand_value(player_hand)
            if player_total > 21:
                await db.update_wallet(user_id, -bet, interaction.guild.id)
                embed = self._blackjack_embed(
                    f"Bust! You lose {bet:,} {self.currency}",
                    player_hand,
                    dealer_hand,
                    bet,
                    -bet,
                    wallet - bet
                )
                self.active_games.remove(user_id)
                return await interaction.response.edit_message(embed=embed, view=None)
                
            # Update message
            embed = self._blackjack_embed(
                "Your turn - Hit or Stand?",
                player_hand,
                [dealer_hand[0], "❓"],
                bet,
                0,
                wallet
            )
            await interaction.response.edit_message(embed=embed, view=view)
        
        async def stand_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Dealer draws until 17 or higher
            dealer_total = self._hand_value(dealer_hand)
            while dealer_total < 17:
                dealer_hand.append(self._draw_card())
                dealer_total = self._hand_value(dealer_hand)
                
            # Determine winner
            player_total = self._hand_value(player_hand)
            outcome = ""
            winnings = 0
            
            if dealer_total > 21:
                outcome = f"Dealer busts! You win {bet:,} {self.currency}"
                winnings = bet
            elif player_total > dealer_total:
                outcome = f"You win {bet:,} {self.currency}!"
                winnings = bet
            elif player_total < dealer_total:
                outcome = f"You lose {bet:,} {self.currency}!"
                winnings = -bet
            else:
                outcome = "Push! Bet returned"
                winnings = 0
                
            # Update balance
            await db.update_wallet(user_id, winnings, interaction.guild.id)
            
            # Send final result
            embed = self._blackjack_embed(
                outcome,
                player_hand,
                dealer_hand,
                bet,
                winnings,
                wallet + winnings
            )
            self.active_games.remove(user_id)
            await interaction.response.edit_message(embed=embed, view=None)
        
        async def double_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Check if player can afford to double
            if wallet < bet * 2:
                return await interaction.response.send_message(
                    "❌ You don't have enough to double!", ephemeral=True)
                    
            # Double the bet and draw one card
            new_bet = bet * 2
            player_hand.append(self._draw_card())
            
            # Check for bust
            player_total = self._hand_value(player_hand)
            if player_total > 21:
                await db.update_wallet(user_id, -new_bet, interaction.guild.id)
                embed = self._blackjack_embed(
                    f"Bust! You lose {new_bet:,} {self.currency}",
                    player_hand,
                    dealer_hand,
                    new_bet,
                    -new_bet,
                    wallet - new_bet
                )
                self.active_games.remove(user_id)
                return await interaction.response.edit_message(embed=embed, view=None)
                
            # Dealer draws until 17 or higher
            dealer_total = self._hand_value(dealer_hand)
            while dealer_total < 17:
                dealer_hand.append(self._draw_card())
                dealer_total = self._hand_value(dealer_hand)
                
            # Determine winner
            outcome = ""
            winnings = 0
            
            if dealer_total > 21:
                outcome = f"Dealer busts! You win {new_bet:,} {self.currency}"
                winnings = new_bet
            elif player_total > dealer_total:
                outcome = f"You win {new_bet:,} {self.currency}!"
                winnings = new_bet
            elif player_total < dealer_total:
                outcome = f"You lose {new_bet:,} {self.currency}!"
                winnings = -new_bet
            else:
                outcome = "Push! Bet returned"
                winnings = 0
                
            # Update balance
            await db.update_wallet(user_id, winnings, interaction.guild.id)
            
            # Send final result
            embed = self._blackjack_embed(
                outcome,
                player_hand,
                dealer_hand,
                new_bet,
                winnings,
                wallet + winnings
            )
            self.active_games.remove(user_id)
            await interaction.response.edit_message(embed=embed, view=None)
        
        hit_button = discord.ui.Button(label="Hit", style=discord.ButtonStyle.green)
        hit_button.callback = hit_callback
        view.add_item(hit_button)
        
        stand_button = discord.ui.Button(label="Stand", style=discord.ButtonStyle.red)
        stand_button.callback = stand_callback
        view.add_item(stand_button)
        
        # Only allow double on first move (2 cards)
        if len(player_hand) == 2:
            double_button = discord.ui.Button(label="Double", style=discord.ButtonStyle.blurple)
            double_button.callback = double_callback
            view.add_item(double_button)
            
        return view

    def _blackjack_embed(self, title: str, player_hand: list, dealer_hand: list, bet: int, winnings: int, new_balance: int):
        """Create a blackjack game embed"""
        embed = discord.Embed(title=f"♠️♥️ Blackjack ♦️♣️ - {title}", color=0x2b2d31)
        
        # Format hands
        player_cards = " ".join([f"`{card}`" for card in player_hand])
        dealer_cards = " ".join([f"`{card}`" for card in dealer_hand])
        
        # Calculate totals if not hidden
        player_total = self._hand_value(player_hand)
        dealer_total = self._hand_value(dealer_hand) if "❓" not in dealer_hand else "?"
        
        embed.add_field(
            name=f"Your Hand ({player_total})",
            value=player_cards,
            inline=False
        )
        embed.add_field(
            name=f"Dealer's Hand ({dealer_total})",
            value=dealer_cards,
            inline=False
        )
        
        # Add bet info
        embed.add_field(
            name="Bet",
            value=f"**{bet:,}** {self.currency}",
            inline=True
        )
        
        # Add winnings if game is over
        if winnings != 0:
            embed.add_field(
                name="Result",
                value=f"**{winnings:,}** {self.currency}",
                inline=True
            )
        
        embed.add_field(
            name="New Balance",
            value=f"**{new_balance:,}** {self.currency}",
            inline=True
        )
        
        return embed

    def _draw_card(self) -> str:
        """Draw a random card"""
        value = random.choice(self.values)
        suit = random.choice(self.suits)
        return f"{value}{suit}"

    def _hand_value(self, hand: list) -> int:
        """Calculate the value of a hand"""
        value = 0
        aces = 0
        
        for card in hand:
            if isinstance(card, str) and card != "❓":
                card_value = card[:-1]  # Remove suit
                if card_value in ["J", "Q", "K"]:
                    value += 10
                elif card_value == "A":
                    value += 11
                    aces += 1
                else:
                    value += int(card_value)
        
        # Adjust for aces if over 21
        while value > 21 and aces > 0:
            value -= 10
            aces -= 1
            
        return value

    def _check_blackjack(self, hand: list) -> bool:
        """Check if hand is a blackjack (21 with 2 cards)"""
        return len(hand) == 2 and self._hand_value(hand) == 21

    @commands.command()
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def crash(self, ctx, bet: str):
        """Bet on a multiplier that can crash at any moment"""
        if ctx.author.id in self.active_games:
            return await ctx.reply("❌ You already have an active game!")
            
        self.active_games.add(ctx.author.id)
        
        try:
            # Parse bet amount
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_bet = await self._parse_bet(bet, wallet)
            
            if not parsed_bet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ Invalid bet amount!")

            if parsed_bet <= 0:
                return await ctx.reply("❌ Bet amount must be greater than 0!")

            if parsed_bet > wallet:
                self.active_games.remove(ctx.author.id)
                return await ctx.reply("❌ You don't have enough money for that bet!")
                
            # Deduct bet immediately
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            self.stats_logger.log_command_usage("crash")  # Log command usage
            
            # Create crash game
            view = self._crash_view(ctx.author.id, parsed_bet, wallet - parsed_bet)
            embed = self._crash_embed(1.0, parsed_bet, wallet - parsed_bet, False)
            
            message = await ctx.send(embed=embed, view=view)
            view.message = message
            
            # Start crash sequence
            await self._run_crash_game(ctx, view, parsed_bet, wallet - parsed_bet)
            
        except Exception as e:
            self.logger.error(f"Crash error: {e}")
            if ctx.author.id in self.active_games:
                self.active_games.remove(ctx.author.id)
            await ctx.reply("❌ An error occurred while starting the game.")

    async def _run_crash_game(self, ctx, view, bet: int, current_balance: int):
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
                    crash_point,
                    bet,
                    current_balance,
                    True,
                    f"💥 Crashed at {crash_point:.2f}x!"
                )
                self.active_games.remove(ctx.author.id)
                return await view.message.edit(embed=embed, view=None)
                
            # Then check for cashout (only possible if we haven't crashed yet)
            if view.cashed_out:
                winnings = int(bet * view.cashout_multiplier)
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                
                # Calculate how close they were to crashing
                percent_to_crash = (view.cashout_multiplier / crash_point) * 100
                closeness = f"{percent_to_crash:.0f}% to crash point"
                
                embed = self._crash_embed(
                    view.cashout_multiplier,
                    bet,
                    current_balance + winnings,
                    True,
                    f"💰 Cashed out at {view.cashout_multiplier:.2f}x!\n\n"
                    f"💡 Game would have crashed at {crash_point:.2f}x ({closeness})"
                )
                self.active_games.remove(ctx.author.id)
                return await view.message.edit(embed=embed, view=None)
                
            # Update multiplier (but never beyond crash_point)
            multiplier = min(multiplier + increment, crash_point)
            increment = max(0.01, increment * 0.99)
            view.current_multiplier = multiplier
            
            # Update display
            embed = self._crash_embed(multiplier, bet, current_balance, False)
            try:
                await view.message.edit(embed=embed)
            except discord.NotFound:
                self.active_games.remove(ctx.author.id)
                return
                
            await asyncio.sleep(0.75)

    def _crash_view(self, user_id: int, bet: int, current_balance: int):
        """Create the crash game view with cashout button"""
        view = discord.ui.View(timeout=30.0)
        view.cashed_out = False
        view.cashout_multiplier = 1.0
        view.current_multiplier = 1.0  # Track current multiplier
        
        async def cashout_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            view.cashed_out = True
            view.cashout_multiplier = view.current_multiplier  # Use the tracked multiplier
            await interaction.response.defer()
        
        cashout_button = discord.ui.Button(label="Cash Out", style=discord.ButtonStyle.green)
        cashout_button.callback = cashout_callback
        view.add_item(cashout_button)
        
        return view

    def _crash_embed(self, multiplier: float, bet: int, balance: int, game_over: bool, status: str = None):
        """Create a crash game embed"""
        color = 0x2ecc71 if not game_over else 0xe74c3c
        title = "🚀 Crash Game" if not game_over else "💥 Game Over"
        
        embed = discord.Embed(title=title, color=color)
        
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

    @commands.command(aliases=['cf', 'flip'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def coinflip(self, ctx, bet: str, choice: str = None):
        """Flip a coin - heads or tails"""
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
            if not choice:
                embed = discord.Embed(
                    title="🪙 Coin Flip",
                    description=f"Bet: **{parsed_bet:,}** {self.currency}\n\n"
                               f"Choose heads or tails:\n"
                               f"`{ctx.prefix}coinflip {bet} heads`\n"
                               f"`{ctx.prefix}coinflip {bet} tails`",
                    color=0xf1c40f
                )
                return await ctx.reply(embed=embed)
                
            choice = choice.lower()
            if choice not in ["heads", "tails", "h", "t"]:
                return await ctx.reply("❌ Invalid choice! Must be 'heads' or 'tails'")
                
            # Convert shorthand
            if choice == "h":
                choice = "heads"
            elif choice == "t":
                choice = "tails"
                
            # Flip coin
            result = random.choice(["heads", "tails"])
            win = choice == result
            
            # Calculate winnings
            if win:
                winnings = parsed_bet
                outcome = f"**You won {parsed_bet:,}** {self.currency}!"
                self.stats_logger.log_economy_transaction(ctx.author.id, "coinflip", winnings, True)  # Log win
            else:
                winnings = -parsed_bet
                outcome = f"**You lost {parsed_bet:,}** {self.currency}!"
                self.stats_logger.log_economy_transaction(ctx.author.id, "coinflip", parsed_bet, False)  # Log loss
                
            # Update balance
            await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
            self.stats_logger.log_command_usage("coinflip")  # Log command usage
            
            # Send result
            embed = discord.Embed(
                title=f"🪙 {'You win!' if win else 'You lose!'}",
                description=f"Your choice: **{choice.title()}**\n"
                          f"Result: **{result.title()}**\n\n"
                          f"{outcome}",
                color=0x2ecc71 if win else 0xe74c3c
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{wallet + winnings:,}** {self.currency}",
                inline=True
            )
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Coinflip error: {e}")
            await ctx.reply("❌ An error occurred while processing your bet.")

    @commands.command()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def slots(self, ctx, bet: str):
        """Play the slot machine"""
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
                
            # Deduct bet
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            self.stats_logger.log_command_usage("slots")  # Log command usage
            
            # Spin the slots
            reels = []
            total_weight = sum(weight for _, weight in self.slot_symbols)
            
            for _ in range(3):
                rand = random.uniform(0, total_weight)
                current = 0
                for symbol, weight in self.slot_symbols:
                    current += weight
                    if rand <= current:
                        reels.append(symbol)
                        break
            
            # Calculate winnings
            winnings = 0
            outcome = "You lost!"
            
            # Check for wins
            if reels[0] == reels[1] == reels[2]:
                if reels[0] == "💎":
                    multiplier = 100
                    outcome = "JACKPOT! 💎💎💎"
                elif reels[0] == "7️⃣":
                    multiplier = 20
                    outcome = "TRIPLE 7s! 🎰"
                elif reels[0] == "🔔":
                    multiplier = 10
                    outcome = "TRIPLE BELLS! 🔔"
                else:
                    multiplier = 5
                    outcome = "TRIPLE MATCH!"
                    
                winnings = parsed_bet * multiplier
            elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
                multiplier = 2
                winnings = parsed_bet * multiplier
                outcome = "DOUBLE MATCH!"
                
            # Update balance if won
            if winnings > 0:
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                self.stats_logger.log_economy_transaction(ctx.author.id, "slots", winnings, True)  # Log win
            else:
                self.stats_logger.log_economy_transaction(ctx.author.id, "slots", parsed_bet, False)  # Log loss
                
            # Create slot display
            slot_display = " | ".join(reels)
            
            embed = discord.Embed(
                title="🎰 Slot Machine",
                description=f"**{slot_display}**\n\n"
                          f"**{outcome}**\n"
                          f"Bet: **{parsed_bet:,}** {self.currency}\n"
                          f"Won: **{winnings:,}** {self.currency}",
                color=0x9b59b6
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{wallet - parsed_bet + winnings:,}** {self.currency}",
                inline=True
            )
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Slots error: {e}")
            await ctx.reply("❌ An error occurred while spinning the slots.")

    @commands.command(aliases=['double', 'don', 'dbl'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def doubleornothing(self, ctx, *, items: str = None):
        """Double your items or lose them"""
        if ctx.author.id in self.active_games:
            return await ctx.reply("❌ You already have an active game!")
            
        if not items:
            return await ctx.reply(f"Usage: `{ctx.prefix}doubleornothing <item1> [item2] ... [item20]`")
            
        try:
            # Get user inventory
            inventory = await db.get_inventory(ctx.author.id, ctx.guild.id)
            if not inventory:
                return await ctx.reply("❌ Your inventory is empty!")
                
            # Parse requested items
            requested_items = items.split()
            if len(requested_items) > 20:
                return await ctx.reply("❌ You can only bet up to 20 items at a time!")
                
            # Find matching items in inventory
            items_to_bet = []
            for item_name in requested_items:
                found = False
                for item in inventory:
                    if (item.get("id", "").lower() == item_name.lower() or 
                        item.get("name", "").lower() == item_name.lower()):
                        items_to_bet.append(item)
                        found = True
                        break
                        
                if not found:
                    return await ctx.reply(f"❌ You don't have '{item_name}' in your inventory!")
                    
            # Create confirmation view
            view = discord.ui.View(timeout=30.0)
            
            async def confirm_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                    
                # Flip coin (50% chance)
                win = random.choice([True, False])
                
                if win:
                    # Double the items
                    for item in items_to_bet:
                        await db.add_to_inventory(
                            ctx.author.id, 
                            ctx.guild.id, 
                            item, 
                            item.get("quantity", 1)
                        )
                        
                    outcome = f"**You won!** All items doubled!"
                    self.stats_logger.log_economy_transaction(
                        ctx.author.id, 
                        "doubleornothing", 
                        sum(item.get("value", 0) for item in items_to_bet), 
                        True
                    )  # Log win (approximate value)
                else:
                    # Remove the items
                    for item in items_to_bet:
                        await db.remove_from_inventory(
                            ctx.author.id, 
                            ctx.guild.id, 
                            item.get("id", item.get("name")), 
                            item.get("quantity", 1)
                        )
                        
                    outcome = "**You lost!** All items are gone!"
                    self.stats_logger.log_economy_transaction(
                        ctx.author.id, 
                        "doubleornothing", 
                        sum(item.get("value", 0) for item in items_to_bet), 
                        False
                    )  # Log loss (approximate value)
                    
                # Log command usage
                self.stats_logger.log_command_usage("doubleornothing")
                
                # Create result embed
                item_names = ", ".join([item.get("name", "Unknown") for item in items_to_bet])
                
                embed = discord.Embed(
                    title="🎲 Double or Nothing",
                    description=f"You bet: **{item_names}**\n\n"
                            f"{outcome}",
                    color=0x2ecc71 if win else 0xe74c3c
                )
                
                await interaction.response.edit_message(embed=embed, view=None)
                self.active_games.remove(ctx.author.id)
                
            async def cancel_callback(interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                    
                await interaction.response.edit_message(content="❌ Game cancelled.", embed=None, view=None)
                self.active_games.remove(ctx.author.id)
                
            confirm_button = discord.ui.Button(label="Confirm", style=discord.ButtonStyle.green)
            confirm_button.callback = confirm_callback
            view.add_item(confirm_button)
            
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
            cancel_button.callback = cancel_callback
            view.add_item(cancel_button)
            
            # Create confirmation message
            item_names = ", ".join([item.get("name", "Unknown") for item in items_to_bet])
            
            embed = discord.Embed(
                title="🎲 Double or Nothing",
                description=f"You're about to bet:\n**{item_names}**\n\n"
                        f"50% chance to double them, 50% chance to lose them all!",
                color=0xf39c12
            )
            
            self.active_games.add(ctx.author.id)
            await ctx.reply(embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Double or nothing error: {e}")
            if ctx.author.id in self.active_games:
                self.active_games.remove(ctx.author.id)
            await ctx.reply("❌ An error occurred while setting up the game.")
            
    @commands.command(aliases=['rlt'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def roulette(self, ctx, bet: str = None, choice: str = None):
        """Play roulette - bet on numbers, colors, or odd/even"""
        if bet is None or choice is None:
            # Show help menu if no args provided
            embed = discord.Embed(
                title="🎡 Roulette Help",
                description="Place bets on numbers, colors, or other options in roulette.",
                color=0x3498db
            )
            
            embed.add_field(
                name="💰 Bet Types & Payouts",
                value=(
                    "`number (0-36)` - 35:1 payout\n"
                    "`red`/`black` - 1:1 payout\n"
                    "`green` (0) - 35:1 payout\n"
                    "`even`/`odd` - 1:1 payout\n"
                    "`1st12`/`2nd12`/`3rd12` - 2:1 payout\n"
                    "`1-18`/`19-36` - 1:1 payout"
                ),
                inline=False
            )
            
            embed.add_field(
                name="📝 Usage Examples",
                value=(
                    "`.rlt 500 red` - Bet 500 on red\n"
                    "`.rlt all 7` - Bet everything on number 7\n"
                    "`.rlt half odd` - Bet half your balance on odd\n"
                    "`.rlt 1k 1st12` - Bet 1,000 on first dozen (1-12)"
                ),
                inline=False
            )
            
            embed.add_field(
                name="💡 Bet Amount Options",
                value=(
                    "You can bet using:\n"
                    "- Exact amounts (`500`)\n"
                    "- `all` or `max` (your entire balance)\n"
                    "- `half` (half your balance)\n"
                    "- Percentages (`50%`)\n"
                    "- Suffixes (`1k` = 1,000, `1.5m` = 1,500,000)"
                ),
                inline=False
            )
            
            embed.set_footer(text=f"Current balance: {await db.get_wallet_balance(ctx.author.id, ctx.guild.id):,} {self.currency}")
            return await ctx.reply(embed=embed)
        
        try:
            # Parse bet amount
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_bet = await self._parse_bet(bet, wallet)
            
            if not parsed_bet:
                return await ctx.reply("❌ Invalid bet amount!")
            
            if parsed_bet <= 0:
                return await ctx.reply("❌ Bet amount must be greater than 0! \n-# *(Do you have $0 in your wallet?)*")
                
            if parsed_bet > wallet:
                return await ctx.reply("❌ You don't have enough money for that bet!")
                
            # Parse choice
            choice = choice.lower()
            # In the valid_choices dictionary, change the multipliers for red/black/even/odd from 1 to 2
            valid_choices = {
                "red": ("color", 2, "Red"),        # Changed from 1 to 2
                "black": ("color", 2, "Black"),    # Changed from 1 to 2
                "green": ("color", 35, "Green (0)"),
                "even": ("even", 2, "Even"),      # Changed from 1 to 2
                "odd": ("odd", 2, "Odd"),          # Changed from 1 to 2
                "1st12": ("dozen", 2, "1st 12"),
                "2nd12": ("dozen", 2, "2nd 12"),
                "3rd12": ("dozen", 2, "3rd 12"),
                "1-18": ("half", 2, "1-18"),       # Changed from 1 to 2
                "19-36": ("half", 2, "19-36")      # Changed from 1 to 2
            }
            
            # Check for number bet
            number_bet = None
            try:
                number = int(choice)
                if 0 <= number <= 36:
                    number_bet = ("number", 35, f"Number {number}")
            except ValueError:
                pass
                
            if not number_bet and choice not in valid_choices:
                return await ctx.reply(
                    "❌ Invalid bet type!\n"
                    "Valid bets: `number (0-36)`, `red`, `black`, `green`, `even`, `odd`, "
                    "`1st12`, `2nd12`, `3rd12`, `1-18`, `19-36`"
                )
                
            bet_type, multiplier, bet_name = number_bet if number_bet else valid_choices[choice]
            
            # Deduct bet
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            
            # Create initial embed
            embed = discord.Embed(
                title="🎡 Roulette - Spinning...",
                description=f"**Your bet:** {bet_name}\n"
                        f"**Bet amount:** {parsed_bet:,} {self.currency}\n"
                        f"**Potential win:** {parsed_bet * multiplier:,} {self.currency}\n\n"
                        f"The wheel is spinning...",
                color=0xf39c12
            )
            message = await ctx.reply(embed=embed)
            
            # Animation sequence
            spin_duration = 5  # seconds
            spin_steps = 10
            delay = spin_duration / spin_steps
            
            # Generate the final result first
            winning_number, winning_color = random.choice(self.roulette_numbers)
            
            # Create animation steps
            for i in range(spin_steps):
                # Show random numbers during spin
                anim_number, anim_color = random.choice(self.roulette_numbers)
                
                # Gradually slow down the animation
                if i > spin_steps * 0.7:  # Last 30% of spins
                    # Start homing in on the actual result
                    if random.random() < 0.3 + (i/spin_steps):
                        anim_number, anim_color = winning_number, winning_color
                
                embed.description = (
                    f"**Your bet:** {bet_name}\n"
                    f"**Bet amount:** {parsed_bet:,} {self.currency}\n"
                    f"**Potential win:** {parsed_bet * multiplier:,} {self.currency}\n\n"
                    f"**The ball is rolling...**\n"
                    f"Current position: {anim_number} {anim_color.title()}"
                )
                
                # Make the wheel appear to slow down
                if i == spin_steps - 1:
                    embed.title = "🎡 Roulette - Almost there..."
                elif i > spin_steps * 0.8:
                    embed.title = "🎡 Roulette - Slowing down..."
                
                await message.edit(embed=embed)
                await asyncio.sleep(delay)
            
            # Determine if bet won
            win = False
            if bet_type == "number":
                win = winning_number == number
            elif bet_type == "color":
                win = winning_color == choice
            elif bet_type == "even":
                win = winning_number != 0 and winning_number % 2 == 0
            elif bet_type == "odd":
                win = winning_number % 2 == 1
            elif bet_type == "dozen":
                dozen = int(choice[:1])  # 1, 2, or 3
                win = (dozen - 1) * 12 < winning_number <= dozen * 12
            elif bet_type == "half":
                if choice == "1-18":
                    win = 1 <= winning_number <= 18
                else:
                    win = 19 <= winning_number <= 36
                    
            # Calculate winnings
            if win:
                winnings = parsed_bet * multiplier
                outcome = f"**You won {winnings:,}** {self.currency}!"
                self.stats_logger.log_economy_transaction(ctx.author.id, "roulette", winnings, True)  # Log win
            else:
                winnings = -parsed_bet
                outcome = f"**You lost {parsed_bet:,}** {self.currency}!"
                self.stats_logger.log_economy_transaction(ctx.author.id, "roulette", parsed_bet, False)  # Log loss
                
            # Update balance
            if winnings > 0:
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                
            # Create final result embed
            result_color = 0xe74c3c if winning_color == "red" else 0x2c3e50 if winning_color == "black" else 0x2ecc71
            
            embed = discord.Embed(
                title=f"🎡 Roulette - {'Winner!' if win else 'Better luck next time!'}",
                description=f"**The ball landed on:**\n"
                        f"**{winning_number} {winning_color.title()}**\n\n"
                        f"**Your bet:** {bet_name}\n"
                        f"**Bet amount:** {parsed_bet:,} {self.currency}\n"
                        f"**Multiplier:** {multiplier}x\n\n"
                        f"{outcome}",
                color=result_color
            )
            
            embed.add_field(
                name="New Balance",
                value=f"**{wallet - parsed_bet + (winnings if win else 0):,}** {self.currency}",
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
    async def bomb(self, ctx, channel: discord.TextChannel = None, amount: int = 1000):
        """💣 Start a money bomb (Duration scales with investment)
        
        Parameters:
        channel: Target channel (#mention)
        amount: Investment (1000-1M coins, default: 1000)
        """
        # Validation checks
        if channel is None:
            embed = discord.Embed(
                color=0xFF0000,
                description=f"{ctx.author.mention}, please specify a channel: `!bomb #channel [amount]`"
            )
            return await ctx.send(embed=embed)
        
        if not isinstance(channel, discord.TextChannel):
            embed = discord.Embed(
                color=0xFF0000,
                description=f"{ctx.author.mention}, you must specify a valid text channel!"
            )
            return await ctx.send(embed=embed)
        
        if not channel.permissions_for(ctx.guild.me).send_messages:
            embed = discord.Embed(
                color=0xFF0000,
                description=f"{ctx.author.mention}, I don't have permission to send messages in {channel.mention}!"
            )
            return await ctx.send(embed=embed)
        
        # Amount validation
        amount = max(1000, min(1000000, amount))  # Clamp between 1k-1M
        wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        
        if wallet < amount:
            embed = discord.Embed(
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
        bomb_embed = discord.Embed(
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
        result_embed = discord.Embed(
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

    async def _parse_bet(self, bet_str: str, wallet: int) -> int:
        """Parse bet amount from string (supports all, half, %, k, m suffixes)"""
        try:
            bet_str = bet_str.lower().strip()
            
            if bet_str in ['all', 'max']:
                return wallet
            elif bet_str in ['half', '1/2']:
                return wallet // 2
            elif bet_str.endswith('%'):
                percent = float(bet_str[:-1])
                if percent <= 0 or percent > 100:
                    return None
                return int(wallet * (percent / 100))
            elif bet_str.endswith('k'):
                return int(float(bet_str[:-1]) * 1000)
            elif bet_str.endswith('m'):
                return int(float(bet_str[:-1]) * 1000000)
            else:
                return int(bet_str)
        except (ValueError, AttributeError):
            return None

async def setup(bot):
    await bot.add_cog(Gambling(bot))