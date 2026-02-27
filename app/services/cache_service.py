"""Cache service for Redis-based caching."""
import json
from datetime import timedelta
from typing import Any, Optional


class CacheService:
    """Service for caching data in Redis."""
    
    def __init__(self, redis_client, default_ttl: timedelta = timedelta(minutes=15)):
        """
        Initialize cache service.
        
        Args:
            redis_client: Redis client instance (can be real Redis or FakeRedis)
            default_ttl: Default time-to-live for cached items
        """
        self.redis = redis_client
        self.default_ttl = default_ttl
    
    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """
        Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache (will be JSON serialized)
            ttl: Time-to-live for the cached item (uses default_ttl if not provided)
        """
        ttl = ttl or self.default_ttl
        serialized_value = json.dumps(value)
        await self.redis.setex(key, int(ttl.total_seconds()), serialized_value)
    
    async def get(self, key: str) -> Optional[Any]:
        """
        Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value (JSON deserialized) or None if not found
        """
        value = await self.redis.get(key)
        if value is None:
            return None
        return json.loads(value)
    
    async def delete(self, key: str) -> None:
        """
        Delete a value from the cache.
        
        Args:
            key: Cache key to delete
        """
        await self.redis.delete(key)
    
    async def delete_pattern(self, pattern: str) -> None:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "expense:*")
        """
        # Scan for keys matching the pattern
        keys = []
        async for key in self.redis.scan_iter(match=pattern):
            keys.append(key)
        
        # Delete all matching keys
        if keys:
            await self.redis.delete(*keys)
