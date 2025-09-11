"""
Distributed locking utility for preventing race conditions in collection creation.

This module provides a simple distributed locking mechanism using file-based locks
as a fallback when Redis is not available, with future Redis implementation ready.
"""

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Optional

logger = logging.getLogger(__name__)


class DistributedLock:
    """
    Distributed lock implementation with file-based fallback.
    
    This class provides distributed locking to prevent race conditions
    during collection creation. Uses file-based locks as fallback when
    Redis is not available.
    """
    
    def __init__(self, lock_key: str, timeout_seconds: int = 30):
        """
        Initialize the distributed lock.
        
        Args:
            lock_key: Unique key for the lock (e.g., collection handle)
            timeout_seconds: Lock timeout in seconds
        """
        self.lock_key = lock_key.replace("/", "_").replace(":", "_")  # Sanitize for filename
        self.timeout_seconds = timeout_seconds
        self.lock_file = f"/tmp/shopify_collection_lock_{self.lock_key}.lock"
        self.acquired = False
        self.start_time: Optional[float] = None
    
    async def acquire(self) -> bool:
        """
        Acquire the distributed lock.
        
        Returns:
            bool: True if lock was acquired, False if already locked
        """
        try:
            # Check if lock file exists and is still valid
            if os.path.exists(self.lock_file):
                try:
                    with open(self.lock_file, 'r') as f:
                        lock_time = float(f.read().strip())
                    
                    # Check if lock has expired
                    if time.time() - lock_time < self.timeout_seconds:
                        logger.debug(f"Lock '{self.lock_key}' already acquired and valid")
                        return False
                    else:
                        logger.debug(f"Lock '{self.lock_key}' expired, removing stale lock")
                        os.remove(self.lock_file)
                except (ValueError, OSError):
                    # Invalid lock file, remove it
                    try:
                        os.remove(self.lock_file)
                    except OSError:
                        pass
            
            # Try to acquire the lock
            self.start_time = time.time()
            
            # Use exclusive creation to prevent race conditions
            try:
                with open(self.lock_file, 'x') as f:  # 'x' mode fails if file exists
                    f.write(str(self.start_time))
                
                self.acquired = True
                logger.debug(f"✅ Acquired lock '{self.lock_key}'")
                return True
                
            except FileExistsError:
                # Another process acquired the lock between our checks
                logger.debug(f"❌ Failed to acquire lock '{self.lock_key}' - race condition")
                return False
        
        except Exception as e:
            logger.error(f"Error acquiring lock '{self.lock_key}': {e}")
            return False
    
    async def release(self):
        """Release the distributed lock."""
        if self.acquired and os.path.exists(self.lock_file):
            try:
                os.remove(self.lock_file)
                self.acquired = False
                duration = time.time() - (self.start_time or 0)
                logger.debug(f"🔓 Released lock '{self.lock_key}' (held for {duration:.2f}s)")
            except OSError as e:
                logger.warning(f"Failed to release lock '{self.lock_key}': {e}")
    
    async def is_expired(self) -> bool:
        """Check if the current lock has expired."""
        if not self.acquired or not self.start_time:
            return True
        
        return time.time() - self.start_time >= self.timeout_seconds
    
    async def extend_lock(self) -> bool:
        """
        Extend the lock timeout (renew).
        
        Returns:
            bool: True if lock was extended successfully
        """
        if not self.acquired:
            return False
        
        try:
            self.start_time = time.time()
            with open(self.lock_file, 'w') as f:
                f.write(str(self.start_time))
            
            logger.debug(f"🔄 Extended lock '{self.lock_key}'")
            return True
            
        except Exception as e:
            logger.error(f"Failed to extend lock '{self.lock_key}': {e}")
            return False


@asynccontextmanager
async def collection_lock(collection_handle: str, timeout_seconds: int = 30):
    """
    Context manager for distributed collection locking.
    
    Args:
        collection_handle: Collection handle to lock on
        timeout_seconds: Lock timeout in seconds
        
    Usage:
        async with collection_lock("my-collection-handle") as lock:
            if lock:
                # Lock acquired, safe to create collection
                pass
            else:
                # Lock not acquired, collection being processed elsewhere
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


class LockManager:
    """
    Manager for handling multiple distributed locks with auto-renewal.
    """
    
    def __init__(self):
        self.locks = {}
        self._renewal_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start the lock manager with auto-renewal."""
        if self._running:
            return
        
        self._running = True
        self._renewal_task = asyncio.create_task(self._renewal_loop())
        logger.info("🔧 Started distributed lock manager")
    
    async def stop(self):
        """Stop the lock manager and release all locks."""
        self._running = False
        
        if self._renewal_task:
            self._renewal_task.cancel()
            try:
                await self._renewal_task
            except asyncio.CancelledError:
                pass
        
        # Release all locks
        for lock in list(self.locks.values()):
            await lock.release()
        
        self.locks.clear()
        logger.info("🛑 Stopped distributed lock manager")
    
    async def acquire_lock(self, key: str, timeout_seconds: int = 30) -> bool:
        """
        Acquire a lock and manage it.
        
        Args:
            key: Lock key
            timeout_seconds: Lock timeout
            
        Returns:
            bool: True if acquired
        """
        if key in self.locks:
            return True  # Already have this lock
        
        lock = DistributedLock(key, timeout_seconds)
        acquired = await lock.acquire()
        
        if acquired:
            self.locks[key] = lock
        
        return acquired
    
    async def release_lock(self, key: str):
        """Release a managed lock."""
        if key in self.locks:
            lock = self.locks.pop(key)
            await lock.release()
    
    async def _renewal_loop(self):
        """Auto-renewal loop for all managed locks."""
        while self._running:
            try:
                # Renew locks that are close to expiring
                for key, lock in list(self.locks.items()):
                    if lock.acquired and lock.start_time:
                        time_held = time.time() - lock.start_time
                        # Renew when 75% of timeout has passed
                        if time_held > (lock.timeout_seconds * 0.75):
                            success = await lock.extend_lock()
                            if not success:
                                logger.warning(f"Failed to renew lock: {key}")
                                self.locks.pop(key, None)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in lock renewal loop: {e}")
                await asyncio.sleep(5)


# Global lock manager instance
_lock_manager: Optional[LockManager] = None


async def get_lock_manager() -> LockManager:
    """Get or create the global lock manager."""
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