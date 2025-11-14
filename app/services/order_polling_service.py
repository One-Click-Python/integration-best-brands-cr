"""
Order Polling Service - Orchestrator for Shopify order polling and sync.

This service coordinates the complete flow of polling orders from Shopify
and syncing them to RMS as an alternative/complement to webhooks.

Architecture:
- Fetch: OrderPollingClient fetches recent orders from Shopify GraphQL
- Deduplicate: OrderRepository checks if orders already exist in RMS
- Sync: Reuses existing sync_shopify_to_rms function for consistency
- Track: Metrics and error handling
"""

import logging
from datetime import UTC, datetime
from typing import Any

from app.core.config import get_settings
from app.db.rms.order_repository import OrderRepository
from app.db.shopify_clients.order_polling_client import OrderPollingClient
from app.services.shopify_to_rms import sync_shopify_to_rms
from app.utils.error_handler import AppException, ErrorAggregator

logger = logging.getLogger(__name__)
settings = get_settings()


class OrderPollingService:
    """
    Orchestrator service for polling and syncing orders from Shopify to RMS.

    This service implements the complete polling workflow:
    1. Fetch recent orders from Shopify (OrderPollingClient)
    2. Check for duplicates in RMS (OrderRepository)
    3. Sync new orders to RMS (sync_shopify_to_rms)
    4. Collect metrics and handle errors
    """

    def __init__(
        self,
        polling_client: OrderPollingClient | None = None,
        order_repository: OrderRepository | None = None,
    ):
        """
        Initialize the polling service.

        Args:
            polling_client: Shopify GraphQL polling client (optional, created if None)
            order_repository: RMS order repository (optional, created if None)
        """
        self.polling_client = polling_client or OrderPollingClient()
        self.order_repository = order_repository or OrderRepository()
        self.error_aggregator = ErrorAggregator()

        # Statistics tracking
        self.stats = {
            "total_polled": 0,
            "already_synced": 0,  # Orders that already existed (for backwards compat)
            "newly_synced": 0,     # New orders created in RMS
            "updated": 0,          # Existing orders updated in RMS
            "sync_errors": 0,
            "last_poll_time": None,
        }

        logger.info("OrderPollingService initialized")

    async def initialize(self):
        """Initialize dependencies (GraphQL client, RMS connection)."""
        try:
            # Initialize Shopify GraphQL client
            await self.polling_client.initialize()

            # Initialize RMS repository
            await self.order_repository.initialize()

            logger.info("✅ OrderPollingService fully initialized")

        except Exception as e:
            logger.error(f"❌ Failed to initialize OrderPollingService: {e}")
            raise AppException(f"Service initialization failed: {str(e)}") from e

    async def close(self):
        """Clean up resources."""
        try:
            if self.polling_client:
                await self.polling_client.close()

            if self.order_repository:
                await self.order_repository.close()

            logger.info("OrderPollingService closed")

        except Exception as e:
            logger.error(f"Error closing OrderPollingService: {e}")

    async def poll_and_sync(
        self,
        lookback_minutes: int | None = None,
        batch_size: int = 50,
        max_pages: int = 10,
        dry_run: bool = False,
        include_test_orders: bool = False,
    ) -> dict[str, Any]:
        """
        Poll recent orders from Shopify and sync new ones to RMS.

        Args:
            lookback_minutes: Minutes to look back (default from config)
            batch_size: Orders per page (max 250)
            max_pages: Maximum pages to fetch
            dry_run: If True, only check for new orders without syncing
            include_test_orders: If True, include test orders in polling

        Returns:
            Dict with comprehensive polling results and statistics
        """
        start_time = datetime.now(UTC)

        try:
            logger.info(
                f"🔄 Starting order polling"
                f"{' (DRY RUN)' if dry_run else ''}: "
                f"lookback={lookback_minutes or settings.ORDER_POLLING_LOOKBACK_MINUTES}m, "
                f"batch_size={batch_size}, "
                f"test_orders={'included' if include_test_orders else 'excluded'}"
            )

            # Step 1: Fetch orders from Shopify
            fetch_result = await self.polling_client.fetch_recent_orders(
                lookback_minutes=lookback_minutes,
                batch_size=batch_size,
                max_pages=max_pages,
                include_test_orders=include_test_orders,
            )

            orders = fetch_result["orders"]
            total_fetched = fetch_result["total_fetched"]

            if not orders:
                logger.info("📭 No orders found in polling window")
                return self._build_result(
                    status="success",
                    total_polled=0,
                    already_synced=0,
                    newly_synced=0,
                    updated=0,
                    sync_errors=0,
                    duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                    message="No orders found in polling window",
                )

            logger.info(f"📦 Fetched {total_fetched} orders from Shopify")

            # Step 2: Check which orders already exist in RMS (batch)
            order_ids = [
                self._extract_order_id(order)
                for order in orders
                if self._extract_order_id(order)
            ]

            existence_map = await self.order_repository.check_orders_exist_batch(
                order_ids
            )

            # IMPORTANT: No longer filter out existing orders
            # We sync ALL orders (new AND edited) - the sync function will handle update vs create
            orders_to_sync = orders
            already_exists_count = sum(existence_map.values())

            logger.info(
                f"🔍 Order analysis: {already_exists_count} exist in RMS, "
                f"{total_fetched - already_exists_count} are new → syncing ALL {total_fetched} orders"
            )

            # Update statistics
            self.stats["total_polled"] = total_fetched
            self.stats["already_synced"] = already_exists_count  # For backwards compat
            self.stats["last_poll_time"] = datetime.now(UTC).isoformat()

            # Dry run - stop here
            if dry_run:
                logger.info(f"🏁 Dry run complete: Would sync {len(orders_to_sync)} orders (new + edited)")
                return self._build_result(
                    status="dry_run",
                    total_polled=total_fetched,
                    already_synced=already_exists_count,
                    newly_synced=0,
                    updated=0,
                    sync_errors=0,
                    duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                    message=f"Dry run: {len(orders_to_sync)} orders ready to sync",
                    new_order_ids=[self._extract_order_id(o) for o in orders_to_sync],
                )

            # Step 3: Sync ALL orders to RMS (both new and edited)
            if orders_to_sync:
                sync_result = await self._sync_orders_to_rms(orders_to_sync)

                # Extract creates vs updates from sync result
                newly_synced = sync_result.get("created_count", 0)
                updated_count = sync_result.get("updated_count", 0)

                self.stats["newly_synced"] = newly_synced
                self.stats["updated"] = updated_count
                self.stats["sync_errors"] = sync_result["error_count"]

                logger.info(
                    f"✅ Polling complete: {newly_synced} created, {updated_count} updated, "
                    f"{sync_result['error_count']} errors"
                )

                return self._build_result(
                    status="success",
                    total_polled=total_fetched,
                    already_synced=already_exists_count,
                    newly_synced=newly_synced,
                    updated=updated_count,
                    sync_errors=sync_result["error_count"],
                    duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                    message=f"Polling complete: {newly_synced} created, {updated_count} updated, {sync_result['error_count']} errors",
                    sync_details=sync_result["details"],
                )

            else:
                logger.info("✅ No orders to sync")
                return self._build_result(
                    status="success",
                    total_polled=total_fetched,
                    already_synced=0,
                    newly_synced=0,
                    updated=0,
                    sync_errors=0,
                    duration_seconds=(datetime.now(UTC) - start_time).total_seconds(),
                    message="No orders found in polling window",
                )

        except Exception as e:
            self.error_aggregator.add_error(
                e,
                {
                    "lookback_minutes": lookback_minutes,
                    "batch_size": batch_size,
                    "dry_run": dry_run,
                },
            )

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.error(f"❌ Polling failed in {duration:.2f}s: {e}")

            return self._build_result(
                status="error",
                total_polled=0,
                already_synced=0,
                newly_synced=0,
                updated=0,
                sync_errors=1,
                duration_seconds=duration,
                message=f"Polling failed: {str(e)}",
                error=str(e),
            )

    async def _sync_orders_to_rms(
        self, orders: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Sync orders to RMS using existing sync_shopify_to_rms function.

        Args:
            orders: List of Shopify order dicts from GraphQL

        Returns:
            Dict with sync results including created_count and updated_count
        """
        try:
            # Extract order IDs (in GID format for sync function)
            order_gids = [order["id"] for order in orders]

            logger.info(f"🔄 Syncing {len(order_gids)} orders to RMS...")

            # Reuse existing sync function for consistency
            sync_result = await sync_shopify_to_rms(order_gids)

            # Extract sync statistics
            # The sync_shopify_to_rms returns stats with "created" and "updated" counts
            stats = sync_result.get("statistics", {})
            created_count = stats.get("created", 0)
            updated_count = stats.get("updated", 0)
            error_count = stats.get("errors", 0)

            return {
                "created_count": created_count,
                "updated_count": updated_count,
                "error_count": error_count,
                "details": sync_result,
            }

        except Exception as e:
            logger.error(f"❌ Error syncing orders to RMS: {e}")
            return {
                "created_count": 0,
                "updated_count": 0,
                "error_count": len(orders),
                "details": {"error": str(e)},
            }

    def _extract_order_id(self, order: dict[str, Any]) -> str | None:
        """
        Extract numeric Shopify order ID from order dict.

        Args:
            order: Shopify order dict

        Returns:
            Numeric order ID or None
        """
        try:
            # Try legacyResourceId first (numeric ID)
            if "legacyResourceId" in order and order["legacyResourceId"]:
                return str(order["legacyResourceId"])

            # Fallback: extract from GID (gid://shopify/Order/123456)
            if "id" in order and order["id"]:
                gid = order["id"]
                if "/" in gid:
                    return gid.split("/")[-1]

            # Last resort: order name without hash (e.g., "#1001" → "1001")
            if "name" in order and order["name"]:
                return order["name"].lstrip("#")

            logger.warning(f"Could not extract order ID from order: {order.keys()}")
            return None

        except Exception as e:
            logger.error(f"Error extracting order ID: {e}")
            return None

    def _build_result(
        self,
        status: str,
        total_polled: int,
        already_synced: int,
        newly_synced: int,
        updated: int,
        sync_errors: int,
        duration_seconds: float,
        message: str,
        sync_details: dict | None = None,
        error: str | None = None,
        new_order_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Build standardized result dictionary.

        Args:
            status: Operation status (success, dry_run, error)
            total_polled: Total orders fetched from Shopify
            already_synced: Orders already existing in RMS
            newly_synced: New orders successfully created in RMS
            updated: Existing orders successfully updated in RMS
            sync_errors: Number of sync errors
            duration_seconds: Operation duration
            message: Human-readable message
            sync_details: Detailed sync results (optional)
            error: Error message (optional)
            new_order_ids: List of new order IDs for dry run (optional)

        Returns:
            Standardized result dict
        """
        total_successful = newly_synced + updated
        result = {
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "duration_seconds": round(duration_seconds, 2),
            "message": message,
            "statistics": {
                "total_polled": total_polled,
                "already_synced": already_synced,
                "newly_synced": newly_synced,
                "updated": updated,
                "sync_errors": sync_errors,
                "success_rate": (
                    round(total_successful / (total_successful + sync_errors) * 100, 2)
                    if (total_successful + sync_errors) > 0
                    else 0.0
                ),
            },
        }

        if sync_details:
            result["sync_details"] = sync_details

        if error:
            result["error"] = error

        if new_order_ids:
            result["new_order_ids"] = new_order_ids

        return result

    def get_statistics(self) -> dict[str, Any]:
        """
        Get current polling statistics.

        Returns:
            Dict with cumulative statistics
        """
        return {
            **self.stats,
            "error_aggregator": self.error_aggregator.get_summary(),
        }

    def reset_statistics(self):
        """Reset cumulative statistics."""
        self.stats = {
            "total_polled": 0,
            "already_synced": 0,
            "newly_synced": 0,
            "updated": 0,
            "sync_errors": 0,
            "last_poll_time": None,
        }
        self.error_aggregator.clear()
        logger.info("Statistics reset")

    def __str__(self):
        """String representation."""
        return f"OrderPollingService(stats={self.stats})"

    def __repr__(self):
        """Detailed string representation."""
        return (
            f"OrderPollingService("
            f"initialized={self.polling_client is not None}, "
            f"stats={self.stats})"
        )


# Singleton instance for global use
_polling_service: OrderPollingService | None = None


async def get_polling_service() -> OrderPollingService:
    """
    Get or create singleton polling service instance.

    Returns:
        OrderPollingService: Initialized polling service
    """
    global _polling_service

    if _polling_service is None:
        _polling_service = OrderPollingService()
        await _polling_service.initialize()

    return _polling_service


async def close_polling_service():
    """Close and clean up singleton polling service."""
    global _polling_service

    if _polling_service is not None:
        await _polling_service.close()
        _polling_service = None
