"""Cache service for Redis operations."""
import redis.asyncio as redis
from typing import Optional, Any
import json
from datetime import timedelta, date, datetime
from decimal import Decimal


class CacheService:
    """Service for managing Redis cache operations."""
    
    def __init__(self, redis_client: redis.Redis):
        """Initialize cache service with Redis client.
        
        Args:
            redis_client: Async Redis client instance
        """
        self.redis = redis_client
        self.default_ttl = timedelta(minutes=15)
    
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value.
        
        Args:
            key: Cache key to retrieve
            
        Returns:
            Cached value if exists, None otherwise
        """
        value = await self.redis.get(key)
        return json.loads(value) if value else None
    
    async def set(self, key: str, value: Any, ttl: Optional[timedelta] = None) -> None:
        """Store value in cache with TTL.
        
        Args:
            key: Cache key to store
            value: Value to cache (will be JSON serialized)
            ttl: Time to live for the cached value (defaults to 15 minutes)
        """
        ttl = ttl or self.default_ttl
        await self.redis.setex(key, int(ttl.total_seconds()), json.dumps(value, default=self._json_serializer))
    
    async def delete(self, key: str) -> None:
        """Remove cached value.
        
        Args:
            key: Cache key to delete
        """
        await self.redis.delete(key)
    
    async def delete_pattern(self, pattern: str) -> None:
        """Remove all keys matching pattern.
        
        Args:
            pattern: Redis key pattern (e.g., "expenses:*")
        """
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)
    
    @staticmethod
    def _json_serializer(obj: Any) -> Any:
        """Custom JSON serializer for objects not serializable by default.
        
        Args:
            obj: Object to serialize
            
        Returns:
            Serializable representation of the object
        """
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
