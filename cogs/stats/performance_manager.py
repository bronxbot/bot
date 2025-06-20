"""
Performance Manager
Handles system performance monitoring and tracking.
"""

import nextcord
import psutil
import time
from datetime import datetime, timedelta
from nextcord.utils import utcnow
from typing import Dict, List, Optional

from utils.db import db
from cogs.logging.logger import CogLogger
from .constants import (
    DEFAULT_PERFORMANCE, PERFORMANCE_THRESHOLDS, ALERT_SETTINGS,
    COLLECTIONS, COLORS, TIME_FORMATS, RETENTION_SETTINGS
)

logger = CogLogger('PerformanceManager')

class PerformanceManager:
    """Manages system performance monitoring"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db = db
        
        # Performance tracking
        self.performance_data = DEFAULT_PERFORMANCE.copy()
        self.last_performance_update = 0
        self.alert_cooldowns = {}
        
    async def collect_performance_data(self) -> Dict:
        """Collect current system performance data"""
        try:
            # CPU and Memory usage
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Bot latency
            latency = round(self.bot.latency * 1000, 2)  # Convert to ms
            
            # Database latency (simple ping test)
            db_start = time.time()
            try:
                await self.db.db.admin.command('ping')
                db_latency = round((time.time() - db_start) * 1000, 2)
            except Exception:
                db_latency = -1
            
            # Response times (recent average)
            avg_response_time = self._calculate_average_response_time()
            
            # Active connections and uptime
            active_connections = len(self.bot.guilds)
            uptime_seconds = self._get_uptime_seconds()
            
            performance_data = {
                'cpu_usage': cpu_percent,
                'memory_usage': round((memory.used / memory.total) * 100, 2),
                'memory_total': round(memory.total / (1024**3), 2),  # GB
                'latency': latency,
                'database_latency': db_latency,
                'response_times': self.performance_data.get('response_times', [])[-10:],  # Last 10
                'active_connections': active_connections,
                'uptime_seconds': uptime_seconds,
                'last_restart': getattr(self.bot, 'launch_time', utcnow()).isoformat(),
                'timestamp': utcnow().isoformat()
            }
            
            # Update stored performance data
            self.performance_data.update(performance_data)
            
            # Check for performance alerts
            await self._check_performance_alerts(performance_data)
            
            return performance_data
            
        except Exception as e:
            logger.error(f"Error collecting performance data: {e}")
            return self.performance_data

    async def save_performance_data(self, data: Dict):
        """Save performance data to database"""
        try:
            collection = self.db.db[COLLECTIONS['performance_logs']]
            
            # Add timestamp if not present
            if 'timestamp' not in data:
                data['timestamp'] = utcnow()
            
            await collection.insert_one(data)
            
            # Clean up old performance logs
            cutoff_time = utcnow() - timedelta(hours=RETENTION_SETTINGS.get('performance_logs_hours', 24))
            await collection.delete_many({'timestamp': {'$lt': cutoff_time}})
            
            logger.debug("Performance data saved to database")
            
        except Exception as e:
            logger.error(f"Error saving performance data: {e}")

    async def _check_performance_alerts(self, data: Dict):
        """Check for performance issues and send alerts if needed"""
        if not ALERT_SETTINGS.get('enable_performance_alerts', False):
            return
        
        alerts = []
        current_time = time.time()
        
        # Check CPU usage
        cpu_usage = data.get('cpu_usage', 0)
        if cpu_usage > PERFORMANCE_THRESHOLDS['cpu_critical']:
            if self._should_send_alert('cpu_critical', current_time):
                alerts.append(f"🔥 **CRITICAL CPU Usage:** {cpu_usage}%")
        elif cpu_usage > PERFORMANCE_THRESHOLDS['cpu_warning']:
            if self._should_send_alert('cpu_warning', current_time):
                alerts.append(f"⚠️ **High CPU Usage:** {cpu_usage}%")
        
        # Check Memory usage
        memory_usage = data.get('memory_usage', 0)
        if memory_usage > PERFORMANCE_THRESHOLDS['memory_critical']:
            if self._should_send_alert('memory_critical', current_time):
                alerts.append(f"🔥 **CRITICAL Memory Usage:** {memory_usage}%")
        elif memory_usage > PERFORMANCE_THRESHOLDS['memory_warning']:
            if self._should_send_alert('memory_warning', current_time):
                alerts.append(f"⚠️ **High Memory Usage:** {memory_usage}%")
        
        # Check Latency
        latency = data.get('latency', 0)
        if latency > PERFORMANCE_THRESHOLDS['latency_critical']:
            if self._should_send_alert('latency_critical', current_time):
                alerts.append(f"🔥 **CRITICAL Latency:** {latency}ms")
        elif latency > PERFORMANCE_THRESHOLDS['latency_warning']:
            if self._should_send_alert('latency_warning', current_time):
                alerts.append(f"⚠️ **High Latency:** {latency}ms")
        
        # Send alerts if any
        if alerts:
            await self._send_performance_alert(alerts, data)

    def _should_send_alert(self, alert_type: str, current_time: float) -> bool:
        """Check if we should send an alert based on cooldown"""
        last_alert = self.alert_cooldowns.get(alert_type, 0)
        cooldown_minutes = ALERT_SETTINGS.get('alert_cooldown_minutes', 30)
        
        if current_time - last_alert > (cooldown_minutes * 60):
            self.alert_cooldowns[alert_type] = current_time
            return True
        return False

    async def _send_performance_alert(self, alerts: List[str], data: Dict):
        """Send performance alert to designated channel"""
        try:
            channel_id = ALERT_SETTINGS.get('alert_channels', {}).get('performance')
            if not channel_id:
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            
            embed = nextcord.Embed(
                title="🚨 Performance Alert",
                description="\n".join(alerts),
                color=COLORS['error'],
                timestamp=utcnow()
            )
            
            embed.add_field(
                name="📊 Current Stats",
                value=(
                    f"**CPU:** {data.get('cpu_usage', 0)}%\n"
                    f"**Memory:** {data.get('memory_usage', 0)}%\n"
                    f"**Latency:** {data.get('latency', 0)}ms\n"
                    f"**Guilds:** {data.get('active_connections', 0)}"
                ),
                inline=True
            )
            
            embed.set_footer(text="Performance monitoring system")
            
            await channel.send(embed=embed)
            logger.warning(f"Performance alert sent: {', '.join(alerts)}")
            
        except Exception as e:
            logger.error(f"Error sending performance alert: {e}")

    def _calculate_average_response_time(self) -> float:
        """Calculate average response time from recent samples"""
        response_times = self.performance_data.get('response_times', [])
        if not response_times:
            return 0.0
        
        return round(sum(response_times) / len(response_times), 2)

    def _get_uptime_seconds(self) -> int:
        """Get bot uptime in seconds"""
        if not hasattr(self.bot, 'launch_time'):
            return 0
        return int((utcnow() - self.bot.launch_time).total_seconds())

    async def test_performance_update(self, ctx):
        """Test the performance monitoring system"""
        try:
            embed = nextcord.Embed(
                title="🔧 Performance Test",
                description="Testing performance monitoring system...",
                color=COLORS['info']
            )
            
            message = await ctx.send(embed=embed)
            
            # Collect performance data
            start_time = time.time()
            perf_data = await self.collect_performance_data()
            collection_time = round((time.time() - start_time) * 1000, 2)
            
            # Save to database
            start_time = time.time()
            await self.save_performance_data(perf_data.copy())
            save_time = round((time.time() - start_time) * 1000, 2)
            
            # Update embed with results
            embed = nextcord.Embed(
                title="✅ Performance Test Complete",
                color=COLORS['success']
            )
            
            embed.add_field(
                name="📊 Current Performance",
                value=(
                    f"**CPU Usage:** {perf_data.get('cpu_usage', 0)}%\n"
                    f"**Memory Usage:** {perf_data.get('memory_usage', 0)}%\n"
                    f"**Bot Latency:** {perf_data.get('latency', 0)}ms\n"
                    f"**DB Latency:** {perf_data.get('database_latency', 0)}ms"
                ),
                inline=True
            )
            
            embed.add_field(
                name="⏱️ Test Metrics",
                value=(
                    f"**Collection Time:** {collection_time}ms\n"
                    f"**Save Time:** {save_time}ms\n"
                    f"**Total Time:** {collection_time + save_time}ms"
                ),
                inline=True
            )
            
            embed.add_field(
                name="🔧 System Info",
                value=(
                    f"**Guilds:** {len(self.bot.guilds)}\n"
                    f"**Users:** {len(self.bot.users)}\n"
                    f"**Uptime:** {self._format_uptime()}"
                ),
                inline=False
            )
            
            await message.edit(embed=embed)
            
        except Exception as e:
            logger.error(f"Error in performance test: {e}")
            await ctx.send("❌ Error during performance test")

    def _format_uptime(self) -> str:
        """Format uptime for display"""
        if not hasattr(self.bot, 'launch_time'):
            return "Unknown"
        
        uptime = utcnow() - self.bot.launch_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m {seconds}s"

    async def get_performance_summary(self) -> Dict:
        """Get a summary of current performance metrics"""
        perf_data = await self.collect_performance_data()
        
        return {
            'cpu_usage': perf_data.get('cpu_usage', 0),
            'memory_usage': perf_data.get('memory_usage', 0),
            'latency': perf_data.get('latency', 0),
            'database_latency': perf_data.get('database_latency', 0),
            'uptime_seconds': perf_data.get('uptime_seconds', 0),
            'active_connections': perf_data.get('active_connections', 0),
            'status': self._get_performance_status(perf_data)
        }

    def _get_performance_status(self, data: Dict) -> str:
        """Get overall performance status"""
        cpu = data.get('cpu_usage', 0)
        memory = data.get('memory_usage', 0)
        latency = data.get('latency', 0)
        
        if (cpu > PERFORMANCE_THRESHOLDS['cpu_critical'] or 
            memory > PERFORMANCE_THRESHOLDS['memory_critical'] or 
            latency > PERFORMANCE_THRESHOLDS['latency_critical']):
            return "critical"
        elif (cpu > PERFORMANCE_THRESHOLDS['cpu_warning'] or 
              memory > PERFORMANCE_THRESHOLDS['memory_warning'] or 
              latency > PERFORMANCE_THRESHOLDS['latency_warning']):
            return "warning"
        else:
            return "healthy"
