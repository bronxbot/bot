"""
Dashboard Manager
Handles integration with external dashboard and API communication.
"""

import nextcord
import aiohttp
import asyncio
import time
import json
from datetime import datetime
from typing import Dict, List, Optional

from cogs.logging.logger import CogLogger
from .constants import (
    DASHBOARD_SETTINGS, API_ENDPOINTS, COLORS, LIMITS
)

logger = CogLogger('DashboardManager')

class DashboardManager:
    """Manages dashboard API integration"""
    
    def __init__(self, bot):
        self.bot = bot
        
        # Set dashboard URL based on dev mode
        self.dashboard_url = "https://bronxbot.xyz" if not getattr(bot, 'dev_mode', False) else "http://localhost:5000"
        self.dashboard_url = self.dashboard_url.rstrip('/')
        
        # API settings
        self.timeout = DASHBOARD_SETTINGS.get('request_timeout_seconds', 30)
        self.max_retries = DASHBOARD_SETTINGS.get('max_retry_attempts', 3)
        
        logger.info(f"Dashboard manager initialized with URL: {self.dashboard_url}")
    
    async def send_comprehensive_stats(self):
        """Send comprehensive statistics to dashboard"""
        try:
            stats_cog = self.bot.get_cog('Stats')
            if not stats_cog:
                return
            
            # Gather data from all managers
            stats_data = await stats_cog.stats_manager.get_stats_summary()
            performance_data = await stats_cog.performance_manager.get_performance_summary()
            guild_data = await stats_cog.guild_manager.get_guild_summary()
            
            # Combine into comprehensive payload
            payload = {
                'stats': stats_data,
                'performance': performance_data,
                'guilds': guild_data,
                'timestamp': datetime.now().isoformat(),
                'bot_id': str(self.bot.user.id) if self.bot.user else None
            }
            
            # Send to dashboard
            success = await self._send_api_request(
                API_ENDPOINTS['stats_update'], 
                payload
            )
            
            if success:
                logger.debug("Comprehensive stats sent to dashboard")
            else:
                logger.warning("Failed to send comprehensive stats to dashboard")
                
        except Exception as e:
            logger.error(f"Error sending comprehensive stats: {e}")
    
    async def send_performance_update(self):
        """Send performance update to dashboard"""
        try:
            stats_cog = self.bot.get_cog('Stats')
            if not stats_cog:
                return
            
            # Get performance data
            performance_data = await stats_cog.performance_manager.collect_performance_data()
            
            # Add additional context
            payload = {
                'performance': performance_data,
                'timestamp': datetime.now().isoformat(),
                'bot_id': str(self.bot.user.id) if self.bot.user else None,
                'guild_count': len(self.bot.guilds),
                'user_count': len(self.bot.users)
            }
            
            # Send to dashboard
            success = await self._send_api_request(
                API_ENDPOINTS['performance_update'], 
                payload
            )
            
            if success:
                logger.debug("Performance update sent to dashboard")
            
        except Exception as e:
            logger.error(f"Error sending performance update: {e}")
    
    async def send_realtime_command_update(self, command_name: str, user_id: int, 
                                         guild_id: Optional[int] = None, 
                                         execution_time: float = 0.0, 
                                         success: bool = True):
        """Send real-time command usage update"""
        try:
            # Rate limiting check
            if not self._should_send_realtime_update():
                return
            
            payload = {
                'command_name': command_name,
                'user_id': str(user_id),
                'guild_id': str(guild_id) if guild_id else None,
                'execution_time': execution_time,
                'success': success,
                'timestamp': time.time(),
                'bot_id': str(self.bot.user.id) if self.bot.user else None
            }
            
            # Send to dashboard (non-blocking)
            asyncio.create_task(
                self._send_api_request(API_ENDPOINTS['command_log'], payload, retry=False)
            )
            
        except Exception as e:
            logger.error(f"Error sending realtime command update: {e}")
    
    async def force_stats_update(self, ctx):
        """Force an immediate stats update to dashboard"""
        try:
            embed = nextcord.Embed(
                title="🔄 Forcing Stats Update",
                description="Sending immediate update to dashboard...",
                color=COLORS['info']
            )
            
            message = await ctx.send(embed=embed)
            
            # Send comprehensive stats
            start_time = time.time()
            await self.send_comprehensive_stats()
            stats_time = round((time.time() - start_time) * 1000, 2)
            
            # Send performance update
            start_time = time.time()
            await self.send_performance_update()
            perf_time = round((time.time() - start_time) * 1000, 2)
            
            # Update embed with results
            embed = nextcord.Embed(
                title="✅ Stats Update Complete",
                color=COLORS['success']
            )
            
            embed.add_field(
                name="📊 Update Times",
                value=(
                    f"**Stats Update:** {stats_time}ms\n"
                    f"**Performance Update:** {perf_time}ms\n"
                    f"**Total Time:** {stats_time + perf_time}ms"
                ),
                inline=True
            )
            
            embed.add_field(
                name="🌐 Dashboard Info",
                value=(
                    f"**URL:** {self.dashboard_url}\n"
                    f"**Timeout:** {self.timeout}s\n"
                    f"**Max Retries:** {self.max_retries}"
                ),
                inline=True
            )
            
            embed.set_footer(text=f"Update sent at {datetime.now().strftime('%H:%M:%S UTC')}")
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in force stats update: {e}")
            await ctx.send("❌ Error during forced stats update")
    
    async def _send_api_request(self, endpoint: str, data: Dict, retry: bool = True) -> bool:
        """Send API request to dashboard with retry logic"""
        url = f"{self.dashboard_url}{endpoint}"
        
        for attempt in range(self.max_retries if retry else 1):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        url, 
                        json=data, 
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    ) as response:
                        
                        if response.status == 200:
                            return True
                        elif response.status == 404:
                            # Only log 404s at debug level to reduce spam
                            logger.debug(f"Dashboard API endpoint not found: {endpoint}")
                            return False  # Don't retry 404s
                        else:
                            logger.warning(f"Dashboard API returned status {response.status} for {endpoint}")
                            if attempt < self.max_retries - 1 and retry:
                                await asyncio.sleep(2 ** attempt)  # Exponential backoff
                            
            except aiohttp.ClientTimeout:
                logger.warning(f"Timeout sending to {endpoint} (attempt {attempt + 1})")
                if attempt < self.max_retries - 1 and retry:
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                logger.error(f"Error sending to {endpoint}: {e}")
                if attempt < self.max_retries - 1 and retry:
                    await asyncio.sleep(2 ** attempt)
        
        return False
    
    def _should_send_realtime_update(self) -> bool:
        """Rate limiting for real-time updates"""
        # Simple rate limiting - could be enhanced
        current_time = time.time()
        
        if not hasattr(self, '_last_realtime_update'):
            self._last_realtime_update = 0
        
        # Allow max 1 realtime update per second
        if current_time - self._last_realtime_update < 1.0:
            return False
        
        self._last_realtime_update = current_time
        return True
    
    async def test_dashboard_connection(self) -> Dict[str, any]:
        """Test connection to dashboard"""
        try:
            start_time = time.time()
            
            # Test health check endpoint
            success = await self._send_api_request(
                API_ENDPOINTS.get('health_check', '/api/health'), 
                {'test': True, 'timestamp': datetime.now().isoformat()},
                retry=False
            )
            
            response_time = round((time.time() - start_time) * 1000, 2)
            
            return {
                'success': success,
                'response_time_ms': response_time,
                'dashboard_url': self.dashboard_url,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error testing dashboard connection: {e}")
            return {
                'success': False,
                'error': str(e),
                'dashboard_url': self.dashboard_url,
                'timestamp': datetime.now().isoformat()
            }
    
    async def get_dashboard_status(self) -> Dict:
        """Get dashboard connection status"""
        test_result = await self.test_dashboard_connection()
        
        return {
            'url': self.dashboard_url,
            'connected': test_result.get('success', False),
            'response_time': test_result.get('response_time_ms', -1),
            'last_test': test_result.get('timestamp'),
            'timeout': self.timeout,
            'max_retries': self.max_retries
        }
