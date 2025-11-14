"""
Test script for order updates and cancellation detection.

This script tests the enhanced Order Polling system which now detects:
- New orders (created)
- Edited orders (updated)
- Cancelled orders

Usage:
    # Dry-run (no actual sync, just check what would be done)
    python scripts/test_order_updates.py --dry-run

    # Normal execution (will sync orders)
    python scripts/test_order_updates.py

    # Custom lookback window (in minutes)
    python scripts/test_order_updates.py --lookback 60

    # Custom configuration
    python scripts/test_order_updates.py --lookback 30 --batch-size 50 --max-pages 5
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

from app.services.order_polling_service import OrderPollingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_order_updates(
    lookback_minutes: int = 60,
    batch_size: int = 50,
    max_pages: int = 10,
    dry_run: bool = False,
):
    """
    Test order polling with update and cancellation detection.

    Args:
        lookback_minutes: Minutes to look back for orders
        batch_size: Orders per page
        max_pages: Maximum pages to fetch
        dry_run: If True, only check without syncing
    """
    service = None
    try:
        logger.info("=" * 80)
        logger.info("ORDER UPDATE & CANCELLATION DETECTION TEST")
        logger.info("=" * 80)
        logger.info(f"Lookback: {lookback_minutes} minutes")
        logger.info(f"Batch size: {batch_size}")
        logger.info(f"Max pages: {max_pages}")
        logger.info(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE (will sync)'}")
        logger.info("=" * 80)

        # Initialize service
        logger.info("\n📊 Initializing Order Polling Service...")
        service = OrderPollingService()
        await service.initialize()

        # Execute polling
        logger.info(f"\n🔄 Polling orders updated in last {lookback_minutes} minutes...")
        result = await service.poll_and_sync(
            lookback_minutes=lookback_minutes,
            batch_size=batch_size,
            max_pages=max_pages,
            dry_run=dry_run,
        )

        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("POLLING RESULTS")
        logger.info("=" * 80)
        logger.info(f"Status: {result['status']}")
        logger.info(f"Duration: {result['duration_seconds']:.2f}s")
        logger.info(f"Message: {result['message']}")

        stats = result.get("statistics", {})
        logger.info("\n📊 Statistics:")
        logger.info(f"  Total polled: {stats.get('total_polled', 0)}")
        logger.info(f"  Already in RMS: {stats.get('already_synced', 0)}")
        logger.info(f"  Newly created: {stats.get('newly_synced', 0)}")
        logger.info(f"  Updated: {stats.get('updated', 0)}")
        logger.info(f"  Errors: {stats.get('sync_errors', 0)}")
        logger.info(f"  Success rate: {stats.get('success_rate', 0):.1f}%")

        # Display order IDs in dry-run mode
        if dry_run and "new_order_ids" in result:
            order_ids = result["new_order_ids"]
            if order_ids:
                logger.info(f"\n📝 Orders that would be synced ({len(order_ids)}):")
                for order_id in order_ids[:10]:  # Show first 10
                    logger.info(f"  - {order_id}")
                if len(order_ids) > 10:
                    logger.info(f"  ... and {len(order_ids) - 10} more")

        # Summary
        logger.info("\n" + "=" * 80)
        if dry_run:
            logger.info("✅ DRY RUN COMPLETE - No changes made")
            logger.info("To actually sync these orders, run without --dry-run")
        else:
            total_synced = stats.get("newly_synced", 0) + stats.get("updated", 0)
            logger.info(f"✅ SYNC COMPLETE - {total_synced} orders synchronized")
        logger.info("=" * 80)

        return result

    except Exception as e:
        logger.error(f"\n❌ Error during test: {e}", exc_info=True)
        raise
    finally:
        if service:
            await service.close()
            logger.info("\n🔒 Service closed")


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Test order updates and cancellation detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run with default settings (60 minutes lookback)
  python scripts/test_order_updates.py --dry-run

  # Check last 30 minutes
  python scripts/test_order_updates.py --lookback 30 --dry-run

  # Actually sync orders from last hour
  python scripts/test_order_updates.py --lookback 60

  # Custom configuration
  python scripts/test_order_updates.py --lookback 120 --batch-size 25 --max-pages 5
        """,
    )

    parser.add_argument(
        "--lookback",
        type=int,
        default=60,
        help="Minutes to look back for orders (default: 60)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Orders per page (default: 50, max: 250)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=10,
        help="Maximum pages to fetch (default: 10)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check what would be synced, don't actually sync",
    )

    args = parser.parse_args()

    # Run test
    asyncio.run(
        test_order_updates(
            lookback_minutes=args.lookback,
            batch_size=args.batch_size,
            max_pages=args.max_pages,
            dry_run=args.dry_run,
        )
    )


if __name__ == "__main__":
    main()
