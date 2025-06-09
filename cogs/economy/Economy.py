from discord.ext import commands
from cogs.logging.logger import CogLogger
from utils.db import async_db as db
from utils.betting import parse_bet
import discord
import random
import json
import asyncio
import datetime
from functools import wraps
from discord.ext import commands
from cogs.logging.stats_logger import StatsLogger

with open('data/config.json', 'r') as f:
    data = json.load(f)

def log_command(func):
    """Decorator to log command usage"""
    @wraps(func)
    async def wrapper(self, ctx, *args, **kwargs):
        if hasattr(self, 'stats_logger'):
            self.stats_logger.log_command_usage(func.__name__)
        return await func(self, ctx, *args, **kwargs)
    return wrapper

def logged_command(*args, **kwargs):
    """Custom command decorator that adds logging"""
    def decorator(func):
        # First apply the command decorator
        cmd = logged_command(*args, **kwargs)(func)
        # Then apply the logging decorator
        return log_command(cmd)
    return decorator

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.currency = "<:bronkbuk:1377389238290747582>"
        self.active_games = set()
        self.stats_logger = StatsLogger()
        self.blocked_channels = [1378156495144751147, 1260347806699491418]
    
    # piece de resistance: cog_check
    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        if ctx.channel.id in self.blocked_channels and not ctx.author.guild_permissions.administrator:
            await ctx.reply(
                random.choice([f"❌ Economy commands are disabled in this channel. "
                f"Please use them in another channel.",
                "<#1314685928614264852> is a good place for that."])
            )
            return False
        return True
    
    @commands.command(aliases=['bal', 'cash', 'bb'])
    async def balance(self, ctx, member: discord.Member = None):
        """Check your balance"""
        member = member or ctx.author
        wallet = await db.get_wallet_balance(member.id, ctx.guild.id)
        bank = await db.get_bank_balance(member.id, ctx.guild.id)
        bank_limit = await db.get_bank_limit(member.id, ctx.guild.id)
        
        badge = await db.get_badge(member.id, ctx.guild.id)
        embed = discord.Embed(
            description=(
                f"💵 Wallet: **{wallet:,}** {self.currency}\n"
                f"🏦 Bank: **{bank:,}**/**{bank_limit:,}** {self.currency}\n"
                f"💰 Net Worth: **{wallet + bank:,}** {self.currency}"
            ),
            color=member.color
        )
        if badge:
            embed.title = f"{badge} | {member.display_name}'s Balance"
        else:
            embed.set_author(name=f"{member.display_name}'s Balance", icon_url=member.display_avatar.url)
        if member != ctx.author:
            embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        try:
            await ctx.reply(embed=embed)
        except discord.HTTPException:
            await ctx.send(embed=embed)
        except discord.Forbidden:
            self.logger.error(f"Failed to send balance embed in {ctx.channel.name}. User: {ctx.author.id}, Member: {member.id}")
            await ctx.send("I can't send embeds in this channel. Please check my permissions.")

    @commands.command(name="deposit", aliases=["dep", 'd'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def deposit(self, ctx, amount: str = None):
        """Deposit money into your bank"""
        try:
            if not amount:
                wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
                bank = await db.get_bank_balance(ctx.author.id, ctx.guild.id)
                limit = await db.get_bank_limit(ctx.author.id, ctx.guild.id)
                space = limit - bank
                if space <= 0:
                    return await ctx.reply("Your bank is **full**! Upgrade your bank *(`.bu`)* to deposit more.")
                
                embed = discord.Embed(
                    description=(
                        "**BronkBuks Bank Deposit Guide**\n\n"
                        f"Your Wallet: **{wallet:,}** {self.currency}\n"
                        f"Bank Space: **{space:,}** {self.currency}\n\n"
                        "**Usage:**\n"
                        "`.deposit <amount>`\n"
                        "`.deposit 50%` - Deposit 50% of wallet\n"
                        "`.deposit all` - Deposit maximum amount\n"
                        "`.deposit 1k` - Deposit 1,000\n"
                        "`.deposit 1.5m` - Deposit 1,500,000"
                    ),
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)

            wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
            bank = await db.get_bank_balance(ctx.author.id, ctx.guild.id)
            limit = await db.get_bank_limit(ctx.author.id, ctx.guild.id)
            space = limit - bank

            # Parse amount
            if amount.lower() in ['all', 'max']:
                amount = min(wallet, space)
            elif amount.endswith('%'):
                try:
                    percentage = float(amount[:-1])
                    if not 0 < percentage <= 100:
                        return await ctx.reply("Percentage must be between 0 and 100!")
                    amount = min(int((percentage / 100) * wallet), space)
                except ValueError:
                    return await ctx.reply("Invalid percentage!")
            else:
                try:
                    if amount.lower().endswith('k'):
                        amount = int(float(amount[:-1]) * 1000)
                    elif amount.lower().endswith('m'):
                        amount = int(float(amount[:-1]) * 1000000)
                    else:
                        amount = int(amount)
                except ValueError:
                    return await ctx.reply("Invalid amount!")

            if amount <= 0:
                return await ctx.reply("Amount must be positive!")
            if amount > wallet:
                return await ctx.reply("You don't have that much in your wallet!")
            if amount > space:
                return await ctx.reply(f"Your bank can only hold {space:,} more coins!")

            if await db.update_wallet(ctx.author.id, -amount, ctx.guild.id):
                if await db.update_bank(ctx.author.id, amount, ctx.guild.id):
                    # Log successful deposit
                    self.stats_logger.log_command_usage("deposit")
                    await ctx.reply(f"💰 Deposited **{amount:,}** {self.currency} into your bank!")
                else:
                    await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
                    await ctx.reply("❌ Failed to deposit money! Transaction reverted.")
            else:
                await ctx.reply("❌ Failed to deposit money!")
                
        except Exception as e:
            self.logger.error(f"Deposit error: {e}")
            await ctx.reply("An error occurred while processing your deposit.")

    @commands.command(name="withdraw", aliases=["with", 'w'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def withdraw(self, ctx, amount: str = None):
        """Withdraw money from your bank"""
        try:
            if not amount:
                wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
                bank = await db.get_bank_balance(ctx.author.id, ctx.guild.id)
                
                embed = discord.Embed(
                    description=(
                        "**BronkBuks Bank Withdrawal Guide**\n\n"
                        f"Your Bank: **{bank:,}** {self.currency}\n"
                        f"Your Wallet: **{wallet:,}** {self.currency}\n\n"
                        "**Usage:**\n"
                        "`.withdraw <amount>`\n"
                        "`.withdraw 50%` - Withdraw 50% of bank\n"
                        "`.withdraw all` - Withdraw everything\n"
                        "`.withdraw 1k` - Withdraw 1,000\n"
                        "`.withdraw 1.5m` - Withdraw 1,500,000"
                    ),
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)

            bank = await db.get_bank_balance(ctx.author.id, ctx.guild.id)

            # Parse amount
            if amount.lower() in ['all', 'max']:
                amount = bank
            elif amount.endswith('%'):
                try:
                    percentage = float(amount[:-1])
                    if not 0 < percentage <= 100:
                        return await ctx.reply("Percentage must be between 0 and 100!")
                    amount = int((percentage / 100) * bank)
                except ValueError:
                    return await ctx.reply("Invalid percentage!")
            else:
                try:
                    if amount.lower().endswith('k'):
                        amount = int(float(amount[:-1]) * 1000)
                    elif amount.lower().endswith('m'):
                        amount = int(float(amount[:-1]) * 1000000)
                    else:
                        amount = int(amount)
                except ValueError:
                    return await ctx.reply("Invalid amount!")

            if amount <= 0:
                return await ctx.reply("Amount must be positive!")
            if amount > bank:
                return await ctx.reply("You don't have that much in your bank!")

            if await db.update_bank(ctx.author.id, -amount, ctx.guild.id):
                if await db.update_wallet(ctx.author.id, amount, ctx.guild.id):
                    await ctx.reply(f"💸 Withdrew **{amount:,}** {self.currency} from your bank!")
                else:
                    await db.update_bank(ctx.author.id, amount, ctx.guild.id)
                    await ctx.reply("❌ Failed to withdraw money! Transaction reverted.")
            else:
                await ctx.reply("❌ Failed to withdraw money!")
        except Exception as e:
            self.logger.error(f"Withdraw error: {e}")
            await ctx.reply("An error occurred while processing your withdrawal.")

    @commands.command(name="pay", aliases=["transfer", 'p'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def pay(self, ctx, member: discord.Member, amount: int):
        """Transfer money to another user"""
        if amount <= 0:
            return await ctx.reply("Amount must be positive!")
        
        if member == ctx.author:
            return await ctx.reply("You can't pay yourself!")
        
        if await db.transfer_money(ctx.author.id, member.id, amount, ctx.guild.id):
            await ctx.reply(f"Transferred **{amount}** {self.currency} to {member.mention}")
        else:
            await ctx.reply("Insufficient funds!")

    @commands.command()
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        """Claim your daily reward"""
        amount = random.randint(1000, 5000)
        await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
        await ctx.reply(f"Daily reward claimed! +**{amount}** {self.currency}")

    @commands.command()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def beg(self, ctx):
        """Beg for money"""
        amount = random.randint(0, 150)
        await db.update_wallet(ctx.author.id, amount, ctx.guild.id)
        await ctx.reply(f"you got +**{amount}** {self.currency}")

    @commands.command()
    @commands.cooldown(1, 300, commands.BucketType.user)
    async def rob(self, ctx, victim: discord.Member):
        """Attempt to rob someone"""
        if victim == ctx.author:
            return await ctx.reply("You can't rob yourself!")
        
        author_bal = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        victim_bal = await db.get_wallet_balance(victim.id, ctx.guild.id)
        if victim_bal < 100:
            return await ctx.reply("They're too poor to rob!")
        
        chance = random.random()
        if chance < 0.6:  # 60% chance to fail
            fine = int((random.random() * 0.3 + 0.1) * author_bal)

            await db.update_wallet(ctx.author.id, -fine, ctx.guild.id)
            await db.update_wallet(victim.id, fine, ctx.guild.id)
            return await ctx.reply(f"You got caught and paid **{fine}** {self.currency} in fines!")
        
        stolen = int(victim_bal * random.uniform(0.1, 0.5))
        await db.update_wallet(victim.id, -stolen, ctx.guild.id)
        await db.update_wallet(ctx.author.id, stolen, ctx.guild.id)
        await ctx.reply(f"You stole **{stolen}** {self.currency} from {victim.mention}!")

    @commands.command(aliases=['lb', 'glb'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def leaderboard(self, ctx, scope: str = "server"):
        """View the richest users"""
        if scope.lower() in ["global", "g", "world", "all"]:
            return await self._show_global_leaderboard(ctx)
        else:
            return await self._show_server_leaderboard(ctx)

    async def _show_server_leaderboard(self, ctx):
        """Show server-specific leaderboard"""
        try:
            if not await db.ensure_connected():
                return await ctx.reply(embed=discord.Embed(
                    description="❌ Database connection failed", 
                    color=0xff0000
                ))

            member_ids = [str(member.id) for member in ctx.guild.members if not member.bot]
            
            if not member_ids:
                return await ctx.reply(embed=discord.Embed(
                    description="No users found in this server",
                    color=0x2b2d31
                ))

            cursor = db.db.users.find({
                "_id": {"$in": member_ids},
                "$or": [
                    {"wallet": {"$gt": 0}},
                    {"bank": {"$gt": 0}}
                ]
            })

            users = []
            async for user_doc in cursor:
                member = ctx.guild.get_member(int(user_doc["_id"]))
                if member:
                    total = user_doc.get("wallet", 0) + user_doc.get("bank", 0)
                    users.append({
                        "member": member,
                        "total": round(total)
                    })

            if not users:
                embed = discord.Embed(
                    description="No economy data for this server.", 
                    color=0x2b2d31
                )
                return await ctx.reply(embed=embed)
            
            users.sort(key=lambda x: x["total"], reverse=True)
            users = users[:10]
            
            content = []
            total_wealth = sum(user["total"] for user in users)
            position_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            
            for i, user in enumerate(users, 1):
                total = user["total"]
                formatted_amount = "{:,}".format(total)
                position = position_emojis.get(i, f"`{i}.`")
                
                # Add percentage for top 3
                percentage_text = ""
                if i <= 3 and total_wealth > 0:
                    percentage = (total / total_wealth) * 100
                    percentage_text = f" ***({percentage:.1f}%)***"
                
                content.append(f"{position} {user['member'].display_name} • **{formatted_amount}** {self.currency} {percentage_text}")
            
            embed = discord.Embed(
                title=f"💰 Richest Users in {ctx.guild.name}",
                description="\n".join(content),
                color=0x2b2d31
            )
            
            formatted_total = "{:,}".format(total_wealth)
            average_wealth = "{:,}".format(total_wealth // len(content)) if content else "0"
            embed.set_footer(text=f"Total Wealth: ${formatted_total} $BB • Average: ${average_wealth} $BB")
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Leaderboard error: {e}")
            return await ctx.reply(embed=discord.Embed(
                description="❌ An error occurred while fetching the leaderboard", 
                color=0xff0000
            ))

    async def _show_global_leaderboard(self, ctx):
        """Show global leaderboard"""
        try:
            if not await db.ensure_connected():
                return await ctx.reply(embed=discord.Embed(
                    description="❌ Database connection failed", 
                    color=0xff0000
                ))
            
            pipeline = [
                {
                    "$group": {
                        "_id": "$_id",
                        "total": {"$sum": {"$add": ["$wallet", "$bank"]}}
                    }
                },
                {"$sort": {"total": -1}},
                {"$limit": 10}
            ]
            
            users = await db.db.users.aggregate(pipeline).to_list(10)
            
            if not users:
                return await ctx.reply(embed=discord.Embed(
                    description="No global economy data found", 
                    color=0x2b2d31
                ))
            
            content = []
            total_wealth = sum(user['total'] for user in users)
            position_emojis = {1: "🥇", 2: "🥈", 3: "🥉"}
            
            for i, user in enumerate(users, 1):
                user_id = int(user['_id'])
                total = user['total']
                
                member = ctx.guild.get_member(user_id) or self.bot.get_user(user_id)
                
                if member:
                    position = position_emojis.get(i, f"`{i}.`")
                    display_name = getattr(member, 'display_name', member.name)
                    
                    # Add percentage for top 3
                    percentage_text = ""
                    if i <= 3 and total_wealth > 0:
                        percentage = (total / total_wealth) * 100
                        percentage_text = f" **({percentage:.1f}%)**"
                    
                    content.append(f"{position} {display_name} • **{total:,}**{percentage_text} {self.currency}")
            
            if not content:
                return await ctx.reply(embed=discord.Embed(
                    description="No active users found", 
                    color=0x2b2d31
                ))
            
            embed = discord.Embed(
                title="🌎 Global Economy Leaderboard",
                description="\n".join(content),
                color=0x2b2d31
            )
            
            formatted_total = "{:,}".format(total_wealth)
            average_wealth = "{:,}".format(total_wealth // len(content)) if content else "0"
            embed.set_footer(text=f"Total Wealth: ${formatted_total} • Average: ${average_wealth}")
            
            await ctx.reply(embed=embed)
            
        except Exception as e:
            self.logger.error(f"Global leaderboard error: {e}")
            return await ctx.reply(embed=discord.Embed(
                description="❌ An error occurred while fetching the global leaderboard", 
                color=0xff0000
            ))

    async def calculate_daily_interest(self, user_id: int, guild_id: int = None) -> float:
        """Calculate and apply daily interest"""
        wallet = await db.get_wallet_balance(user_id, guild_id)
        interest_level = await db.get_interest_level(user_id)

        base_rate = 0.0003  # Base rate of 0.03%
        level_bonus = interest_level * 0.0005  # Each level adds 0.05% (0.0005)
        random_bonus = random.randint(0, 100) / 100000  # 0-0.1% random bonus
        total_rate = base_rate + level_bonus + random_bonus
        
        # Calculate interest based on wallet + bank balance
        bank = await db.get_bank_balance(user_id, guild_id)
        total_balance = wallet + bank
        interest = total_balance * total_rate
        
        # Apply minimum (1 coin) and maximum (1% of total balance) bounds
        interest = max(1, min(interest, total_balance * 0.01))
        
        # Apply the interest to wallet
        if await db.update_wallet(user_id, int(interest), guild_id):
            return interest
        return 0


    @commands.command(aliases=['interest', 'i'])
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def claim_interest(self, ctx):
        """Claim your daily interest"""
        interest = await self.calculate_daily_interest(ctx.author.id, ctx.guild.id)
        if interest > 0:
            await ctx.reply(f"💰 You earned **{interest:,}** {self.currency} in daily interest!")
        else:
            await ctx.reply("❌ Failed to claim interest. Try again later.")

    
    @commands.command(aliases=['interest_info', 'ii'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def interest_status(self, ctx):
        """Check your current interest rate and level"""
        wallet = await db.get_wallet_balance(ctx.author.id, ctx.guild.id)
        bank = await db.get_bank_balance(ctx.author.id, ctx.guild.id)
        total_balance = wallet + bank
        level = await db.get_interest_level(ctx.author.id)
        
        # Calculate current rate in percentage
        current_rate_percent = (0.03 + (level * 0.05))  # 0.03% base + 0.05% per level
        next_rate_percent = (0.03 + ((level + 1) * 0.05)) if level < 60 else current_rate_percent
        
        # Calculate estimated earnings (without random bonus for display)
        estimated_interest = total_balance * (current_rate_percent / 100)
        estimated_interest = max(1, min(estimated_interest, total_balance * 0.01))
        
        embed = discord.Embed(
            title="Interest Account Status",
            description=(
                f"**Current Level:** {level}/60\n"
                f"**Daily Interest Rate:** {current_rate_percent:.2f}%\n"
                f"**Wallet Balance:** {wallet:,} {self.currency}\n"
                f"**Bank Balance:** {bank:,} {self.currency}\n"
                f"**Estimated Daily Earnings:** {int(estimated_interest):,} {self.currency}\n"
                f"**Next Level Rate:** {next_rate_percent:.2f}%\n"
                f"*Actual earnings may vary slightly due to random bonus*"
            ),
            color=discord.Color.blue()
        )
        
        if level < 60:
            base_cost = 1000
            cost = base_cost * (level + 1)
            embed.add_field(
                name="Next Upgrade",
                value=f"Cost: **{cost:,}** {self.currency}\n" + 
                    ("*Requires Interest Token*" if level >= 20 else ""),
                inline=False
            )
        
        await ctx.reply(embed=embed)

    @commands.command(aliases=['upgrade_interest', 'iu'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def interest_upgrade(self, ctx):
        """Upgrade your daily interest rate"""
        
        async def create_upgrade_embed(user_id):
            current_level = await db.get_interest_level(user_id)
            if current_level >= 60:
                embed = discord.Embed(
                    title="Interest Rate Upgrade",
                    description="You've reached the maximum interest level!",
                    color=discord.Color.gold()
                )
                return embed, None, True
            
            base_cost = 1000
            cost = base_cost * (current_level + 1)
            item_required = current_level >= 20
            
            # Display rates in percentage form
            current_rate = 0.003 + (current_level * 0.05)
            next_rate = 0.003 + ((current_level + 1) * 0.05)
            
            embed = discord.Embed(
                title="Interest Rate Upgrade",
                description=(
                    f"Current interest level: **{current_level}**\n"
                    f"Next level cost: **{cost:,}** {self.currency}\n"
                    f"Item required: {'Yes' if item_required else 'No'}\n\n"
                    f"Your current daily interest rate: **{current_rate:.3f}%**\n"
                    f"Next level rate: **{next_rate:.3f}%**"
                ),
                color=discord.Color.green()
            )
            
            if item_required:
                embed.add_field(
                    name="Special Item Required",
                    value="You need an **Interest Token** to upgrade beyond level 20!",
                    inline=False
                )
            
            view = discord.ui.View()
            confirm_button = discord.ui.Button(label="Upgrade", style=discord.ButtonStyle.green)
            
            async def confirm_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("This isn't your upgrade!", ephemeral=True)
                
                fresh_level = await db.get_interest_level(ctx.author.id)
                fresh_cost = base_cost * (fresh_level + 1)
                fresh_item_required = fresh_level >= 20
                
                success, message = await db.upgrade_interest(ctx.author.id, fresh_cost, fresh_item_required)
                
                if success:
                    new_embed, new_view, max_reached = await create_upgrade_embed(ctx.author.id)
                    if max_reached:
                        await interaction.response.edit_message(embed=new_embed, view=None)
                    else:
                        await interaction.response.edit_message(embed=new_embed, view=new_view)
                else:
                    error_embed = discord.Embed(
                        description=f"❌ {message}",
                        color=discord.Color.red()
                    )
                    await interaction.response.edit_message(embed=error_embed, view=None)
                    await asyncio.sleep(3)
                    original_embed, original_view, _ = await create_upgrade_embed(ctx.author.id)
                    await interaction.edit_original_response(embed=original_embed, view=original_view)
            
            confirm_button.callback = confirm_callback
            view.add_item(confirm_button)
            
            cancel_button = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.red)
            
            async def cancel_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("This isn't your upgrade!", ephemeral=True)
                await interaction.response.edit_message(content="Upgrade cancelled.", embed=None, view=None)
            
            cancel_button.callback = cancel_callback
            view.add_item(cancel_button)
            
            return embed, view, False
        
        embed, view, max_reached = await create_upgrade_embed(ctx.author.id)
        await ctx.reply(embed=embed, view=view if not max_reached else None)

    @commands.command(aliases=['upgrade_bank', 'bu'])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def bankupgrade(self, ctx):
        """Upgrade your bank capacity (price scales with current limit)"""
        
        async def create_upgrade_embed(user_id, guild_id):
            # Get current bank stats
            current_limit = await db.get_bank_limit(user_id, guild_id)
            current_balance = await db.get_bank_balance(user_id, guild_id)
            
            # Dynamic pricing formula (example: 10% of current limit + base 1000)
            base_cost = 1000
            upgrade_cost = int(current_limit * 0.1) + base_cost
            new_limit = current_limit + 5000  # Fixed increase per upgrade
            
            # Check if user can afford it
            can_afford = current_balance >= upgrade_cost
            
            # Create embed
            embed = discord.Embed(
                title="🏦 Bank Upgrade",
                color=0x2ecc71 if can_afford else 0xe74c3c,
                description=(
                    f"Current Bank Limit: **{current_limit:,}** {self.currency}\n"
                    f"Current Bank Balance: **{current_balance:,}** {self.currency}\n\n"
                    f"Upgrade Cost: **{upgrade_cost:,}** {self.currency}\n"
                    f"New Limit: **{new_limit:,}** {self.currency}\n"
                    f"*Money will be taken directly from your bank*"
                )
            )
            
            if not can_afford:
                embed.add_field(
                    name="Insufficient Funds",
                    value=f"You need **{upgrade_cost - current_balance:,}** more {self.currency} in your bank to upgrade!",
                    inline=False
                )
            
            # Create view with buttons
            view = discord.ui.View()
            
            if can_afford:
                confirm_button = discord.ui.Button(label="Upgrade", style=discord.ButtonStyle.green)
                
                async def confirm_callback(interaction):
                    if interaction.user != ctx.author:
                        return await interaction.response.send_message("This isn't your upgrade!", ephemeral=True)
                    
                    # Verify balance again in case it changed
                    fresh_balance = await db.get_bank_balance(user_id, guild_id)
                    fresh_limit = await db.get_bank_limit(user_id, guild_id)
                    fresh_cost = int(fresh_limit * 0.1) + base_cost
                    
                    if fresh_balance < fresh_cost:
                        error_embed = discord.Embed(
                            description="❌ Your bank balance changed and you can no longer afford this upgrade!",
                            color=discord.Color.red()
                        )
                        return await interaction.response.edit_message(embed=error_embed, view=None)
                    
                    # Process the upgrade
                    await db.update_bank(user_id, -fresh_cost, guild_id)
                    await db.update_bank_limit(user_id, 5000, guild_id)  # Increase by 5000
                    
                    # Show new upgrade options
                    new_embed, new_view = await create_upgrade_embed(user_id, guild_id)
                    await interaction.response.edit_message(embed=new_embed, view=new_view)
                
                confirm_button.callback = confirm_callback
                view.add_item(confirm_button)
            
            cancel_button = discord.ui.Button(label="Close", style=discord.ButtonStyle.red)
            
            async def cancel_callback(interaction):
                if interaction.user != ctx.author:
                    return await interaction.response.send_message("This isn't your upgrade!", ephemeral=True)
                await interaction.response.edit_message(content="Bank upgrade closed.", embed=None, view=None)
            
            cancel_button.callback = cancel_callback
            view.add_item(cancel_button)
            
            return embed, view
        
        embed, view = await create_upgrade_embed(ctx.author.id, ctx.guild.id)
        await ctx.reply(embed=embed, view=view)

    @commands.command()
    async def voteinfo(self, ctx):
        """Get information about voting rewards"""
        embed = discord.Embed(
            title="Vote Rewards",
            description=(
                f"Vote for our bot on Top.gg every 12 hours to receive rewards!\n\n"
                f"**Reward:** 1,000 {self.currency}\n"
                f"[**Vote Here**](https://top.gg/bot/{self.bot.user.id}/vote)\n\n"
                f"Use `{ctx.prefix}checkvote` to see if you can claim your reward!"
            ),
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(aliases=['vote', 'votereward'])
    async def checkvote(self, ctx):
        """Check if you've voted and claim your reward"""
        if not data['top_gg']:
            return await ctx.send("Vote rewards are currently disabled in this server.")
        # Check if user has voted in the last 12 hours
        headers = {
            "Authorization": data['top_ggtoken']
        }
        
        try:
            async with self.bot.session.get(
                f"https://top.gg/api/bots/{self.bot.user.id}/check",
                params={"userId": ctx.author.id},
                headers=headers
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get('voted', 0) == 1:
                        # Check if they've already claimed today
                        last_vote = await db.db.users.find_one({
                            "_id": str(ctx.author.id),
                            "last_vote_reward": {"$gte": datetime.datetime.now() - datetime.timedelta(hours=12)}
                        })
                        
                        if last_vote:
                            return await ctx.send("You've already claimed your vote reward in the last 12 hours!")
                        
                        # Give reward
                        reward_amount = 1000
                        await db.update_wallet(ctx.author.id, reward_amount, ctx.guild.id)
                        await db.db.users.update_one(
                            {"_id": str(ctx.author.id)},
                            {"$set": {"last_vote_reward": datetime.datetime.now()}},
                            upsert=True
                        )
                        
                        return await ctx.send(f"Thanks for voting! You've received {reward_amount} {self.currency}!")
                    else:
                        return await ctx.send(f"You haven't voted yet! Vote here: https://top.gg/bot/{self.bot.user.id}/vote")
                else:
                    return await ctx.send("Couldn't check your vote status. Please try again later.")
        except Exception as e:
            self.logger.error(f"Vote check error: {e}")
            return await ctx.send("An error occurred while checking your vote status.")

async def setup(bot):
    await bot.add_cog(Economy(bot))
