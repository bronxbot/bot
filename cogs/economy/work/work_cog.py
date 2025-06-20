"""
Main Work Cog - Commands and core functionality
"""
import nextcord
from nextcord.ext import commands
import time
import asyncio
from typing import Dict, Any, Optional, Tuple

from cogs.logging.logger import CogLogger
from utils.db import db
from utils.safe_reply import safe_reply
from utils.tos_handler import check_tos_acceptance, prompt_tos_acceptance

from .constants import JOBS, CURRENCY, WORK_COOLDOWN, RAISE_COOLDOWN
from .work_utils import (
    get_user_job, set_user_job, remove_user_job, calculate_wage,
    get_job_display_name, get_boss_relationship_status, get_coworkers,
    format_currency, get_job_list_embed_description, is_valid_job_id,
    update_work_timestamp, update_raise_timestamp
)
from .work_views import JobManagementView, CoworkersView
from .minigames import get_minigame_class

class Work(commands.Cog):
    """Work system for earning money through various jobs"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = CogLogger(self.__class__.__name__)
        self.pending_raises = {}  # Track raise requests for group bonuses
        self.work_cooldowns = {}  # Track work cooldowns per user

    async def cog_check(self, ctx):
        """Global check for all commands in this cog"""
        # Check if user has accepted ToS
        if not await check_tos_acceptance(ctx.author.id):
            await prompt_tos_acceptance(ctx)
            return False
        return True

    async def can_work(self, user_id: int) -> Tuple[bool, int]:
        """Check if user can work (cooldown check)"""
        user_job = await get_user_job(user_id)
        if not user_job or not user_job['last_work']:
            return True, 0
        
        time_since_work = time.time() - user_job['last_work']
        if time_since_work >= WORK_COOLDOWN:
            return True, 0
        
        remaining = int(WORK_COOLDOWN - time_since_work)
        return False, remaining

    async def can_ask_raise(self, user_id: int) -> Tuple[bool, int]:
        """Check if user can ask for a raise"""
        user_job = await get_user_job(user_id)
        if not user_job or not user_job['last_raise']:
            return True, 0
        
        time_since_raise = time.time() - user_job['last_raise']
        if time_since_raise >= RAISE_COOLDOWN:
            return True, 0
        
        remaining = int(RAISE_COOLDOWN - time_since_raise)
        return False, remaining

    @commands.command(name="job", aliases=["career"])
    async def job_command(self, ctx):
        """Manage your job and career"""
        user_job = await get_user_job(ctx.author.id)
        
        embed = nextcord.Embed(
            title="💼 Job Management",
            description="Manage your career and employment status:",
            color=0x2ecc71
        )
        
        if user_job:
            job_info = user_job['job_info']
            status_text, status_emoji = get_boss_relationship_status(
                user_job['boss_hostile'], user_job['boss_loyalty']
            )
            
            embed.add_field(
                name=f"{job_info['emoji']} Current Job",
                value=f"**{job_info['name']}**\n{job_info['description']}",
                inline=False
            )
            embed.add_field(
                name="💰 Wage Range",
                value=f"{job_info['wage']['min']:,} - {job_info['wage']['max']:,} {CURRENCY}",
                inline=True
            )
            embed.add_field(
                name=f"{status_emoji} Boss Status",
                value=status_text,
                inline=True
            )
        else:
            embed.add_field(
                name="📋 Employment Status",
                value="**Unemployed**\nChoose a job to start earning money!",
                inline=False
            )
        
        view = JobManagementView(ctx.author.id)
        await safe_reply(ctx, embed=embed, view=view)

    @commands.command(name="work", aliases=["wrk", "earn"])
    async def work_command(self, ctx):
        """Work at your job to earn money"""
        # Check work cooldown
        can_work, cooldown_remaining = await self.can_work(ctx.author.id)
        if not can_work:
            hours = cooldown_remaining // 3600
            minutes = (cooldown_remaining % 3600) // 60
            seconds = cooldown_remaining % 60
            
            embed = nextcord.Embed(
                title="⏰ Work Cooldown",
                description=f"You need to wait **{hours}h {minutes}m {seconds}s** before working again.",
                color=0xf39c12
            )
            await safe_reply(ctx, embed=embed)
            return

        # Check if user has a job
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="🚫 No Job",
                description="You need a job first! Use `!job` to choose one.",
                color=0xe74c3c
            )
            await safe_reply(ctx, embed=embed)
            return

        # Get job info and start minigame
        job_info = user_job['job_info']
        minigame_class = get_minigame_class(user_job['job_id'])
        minigame_view = minigame_class(self, user_job, ctx.author.id)
        
        embed = nextcord.Embed(
            title=f"{job_info['emoji']} Time to Work!",
            description=f"**Job:** {job_info['name']}\n**Task:** {job_info['description']}\n\nChoose your approach:",
            color=0x3498db
        )
        
        await safe_reply(ctx, embed=embed, view=minigame_view)

    @commands.command(name="choosejob", aliases=["selectjob", "getjob"])
    async def choose_job_command(self, ctx, *, job_name: str = None):
        """Choose a new job"""
        # Check if user already has a job
        current_job = await get_user_job(ctx.author.id)
        if current_job:
            embed = nextcord.Embed(
                title="❌ Already Employed",
                description=f"You already work as a **{current_job['job_info']['name']}**!\nUse `!leavejob` first if you want to change jobs.",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        if not job_name:
            # Show job selection interface
            embed = nextcord.Embed(
                title="💼 Available Jobs",
                description=get_job_list_embed_description(),
                color=0x0099ff
            )
            embed.set_footer(text="Use !choosejob <job_name> to select a job")
            await safe_reply(ctx, embed=embed)
            return

        # Find job by name (case insensitive partial match)
        job_name_lower = job_name.lower()
        selected_job_id = None
        
        for job_id, job_info in JOBS.items():
            if (job_name_lower in job_info['name'].lower() or 
                job_name_lower in job_id.lower()):
                selected_job_id = job_id
                break

        if not selected_job_id:
            embed = nextcord.Embed(
                title="❌ Job Not Found",
                description=f"No job found matching '{job_name}'. Use `!choosejob` to see available jobs.",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        # Set the job
        success = await set_user_job(ctx.author.id, selected_job_id)
        if success:
            job_info = JOBS[selected_job_id]
            embed = nextcord.Embed(
                title="🎉 Job Acquired!",
                description=f"Congratulations! You're now employed as a **{job_info['name']}**!",
                color=0x00ff00
            )
            embed.add_field(
                name="💼 Job Details",
                value=f"**Description:** {job_info['description']}\n**Wage:** {format_currency(job_info['wage']['min'])} - {format_currency(job_info['wage']['max'])}",
                inline=False
            )
            embed.add_field(
                name="🚀 Getting Started",
                value="Use `!work` to start earning money!",
                inline=False
            )
        else:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Failed to assign job. Please try again.",
                color=0xff0000
            )

        await safe_reply(ctx, embed=embed)

    @commands.command(name="leavejob", aliases=["quitjob", "quit"])
    async def leave_job_command(self, ctx):
        """Leave your current job"""
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="❌ No Job",
                description="You don't have a job to leave!",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        success = await remove_user_job(ctx.author.id)
        if success:
            embed = nextcord.Embed(
                title="👋 Job Left",
                description=f"You have left your position as a **{user_job['job_info']['name']}**.",
                color=0x00ff00
            )
            embed.add_field(
                name="💡 What's Next?",
                value="Use `!choosejob` to find a new career!",
                inline=False
            )
        else:
            embed = nextcord.Embed(
                title="❌ Error",
                description="Failed to leave job. Please try again.",
                color=0xff0000
            )

        await safe_reply(ctx, embed=embed)

    @commands.command(name="jobstatus", aliases=["mystatus", "workstatus"])
    async def job_status_command(self, ctx):
        """Check your job status and boss relationship"""
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="❌ Unemployed",
                description="You don't have a job! Use `!choosejob` to get started.",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        job_info = user_job['job_info']
        status_text, status_emoji = get_boss_relationship_status(
            user_job['boss_hostile'], user_job['boss_loyalty']
        )
        
        # Calculate current wage range based on boss relationship
        min_wage = calculate_wage(job_info, user_job['boss_hostile'], user_job['boss_loyalty'])
        max_wage = calculate_wage(job_info, user_job['boss_hostile'], user_job['boss_loyalty'])
        
        embed = nextcord.Embed(
            title=f"{job_info['emoji']} Your Job Status",
            description=f"**Position:** {job_info['name']}\n**Description:** {job_info['description']}",
            color=0x00ff00
        )
        embed.add_field(
            name="💰 Current Wage Range",
            value=format_currency(min_wage),
            inline=True
        )
        embed.add_field(
            name=f"{status_emoji} Boss Relationship",
            value=status_text,
            inline=True
        )
        embed.add_field(
            name="📈 Boss Stats",
            value=f"Hostility: {user_job['boss_hostile']}/100\nLoyalty: {user_job['boss_loyalty']}/100",
            inline=True
        )

        # Add cooldown info
        can_work, work_cooldown = await self.can_work(ctx.author.id)
        can_raise, raise_cooldown = await self.can_ask_raise(ctx.author.id)
        
        status_info = []
        if not can_work:
            hours = work_cooldown // 3600
            minutes = (work_cooldown % 3600) // 60
            status_info.append(f"⏰ Work cooldown: {hours}h {minutes}m")
        else:
            status_info.append("✅ Ready to work")
            
        if not can_raise:
            hours = raise_cooldown // 3600
            status_info.append(f"📈 Raise cooldown: {hours}h")
        else:
            status_info.append("💰 Can ask for raise")

        embed.add_field(
            name="⏱️ Status",
            value="\n".join(status_info),
            inline=False
        )

        await safe_reply(ctx, embed=embed)

    @commands.command(name="askraise", aliases=["raise", "promotion"])
    async def ask_raise_command(self, ctx):
        """Ask your boss for a raise (increases loyalty, might increase hostility)"""
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="❌ No Job",
                description="You need a job to ask for a raise!",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        # Check raise cooldown
        can_raise, cooldown_remaining = await self.can_ask_raise(ctx.author.id)
        if not can_raise:
            hours = cooldown_remaining // 3600
            embed = nextcord.Embed(
                title="⏰ Raise Cooldown",
                description=f"You recently asked for a raise. Wait **{hours}** hours before asking again.",
                color=0xf39c12
            )
            await safe_reply(ctx, embed=embed)
            return

        # Determine outcome based on current relationship
        import random
        loyalty = user_job['boss_loyalty']
        hostility = user_job['boss_hostile']
        
        # Higher loyalty = better chance of success
        success_chance = min(0.8, 0.2 + (loyalty / 100) * 0.6)
        success = random.random() < success_chance
        
        if success:
            loyalty_gain = random.randint(5, 15)
            hostility_change = random.randint(-2, 3)  # Might actually decrease hostility
            
            from .work_utils import update_boss_relationship
            await update_boss_relationship(ctx.author.id, hostility_change, loyalty_gain)
            await update_raise_timestamp(ctx.author.id)
            
            embed = nextcord.Embed(
                title="🎉 Raise Approved!",
                description="Your boss approved your raise request!",
                color=0x00ff00
            )
            embed.add_field(
                name="📈 Relationship Change",
                value=f"Loyalty: +{loyalty_gain}\nHostility: {hostility_change:+d}",
                inline=True
            )
        else:
            hostility_gain = random.randint(3, 8)
            loyalty_loss = random.randint(0, 3)
            
            from .work_utils import update_boss_relationship
            await update_boss_relationship(ctx.author.id, hostility_gain, -loyalty_loss)
            await update_raise_timestamp(ctx.author.id)
            
            embed = nextcord.Embed(
                title="❌ Raise Denied",
                description="Your boss denied your raise request and seems annoyed.",
                color=0xff0000
            )
            embed.add_field(
                name="📉 Relationship Change",
                value=f"Hostility: +{hostility_gain}\nLoyalty: -{loyalty_loss}",
                inline=True
            )

        await safe_reply(ctx, embed=embed)

    @commands.command(name="giftboss", aliases=["gift", "bribe"])
    async def gift_boss_command(self, ctx):
        """Give a gift to your boss to improve relationship"""
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="❌ No Job",
                description="You need a job to give gifts to your boss!",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        # Show gift options through the boss relations view
        from .work_views import BossRelationsView
        view = BossRelationsView(ctx.author.id, user_job)
        embed = nextcord.Embed(
            title="🎁 Boss Gift Shop",
            description="Choose a gift to improve your relationship with your boss:",
            color=0x0099ff
        )
        
        await safe_reply(ctx, embed=embed, view=view)

    @commands.command(name="joblist", aliases=["jobs", "careers", "jobslist"])
    async def job_list_command(self, ctx):
        """List all available jobs"""
        embed = nextcord.Embed(
            title="💼 Available Careers",
            description=get_job_list_embed_description(),
            color=0x0099ff
        )
        embed.set_footer(text="Use !choosejob <job_name> to select a job")
        await safe_reply(ctx, embed=embed)

    @commands.command(name="coworkers", aliases=["colleagues", "teammates"])
    async def coworkers_command(self, ctx):
        """View your coworkers"""
        user_job = await get_user_job(ctx.author.id)
        if not user_job:
            embed = nextcord.Embed(
                title="❌ No Job",
                description="You need a job to have coworkers!",
                color=0xff0000
            )
            await safe_reply(ctx, embed=embed)
            return

        coworkers = await get_coworkers(ctx.author.id, user_job['job_id'])
        job_info = user_job['job_info']
        
        if not coworkers:
            embed = nextcord.Embed(
                title="👥 No Coworkers",
                description=f"You're the only {job_info['name']} currently employed!",
                color=0x0099ff
            )
        else:
            coworker_list = []
            for i, coworker in enumerate(coworkers, 1):
                username = coworker['username'] or f"User {coworker['id']}"
                coworker_list.append(f"{i}. {username}")
            
            embed = nextcord.Embed(
                title=f"👥 Your {job_info['name']} Coworkers",
                description="\n".join(coworker_list),
                color=0x0099ff
            )
            embed.set_footer(text=f"Total coworkers: {len(coworkers)}")

        view = CoworkersView(ctx.author.id, user_job['job_id'])
        await safe_reply(ctx, embed=embed, view=view)

async def setup(bot):
    bot.add_cog(Work(bot))
