"""
Distributed Lock Implementation using Redis.

Provides thread-safe and process-safe locking mechanism to prevent race conditions
in distributed systems. Uses Redis SET with NX (not exists) and EX (expiry) options
to ensure atomic lock acquisition and automatic release on timeout.

Key Features:
- Atomic lock acquisition (SET NX)
- Auto-expiration (prevents deadlocks)
- Token-based release (prevents accidental unlocks)
- Context manager support (async with)
- File-based fallback when Redis unavailable

Usage:
    async with DistributedLock("product:123", timeout=300) as lock:
        # Critical section - only one process can execute this
        await process_product(product_id="123")
"""

import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class LockAcquisitionError(Exception):
    """Raised when lock cannot be acquired within timeout."""

    def __init__(self, key: str, waited: float):
        self.key = key
        self.waited = waited
        super().__init__(f"Could not acquire lock '{key}' after {waited:.2f}s")


class DistributedLock:
    """
    Redis-based distributed lock with file-based fallback.

    This implementation follows best practices for distributed locking:
    1. Atomic acquisition using Redis SET NX (or file exclusive create)
    2. Automatic expiration to prevent deadlocks
    3. Token-based release to prevent accidental unlocks
    4. Exponential backoff for retry attempts
    5. File-based fallback when Redis is unavailable

    Args:
        lock_key: Lock identifier (e.g., "product:123", "sync:reverse")
        timeout_seconds: Lock TTL in seconds (default: 300 = 5 minutes)
        retry_delay: Initial delay between retry attempts in seconds (default: 0.1)
        max_retries: Maximum number of acquisition attempts (default: 50)
        use_redis: Whether to prefer Redis over file-based locks (default: True)

    Example:
        ```python
        async with DistributedLock("product:123", timeout_seconds=300):
            # Only one process can execute this block at a time
            await update_product_inventory(product_id="123")
        ```

    Note:
        - Lock is automatically released on exit (success or exception)
        - If process crashes, lock expires after `timeout_seconds`
        - Use shorter timeout for fast operations, longer for slow operations
    """

    def __init__(
        self,
        lock_key: str,
        timeout_seconds: int = 300,
        retry_delay: float = 0.1,
        max_retries: int = 50,
        use_redis: bool = True,
    ):
        """
        Initialize distributed lock.

        Args:
            lock_key: Unique lock identifier
            timeout_seconds: Lock expiration time in seconds (prevents deadlocks)
            retry_delay: Initial delay between retries (exponential backoff)
            max_retries: Maximum acquisition attempts before raising error
            use_redis: Whether to use Redis (True) or file-based (False) locking
        """
        self.lock_key = lock_key.replace("/", "_").replace(":", "_")  # Sanitize for filename
        self.redis_key = f"lock:{lock_key}"
        self.timeout_seconds = timeout_seconds
        self.retry_delay = retry_delay
        self.max_retries = max_retries
        self.use_redis = use_redis
        self.token = str(uuid.uuid4())  # Unique token for this lock instance
        self.acquired = False
        self.start_time: Optional[float] = None
        self.redis_client = None

        # File-based fallback
        self.lock_file = f"/tmp/shopify_lock_{self.lock_key}.lock"

        # Try to get Redis client if available
        if self.use_redis:
            try:
                from app.core.redis_client import get_redis_client

                self.redis_client = get_redis_client()
            except Exception as e:
                logger.warning(f"Redis not available, falling back to file-based lock: {e}")
                self.use_redis = False

    async def __aenter__(self):
        """Acquire lock when entering context."""
        await self.acquire()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release lock when exiting context (even on exception)."""
        await self.release()
        return False  # Don't suppress exceptions

    async def acquire(self) -> bool:
        """
        Attempt to acquire lock with exponential backoff retry.

        Returns:
            True if lock acquired successfully

        Raises:
            LockAcquisitionError: If lock cannot be acquired after max_retries
        """
        start_time = time.time()
        current_delay = self.retry_delay

        for attempt in range(self.max_retries):
            try:
                if self.use_redis and self.redis_client:
                    acquired = await self._acquire_redis()
                else:
                    acquired = await self._acquire_file()

                if acquired:
                    self.acquired = True
                    self.start_time = time.time()
                    elapsed = self.start_time - start_time
                    logger.debug(
                        f"🔒 Lock acquired: {self.lock_key} "
                        f"(attempt {attempt + 1}, waited {elapsed:.2f}s, "
                        f"method: {'Redis' if self.use_redis else 'file'})"
                    )
                    return True

                # Lock already held by another process, retry with backoff
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(current_delay)
                    current_delay = min(current_delay * 2, 5.0)  # Max 5s delay

            except Exception as e:
                logger.error(f"Error acquiring lock {self.lock_key}: {e}")
                raise

        # Failed to acquire lock after all retries
        elapsed = time.time() - start_time
        raise LockAcquisitionError(self.lock_key, elapsed)

    async def _acquire_redis(self) -> bool:
        """Acquire lock using Redis SET NX."""
        try:
            # Try to set key with NX (only if not exists) and EX (expiry)
            acquired = await self.redis_client.set(
                self.redis_key,
                self.token,
                nx=True,  # Only set if key doesn't exist
                ex=self.timeout_seconds,  # Expire after timeout seconds
            )
            return bool(acquired)
        except Exception as e:
            logger.warning(f"Redis lock acquisition failed, falling back to file: {e}")
            self.use_redis = False
            return await self._acquire_file()

    async def _acquire_file(self) -> bool:
        """Acquire lock using file exclusive create."""
        try:
            # Check if lock file exists and is still valid
            if os.path.exists(self.lock_file):
                try:
                    with open(self.lock_file, "r") as f:
                        data = f.read().strip().split("|")
                        lock_time = float(data[0])
                        _ = data[1] if len(data) > 1 else ""  # token (unused)

                    # Check if lock has expired
                    if time.time() - lock_time < self.timeout_seconds:
                        logger.debug(f"Lock '{self.lock_key}' already acquired and valid")
                        return False
                    else:
                        logger.debug(f"Lock '{self.lock_key}' expired, removing stale lock")
                        os.remove(self.lock_file)
                except (ValueError, OSError, IndexError):
                    # Invalid lock file, remove it
                    try:
                        os.remove(self.lock_file)
                    except OSError:
                        pass

            # Try to acquire the lock with exclusive creation
            try:
                with open(self.lock_file, "x") as f:  # 'x' mode fails if file exists
                    f.write(f"{time.time()}|{self.token}")
                return True
            except FileExistsError:
                # Another process acquired the lock between our checks
                return False

        except Exception as e:
            logger.error(f"File lock acquisition failed: {e}")
            return False

    async def release(self) -> bool:
        """
        Release lock using atomic check-and-delete.

        Only releases if the token matches (prevents releasing someone else's lock).

        Returns:
            True if lock was released, False if lock was already released or held by another
        """
        if not self.acquired:
            return False

        try:
            if self.use_redis and self.redis_client:
                result = await self._release_redis()
            else:
                result = await self._release_file()

            if result:
                self.acquired = False
                if self.start_time:
                    held_duration = time.time() - self.start_time
                    logger.debug(
                        f"🔓 Lock released: {self.lock_key} "
                        f"(held for {held_duration:.2f}s, "
                        f"method: {'Redis' if self.use_redis else 'file'})"
                    )
                return True
            else:
                logger.warning(
                    f"⚠️ Lock release failed: {self.lock_key} " f"(already released or held by another process)"
                )
                return False

        except Exception as e:
            logger.error(f"Error releasing lock {self.lock_key}: {e}")
            return False

    async def _release_redis(self) -> bool:
        """Release lock using Redis Lua script for atomicity."""
        try:
            # Lua script for atomic release (check token before deleting)
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            result = await self.redis_client.eval(lua_script, 1, self.redis_key, self.token)
            return result == 1
        except Exception as e:
            logger.warning(f"Redis lock release failed: {e}")
            return False

    async def _release_file(self) -> bool:
        """Release lock by removing file if token matches."""
        if not os.path.exists(self.lock_file):
            return False

        try:
            # Verify token before deleting
            with open(self.lock_file, "r") as f:
                data = f.read().strip().split("|")
                lock_token = data[1] if len(data) > 1 else ""

            if lock_token == self.token:
                os.remove(self.lock_file)
                return True
            else:
                logger.warning(f"Token mismatch in lock file: {self.lock_key}")
                return False

        except Exception as e:
            logger.error(f"Error releasing file lock: {e}")
            return False

    async def extend(self, additional_time: int) -> bool:
        """
        Extend lock expiration time.

        Args:
            additional_time: Additional seconds to extend lock

        Returns:
            True if lock was extended successfully
        """
        if not self.acquired:
            return False

        try:
            if self.use_redis and self.redis_client:
                return await self._extend_redis(additional_time)
            else:
                return await self._extend_file()
        except Exception as e:
            logger.error(f"Error extending lock {self.lock_key}: {e}")
            return False

    async def _extend_redis(self, additional_time: int) -> bool:
        """Extend Redis lock expiration."""
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await self.redis_client.eval(
            lua_script, 1, self.redis_key, self.token, str(self.timeout_seconds + additional_time)
        )
        if result == 1:
            logger.debug(f"⏰ Lock extended: {self.lock_key} (+{additional_time}s)")
            return True
        return False

    async def _extend_file(self) -> bool:
        """Extend file lock by updating timestamp."""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file, "w") as f:
                    f.write(f"{time.time()}|{self.token}")
                logger.debug(f"🔄 Extended file lock '{self.lock_key}'")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to extend file lock '{self.lock_key}': {e}")
            return False

    @property
    def is_locked(self) -> bool:
        """Check if lock is currently held by this instance."""
        return self.acquired

    @property
    def time_held(self) -> Optional[float]:
        """Get duration lock has been held in seconds."""
        if self.acquired and self.start_time:
            return time.time() - self.start_time
        return None

    async def is_expired(self) -> bool:
        """Check if the current lock has expired."""
        if not self.acquired or not self.start_time:
            return True
        return time.time() - self.start_time >= self.timeout_seconds


# Legacy alias for backwards compatibility
@asynccontextmanager
async def collection_lock(collection_handle: str, timeout_seconds: int = 30):
    """
    Context manager for distributed collection locking (legacy).

    Args:
        collection_handle: Collection handle to lock on
        timeout_seconds: Lock timeout in seconds

    Usage:
        async with collection_lock("my-collection-handle") as lock:
            if lock:
                # Lock acquired, safe to create collection
                pass
    """
    lock = DistributedLock(f"collection:{collection_handle}", timeout_seconds)

    try:
        acquired = await lock.acquire()
        if acquired:
            logger.info(f"🔒 Acquired collection lock for: {collection_handle}")
        else:
            logger.info(f"⏳ Collection lock busy for: {collection_handle}")

        yield acquired

    finally:
        if lock.acquired:
            await lock.release()


class ProductLock(DistributedLock):
    """
    Specialized lock for product operations.

    Example:
        ```python
        async with ProductLock(product_id="gid://shopify/Product/123") as lock:
            await update_product_inventory(product_id)
        ```
    """

    def __init__(self, product_id: str, timeout_seconds: int = 300):
        # Extract numeric ID from GID if needed
        if "Product/" in product_id:
            numeric_id = product_id.split("Product/")[-1]
        else:
            numeric_id = product_id
        super().__init__(lock_key=f"product:{numeric_id}", timeout_seconds=timeout_seconds)


class SyncLock(DistributedLock):
    """
    Global sync operation lock.

    Prevents multiple sync operations from running simultaneously.

    Example:
        ```python
        async with SyncLock(sync_type="reverse", timeout_seconds=1800) as lock:
            await execute_reverse_sync()
        ```
    """

    def __init__(self, sync_type: str, timeout_seconds: int = 1800):
        super().__init__(lock_key=f"sync:{sync_type}", timeout_seconds=timeout_seconds)


# Backwards compatibility - LockManager removed in favor of individual locks
class LockManager:
    """Legacy LockManager for backwards compatibility."""

    def __init__(self):
        logger.warning("LockManager is deprecated, use DistributedLock directly")
        self.locks = {}
        self._running = False

    async def start(self):
        self._running = True

    async def stop(self):
        self._running = False
        for lock in list(self.locks.values()):
            await lock.release()
        self.locks.clear()

    async def acquire_lock(self, key: str, timeout_seconds: int = 30) -> bool:
        if key in self.locks:
            return True
        lock = DistributedLock(key, timeout_seconds)
        acquired = await lock.acquire()
        if acquired:
            self.locks[key] = lock
        return acquired

    async def release_lock(self, key: str):
        if key in self.locks:
            lock = self.locks.pop(key)
            await lock.release()


_lock_manager: Optional[LockManager] = None


async def get_lock_manager() -> LockManager:
    """Get or create the global lock manager (legacy)."""
    global _lock_manager
    if _lock_manager is None:
        _lock_manager = LockManager()
        await _lock_manager.start()
    return _lock_manager


async def cleanup_locks():
    """Cleanup function to call during application shutdown."""
    global _lock_manager
    if _lock_manager:
        await _lock_manager.stop()
        _lock_manager = None
