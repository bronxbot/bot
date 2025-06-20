"""
Task Manager
Handles background tasks for the statistics system.
"""

import asyncio
from datetime import datetime, time
from nextcord.ext import tasks
from typing import Dict, List

from cogs.logging.logger import CogLogger
from .constants import DASHBOARD_SETTINGS

logger = CogLogger('TaskManager')

class TaskManager:
    """Manages background tasks for statistics system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.tasks = {}
        
        # Initialize tasks
        self._setup_tasks()
        
    def _setup_tasks(self):
        """Set up all background tasks"""
        
        @tasks.loop(hours=1)
        async def load_stats_task():
            """Load statistics from database periodically"""
            try:
                stats_cog = self.bot.get_cog('Stats')
                if stats_cog and hasattr(stats_cog, 'stats_manager'):
                    await stats_cog.stats_manager.load_stats_from_mongodb()
                    logger.debug("Periodic stats load completed")
            except Exception as e:
                logger.error(f"Error in load stats task: {e}")
        
        @load_stats_task.before_loop
        async def before_load_stats_task():
            """Wait for bot to be ready before starting"""
            await self.bot.wait_until_ready()
        
        @tasks.loop(minutes=DASHBOARD_SETTINGS['update_interval_minutes'])
        async def send_stats_task():
            """Send stats to dashboard periodically"""
            try:
                stats_cog = self.bot.get_cog('Stats')
                if stats_cog and hasattr(stats_cog, 'dashboard_manager'):
                    await stats_cog.dashboard_manager.send_comprehensive_stats()
                    logger.debug("Periodic stats update sent")
            except Exception as e:
                logger.error(f"Error in send stats task: {e}")
        
        @send_stats_task.before_loop
        async def before_send_stats_task():
            """Wait for bot to be ready before starting"""
            await self.bot.wait_until_ready()
        
        @tasks.loop(minutes=DASHBOARD_SETTINGS['performance_update_interval_minutes'])
        async def send_performance_update_task():
            """Send performance updates to dashboard"""
            try:
                stats_cog = self.bot.get_cog('Stats')
                if stats_cog and hasattr(stats_cog, 'dashboard_manager'):
                    await stats_cog.dashboard_manager.send_performance_update()
                    logger.debug("Performance update sent")
            except Exception as e:
                logger.error(f"Error in performance update task: {e}")
        
        @send_performance_update_task.before_loop
        async def before_send_performance_update_task():
            """Wait for bot to be ready before starting"""
            await self.bot.wait_until_ready()
        
        @tasks.loop(hours=24)
        async def reset_daily_stats_task():
            """Reset daily statistics at midnight UTC"""
            try:
                stats_cog = self.bot.get_cog('Stats')
                if stats_cog and hasattr(stats_cog, 'stats_manager'):
                    await stats_cog.stats_manager.reset_daily_stats()
                    logger.info("Daily stats reset completed")
            except Exception as e:
                logger.error(f"Error in daily reset task: {e}")
        
        @reset_daily_stats_task.before_loop
        async def before_reset_daily_stats_task():
            """Wait for bot to be ready and sync to midnight UTC"""
            await self.bot.wait_until_ready()
            
            # Calculate time until next midnight UTC
            now = datetime.utcnow()
            midnight = datetime.combine(now.date(), time(DASHBOARD_SETTINGS.get('daily_reset_hour', 0)))
            if now.time() >= time(DASHBOARD_SETTINGS.get('daily_reset_hour', 0)):
                # If past midnight today, wait until tomorrow
                from datetime import timedelta
                midnight += timedelta(days=1)
            
            wait_time = (midnight - now).total_seconds()
            logger.info(f"Waiting {wait_time/3600:.1f} hours until daily reset")
            await asyncio.sleep(wait_time)
        
        # Store tasks
        self.tasks = {
            'load_stats': load_stats_task,
            'send_stats': send_stats_task,
            'send_performance': send_performance_update_task,
            'reset_daily': reset_daily_stats_task
        }
        
        logger.info("Background tasks initialized")
    
    def start_all_tasks(self):
        """Start all background tasks"""
        for task_name, task in self.tasks.items():
            try:
                if not task.is_running():
                    task.start()
                    logger.info(f"Started task: {task_name}")
            except Exception as e:
                logger.error(f"Error starting task {task_name}: {e}")
    
    def stop_all_tasks(self):
        """Stop all background tasks"""
        for task_name, task in self.tasks.items():
            try:
                if task.is_running():
                    task.cancel()
                    logger.info(f"Stopped task: {task_name}")
            except Exception as e:
                logger.error(f"Error stopping task {task_name}: {e}")
    
    def restart_task(self, task_name: str):
        """Restart a specific task"""
        if task_name not in self.tasks:
            logger.error(f"Unknown task: {task_name}")
            return
        
        task = self.tasks[task_name]
        try:
            if task.is_running():
                task.restart()
            else:
                task.start()
            logger.info(f"Restarted task: {task_name}")
        except Exception as e:
            logger.error(f"Error restarting task {task_name}: {e}")
    
    def get_task_status(self) -> Dict[str, bool]:
        """Get the status of all tasks"""
        return {
            task_name: task.is_running() 
            for task_name, task in self.tasks.items()
        }
    
    async def force_run_task(self, task_name: str):
        """Force run a task immediately"""
        if task_name not in self.tasks:
            logger.error(f"Unknown task: {task_name}")
            return False
        
        try:
            # Get the task function and run it
            task = self.tasks[task_name]
            if hasattr(task, '_coro'):
                await task._coro()
                logger.info(f"Manually executed task: {task_name}")
                return True
        except Exception as e:
            logger.error(f"Error manually running task {task_name}: {e}")
        
        return False
