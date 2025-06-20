import nextcord
from nextcord.ext import commands
# from nextcord import app_commands  # Not available in nextcord
import asyncio
from typing import Optional

class TicTacToeButton(nextcord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=nextcord.ButtonStyle.secondary, label='\u200b', row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: nextcord.Interaction):
        view: TicTacToeView = self.view
        state = view.board[self.y][self.x]
        
        # Check if the button is already pressed or game is over
        if state in (view.X, view.O) or view.game_over:
            await interaction.response.send_message("This spot is already taken!", ephemeral=True)
            return
        
        # Check if it's the current player's turn
        if interaction.user != view.current_player:
            await interaction.response.send_message("It's not your turn!", ephemeral=True)
            return

        # Make the move
        if view.current_player == view.player1:
            self.style = nextcord.ButtonStyle.danger
            self.label = 'X'
            self.emoji = '❌'
            view.board[self.y][self.x] = view.X
            view.current_player = view.player2
        else:
            self.style = nextcord.ButtonStyle.primary
            self.label = 'O'
            self.emoji = '⭕'
            view.board[self.y][self.x] = view.O
            view.current_player = view.player1

        # Disable the button
        self.disabled = True
        
        # Check for winner
        winner = view.check_board_winner()
        if winner is not None:
            view.game_over = True
            if winner == view.X:
                content = f"🎉 {view.player1.mention} (X) wins!"
            elif winner == view.O:
                content = f"🎉 {view.player2.mention} (O) wins!"
            else:
                content = "🤝 It's a tie!"
            
            # Disable all buttons
            for item in view.children:
                item.disabled = True
            
            await interaction.response.edit_message(content=content, view=view)
        else:
            content = f"🎮 TicTacToe Game\n{view.current_player.mention}'s turn!"
            await interaction.response.edit_message(content=content, view=view)

class TicTacToeView(nextcord.ui.View):
    X = -1
    O = 1
    Tie = 2

    def __init__(self, player1: nextcord.Member, player2: nextcord.Member):
        super().__init__(timeout=300)
        self.player1 = player1
        self.player2 = player2
        self.current_player = player1
        self.game_over = False
        
        # Initialize empty board
        self.board = [
            [0, 0, 0],
            [0, 0, 0],
            [0, 0, 0],
        ]

        # Create 3x3 grid of buttons
        for x in range(3):
            for y in range(3):
                self.add_item(TicTacToeButton(x, y))

    def check_board_winner(self):
        # Check rows
        for across in self.board:
            value = sum(across)
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        # Check columns
        for line in range(3):
            value = self.board[0][line] + self.board[1][line] + self.board[2][line]
            if value == 3:
                return self.O
            elif value == -3:
                return self.X

        # Check diagonals
        diag = self.board[0][2] + self.board[1][1] + self.board[2][0]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        diag = self.board[0][0] + self.board[1][1] + self.board[2][2]
        if diag == 3:
            return self.O
        elif diag == -3:
            return self.X

        # Check if board is full (tie)
        if all(all(row) for row in self.board):
            return self.Tie

        return None

    async def on_timeout(self):
        # Disable all buttons when timeout occurs
        for item in self.children:
            item.disabled = True
        
        # Try to edit the message to show timeout
        try:
            await self.message.edit(content="⏰ Game timed out after 5 minutes!", view=self)
        except:
            pass

class TicTacToe(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @nextcord.slash_command(description="Start a TicTacToe game with another player")
    async def tictactoe(self, interaction: nextcord.Interaction, opponent: nextcord.Member):
        # Validation checks
        if opponent == interaction.user:
            await interaction.response.send_message("❌ You can't play against yourself!", ephemeral=True)
            return
        
        if opponent.bot:
            await interaction.response.send_message("❌ You can't play against a bot!", ephemeral=True)
            return

        # Create the game view
        view = TicTacToeView(interaction.user, opponent)
        
        content = (f"🎮 **TicTacToe Game Started!**\n"
                  f"{interaction.user.mention} (❌) vs {opponent.mention} (⭕)\n"
                  f"{interaction.user.mention}'s turn!")
        
        await interaction.response.send_message(content=content, view=view)
        
        # Store the message for timeout handling
        view.message = await interaction.original_response()

    @tictactoe.error
    async def tictactoe_error(self, interaction: nextcord.Interaction, error):
        if hasattr(error, 'code') and error.code == 50013:  # Missing permissions
            await interaction.response.send_message("❌ You don't have permission to use this command!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ An error occurred while starting the game!", ephemeral=True)

async def setup(bot):
    bot.add_cog(TicTacToe(bot))