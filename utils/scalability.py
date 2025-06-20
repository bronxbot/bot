import asyncio
import time
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import json
import redis
from nextcord.ext import commands
import nextcord

class RateLimitManager:
    """Advanced rate limiting and request queuing system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('RateLimitManager')
        
        # Rate limit tracking
        self.rate_limits = defaultdict(lambda: {
            'remaining': 0,
            'reset_time': 0,
            'bucket': None
        })
        
        # Request queues per endpoint
        self.request_queues = defaultdict(lambda: asyncio.Queue())
        self.queue_processors = {}
        
        # Global rate limit tracking
        self.global_rate_limit = {
            'active': False,
            'reset_time': 0,
            'retry_after': 0
        }
        
        # Request retry configuration
        self.retry_config = {
            'max_retries': 3,
            'base_delay': 1.0,
            'max_delay': 60.0,
            'backoff_factor': 2.0
        }
        
        # Start queue processors for common endpoints
        self.start_queue_processors()
    
    def start_queue_processors(self):
        """Start queue processors for different Discord API endpoints"""
        endpoints = [
            'messages',
            'reactions', 
            'channels',
            'guilds',
            'members',
            'embeds'
        ]
        
        for endpoint in endpoints:
            task = asyncio.create_task(self.process_request_queue(endpoint))
            self.queue_processors[endpoint] = task
    
    async def process_request_queue(self, endpoint: str):
        """Process requests for a specific endpoint with rate limiting"""
        queue = self.request_queues[endpoint]
        
        while True:
            try:
                # Wait for request
                request = await queue.get()
                
                # Check global rate limit
                if self.global_rate_limit['active']:
                    wait_time = self.global_rate_limit['reset_time'] - time.time()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                        self.global_rate_limit['active'] = False
                
                # Check endpoint-specific rate limit
                bucket_info = self.rate_limits[endpoint]
                if bucket_info['remaining'] <= 0:
                    wait_time = bucket_info['reset_time'] - time.time()
                    if wait_time > 0:
                        await asyncio.sleep(wait_time)
                
                # Execute request with retry logic
                await self.execute_with_retry(request)
                
                # Mark task as done
                queue.task_done()
                
            except Exception as e:
                self.logger.error(f"Error processing {endpoint} queue: {e}")
                await asyncio.sleep(1)
    
    async def execute_with_retry(self, request: Dict[str, Any]):
        """Execute a request with exponential backoff retry"""
        func = request['function']
        args = request.get('args', ())
        kwargs = request.get('kwargs', {})
        callback = request.get('callback')
        
        for attempt in range(self.retry_config['max_retries']):
            try:
                result = await func(*args, **kwargs)
                
                # Call success callback if provided
                if callback:
                    await callback(result, None)
                
                return result
                
            except nextcord.HTTPException as e:
                # Handle rate limits
                if e.status == 429:
                    retry_after = float(e.response.headers.get('Retry-After', 1))
                    
                    # Update rate limit info
                    if e.response.headers.get('X-RateLimit-Global'):
                        self.global_rate_limit = {
                            'active': True,
                            'reset_time': time.time() + retry_after,
                            'retry_after': retry_after
                        }
                    
                    await asyncio.sleep(retry_after)
                    continue
                
                # Handle other HTTP errors
                if attempt == self.retry_config['max_retries'] - 1:
                    if callback:
                        await callback(None, e)
                    raise
                
                # Calculate backoff delay
                delay = min(
                    self.retry_config['base_delay'] * (self.retry_config['backoff_factor'] ** attempt),
                    self.retry_config['max_delay']
                )
                await asyncio.sleep(delay)
                
            except Exception as e:
                if callback:
                    await callback(None, e)
                raise
    
    async def queue_request(self, endpoint: str, function, *args, callback=None, **kwargs):
        """Queue a request for rate-limited execution"""
        request = {
            'function': function,
            'args': args,
            'kwargs': kwargs,
            'callback': callback,
            'timestamp': time.time()
        }
        
        await self.request_queues[endpoint].put(request)
    
    def update_rate_limit_info(self, endpoint: str, response_headers: Dict[str, str]):
        """Update rate limit information from Discord response headers"""
        if 'X-RateLimit-Remaining' in response_headers:
            self.rate_limits[endpoint].update({
                'remaining': int(response_headers['X-RateLimit-Remaining']),
                'reset_time': float(response_headers.get('X-RateLimit-Reset', time.time())),
                'bucket': response_headers.get('X-RateLimit-Bucket')
            })


class CacheManager:
    """Redis-based caching system for scalability"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis = None
        self.logger = logging.getLogger('CacheManager')
        
        # Cache TTL configurations (in seconds)
        self.ttl_config = {
            'user_data': 300,      # 5 minutes
            'guild_data': 600,     # 10 minutes  
            'command_stats': 1800, # 30 minutes
            'economy_data': 180,   # 3 minutes
            'fishing_data': 240,   # 4 minutes
            'temp_data': 60        # 1 minute
        }
    
    async def connect(self):
        """Connect to Redis"""
        try:
            # Try new aioredis API first
            try:
                self.redis = redis.Redis.from_url(self.redis_url)
            except AttributeError:
                # Fallback to older API
                self.redis = await redis.from_url(self.redis_url)
            
            await self.redis.ping()
            self.logger.info("Connected to Redis cache")
            self.redis_available = True
        except Exception as e:
            self.logger.info(f"Redis not available ({e}). Using efficient in-memory cache")
            self.redis = None
            self.redis_available = False
    
    async def get(self, key: str, default=None) -> Any:
        """Get value from cache"""
        if not self.redis:
            return default
        
        try:
            value = await self.redis.get(key)
            if value:
                return json.loads(value)
            return default
        except Exception as e:
            self.logger.error(f"Cache get error for {key}: {e}")
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None, category: str = 'temp_data'):
        """Set value in cache with TTL"""
        if not self.redis:
            return False
        
        try:
            serialized = json.dumps(value, default=str)
            ttl = ttl or self.ttl_config.get(category, 60)
            await self.redis.setex(key, ttl, serialized)
            return True
        except Exception as e:
            self.logger.error(f"Cache set error for {key}: {e}")
            return False
    
    async def delete(self, key: str):
        """Delete value from cache"""
        if not self.redis:
            return False
        
        try:
            await self.redis.delete(key)
            return True
        except Exception as e:
            self.logger.error(f"Cache delete error for {key}: {e}")
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.redis:
            return False
        
        try:
            return bool(await self.redis.exists(key))
        except Exception as e:
            self.logger.error(f"Cache exists error for {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1, ttl: Optional[int] = None):
        """Increment a counter in cache"""
        if not self.redis:
            return 0
        
        try:
            result = await self.redis.incrby(key, amount)
            if ttl:
                await self.redis.expire(key, ttl)
            return result
        except Exception as e:
            self.logger.error(f"Cache increment error for {key}: {e}")
            return 0
    
    async def get_or_set(self, key: str, fetch_function, ttl: Optional[int] = None, category: str = 'temp_data'):
        """Get from cache or fetch and cache the result"""
        # Try to get from cache first
        cached_value = await self.get(key)
        if cached_value is not None:
            return cached_value
        
        # Fetch the value
        try:
            value = await fetch_function()
            await self.set(key, value, ttl, category)
            return value
        except Exception as e:
            self.logger.error(f"Fetch function error for {key}: {e}")
            return None
    
    async def clear_pattern(self, pattern: str):
        """Clear all keys matching a pattern"""
        if not self.redis:
            return 0
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            self.logger.error(f"Cache clear pattern error for {pattern}: {e}")
            return 0


class BackgroundTaskManager:
    """Enhanced background task management system"""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger('BackgroundTaskManager')
        self.tasks = {}
        self.task_stats = defaultdict(lambda: {
            'runs': 0,
            'errors': 0,
            'last_run': None,
            'last_error': None,
            'avg_duration': 0,
            'durations': deque(maxlen=100)
        })
    
    def register_task(self, name: str, coro, interval: int, **kwargs):
        """Register a background task with enhanced monitoring"""
        
        async def wrapped_task():
            while True:
                start_time = time.time()
                try:
                    await coro()
                    
                    # Update stats
                    duration = time.time() - start_time
                    stats = self.task_stats[name]
                    stats['runs'] += 1
                    stats['last_run'] = datetime.now().isoformat()
                    stats['durations'].append(duration)
                    stats['avg_duration'] = sum(stats['durations']) / len(stats['durations'])
                    
                except Exception as e:
                    self.task_stats[name]['errors'] += 1
                    self.task_stats[name]['last_error'] = str(e)
                    self.logger.error(f"Background task {name} error: {e}")
                
                await asyncio.sleep(interval)
        
        task = asyncio.create_task(wrapped_task())
        self.tasks[name] = {
            'task': task,
            'interval': interval,
            'kwargs': kwargs
        }
        
        self.logger.info(f"Registered background task: {name} (interval: {interval}s)")
        return task
    
    def get_task_stats(self) -> Dict[str, Dict]:
        """Get statistics for all background tasks"""
        return dict(self.task_stats)
    
    async def stop_task(self, name: str):
        """Stop a specific background task"""
        if name in self.tasks:
            self.tasks[name]['task'].cancel()
            del self.tasks[name]
            self.logger.info(f"Stopped background task: {name}")
    
    async def stop_all_tasks(self):
        """Stop all background tasks"""
        for name in list(self.tasks.keys()):
            await self.stop_task(name)


class ScalabilityManager:
    """Main scalability management system"""
    
    def __init__(self, bot, redis_url: str = "redis://localhost:6379"):
        self.bot = bot
        self.logger = logging.getLogger('ScalabilityManager')
        
        # Initialize managers
        self.cache = CacheManager(redis_url)
        self.rate_limiter = RateLimitManager(bot)
        self.task_manager = BackgroundTaskManager(bot)
        
        # Performance metrics
        self.metrics = {
            'requests_queued': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'rate_limits_hit': 0,
            'background_tasks': 0
        }
    
    async def initialize(self):
        """Initialize all scalability components"""
        await self.cache.connect()
        
        # Register optimized background tasks
        self.register_optimized_tasks()
        
        self.logger.info("Scalability manager initialized")
    
    def register_optimized_tasks(self):
        """Register optimized background tasks to prevent rate limits"""
        
        # Roulette message editing (reduced frequency)
        async def optimized_roulette_edits():
            """Process roulette message edits with rate limiting"""
            if hasattr(self.bot, 'get_cog'):
                gambling_cog = self.bot.get_cog('Gambling')
                if gambling_cog and hasattr(gambling_cog, 'process_message_edits'):
                    await gambling_cog.process_message_edits()
        
        # VoteBan message editing (reduced frequency)  
        async def optimized_voteban_edits():
            """Process voteban message edits with rate limiting"""
            if hasattr(self.bot, 'get_cog'):
                voteban_cog = self.bot.get_cog('VoteBans')
                if voteban_cog and hasattr(voteban_cog, 'process_message_edits'):
                    await voteban_cog.process_message_edits()
        
        # AutoFishing processing (optimized)
        async def optimized_autofishing():
            """Process autofishing with distributed load"""
            if hasattr(self.bot, 'get_cog'):
                autofishing_cog = self.bot.get_cog('AutoFishing')
                if autofishing_cog and hasattr(autofishing_cog, 'process_all_autofishing'):
                    await autofishing_cog.process_all_autofishing()
        
        # Cache cleanup
        async def cache_cleanup():
            """Clean up expired cache entries"""
            await self.cache.clear_pattern("temp:*")
        
        # Register tasks with optimized intervals
        self.task_manager.register_task('roulette_edits', optimized_roulette_edits, 3)  # Every 3 seconds
        self.task_manager.register_task('voteban_edits', optimized_voteban_edits, 15)   # Every 15 seconds  
        self.task_manager.register_task('autofishing', optimized_autofishing, 30)       # Every 30 seconds
        self.task_manager.register_task('cache_cleanup', cache_cleanup, 300)            # Every 5 minutes
    
    async def queue_discord_request(self, endpoint: str, function, *args, **kwargs):
        """Queue a Discord API request for rate-limited execution"""
        await self.rate_limiter.queue_request(endpoint, function, *args, **kwargs)
        self.metrics['requests_queued'] += 1
    
    async def get_cached_data(self, key: str, fetch_function, ttl: int = None, category: str = 'temp_data'):
        """Get data from cache or fetch and cache it"""
        result = await self.cache.get_or_set(key, fetch_function, ttl, category)
        
        if await self.cache.exists(key):
            self.metrics['cache_hits'] += 1
        else:
            self.metrics['cache_misses'] += 1
        
        return result
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scalability metrics"""
        task_stats = self.task_manager.get_task_stats()
        
        cache_status = 'redis' if self.cache.redis else 'memory'
        
        return {
            'performance': self.metrics,
            'cache_status': cache_status,
            'background_tasks': len(self.task_manager.tasks),
            'task_statistics': task_stats,
            'rate_limit_status': {
                'global_active': self.rate_limiter.global_rate_limit['active'],
                'queued_requests': sum(q.qsize() for q in self.rate_limiter.request_queues.values())
            }
        }
    
    async def shutdown(self):
        """Gracefully shutdown all scalability components"""
        await self.task_manager.stop_all_tasks()
        
        if self.cache.redis:
            await self.cache.redis.close()
        
        self.logger.info("Scalability manager shutdown complete")


# Global scalability manager instance
scalability_manager = None

async def initialize_scalability(bot, redis_url: str = "redis://localhost:6379"):
    """Initialize the global scalability manager"""
    global scalability_manager
    scalability_manager = ScalabilityManager(bot, redis_url)
    await scalability_manager.initialize()
    return scalability_manager
