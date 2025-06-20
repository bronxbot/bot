"""
Main Economy Cog - Core economy commands and functionality
"""
import nextcord
from nextcord.ext import commands
import random
import json
from functools import wraps

from cogs.logging.logger import CogLogger
from cogs.logging.stats_logger import StatsLogger
from utils.db import db
from utils.amount_parser import parse_amount
from utils.safe_reply import safe_reply
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance

from .constants import CURRENCY, BLOCKED_CHANNELS, COOLDOWNS, COLORS
from .economy_utils import (
    get_user_economy_data, format_balance_embed, create_deposit_help_embed,
    create_withdraw_help_embed, validate_payment_amount, create_leaderboard_data,
    format_leaderboard_embed, process_vote_reward, calculate_interest,
    get_bank_upgrade_info, get_interest_upgrade_info
)
from .economy_views import PaymentConfirmView, LeaderboardPaginationView, InventoryPaginationView

# Load config from environment variables
import os
config_data = {
    'OWNER_IDS': os.getenv('DISCORD_BOT_OWNER_IDS', '').split(',') if os.getenv('DISCORD_BOT_OWNER_IDS') else [],
    'CLIENT_ID': os.getenv('DISCORD_CLIENT_ID', ''),
    'GUILD_COUNT': int(os.getenv('GUILD_COUNT', '0'))
}

def log_command(func):
    """Decorator to log command usage"""
    @wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        if hasattr(self, 'stats_logger'):
            self.stats_logger.log_command_usage(func.__name__)
        return await func(self, ctx, *args, **kwargs)
    return wrapper

