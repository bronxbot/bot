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
from typing import List

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

class Plinko(commands.Cog):
    """The classic plinko game - watch your mortgage disappear!"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        
        # Plinko board configuration (16 slots at bottom)
        # Multipliers for each slot
        self.multipliers = [0.1, 0.3, 0.5, 0.8, 1.0, 1.2, 1.5, 2.0, 2.0, 1.5, 1.2, 1.0, 0.8, 0.5, 0.3, 0.1]
        self.rows = 10  # Number of peg rows
        

        
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
                parsed_bet = wallet
            elif bet_str.lower() == "half":
                parsed_bet = int(wallet / 2)
            elif bet_str.endswith("%"):
                percentage = float(bet_str[:-1])
                if percentage < 0 or percentage > 100:
                    return None
                parsed_bet = int(wallet * (percentage / 100))
            else:
                parsed_bet = int(bet_str.replace(",", ""))
            
            return parsed_bet
            
        except (ValueError, TypeError):
            return None

    @commands.command(aliases=['plink', 'ball'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @requires_tos()
    async def plinko(self, ctx, bet: str):
        """Play plinko - watch the ball bounce to glory or despair!
        
        Usage: `.plinko <bet>`
        Examples: `.plinko 1000`, `.plinko all`, `.plinko 50%`
        
        Drop a ball down the plinko board and watch it bounce between pegs
        until it lands in one of 16 slots with different multipliers!
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
                
            # Deduct bet
            await db.update_wallet(ctx.author.id, -parsed_bet, ctx.guild.id)
            self.stats_logger.log_command_usage("plinko")
            
            # Start the plinko game
            await self._run_plinko_game(ctx, parsed_bet, wallet - parsed_bet)
            
        except Exception as e:
            self.logger.error(f"Plinko error: {e}")
            if ctx.author.id in self.active_games:
                self.active_games.remove(ctx.author.id)
            await ctx.reply("❌ An error occurred while starting the game.")
    
    async def _run_plinko_game(self, ctx, bet: int, current_balance: int):
        """Run the plinko ball drop animation"""
        # Calculate ball path
        ball_path = self._calculate_ball_path()
        final_slot = ball_path[-1]
        final_multiplier = self.multipliers[final_slot]
        winnings = int(bet * final_multiplier)
        
        # Show initial board
        embed = self._create_plinko_embed(
            ctx.author.name,
            bet,
            current_balance,
            "🔴 Ball dropped! Watch it bounce...",
            ball_position=8,  # Start at center top
            current_row=0
        )
        
        message = await ctx.send(embed=embed)
        
        # Optimize animation to reduce rate limits - batch updates
        animation_updates = []
        
        # Collect all animation frames first
        for row in range(1, self.rows + 1):
            ball_pos = ball_path[row] if row < len(ball_path) else final_slot
            
            frame_embed = self._create_plinko_embed(
                ctx.author.name,
                bet,
                current_balance,
                f"🔴 Ball at row {row}... bouncing through the pegs!",
                ball_position=ball_pos,
                current_row=row
            )
            animation_updates.append((frame_embed, 0.8))  # Slightly longer delay
        
        # Animate with rate-limit-friendly timing
        for i, (frame_embed, delay) in enumerate(animation_updates):
            await asyncio.sleep(delay)
            
            try:
                await message.edit(embed=frame_embed)
                
                # Add extra delay every 3 frames to avoid rate limits
                if (i + 1) % 3 == 0:
                    await asyncio.sleep(0.4)
                    
            except nextcord.NotFound:
                self.active_games.remove(ctx.author.id)
                return
            except nextcord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    # Wait and try again
                    await asyncio.sleep(1.0)
                    try:
                        await message.edit(embed=frame_embed)
                    except (nextcord.NotFound, nextcord.HTTPException):
                        # If still failing, skip this frame
                        continue
                else:
                    # Other HTTP error, skip frame
                    continue
        
        # Show final result
        await asyncio.sleep(1.2)
        
        # Update balance if won
        if winnings > 0:
            await db.update_wallet(ctx.author.id, winnings, ctx.guild.id)
            self.stats_logger.log_economy_transaction(ctx.author.id, "plinko", winnings, True)
        else:
            self.stats_logger.log_economy_transaction(ctx.author.id, "plinko", bet, False)
        
        # Determine result message and color
        if final_multiplier >= 5.0:
            result_msg = f"🎉 **AMAZING!** You hit {final_multiplier}x!"
            color = 0xFFD700  # Gold
        elif final_multiplier >= 2.0:
            result_msg = f"🎊 **NICE!** You hit {final_multiplier}x!"
            color = 0x2ecc71  # Green
        elif final_multiplier >= 1.0:
            result_msg = f"😊 You hit {final_multiplier}x - not bad!"
            color = 0x3498db  # Blue
        else:
            result_msg = f"😔 You hit {final_multiplier}x... better luck next time!"
            color = 0xe74c3c  # Red
        
        # Create final embed
        final_embed = nextcord.Embed(
            title="🎯 Plinko Results",
            description=result_msg,
            color=color
        )
        
        final_embed.add_field(
            name="Multiplier Hit",
            value=f"**{final_multiplier}x**",
            inline=True
        )
        
        final_embed.add_field(
            name="Winnings",
            value=f"**{winnings:,}** {self.currency}",
            inline=True
        )
        
        final_embed.add_field(
            name="New Balance",
            value=f"**{current_balance + winnings:,}** {self.currency}",
            inline=True
        )
        
        # Add plinko board showing final position
        board_display = self._create_board_display(final_slot, self.rows)
        final_embed.add_field(
            name="Final Board",
            value=f"```\n{board_display}\n```",
            inline=False
        )
        
        # Add multiplier display
        multiplier_display = self._create_multiplier_display(final_slot)
        final_embed.add_field(
            name="Multipliers",
            value=multiplier_display,
            inline=False
        )
        
        self.active_games.remove(ctx.author.id)
        await message.edit(embed=final_embed)
    
    def _calculate_ball_path(self) -> List[int]:
        """Calculate the path the ball takes through the plinko board"""
        position = 8  # Start at center (8 out of 0-15)
        path = [8]  # Starting position
        
        for row in range(self.rows):
            # Each peg has 50% chance to bounce left or right
            if random.random() < 0.5:
                position = max(0, position - 1)  # Bounce left
            else:
                position = min(15, position + 1)  # Bounce right
            
            path.append(position)
        
        return path
    
    def _create_plinko_embed(self, author: str, bet: int, balance: int, status: str, ball_position: int, current_row: int):
        """Create the plinko game embed with current ball position"""
        embed = nextcord.Embed(
            title=f"🎯 {author.capitalize()}'s Plinko Game",
            description=status,
            color=0x9b59b6
        )
        
        embed.add_field(
            name="Bet Amount",
            value=f"**{bet:,}** {self.currency}",
            inline=True
        )
        
        embed.add_field(
            name="Current Balance",
            value=f"**{balance:,}** {self.currency}",
            inline=True
        )
        
        embed.add_field(
            name="Row",
            value=f"**{current_row}/{self.rows}**",
            inline=True
        )
        
        # Add simplified board display
        board_display = self._create_board_display(ball_position, current_row)
        embed.add_field(
            name="Plinko Board",
            value=f"```\n{board_display}\n```",
            inline=False
        )
        
        # Add multiplier display
        multiplier_display = self._create_multiplier_display()
        embed.add_field(
            name="Multipliers (Left → Right)",
            value=multiplier_display,
            inline=False
        )
        
        return embed
    
    def _create_board_display(self, ball_position: int, current_row: int = None) -> str:
        """Create a visual representation of the plinko board"""
        board = []
        
        # Use consistent monospace characters for better Discord alignment
        # Each "slot" is 2 characters wide for better spacing
        
        # Top of board - ball starts here (centered at position 8)
        if current_row == 0:
            board.append("       🔴       ")  # Ball at center top
        else:
            board.append("       ○        ")  # Empty center top
        
        # Create peg rows with consistent spacing
        # Use a different approach - build each row as a fixed-width string
        for row in range(1, self.rows + 1):
            # Each row has (row + 1) pegs
            pegs_in_row = row + 1
            
            # Start with empty 16-character line
            line_chars = [' '] * 16
            
            # Calculate positions for pegs in this row
            # Distribute pegs evenly across the width
            if pegs_in_row > 1:
                step = 15 / (pegs_in_row - 1)  # Spread across positions 0-15
                peg_positions = [int(i * step) for i in range(pegs_in_row)]
            else:
                peg_positions = [7]  # Single peg in center
            
            # Place pegs at calculated positions
            for i, pos in enumerate(peg_positions):
                pos = max(0, min(15, pos))  # Clamp to valid range
                
                # Show ball if it's at this position and row
                if (current_row == row and pos == ball_position):
                    line_chars[pos] = '🔴'
                else:
                    line_chars[pos] = '●'
            
            board.append(''.join(line_chars))
        
        # Bottom slots - one character per slot position
        slots_line = ""
        for i in range(16):
            if ball_position == i and (current_row == self.rows or current_row is None):
                slots_line += "🔴"
            else:
                slots_line += "│"
        
        board.append(slots_line)
        
        return "\n".join(board)
    
    def _create_multiplier_display(self, highlight_slot: int = None) -> str:
        """Create the multiplier display at the bottom"""
        display = []
        
        for i, mult in enumerate(self.multipliers):
            if highlight_slot == i:
                if mult < 1.0:
                    display.append(f"**{mult}x**")  # Keep decimals for losing multipliers
                else:
                    display.append(f"**{mult:.0f}x**" if mult == int(mult) else f"**{mult}x**")
            else:
                if mult < 1.0:
                    display.append(f"{mult}x")  # Keep decimals for losing multipliers
                else:
                    display.append(f"{mult:.0f}x" if mult == int(mult) else f"{mult}x")
        
        # Use proper spacing for better alignment
        return " ".join(display)

async def setup(bot):
    bot.add_cog(Plinko(bot))
