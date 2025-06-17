"""
Cache management system for storing and retrieving cached data.

This module provides a unified interface for caching operations,
supporting both in-memory and Redis-based caching strategies.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

# In-memory cache fallback
_memory_cache: Dict[str, Dict[str, Any]] = {}
_cache_initialized = False


async def initialize_cache():
    """
    Initialize the cache management system.
    """
    global _cache_initialized

    try:
        logger.info("Initializing cache management system")

        # Try to use Redis if available, otherwise use memory cache
        if settings.REDIS_URL:
            try:
                from app.core.redis_client import test_redis_connection

                if await test_redis_connection():
                    logger.info("Using Redis for caching")
                else:
                    logger.warning("Redis not available, using memory cache")
            except Exception as e:
                logger.warning(f"Redis initialization failed, using memory cache: {e}")
        else:
            logger.info("Redis not configured, using memory cache")

        _cache_initialized = True
        logger.info("Cache management system initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize cache management: {e}")
        raise


async def get_cached_data(key: str) -> Optional[Any]:
    """
    Retrieve cached data by key.

    Args:
        key: Cache key

    Returns:
        Cached data or None if not found/expired
    """
    try:
        if not _cache_initialized:
            return None

        # Try Redis first if available
        if settings.REDIS_URL:
            try:
                from app.core.redis_client import get_cache

                cached_value = await get_cache(key)
                if cached_value:
                    return json.loads(cached_value)
            except Exception as e:
                logger.debug(f"Redis cache miss for key {key}: {e}")

        # Fallback to memory cache
        if key in _memory_cache:
            cache_entry = _memory_cache[key]

            # Check expiration
            if cache_entry.get("expires_at"):
                if datetime.now(timezone.utc).timestamp() > cache_entry["expires_at"]:
                    del _memory_cache[key]
                    return None

            return cache_entry["data"]

        return None

    except Exception as e:
        logger.error(f"Error retrieving cached data for key {key}: {e}")
        return None


async def set_cached_data(key: str, data: Any, ttl_seconds: Optional[int] = None) -> bool:
    """
    Store data in cache with optional TTL.

    Args:
        key: Cache key
        data: Data to cache
        ttl_seconds: Time to live in seconds

    Returns:
        bool: True if successful
    """
    try:
        if not _cache_initialized:
            return False

        # Calculate expiration
        expires_at = None
        if ttl_seconds:
            expires_at = datetime.now(timezone.utc).timestamp() + ttl_seconds

        # Try Redis first if available
        if settings.REDIS_URL:
            try:
                from app.core.redis_client import set_cache

                json_data = json.dumps(data, default=str)
                success = await set_cache(key, json_data, ttl_seconds)
                if success:
                    return True
            except Exception as e:
                logger.debug(f"Redis cache set failed for key {key}: {e}")

        # Fallback to memory cache
        _memory_cache[key] = {
            "data": data,
            "created_at": datetime.now(timezone.utc).timestamp(),
            "expires_at": expires_at,
        }

        # Clean up expired entries periodically
        await _cleanup_expired_memory_cache()

        return True

    except Exception as e:
        logger.error(f"Error setting cached data for key {key}: {e}")
        return False


async def delete_cached_data(key: str) -> bool:
    """
    Delete cached data by key.

    Args:
        key: Cache key to delete

    Returns:
        bool: True if successful
    """
    try:
        if not _cache_initialized:
            return False

        # Try Redis first if available
        if settings.REDIS_URL:
            try:
                from app.core.redis_client import delete_cache

                await delete_cache(key)
            except Exception as e:
                logger.debug(f"Redis cache delete failed for key {key}: {e}")

        # Remove from memory cache
        if key in _memory_cache:
            del _memory_cache[key]

        return True

    except Exception as e:
        logger.error(f"Error deleting cached data for key {key}: {e}")
        return False


async def clear_cache_pattern(pattern: str) -> int:
    """
    Clear cached data matching a pattern.

    Args:
        pattern: Pattern to match (simple string matching)

    Returns:
        int: Number of keys cleared
    """
    try:
        if not _cache_initialized:
            return 0

        cleared_count = 0

        # Clear from memory cache
        keys_to_delete = [key for key in _memory_cache.keys() if pattern in key]
        for key in keys_to_delete:
            del _memory_cache[key]
            cleared_count += 1

        # TODO: Implement Redis pattern clearing if needed

        logger.info(f"Cleared {cleared_count} cache entries matching pattern: {pattern}")
        return cleared_count

    except Exception as e:
        logger.error(f"Error clearing cache pattern {pattern}: {e}")
        return 0


async def clear_all_cache():
    """
    Clear all cached data.
    """
    try:
        if not _cache_initialized:
            return

        # Clear memory cache
        initial_count = len(_memory_cache)
        _memory_cache.clear()

        # TODO: Clear Redis cache if needed

        logger.info(f"Cleared all cache data ({initial_count} memory entries)")

    except Exception as e:
        logger.error(f"Error clearing all cache: {e}")


async def get_cache_stats() -> Dict[str, Any]:
    """
    Get cache statistics.

    Returns:
        Dict: Cache statistics
    """
    try:
        if not _cache_initialized:
            return {"status": "not_initialized"}

        # Memory cache stats
        memory_stats = {
            "total_keys": len(_memory_cache),
            "expired_keys": 0,
        }

        # Count expired keys
        current_time = datetime.now(timezone.utc).timestamp()
        for cache_entry in _memory_cache.values():
            if cache_entry.get("expires_at") and current_time > cache_entry["expires_at"]:
                memory_stats["expired_keys"] += 1

        stats = {
            "status": "active",
            "backend": "redis" if settings.REDIS_URL else "memory",
            "memory_cache": memory_stats,
        }

        # TODO: Add Redis stats if available

        return stats

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return {"error": str(e)}


async def _cleanup_expired_memory_cache():
    """
    Clean up expired entries from memory cache.
    """
    try:
        current_time = datetime.now(timezone.utc).timestamp()
        expired_keys = []

        for key, cache_entry in _memory_cache.items():
            if cache_entry.get("expires_at") and current_time > cache_entry["expires_at"]:
                expired_keys.append(key)

        for key in expired_keys:
            del _memory_cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    except Exception as e:
        logger.error(f"Error cleaning up expired cache entries: {e}")


# Cache helper functions for common operations
async def cache_product_data(product_id: str, product_data: Dict[str, Any], ttl: int = 3600):
    """
    Cache product data with a 1-hour default TTL.

    Args:
        product_id: Product identifier
        product_data: Product information
        ttl: Time to live in seconds
    """
    await set_cached_data(f"product:{product_id}", product_data, ttl)


async def get_cached_product_data(product_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached product data.

    Args:
        product_id: Product identifier

    Returns:
        Product data or None if not cached
    """
    return await get_cached_data(f"product:{product_id}")


async def cache_sync_result(sync_id: str, result_data: Dict[str, Any], ttl: int = 86400):
    """
    Cache sync operation result with a 24-hour default TTL.

    Args:
        sync_id: Sync operation identifier
        result_data: Sync result information
        ttl: Time to live in seconds
    """
    await set_cached_data(f"sync_result:{sync_id}", result_data, ttl)


async def get_cached_sync_result(sync_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve cached sync result.

    Args:
        sync_id: Sync operation identifier

    Returns:
        Sync result data or None if not cached
    """
    return await get_cached_data(f"sync_result:{sync_id}")

