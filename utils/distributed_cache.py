"""
Distributed caching system using Redis.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, Optional, Union, List, Callable
from dataclasses import dataclass, asdict
from functools import wraps
import redis
from redis.asyncio import Redis as AsyncRedis
from clinicaltrials.config import get_global_config

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cache entry with metadata."""
    value: Any
    timestamp: float
    ttl: int
    hit_count: int = 0
    last_accessed: float = 0.0
    
    def is_expired(self) -> bool:
        """Check if the cache entry is expired."""
        if self.ttl <= 0:
            return False  # Never expires
        return time.time() - self.timestamp > self.ttl
    
    def update_access(self) -> None:
        """Update access metadata."""
        self.hit_count += 1
        self.last_accessed = time.time()


class DistributedCache:
    """
    Distributed caching system with Redis backend.
    
    Features:
    - TTL support
    - Hit count tracking
    - Async/sync support
    - Cache warming
    - Smart invalidation
    - Analytics
    """
    
    def __init__(
        self,
        redis_url: str = "redis://localhost:6379",
        key_prefix: str = "clinical_trials",
        default_ttl: int = 3600,
        max_retries: int = 3
    ):
        self.redis_url = redis_url
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.max_retries = max_retries
        
        # Initialize Redis clients
        self._sync_client = None
        self._async_client = None
        
        # Cache statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
            "invalidations": 0
        }
    
    def _get_sync_client(self) -> redis.Redis:
        """Get or create sync Redis client."""
        if self._sync_client is None:
            self._sync_client = redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
        return self._sync_client
    
    async def _get_async_client(self) -> AsyncRedis:
        """Get or create async Redis client."""
        if self._async_client is None:
            self._async_client = AsyncRedis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
        return self._async_client
    
    def _make_key(self, key: str) -> str:
        """Create a prefixed cache key."""
        return f"{self.key_prefix}:{key}"
    
    def _hash_key(self, data: Union[str, Dict[str, Any]]) -> str:
        """Create a hash key from data."""
        if isinstance(data, str):
            content = data
        else:
            content = json.dumps(data, sort_keys=True)
        return hashlib.md5(content.encode()).hexdigest()
    
    def _serialize_entry(self, entry: CacheEntry) -> str:
        """Serialize cache entry to JSON string."""
        return json.dumps(asdict(entry))
    
    def _deserialize_entry(self, data: str) -> CacheEntry:
        """Deserialize cache entry from JSON string."""
        entry_dict = json.loads(data)
        # Ensure required fields with defaults
        entry_dict.setdefault('hit_count', 0)
        entry_dict.setdefault('last_accessed', 0.0)
        return CacheEntry(**entry_dict)
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache synchronously.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            client = self._get_sync_client()
            cache_key = self._make_key(key)
            
            data = client.get(cache_key)
            if data is None:
                self._stats["misses"] += 1
                return None
            
            entry = self._deserialize_entry(data)
            
            # Check if expired
            if entry.is_expired():
                self._stats["misses"] += 1
                # Remove expired entry
                client.delete(cache_key)
                return None
            
            # Update access metadata
            entry.update_access()
            client.set(cache_key, self._serialize_entry(entry), ex=entry.ttl)
            
            self._stats["hits"] += 1
            return entry.value
            
        except Exception as e:
            logger.error(f"Error getting from cache: {e}")
            self._stats["errors"] += 1
            return None
    
    async def get_async(self, key: str) -> Optional[Any]:
        """
        Get value from cache asynchronously.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        try:
            client = await self._get_async_client()
            cache_key = self._make_key(key)
            
            data = await client.get(cache_key)
            if data is None:
                self._stats["misses"] += 1
                return None
            
            entry = self._deserialize_entry(data)
            
            # Check if expired
            if entry.is_expired():
                self._stats["misses"] += 1
                # Remove expired entry
                await client.delete(cache_key)
                return None
            
            # Update access metadata
            entry.update_access()
            await client.set(cache_key, self._serialize_entry(entry), ex=entry.ttl)
            
            self._stats["hits"] += 1
            return entry.value
            
        except Exception as e:
            logger.error(f"Error getting from async cache: {e}")
            self._stats["errors"] += 1
            return None
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache synchronously.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_sync_client()
            cache_key = self._make_key(key)
            
            if ttl is None:
                ttl = self.default_ttl
            
            entry = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl
            )
            
            client.set(cache_key, self._serialize_entry(entry), ex=ttl)
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            self._stats["errors"] += 1
            return False
    
    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache asynchronously.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_async_client()
            cache_key = self._make_key(key)
            
            if ttl is None:
                ttl = self.default_ttl
            
            entry = CacheEntry(
                value=value,
                timestamp=time.time(),
                ttl=ttl
            )
            
            await client.set(cache_key, self._serialize_entry(entry), ex=ttl)
            self._stats["sets"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error setting async cache: {e}")
            self._stats["errors"] += 1
            return False
    
    def delete(self, key: str) -> bool:
        """
        Delete value from cache synchronously.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            client = self._get_sync_client()
            cache_key = self._make_key(key)
            
            client.delete(cache_key)
            self._stats["invalidations"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")
            self._stats["errors"] += 1
            return False
    
    async def delete_async(self, key: str) -> bool:
        """
        Delete value from cache asynchronously.
        
        Args:
            key: Cache key
            
        Returns:
            True if successful, False otherwise
        """
        try:
            client = await self._get_async_client()
            cache_key = self._make_key(key)
            
            await client.delete(cache_key)
            self._stats["invalidations"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error deleting from async cache: {e}")
            self._stats["errors"] += 1
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate keys matching a pattern synchronously.
        
        Args:
            pattern: Pattern to match (e.g., "mutation:*")
            
        Returns:
            Number of keys invalidated
        """
        try:
            client = self._get_sync_client()
            pattern_key = self._make_key(pattern)
            
            keys = client.keys(pattern_key)
            if keys:
                deleted = client.delete(*keys)
                self._stats["invalidations"] += deleted
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating pattern: {e}")
            self._stats["errors"] += 1
            return 0
    
    async def invalidate_pattern_async(self, pattern: str) -> int:
        """
        Invalidate keys matching a pattern asynchronously.
        
        Args:
            pattern: Pattern to match (e.g., "mutation:*")
            
        Returns:
            Number of keys invalidated
        """
        try:
            client = await self._get_async_client()
            pattern_key = self._make_key(pattern)
            
            keys = await client.keys(pattern_key)
            if keys:
                deleted = await client.delete(*keys)
                self._stats["invalidations"] += deleted
                return deleted
            return 0
            
        except Exception as e:
            logger.error(f"Error invalidating async pattern: {e}")
            self._stats["errors"] += 1
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0
        
        return {
            **self._stats,
            "hit_rate": hit_rate,
            "total_requests": total_requests
        }
    
    async def warm_cache(self, warm_data: Dict[str, Any]) -> int:
        """
        Warm the cache with predefined data.
        
        Args:
            warm_data: Dictionary of key-value pairs to cache
            
        Returns:
            Number of items successfully cached
        """
        successful = 0
        tasks = []
        
        for key, value in warm_data.items():
            task = self.set_async(key, value)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, bool) and result:
                successful += 1
            elif isinstance(result, Exception):
                logger.error(f"Error warming cache: {result}")
        
        logger.info(f"Cache warmed: {successful}/{len(warm_data)} items")
        return successful
    
    def close(self):
        """Close Redis connections."""
        if self._sync_client:
            self._sync_client.close()
        if self._async_client:
            asyncio.create_task(self._async_client.close())


# Global cache instance
_cache_instance: Optional[DistributedCache] = None


def get_cache() -> DistributedCache:
    """Get or create global cache instance."""
    global _cache_instance
    if _cache_instance is None:
        try:
            config = get_global_config()
            redis_url = getattr(config, 'redis_url', 'redis://localhost:6379')
            default_ttl = getattr(config, 'cache_ttl', 3600)
        except:
            # Fallback for testing
            redis_url = 'redis://localhost:6379'
            default_ttl = 3600
        
        _cache_instance = DistributedCache(
            redis_url=redis_url,
            default_ttl=default_ttl
        )
    assert _cache_instance is not None  # Type narrowing
    return _cache_instance


def cached(ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """
    Decorator for caching function results.
    
    Args:
        ttl: Time to live in seconds
        key_func: Function to generate cache key from arguments
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{getattr(func, '__name__', 'unknown')}:{cache._hash_key(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator


def async_cached(ttl: Optional[int] = None, key_func: Optional[Callable] = None):
    """
    Decorator for caching async function results.
    
    Args:
        ttl: Time to live in seconds
        key_func: Function to generate cache key from arguments
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generate cache key
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                cache_key = f"{getattr(func, '__name__', 'unknown')}:{cache._hash_key(str(args) + str(kwargs))}"
            
            # Try to get from cache
            cached_result = await cache.get_async(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache.set_async(cache_key, result, ttl)
            
            return result
        return wrapper
    return decorator