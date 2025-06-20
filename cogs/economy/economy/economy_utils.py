"""
Economy utility functions and helpers
"""
import nextcord
import asyncio
from typing import Optional, Tuple, Dict, Any
from utils.db import db
from utils.amount_parser import parse_amount
from .constants import CURRENCY, BANK_UPGRADE_LEVELS, INTEREST_UPGRADE_LEVELS, VOTE_REWARDS

async def get_user_economy_data(user_id: int, guild_id: int) -> Dict[str, Any]:
    """Get comprehensive economy data for a user"""
    wallet = await db.get_wallet_balance(user_id, guild_id)
    bank = await db.get_bank_balance(user_id, guild_id)
    bank_limit = await db.get_bank_limit(user_id, guild_id)
    badge = await db.get_badge(user_id, guild_id)
    
    return {
        "wallet": wallet,
        "bank": bank,
        "bank_limit": bank_limit,
        "bank_space": bank_limit - bank,
        "net_worth": wallet + bank,
        "badge": badge
    }

async def transfer_money_safely(sender_id: int, receiver_id: int, amount: int, guild_id: int) -> bool:
    """Safely transfer money between users with validation"""
    try:
        sender_wallet = await db.get_wallet_balance(sender_id, guild_id)
        if sender_wallet < amount:
            return False
        
        return await db.transfer_money(sender_id, receiver_id, amount, guild_id)
    except Exception:
        return False

def format_currency(amount: int) -> str:
    """Format currency amount with proper formatting"""
    return f"{amount:,} {CURRENCY}"

def format_balance_embed(user: nextcord.Member, economy_data: Dict[str, Any], requester: Optional[nextcord.Member] = None) -> nextcord.Embed:
    """Create a formatted balance embed"""
    embed = nextcord.Embed(
        description=(
            f"💵 Wallet: **{economy_data['wallet']:,}** {CURRENCY}\n"
            f"🏦 Bank: **{economy_data['bank']:,}**/**{economy_data['bank_limit']:,}** {CURRENCY}\n"
            f"💰 Net Worth: **{economy_data['net_worth']:,}** {CURRENCY}"
        ),
        color=user.color
    )
    
    if economy_data['badge']:
        embed.title = f"{economy_data['badge']} | {user.display_name}'s Balance"
    else:
        embed.set_author(name=f"{user.display_name}'s Balance", icon_url=user.display_avatar.url)
    
    if requester and requester != user:
        embed.set_footer(text=f"Requested by {requester.display_name}", icon_url=requester.display_avatar.url)
    
    return embed

def get_bank_upgrade_info(current_level: int) -> Optional[Dict[str, Any]]:
    """Get information about the next bank upgrade"""
    next_level = current_level + 1
    if next_level in BANK_UPGRADE_LEVELS:
        return {
            "level": next_level,
            "cost": BANK_UPGRADE_LEVELS[next_level]["cost"],
            "limit": BANK_UPGRADE_LEVELS[next_level]["limit"],
            "current_limit": BANK_UPGRADE_LEVELS.get(current_level, {"limit": 5000})["limit"]
        }
    return None

def get_interest_upgrade_info(current_level: int) -> Optional[Dict[str, Any]]:
    """Get information about the next interest upgrade"""
    next_level = current_level + 1
    
    if next_level in INTEREST_UPGRADE_LEVELS:
        return {
            "level": next_level,
            "cost": INTEREST_UPGRADE_LEVELS[next_level]["cost"],
            "rate": INTEREST_UPGRADE_LEVELS[next_level]["rate"],
            "current_rate": INTEREST_UPGRADE_LEVELS.get(current_level, {"rate": 0.01})["rate"]
        }
    elif next_level > 20:
        # For levels above 20, extrapolate costs and rates
        # Level 20 is 11.5% rate and 50,000,000,000 cost
        # Each level above 20 adds 0.5% rate and doubles the cost
        base_cost = 50000000000  # Level 20 cost
        base_rate = 0.115  # Level 20 rate
        extra_levels = next_level - 20
        
        new_cost = int(base_cost * (2 ** extra_levels))  # Double cost each level
        new_rate = base_rate + (extra_levels * 0.005)  # Add 0.5% per level
        
        # Get current rate for display
        if current_level in INTEREST_UPGRADE_LEVELS:
            current_rate = INTEREST_UPGRADE_LEVELS[current_level]["rate"]
        elif current_level > 20:
            current_extra_levels = current_level - 20
            current_rate = base_rate + (current_extra_levels * 0.005)
        else:
            current_rate = 0.01
        
        return {
            "level": next_level,
            "cost": new_cost,
            "rate": new_rate,
            "current_rate": current_rate
        }
    
    return None

async def calculate_interest(user_id: int, guild_id: int) -> Tuple[int, float]:
    """Calculate interest for a user"""
    bank_balance = await db.get_bank_balance(user_id, guild_id)
    interest_level = await db.get_interest_level(user_id, guild_id)
    
    # Get interest rate from upgrade levels
    if interest_level in INTEREST_UPGRADE_LEVELS:
        rate = INTEREST_UPGRADE_LEVELS[interest_level]["rate"]
    elif interest_level > 20:
        # For levels above 20, extrapolate the rate
        # Level 20 is 11.5%, so each level adds 0.5%
        base_rate = 0.115  # Level 20 rate
        extra_levels = interest_level - 20
        rate = base_rate + (extra_levels * 0.005)  # Add 0.5% per level above 20
    else:
        # Level 0 or below
        rate = 0.01  # 1% base rate
    
    interest = int(bank_balance * rate)
    
    return interest, rate

