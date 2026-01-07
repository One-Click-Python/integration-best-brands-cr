"""
OrderLock - Distributed Lock for Shopify Order Processing.

Prevents concurrent processing of the same Shopify order from multiple sources:
- Order polling (scheduled every 10 minutes)
- Webhook handlers (orders/create, orders/updated)
- Manual API triggers

This lock is CRITICAL for preventing duplicate order creation in RMS.
Without it, race conditions between polling and webhooks can create
two RMS orders for the same Shopify order.

Usage:
    from app.utils.order_lock import OrderLock, LockAcquisitionError

    async with OrderLock("6283579359292") as lock:
        # Only one process can execute this block for this order
        await sync_order_to_rms(order_data)
"""

import logging

from app.utils.distributed_lock import DistributedLock, LockAcquisitionError

logger = logging.getLogger(__name__)

# Re-export for convenience
__all__ = ["OrderLock", "LockAcquisitionError"]


class OrderLock(DistributedLock):
    """
    Specialized distributed lock for Shopify order operations.

    Prevents concurrent processing of the same Shopify order across all
    entry points (polling, webhooks, manual API).

    Features:
    - Redis-based locking with file-based fallback
    - Automatic expiration (prevents deadlocks)
    - Token-based release (prevents accidental unlocks)
    - Fast retry with exponential backoff

    Example:
        ```python
        from app.utils.order_lock import OrderLock, LockAcquisitionError

        try:
            async with OrderLock(shopify_order_id="6283579359292") as lock:
                # Protected section - only one process at a time
                await process_order(order_data)
        except LockAcquisitionError as e:
            logger.warning(f"Order being processed elsewhere: {e}")
            # Skip this order, another process is handling it
        ```

    Notes:
        - Lock key format: `lock:order:{numeric_id}` in Redis
        - Default timeout: 120 seconds (sufficient for order sync)
        - Max wait time: ~6 seconds before giving up
        - Use shorter timeout for simple checks, longer for full sync
    """

    def __init__(self, shopify_order_id: str, timeout_seconds: int = 120):
        """
        Initialize order lock.

        Args:
            shopify_order_id: Shopify order ID (supports both formats):
                - Numeric: "6283579359292"
                - GID: "gid://shopify/Order/6283579359292"
            timeout_seconds: Lock TTL in seconds (default: 120)
                - Prevents deadlocks if process crashes
                - Should be longer than typical order sync time
        """
        # Normalize ID - extract numeric part from GID if present
        if "Order/" in shopify_order_id:
            numeric_id = shopify_order_id.split("Order/")[-1]
        else:
            numeric_id = shopify_order_id

        # Initialize parent with order-specific settings
        super().__init__(
            lock_key=f"order:{numeric_id}",
            timeout_seconds=timeout_seconds,
            retry_delay=0.2,  # Fast initial retry (200ms)
            max_retries=30,  # ~6 seconds max wait with backoff
            use_redis=True,  # Prefer Redis, fallback to file
        )

        self.shopify_order_id = numeric_id

    async def __aenter__(self):
        """Acquire lock with enhanced logging for order operations."""
        logger.debug(f"Attempting to acquire lock for Shopify order {self.shopify_order_id}")
        result = await super().__aenter__()
        logger.debug(f"Lock acquired for Shopify order {self.shopify_order_id}")
        return result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Release lock with enhanced logging for order operations."""
        result = await super().__aexit__(exc_type, exc_val, exc_tb)
        if exc_type:
            logger.debug(
                f"Lock released for Shopify order {self.shopify_order_id} " f"(exception occurred: {exc_type.__name__})"
            )
        else:
            logger.debug(f"Lock released for Shopify order {self.shopify_order_id}")
        return result
