# Card Games Module
# Contains card-based gambling games like Blackjack

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
import functools
from typing import Optional, List

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

class CardGames(commands.Cog):
    """Card-based gambling games"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        

        
        # Card deck
        self.suits = ["♠", "♥", "♦", "♣"]
        self.values = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
        
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
        self.logger.info("Card games module initialized")
    
    async def cog_check(self, ctx):
        """Global check for gambling commands"""
        if ctx.channel.id in self.blocked_channels:
            await ctx.reply("❌ Gambling commands are not allowed in this channel!")
            return False
            
        # Ensure user exists in database by getting their wallet balance
        # This will automatically create the user if they don't exist due to upsert=True
        await db.get_wallet_balance(ctx.author.id)
        
        return True

    async def _parse_bet(self, bet_str: str, wallet: int) -> int:
        """Parse bet string (all, half, percentage, or number)"""
        bet_str = bet_str.lower().strip()
        
        if bet_str in ['all', 'max']:
            return wallet
        elif bet_str in ['half', '50%']:
            return wallet // 2
        elif bet_str.endswith('%'):
            try:
                percentage = float(bet_str[:-1])
                if 0 <= percentage <= 100:
                    return int(wallet * (percentage / 100))
            except ValueError:
                pass
        else:
            try:
                return int(bet_str.replace(',', ''))
            except ValueError:
                pass
        
        return None

    @commands.command(aliases=['bj'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @requires_tos()
    async def blackjack(self, ctx, bet: str):
        """Play blackjack against the dealer
        
        Usage: `.blackjack <bet>`
        Examples: `.blackjack 1000`, `.blackjack all`, `.blackjack 50%`
        
        Payouts:
        - Blackjack: 1.3x bet
        - Regular win: 0.9x bet
        """
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
                self.active_games.remove(ctx.author.id)
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
                self.stats_logger.log_command_usage("blackjack")
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
                # Player wins blackjack
                winnings = int(parsed_bet * 1.3)
                await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
                self.stats_logger.log_command_usage("blackjack")
                self.stats_logger.log_economy_transaction(ctx.author.id, "blackjack", winnings, True)
                self.active_games.remove(ctx.author.id)
                return await ctx.send(embed=self._blackjack_embed(
                    "Blackjack! You win! (1.3x payout)",
                    player_hand,
                    dealer_hand,
                    parsed_bet,
                    winnings,
                    wallet + winnings
                ))
            elif dealer_bj:
                # Dealer wins
                await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
                self.stats_logger.log_command_usage("blackjack")
                self.stats_logger.log_economy_transaction(ctx.author.id, "blackjack", parsed_bet, False)
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

    def _can_split(self, hand: list) -> bool:
        """Check if hand can be split (two cards of same value)"""
        if len(hand) != 2:
            return False
        card1 = hand[0][:-1]  # Remove suit
        card2 = hand[1][:-1]
        return card1 == card2

    def _blackjack_view(self, user_id: int, bet: int, player_hand: list, dealer_hand: list, wallet: int, split_count: int = 0):
        """Create the blackjack game view with buttons"""
        view = nextcord.ui.View(timeout=60.0)
        
        async def hit_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Draw new card
            player_hand.append(self._draw_card())
            
            # Check for bust
            player_total = self._hand_value(player_hand)
            if player_total > 21:
                await db.update_wallet(user_id, -bet * (split_count + 1), interaction.guild.id)
                embed = self._blackjack_embed(
                    f"Bust! You lose {bet * (split_count + 1):,} {self.currency}",
                    player_hand,
                    dealer_hand,
                    bet,
                    -bet * (split_count + 1),
                    wallet - bet * (split_count + 1),
                    split_count
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
                wallet,
                split_count
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
                outcome = f"Dealer busts! You win {int(bet * 0.9 * (split_count + 1)):,} {self.currency} (0.9x payout)"
                winnings = int(bet * 0.9 * (split_count + 1))
            elif player_total > dealer_total:
                outcome = f"You win {int(bet * 0.9 * (split_count + 1)):,} {self.currency}! (0.9x payout)"
                winnings = int(bet * 0.9 * (split_count + 1))
            elif player_total < dealer_total:
                outcome = f"You lose {bet * (split_count + 1):,} {self.currency}!"
                winnings = -bet * (split_count + 1)
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
                wallet + winnings,
                split_count
            )
            self.active_games.remove(user_id)
            await interaction.response.edit_message(embed=embed, view=None)
        
        async def double_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Check if player can afford to double
            if wallet < bet * (split_count + 2):
                return await interaction.response.send_message(
                    "❌ You don't have enough to double!", ephemeral=True)
                    
            # Double the bet and draw one card
            new_bet = bet * 2
            player_hand.append(self._draw_card())
            
            # Check for bust
            player_total = self._hand_value(player_hand)
            if player_total > 21:
                await db.update_wallet(user_id, -new_bet * (split_count + 1), interaction.guild.id)
                embed = self._blackjack_embed(
                    f"Bust! You lose {new_bet * (split_count + 1):,} {self.currency}",
                    player_hand,
                    dealer_hand,
                    new_bet,
                    -new_bet * (split_count + 1),
                    wallet - new_bet * (split_count + 1),
                    split_count
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
                outcome = f"Dealer busts! You win {new_bet * (split_count + 1):,} {self.currency}"
                winnings = new_bet * (split_count + 1)
            elif player_total > dealer_total:
                outcome = f"You win {new_bet * (split_count + 1):,} {self.currency}!"
                winnings = new_bet * (split_count + 1)
            elif player_total < dealer_total:
                outcome = f"You lose {new_bet * (split_count + 1):,} {self.currency}!"
                winnings = -new_bet * (split_count + 1)
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
                wallet + winnings,
                split_count
            )
            self.active_games.remove(user_id)
            await interaction.response.edit_message(embed=embed, view=None)
        
        async def split_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Check if player can afford another split (max 4 hands)
            if split_count >= 3:
                return await interaction.response.send_message(
                    "❌ You can't split more than 4 hands!", ephemeral=True)
                    
            if wallet < bet * (split_count + 2):
                return await interaction.response.send_message(
                    "❌ You don't have enough to split again!", ephemeral=True)
                    
            # Split the hand into two hands
            hand1 = [player_hand[0], self._draw_card()]
            hand2 = [player_hand[1], self._draw_card()]
            
            # Create split queue
            split_queue = [hand1, hand2]
            
            # Create split game view
            view = self._blackjack_split_view(
                user_id,
                bet,
                split_queue,
                dealer_hand,
                wallet - bet,
                split_count + 1
            )
            
            embed = self._blackjack_split_embed(
                f"Split 1/{len(split_queue)} - Hit or Stand?",
                split_queue[0],
                split_queue[1:] if len(split_queue) > 1 else None,
                [dealer_hand[0], "❓"],
                bet,
                0,
                wallet - bet,
                split_count + 1
            )
            
            await interaction.response.edit_message(embed=embed, view=view)
        
        hit_button = nextcord.ui.Button(label="Hit", style=nextcord.ButtonStyle.green)
        hit_button.callback = hit_callback
        view.add_item(hit_button)
        
        stand_button = nextcord.ui.Button(label="Stand", style=nextcord.ButtonStyle.red)
        stand_button.callback = stand_callback
        view.add_item(stand_button)
        
        # Only allow double on first move (2 cards)
        if len(player_hand) == 2:
            double_button = nextcord.ui.Button(label="Double", style=nextcord.ButtonStyle.blurple)
            double_button.callback = double_callback
            view.add_item(double_button)
            
            # Only allow split if cards have same value and we have < 4 hands
            if self._can_split(player_hand) and split_count < 3:
                split_button = nextcord.ui.Button(label="Split", style=nextcord.ButtonStyle.grey)
                split_button.callback = split_callback
                view.add_item(split_button)
                
        return view

    def _blackjack_split_view(self, user_id: int, bet: int, split_queue: list, dealer_hand: list, wallet: int, split_count: int):
        """Create a view for split hands with queue"""
        view = nextcord.ui.View(timeout=60.0)
        view.current_hand_index = 0
        view.split_queue = split_queue
        view.hands_completed = 0
        view.split_count = split_count
        
        async def hit_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Add card to current hand
            view.split_queue[view.current_hand_index].append(self._draw_card())
            current_hand = view.split_queue[view.current_hand_index]
            
            # Check for bust
            hand_value = self._hand_value(current_hand)
            if hand_value > 21:
                # Mark hand as done
                view.hands_completed += 1
                
                # Check if all hands are done
                if view.hands_completed == len(view.split_queue):
                    total_loss = bet * len(view.split_queue)
                    await db.update_wallet(user_id, -total_loss, interaction.guild.id)
                    embed = self._blackjack_split_embed(
                        f"All hands bust! You lose {total_loss:,} {self.currency}",
                        view.split_queue[0],
                        view.split_queue[1:],
                        dealer_hand,
                        bet,
                        -total_loss,
                        wallet - total_loss + bet,
                        view.split_count
                    )
                    self.active_games.remove(user_id)
                    return await interaction.response.edit_message(embed=embed, view=None)
                else:
                    # Move to next hand
                    view.current_hand_index += 1
                    embed = self._blackjack_split_embed(
                        f"Split {view.current_hand_index + 1}/{len(view.split_queue)} - Hit or Stand?",
                        view.split_queue[view.current_hand_index],
                        [h for i, h in enumerate(view.split_queue) if i != view.current_hand_index],
                        [dealer_hand[0], "❓"],
                        bet,
                        0,
                        wallet,
                        view.split_count
                    )
                    return await interaction.response.edit_message(embed=embed, view=view)
                    
            # Update message
            embed = self._blackjack_split_embed(
                f"Split {view.current_hand_index + 1}/{len(view.split_queue)} - Hit or Stand?",
                view.split_queue[view.current_hand_index],
                [h for i, h in enumerate(view.split_queue) if i != view.current_hand_index],
                [dealer_hand[0], "❓"],
                bet,
                0,
                wallet,
                view.split_count
            )
            await interaction.response.edit_message(embed=embed, view=view)
        
        async def stand_callback(interaction):
            if interaction.user.id != user_id:
                return await interaction.response.send_message("❌ This isn't your game!", ephemeral=True)
                
            # Mark current hand as done
            view.hands_completed += 1
            
            # Check if all hands are done
            if view.hands_completed == len(view.split_queue):
                # Dealer draws until 17 or higher
                dealer_total = self._hand_value(dealer_hand)
                while dealer_total < 17:
                    dealer_hand.append(self._draw_card())
                    dealer_total = self._hand_value(dealer_hand)
                    
                # Evaluate all hands
                results = []
                total_winnings = 0
                
                for hand in view.split_queue:
                    hand_value = self._hand_value(hand)
                    
                    if hand_value > 21:
                        results.append("Bust")
                        total_winnings -= bet
                    elif dealer_total > 21:
                        results.append("Win (Dealer bust)")
                        total_winnings += bet
                    elif hand_value > dealer_total:
                        results.append("Win")
                        total_winnings += bet
                    elif hand_value < dealer_total:
                        results.append("Lose")
                        total_winnings -= bet
                    else:
                        results.append("Push")
                        
                # Update balance
                await db.update_wallet(user_id, total_winnings, interaction.guild.id)
                
                # Create result message
                outcome = "\n".join(
                    f"Hand {i+1}: {result}" 
                    for i, result in enumerate(results)
                )
                outcome += f"\n\n**Net {'win' if total_winnings > 0 else 'loss'}: {abs(total_winnings):,} {self.currency}**"
                    
                embed = self._blackjack_split_embed(
                    outcome,
                    view.split_queue[0],
                    view.split_queue[1:],
                    dealer_hand,
                    bet,
                    total_winnings,
                    wallet + total_winnings + bet,
                    view.split_count
                )
                self.active_games.remove(user_id)
                return await interaction.response.edit_message(embed=embed, view=None)
            else:
                # Move to next hand
                view.current_hand_index += 1
                embed = self._blackjack_split_embed(
                    f"Split {view.current_hand_index + 1}/{len(view.split_queue)} - Hit or Stand?",
                    view.split_queue[view.current_hand_index],
                    [h for i, h in enumerate(view.split_queue) if i != view.current_hand_index],
                    [dealer_hand[0], "❓"],
                    bet,
                    0,
                    wallet,
                    view.split_count
                )
                return await interaction.response.edit_message(embed=embed, view=view)
        
        hit_button = nextcord.ui.Button(label="Hit", style=nextcord.ButtonStyle.green)
        hit_button.callback = hit_callback
        view.add_item(hit_button)
        
        stand_button = nextcord.ui.Button(label="Stand", style=nextcord.ButtonStyle.red)
        stand_button.callback = stand_callback
        view.add_item(stand_button)
        
        return view

    def _blackjack_split_embed(self, title: str, current_hand: list, other_hands: list, dealer_hand: list, bet: int, winnings: int, new_balance: int, split_count: int):
        """Create a blackjack split game embed"""
        embed = nextcord.Embed(
            title=f"♠️♥️ Blackjack Game (Split {split_count}/4) ♦️♣️ - {title}", 
            color=0x2b2d31
        )
        
        # Format hands
        current_hand_cards = " ".join([f"`{card}`" for card in current_hand])
        dealer_cards = " ".join([f"`{card}`" for card in dealer_hand])
        
        # Calculate totals
        current_hand_total = self._hand_value(current_hand)
        dealer_total = self._hand_value(dealer_hand) if "❓" not in dealer_hand else "?"
        
        embed.add_field(
            name=f"Current Hand ({current_hand_total})",
            value=current_hand_cards,
            inline=False
        )
        
        # Show other hands if they exist
        if other_hands and len(other_hands) > 0:
            other_hands_text = []
            for i, hand in enumerate(other_hands, 1):
                hand_cards = " ".join([f"`{card}`" for card in hand])
                hand_total = self._hand_value(hand)
                other_hands_text.append(f"**Hand {i} ({hand_total})**: {hand_cards}")
            
            embed.add_field(
                name="Other Hands",
                value="\n".join(other_hands_text),
                inline=False
            )
        
        embed.add_field(
            name=f"Dealer's Hand ({dealer_total})",
            value=dealer_cards,
            inline=False
        )
        
        # Add bet info
        embed.add_field(
            name="Bet per Hand",
            value=f"**{bet:,}** {self.currency}",
            inline=True
        )
        
        # Add winnings if game is over
        if winnings != 0:
            embed.add_field(
                name="Net Result",
                value=f"**{winnings:,}** {self.currency}",
                inline=True
            )
        
        embed.add_field(
            name="New Balance",
            value=f"**{new_balance:,}** {self.currency}",
            inline=True
        )
        
        return embed

    def _blackjack_embed(self, title: str, player_hand: list, dealer_hand: list, bet: int, winnings: int, new_balance: int, split_count: int = 0):
        """Create a blackjack game embed"""
        embed_title = f"♠️♥️ Blackjack Game"
        if split_count > 0:
            embed_title += f" (Split {split_count}/4)"
        embed_title += f" ♦️♣️ - {title}"
        
        embed = nextcord.Embed(title=embed_title, color=0x2b2d31)
        
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
        bet_amount = bet * (split_count + 1) if split_count > 0 else bet
        embed.add_field(
            name="Bet",
            value=f"**{bet_amount:,}** {self.currency}",
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

async def setup(bot):
    bot.add_cog(CardGames(bot))
