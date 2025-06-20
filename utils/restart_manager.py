import nextcord
import asyncio

class RestartConfirmView(nextcord.ui.View):
    def __init__(self, utility_cog, ctx, timeout=60):
        super().__init__(timeout=timeout)
        self.utility_cog = utility_cog
        self.ctx = ctx
        
    async def interaction_check(self, interaction: nextcord.Interaction) -> bool:
        """Only the command author can use these buttons"""
        if interaction.user != self.ctx.author:
            await interaction.response.send_message(
                "❌ Only the command author can confirm this restart!", 
                ephemeral=True
            )
            return False
        return True
    
    @nextcord.ui.button(label="🔄 Force Restart", style=nextcord.ButtonStyle.danger)
    async def confirm_restart(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Confirm the force restart"""
        embed = nextcord.Embed(
            title="🔄 Force Restarting Bot",
            description="Restarting immediately...",
            color=nextcord.Color.red()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        await asyncio.sleep(2)
        await self.utility_cog._perform_restart()
    
    @nextcord.ui.button(label="❌ Cancel", style=nextcord.ButtonStyle.secondary)
    async def cancel_restart(self, interaction: nextcord.Interaction, button: nextcord.ui.Button):
        """Cancel the restart"""
        embed = nextcord.Embed(
            title="❌ Restart Cancelled",
            description="Force restart has been cancelled.",
            color=nextcord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        
    async def on_timeout(self):
        """Handle timeout"""
        embed = nextcord.Embed(
            title="⏰ Restart Timeout",
            description="Force restart confirmation timed out.",
            color=nextcord.Color.gray()
        )
        
        try:
            await self.ctx.edit_last_response(embed=embed, view=None)
        except:
            pass
