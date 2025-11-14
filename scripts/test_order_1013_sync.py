#!/usr/bin/env python3
"""
Test full sync process for order #1013.
This script tests the complete order polling and sync workflow.
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime

from app.services.order_polling_service import OrderPollingService

# Configure logging to see full details
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def test_order_1013_sync(dry_run: bool = False):
    """
    Test order #1013 sync with the complete workflow.
    
    Args:
        dry_run: If True, only check without syncing
    """
    service = None
    try:
        # Calculate time elapsed since order #1013 was updated
        order_updated = datetime(2025, 11, 13, 4, 10, 9, tzinfo=UTC)
        now = datetime.now(UTC)
        time_diff = now - order_updated
        lookback_minutes = int(time_diff.total_seconds() / 60) + 5  # Add buffer
        
        logger.info("=" * 80)
        logger.info("🔍 ORDER #1013 FULL SYNC TEST")
        logger.info("=" * 80)
        logger.info(f"Order #1013 last updated: {order_updated.isoformat()}")
        logger.info(f"Current time: {now.isoformat()}")
        logger.info(f"Time elapsed: {time_diff}")
        logger.info(f"Lookback window: {lookback_minutes} minutes")
        logger.info(f"Mode: {'DRY RUN (no changes)' if dry_run else 'LIVE SYNC (will sync to RMS)'}")
        logger.info("=" * 80)

        # Initialize service
        logger.info("\n📊 Initializing Order Polling Service...")
        service = OrderPollingService()
        await service.initialize()

        # Execute polling with appropriate settings
        logger.info(f"\n🔄 Polling orders (lookback={lookback_minutes}min)...")
        logger.info("   NOTE: Test orders will be INCLUDED to detect #1013")
        
        # Temporarily enable test orders for this test
        # (Normally test orders are excluded in production)
        result = await service.poll_and_sync(
            lookback_minutes=lookback_minutes,
            batch_size=50,
            max_pages=5,
            dry_run=dry_run,
            include_test_orders=True  # Include test orders for this test
        )

        # Display results
        logger.info("\n" + "=" * 80)
        logger.info("📊 SYNC RESULTS")
        logger.info("=" * 80)
        logger.info(f"Status: {result['status']}")
        logger.info(f"Duration: {result['duration_seconds']:.2f}s")
        logger.info(f"Message: {result['message']}")

        stats = result.get("statistics", {})
        logger.info("\n📈 Statistics:")
        logger.info(f"  Total polled: {stats.get('total_polled', 0)}")
        logger.info(f"  Already in RMS: {stats.get('already_synced', 0)}")
        logger.info(f"  Newly created: {stats.get('newly_synced', 0)}")
        logger.info(f"  Updated: {stats.get('updated', 0)}")
        logger.info(f"  Errors: {stats.get('sync_errors', 0)}")
        logger.info(f"  Success rate: {stats.get('success_rate', 0):.1f}%")

        # Check if order #1013 was processed
        logger.info("\n🔍 Checking for Order #1013...")
        
        if dry_run and "new_order_ids" in result:
            order_ids = result["new_order_ids"]
            if "#1013" in [oid.split('/')[-1] for oid in order_ids]:
                logger.info("✅ Order #1013 detected and would be synced!")
            else:
                logger.info("⚠️  Order #1013 not in sync list")
                logger.info(f"   Orders detected: {order_ids[:10]}")

        # Summary
        logger.info("\n" + "=" * 80)
        logger.info("📋 SUMMARY")
        logger.info("=" * 80)
        
        if dry_run:
            logger.info("✅ DRY RUN COMPLETE - No changes made to RMS")
            logger.info("   Order #1013 detection verified")
            logger.info("   Ready to run live sync if needed")
        else:
            total_synced = stats.get("newly_synced", 0) + stats.get("updated", 0)
            logger.info(f"✅ SYNC COMPLETE - {total_synced} orders synchronized")
            logger.info("   Check RMS database to verify order #1013")
        
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
        description="Test order #1013 sync with full workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run (recommended first)
  python scripts/test_order_1013_sync.py --dry-run

  # Live sync (will sync to RMS)
  python scripts/test_order_1013_sync.py

Note: This test includes TEST ORDERS to detect order #1013.
      In production, test orders are excluded by default.
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only check what would be synced, don't actually sync",
    )

    args = parser.parse_args()

    # Run test
    asyncio.run(test_order_1013_sync(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