def create_deposit_help_embed(wallet: int, bank_space: int) -> nextcord.Embed:
    """Create help embed for deposit command"""
    return nextcord.Embed(
        description=(
            "**BronkBuks Bank Deposit Guide**\n\n"
            f"Your Wallet: **{wallet:,}** {CURRENCY}\n"
            f"Bank Space: **{bank_space:,}** {CURRENCY}\n\n"
            "**Usage:**\n"
            "`.deposit <amount>`\n"
            "`.deposit 50%` - Deposit 50% of wallet\n"
            "`.deposit all` - Deposit maximum amount\n"
            "`.deposit 1k` - Deposit 1,000\n"
            "`.deposit 1.5m` - Deposit 1,500,000\n"
            "`.deposit 2b` - Deposit 2,000,000,000\n"
            "`.deposit 1e3` - Deposit 1,000 (scientific notation)\n"
            "`.deposit 2.5e5` - Deposit 250,000 (scientific notation)"
        ),
        color=0x2b2d31
    )

def create_withdraw_help_embed(wallet: int, bank: int) -> nextcord.Embed:
    """Create help embed for withdraw command"""
    return nextcord.Embed(
        description=(
            "**BronkBuks Bank Withdrawal Guide**\n\n"
            f"Your Bank: **{bank:,}** {CURRENCY}\n"
            f"Your Wallet: **{wallet:,}** {CURRENCY}\n\n"
            "**Usage:**\n"
            "`.withdraw <amount>`\n"
            "`.withdraw 50%` - Withdraw 50% of bank\n"
            "`.withdraw all` - Withdraw everything\n"
            "`.withdraw 1k` - Withdraw 1,000\n"
            "`.withdraw 1.5m` - Withdraw 1,500,000\n"
            "`.withdraw 2b` - Withdraw 2,000,000,000\n"
            "`.withdraw 1e3` - Withdraw 1,000 (scientific notation)\n"
            "`.withdraw 2.5e5` - Withdraw 250,000 (scientific notation)"
        ),
        color=0x2b2d31
    )

async def process_vote_reward(user_id: int, guild_id: int) -> Dict[str, Any]:
    """Process vote reward and calculate bonuses"""
    base_reward = VOTE_REWARDS["daily"]
    
    # Get user's vote streak
    vote_streak = await db.get_vote_streak(user_id, guild_id)
    
    # Calculate streak bonus
    streak_bonus = min(vote_streak * VOTE_REWARDS["streak_bonus"], VOTE_REWARDS["max_streak_bonus"])
    
    # Random bonus
    import random
    random_bonus = random.randint(VOTE_REWARDS["random_bonus_min"], VOTE_REWARDS["random_bonus_max"])
    
    total_reward = base_reward + streak_bonus + random_bonus
    
    # Update wallet
    await db.update_wallet(user_id, total_reward, guild_id)
    
    return {
        "base_reward": base_reward,
        "streak_bonus": streak_bonus,
        "random_bonus": random_bonus,
        "total_reward": total_reward,
        "streak": vote_streak
    }

def validate_payment_amount(amount_str: str, wallet: int) -> Tuple[Optional[int], Optional[str]]:
    """Validate and parse payment amount"""
    if not amount_str:
        return None, "Amount is required!"
    
    parsed_amount, error = parse_amount(amount_str, wallet, context="wallet")
    
    if error:
        return None, error
    
    if parsed_amount <= 0:
        return None, "Amount must be positive!"
    
    if parsed_amount > wallet:
        return None, "You don't have that much money!"
    
    return parsed_amount, None

async def create_leaderboard_data(guild_id: int, limit: int = 10) -> list:
    """Get leaderboard data for a guild"""
    try:
        leaderboard = await db.get_leaderboard(guild_id, limit)
        return leaderboard or []
    except Exception:
        return []

async def format_leaderboard_embed(leaderboard: list, guild: nextcord.Guild, page: int = 1, bot=None) -> nextcord.Embed:
    """Format leaderboard data into an embed"""
    embed = nextcord.Embed(
        title=f"💰 {guild.name} Economy Leaderboard",
        color=0xffd700
    )
    
    if not leaderboard:
        embed.description = "No economy data found for this server."
        return embed
    
    start_index = (page - 1) * 10
    description = ""
    
    for i, user_data in enumerate(leaderboard[start_index:start_index + 10], start=start_index + 1):
        user_id = user_data.get('user_id') or user_data.get('id')
        net_worth = user_data.get('net_worth', 0)
        
        # Get medal emoji for top 3
        if i == 1:
            medal = "🥇"
        elif i == 2:
            medal = "🥈"
        elif i == 3:
            medal = "🥉"
        else:
            medal = f"`{i:2d}.`"
        
        # Try to get username with multiple fallbacks
        username = f"User {user_id}"  # Default fallback
        
        try:
            # First try to get member from guild
            user = guild.get_member(user_id)
            if user:
                username = user.display_name
            elif bot:
                # If not in guild, try to get user from bot cache
                user = bot.get_user(user_id)
                if user:
                    username = user.display_name
                else:
                    # Try to fetch user from Discord API
                    try:
                        user = await bot.fetch_user(user_id)
                        username = user.display_name
                    except:
                        pass
        except Exception as e:
            pass  # Keep default fallback
        
        description += f"{medal} **{username}** - {net_worth:,} {CURRENCY}\n"
    
    embed.description = description
    embed.set_footer(text=f"Page {page} • Total users: {len(leaderboard)}")
    
    return embed