class Economy(commands.Cog):
    """Core economy system with wallet, bank, and transfer functionality"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = CURRENCY
        self.active_games = set()
        self.stats_logger = StatsLogger()
        self.blocked_channels = BLOCKED_CHANNELS

    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        # Check if economy commands are disabled in this channel
        if ctx.channel.id in self.blocked_channels and not ctx.author.guild_permissions.administrator:
            await safe_reply(ctx,
                random.choice([
                    f"❌ Economy commands are disabled in this channel. Please use them in another channel.",
                    "<#1314685928614264852> is a good place for that."
                ])
            )
            return False
        
        # Check if user has accepted ToS
        if not await check_tos_acceptance(ctx.author.id):
            await prompt_tos_acceptance(ctx)
            return False
            
        return True

    @commands.command(aliases=['bal', 'cash', 'bb'])
    @log_command
    async def balance(self, ctx, member: nextcord.Member = None):
        """Check your or another user's balance"""
        member = member or ctx.author
        
        try:
            economy_data = await get_user_economy_data(member.id, ctx.guild.id)
            embed = format_balance_embed(member, economy_data, ctx.author if member != ctx.author else None)
            await safe_reply(ctx, embed=embed)
        except Exception as e:
            self.logger.error(f"Failed to show balance for {member.id}: {e}")
            await safe_reply(ctx, "An error occurred while displaying the balance.")

    @commands.command(name="deposit", aliases=["dep", 'd'])
    @commands.cooldown(1, COOLDOWNS["deposit"], commands.BucketType.user)
    @log_command
    async def deposit(self, ctx, amount: str = None):
        """Deposit money into your bank"""
        try:
            economy_data = await get_user_economy_data(ctx.author.id, ctx.guild.id)
            
            if not amount:
                if economy_data['bank_space'] <= 0:
                    return await safe_reply(ctx, "Your bank is **full**! Upgrade your bank *(`.bu`)* to deposit more.")
                
                embed = create_deposit_help_embed(economy_data['wallet'], economy_data['bank_space'])
                return await safe_reply(ctx, embed=embed)

            # Parse amount using the new unified parser
            parsed_amount, error = parse_amount(amount, economy_data['wallet'], max_amount=economy_data['bank_space'], context="wallet")
            
            if error:
                return await safe_reply(ctx, f"❌ {error}")

            if parsed_amount <= 0:
                return await safe_reply(ctx, "Amount must be positive!")
            if parsed_amount > economy_data['wallet']:
                return await safe_reply(ctx, "You don't have that much in your wallet!")
            if parsed_amount > economy_data['bank_space']:
                return await safe_reply(ctx, f"Your bank can only hold {economy_data['bank_space']:,} more coins!")

            # Process the deposit
            if await db.update_wallet(ctx.author.id, -parsed_amount, ctx.guild.id):
                if await db.update_bank(ctx.author.id, parsed_amount, ctx.guild.id):
                    await safe_reply(ctx, f"💰 Deposited **{parsed_amount:,}** {self.currency} into your bank!")
                else:
                    # Revert wallet change if bank update failed
                    await db.update_wallet(ctx.author.id, parsed_amount, ctx.guild.id)
                    await safe_reply(ctx, "❌ Failed to deposit money! Transaction reverted.")
            else:
                await safe_reply(ctx, "❌ Failed to deposit money!")
                
        except Exception as e:
            self.logger.error(f"Deposit error for user {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while processing your deposit.")

    @commands.command(name="withdraw", aliases=["with", 'w'])
    @commands.cooldown(1, COOLDOWNS["withdraw"], commands.BucketType.user)
    @log_command
    async def withdraw(self, ctx, amount: str = None):
        """Withdraw money from your bank"""
        try:
            economy_data = await get_user_economy_data(ctx.author.id, ctx.guild.id)
            
            if not amount:
                embed = create_withdraw_help_embed(economy_data['wallet'], economy_data['bank'])
                return await safe_reply(ctx, embed=embed)

            # Parse amount using the new unified parser
            parsed_amount, error = parse_amount(amount, economy_data['bank'], context="bank")
            
            if error:
                return await safe_reply(ctx, f"❌ {error}")

            if parsed_amount <= 0:
                return await safe_reply(ctx, "Amount must be positive!")
            if parsed_amount > economy_data['bank']:
                return await safe_reply(ctx, "You don't have that much in your bank!")

            # Process the withdrawal
            if await db.update_bank(ctx.author.id, -parsed_amount, ctx.guild.id):
                if await db.update_wallet(ctx.author.id, parsed_amount, ctx.guild.id):
                    await safe_reply(ctx, f"💰 Withdrew **{parsed_amount:,}** {self.currency} from your bank!")
                else:
                    # Revert bank change if wallet update failed
                    await db.update_bank(ctx.author.id, parsed_amount, ctx.guild.id)
                    await safe_reply(ctx, "❌ Failed to withdraw money! Transaction reverted.")
            else:
                await safe_reply(ctx, "❌ Failed to withdraw money!")
                
        except Exception as e:
            self.logger.error(f"Withdraw error for user {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while processing your withdrawal.")

    @commands.command(name="pay", aliases=["transfer"])
    @commands.cooldown(1, COOLDOWNS["pay"], commands.BucketType.user)
    @log_command
    async def pay(self, ctx, member: nextcord.Member, amount: str):
        """Pay another user with confirmation"""
        if member == ctx.author:
            return await safe_reply(ctx, "❌ You can't pay yourself!")
        if member.bot:
            return await safe_reply(ctx, "❌ You can't pay bots!")

        try:
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            parsed_amount, error = validate_payment_amount(amount, wallet)
            
            if error:
                return await safe_reply(ctx, f"❌ {error}")

            # Create payment confirmation view
            view = PaymentConfirmView(ctx.author, member, parsed_amount)
            
            embed = nextcord.Embed(
                title="💸 Payment Request",
                description=f"**{ctx.author.display_name}** wants to pay you **{parsed_amount:,}** {self.currency}",
                color=COLORS["info"]
            )
            embed.add_field(name="From:", value=ctx.author.display_name, inline=True)
            embed.add_field(name="To:", value=member.display_name, inline=True)
            embed.add_field(name="Amount:", value=f"{parsed_amount:,} {self.currency}", inline=True)
            embed.set_footer(text="This request will expire in 5 minutes")
            
            # Send to the receiver
            try:
                message = await member.send(embed=embed, view=view)
                view.message = message
                
                # Send confirmation to sender
                sender_embed = nextcord.Embed(
                    title="📨 Payment Request Sent",
                    description=f"Payment request of **{parsed_amount:,}** {self.currency} sent to {member.display_name}",
                    color=COLORS["success"]
                )
                await safe_reply(ctx, embed=sender_embed)
                
            except nextcord.Forbidden:
                # If DM fails, send in channel
                embed.set_footer(text=f"{member.display_name}, this payment request will expire in 5 minutes")
                message = await safe_reply(ctx, f"{member.mention}", embed=embed, view=view)
                view.message = message
                
        except Exception as e:
            self.logger.error(f"Pay error for {ctx.author.id} -> {member.id}: {e}")
            await safe_reply(ctx, "An error occurred while processing the payment.")

    @commands.command()
    @log_command
    async def daily(self, ctx):
        """Claim your daily reward"""
        amount = random.randint(1000, 5000)
        await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
        await safe_reply(ctx, f"Daily reward claimed! +**{amount:,}** {self.currency}")

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    @log_command
    async def beg(self, ctx):
        """Beg for money"""
        amount = random.randint(0, 150)
        await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
        await safe_reply(ctx, f"You got +**{amount:,}** {self.currency}")

    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.user)
    @log_command
    async def rob(self, ctx, victim: nextcord.Member):
        """Attempt to rob someone"""
        if victim == ctx.author:
            return await safe_reply(ctx, "You can't rob yourself!")
        if victim.bot:
            return await safe_reply(ctx, "You can't rob bots!")
        
        author_bal = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        victim_bal = await db.get_wallet_balance(victim.id, ctx.guild.id)
        
        if victim_bal < 100:
            return await safe_reply(ctx, "They're too poor to rob!")
        
        chance = random.random()
        if chance < 0.6:  # 60% chance to fail
            fine = int((random.random() * 0.3 + 0.1) * author_bal)
            await db.update_wallet(ctx.author.id, -fine, ctx.guild.id)
            await db.update_wallet(victim.id, fine, ctx.guild.id)
            return await safe_reply(ctx, f"You got caught and paid **{fine:,}** {self.currency} in fines!")
        
        stolen = int(victim_bal * random.uniform(0.1, 0.5))
        await db.update_wallet(victim.id, -stolen, ctx.guild.id)
        await db.update_wallet(ctx.author.id, stolen, ctx.guild.id)
        await safe_reply(ctx, f"You stole **{stolen:,}** {self.currency} from {victim.mention}!")

    @commands.command(aliases=['lb', 'glb'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    @log_command
    async def leaderboard(self, ctx, scope: str = "server"):
        """View the richest users"""
        try:
            if scope.lower() in ["global", "g", "world", "all"]:
                # Global leaderboard - get from all guilds
                leaderboard_data = await create_leaderboard_data(None, limit=100)  # None for global
            else:
                # Server leaderboard
                leaderboard_data = await create_leaderboard_data(ctx.guild.id, limit=100)
            
            if not leaderboard_data:
                scope_text = "global" if scope.lower() in ["global", "g", "world", "all"] else "server"
                embed = nextcord.Embed(
                    description=f"No {scope_text} economy data found.",
                    color=COLORS["neutral"]
                )
                return await safe_reply(ctx, embed=embed)
            
            embed = await format_leaderboard_embed(leaderboard_data, ctx.guild, page=1, bot=self.bot)
            view = LeaderboardPaginationView(ctx.guild, leaderboard_data, current_page=1)
            
            await safe_reply(ctx, embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Leaderboard error: {e}")
            await safe_reply(ctx, "❌ An error occurred while fetching the leaderboard")

    @commands.command(aliases=['hourly', 'getinterest'])
    @commands.cooldown(1, COOLDOWNS["interest"], commands.BucketType.user)
    @log_command
    async def collect_interest(self, ctx):
        """Collect hourly interest on your bank balance"""
        try:
            bank_balance = await db.get_bank_balance(ctx.author.id, ctx.guild.id)
            if bank_balance <= 0:
                return await safe_reply(ctx, "You need money in your bank to earn interest!")
            
            interest, rate = await calculate_interest(ctx.author.id, ctx.guild.id)
            
            if interest <= 0:
                return await safe_reply(ctx, "No interest earned!")
            
            # Add interest to bank
            await db.update_bank(ctx.author.id, interest, ctx.guild.id)
            
            embed = nextcord.Embed(
                title="💰 Interest Collected!",
                description=f"You earned **{interest:,}** {self.currency} in interest!",
                color=COLORS["success"]
            )
            embed.add_field(name="Interest Rate", value=f"{rate*100:.1f}% hourly", inline=True)
            embed.add_field(name="Bank Balance", value=f"{bank_balance:,} {self.currency}", inline=True)
            
            await safe_reply(ctx, embed=embed)
            
        except Exception as e:
            self.logger.error(f"Interest collection error for {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while collecting interest.")

    @commands.command(aliases=['interest', 'interestinfo'])
    @log_command
    async def interest_info(self, ctx):
        """Show information about interest rates and upgrades"""
        try:
            interest_level = await db.get_interest_level(ctx.author.id, ctx.guild.id)
            _, current_rate = await calculate_interest(ctx.author.id, ctx.guild.id)
            
            embed = nextcord.Embed(
                title="💹 Interest Information",
                color=COLORS["info"]
            )
            
            embed.add_field(
                name="Current Level",
                value=f"Level {interest_level}",
                inline=True
            )
            embed.add_field(
                name="Current Rate",
                value=f"{current_rate*100:.1f}% hourly",
                inline=True
            )
            
            # Show next upgrade info
            upgrade_info = get_interest_upgrade_info(interest_level)
            if upgrade_info:
                embed.add_field(
                    name=f"Next Upgrade (Level {upgrade_info['level']})",
                    value=f"Cost: {upgrade_info['cost']:,} {self.currency}\nRate: {upgrade_info['rate']*100:.1f}% hourly",
                    inline=False
                )
            else:
                embed.add_field(
                    name="Max Level Reached",
                    value="You have the highest interest rate!",
                    inline=False
                )
            
            await safe_reply(ctx, embed=embed)
            
        except Exception as e:
            self.logger.error(f"Interest info error for {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while fetching interest information.")

    @commands.command(aliases=['interestup', 'iup'])
    @log_command
    async def upgrade_interest(self, ctx):
        """Upgrade your interest rate"""
        try:
            current_level = await db.get_interest_level(ctx.author.id, ctx.guild.id)
            upgrade_info = get_interest_upgrade_info(current_level)
            
            if not upgrade_info:
                return await safe_reply(ctx, "You already have the maximum interest rate!")
            
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            cost = upgrade_info['cost']
            
            if wallet < cost:
                return await safe_reply(ctx, f"You need {cost:,} {self.currency} to upgrade! (You have {wallet:,})")
            
            # Process the upgrade
            if await db.update_wallet(ctx.author.id, -cost, ctx.guild.id):
                if await db.set_interest_level(ctx.author.id, ctx.guild.id, upgrade_info['level']):
                    embed = nextcord.Embed(
                        title="📈 Interest Rate Upgraded!",
                        description=f"Upgraded to Level {upgrade_info['level']}!",
                        color=COLORS["success"]
                    )
                    embed.add_field(
                        name="New Rate",
                        value=f"{upgrade_info['rate']*100:.1f}% hourly",
                        inline=True
                    )
                    embed.add_field(
                        name="Cost",
                        value=f"{cost:,} {self.currency}",
                        inline=True
                    )
                    await safe_reply(ctx, embed=embed)
                else:
                    # Revert wallet change
                    await db.update_wallet(ctx.author.id, cost, ctx.guild.id)
                    await safe_reply(ctx, "❌ Failed to upgrade interest rate! Payment refunded.")
            else:
                await safe_reply(ctx, "❌ Failed to process payment!")
                
        except Exception as e:
            self.logger.error(f"Interest upgrade error for {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while upgrading interest rate.")

    @commands.command(aliases=['bankup', 'bup'])
    @log_command
    async def upgrade_bank(self, ctx):
        """Upgrade your bank capacity"""
        try:
            current_level = await db.get_bank_level(ctx.author.id, ctx.guild.id)
            upgrade_info = get_bank_upgrade_info(current_level)
            
            if not upgrade_info:
                return await safe_reply(ctx, "You already have the maximum bank capacity!")
            
            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            cost = upgrade_info['cost']
            
            if wallet < cost:
                return await safe_reply(ctx, f"You need {cost:,} {self.currency} to upgrade! (You have {wallet:,})")
            
            # Process the upgrade
            if await db.update_wallet(ctx.author.id, -cost, ctx.guild.id):
                if await db.set_bank_level(ctx.author.id, ctx.guild.id, upgrade_info['level']):
                    embed = nextcord.Embed(
                        title="🏦 Bank Upgraded!",
                        description=f"Upgraded to Level {upgrade_info['level']}!",
                        color=COLORS["success"]
                    )
                    embed.add_field(
                        name="New Capacity",
                        value=f"{upgrade_info['limit']:,} {self.currency}",
                        inline=True
                    )
                    embed.add_field(
                        name="Cost",
                        value=f"{cost:,} {self.currency}",
                        inline=True
                    )
                    await safe_reply(ctx, embed=embed)
                else:
                    # Revert wallet change
                    await db.update_wallet(ctx.author.id, cost, ctx.guild.id)
                    await safe_reply(ctx, "❌ Failed to upgrade bank! Payment refunded.")
            else:
                await safe_reply(ctx, "❌ Failed to process payment!")
                
        except Exception as e:
            self.logger.error(f"Bank upgrade error for {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while upgrading bank.")

    @commands.command(aliases=['vote', 'votereward'])
    @commands.cooldown(1, COOLDOWNS["vote"], commands.BucketType.user)
    @log_command
    async def vote_reward(self, ctx):
        """Claim your voting reward"""
        try:
            reward_data = await process_vote_reward(ctx.author.id, ctx.guild.id)
            
            embed = nextcord.Embed(
                title="🗳️ Vote Reward Claimed!",
                description=f"Thank you for voting! You received **{reward_data['total_reward']:,}** {self.currency}!",
                color=COLORS["success"]
            )
            
            embed.add_field(
                name="Base Reward",
                value=f"{reward_data['base_reward']:,} {self.currency}",
                inline=True
            )
            embed.add_field(
                name="Streak Bonus",
                value=f"{reward_data['streak_bonus']:,} {self.currency}",
                inline=True
            )
            embed.add_field(
                name="Random Bonus",
                value=f"{reward_data['random_bonus']:,} {self.currency}",
                inline=True
            )
            embed.add_field(
                name="Vote Streak",
                value=f"{reward_data['streak']} days",
                inline=True
            )
            
            await safe_reply(ctx, embed=embed)
            
        except Exception as e:
            self.logger.error(f"Vote reward error for {ctx.author.id}: {e}")
            await safe_reply(ctx, "An error occurred while processing vote reward.")

    @commands.command(aliases=['inv', 'items', 'bag'])
    @log_command
    async def inventory(self, ctx, member: nextcord.Member = None):
        """View your or another user's inventory"""
        member = member or ctx.author
        
        try:
            inventory_data = await db.get_inventory(member.id) or []
            
            if not inventory_data:
                embed = nextcord.Embed(
                    title=f"🎒 {member.display_name}'s Inventory",
                    description="This inventory is empty!",
                    color=member.color
                )
                return await safe_reply(ctx, embed=embed)
            
            view = InventoryPaginationView(member, inventory_data, current_page=1)
            embed = view.create_inventory_embed()
            
            await safe_reply(ctx, embed=embed, view=view)
            
        except Exception as e:
            self.logger.error(f"Inventory error for {member.id}: {e}")
            await safe_reply(ctx, "An error occurred while fetching the inventory.")

async def setup(bot):
    bot.add_cog(Economy(bot))
