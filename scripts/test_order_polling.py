#!/usr/bin/env python3
"""
Script de prueba para Order Polling Service.

Este script permite probar el servicio de polling de órdenes de Shopify
de forma independiente para validar su funcionamiento antes de la integración
completa con el scheduler automático.

Uso:
    # Dry-run (solo consulta, no sincroniza)
    python scripts/test_order_polling.py --dry-run

    # Polling normal (últimos 15 minutos)
    python scripts/test_order_polling.py

    # Polling con lookback personalizado (últimos 60 minutos)
    python scripts/test_order_polling.py --lookback 60

    # Polling con configuración custom
    python scripts/test_order_polling.py --lookback 30 --batch-size 50 --max-pages 5

    # Ver estadísticas acumuladas
    python scripts/test_order_polling.py --stats-only
"""

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.services.order_polling_service import get_polling_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/order_polling_test.log"),
    ],
)

logger = logging.getLogger(__name__)
settings = get_settings()


def print_header():
    """Print test header."""
    print("\n" + "=" * 80)
    print("ORDER POLLING SERVICE - TEST SCRIPT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Shopify Shop: {settings.SHOPIFY_SHOP_URL}")
    print(f"Shopify API Version: {settings.SHOPIFY_API_VERSION}")
    print(f"\nConfiguration:")
    print(f"  • Order Polling Enabled: {settings.ENABLE_ORDER_POLLING}")
    print(f"  • Webhooks Enabled: {settings.ENABLE_WEBHOOKS}")
    print(f"  • Polling Interval: {settings.ORDER_POLLING_INTERVAL_MINUTES} min")
    print(f"  • Lookback Window: {settings.ORDER_POLLING_LOOKBACK_MINUTES} min")
    print(f"  • Batch Size: {settings.ORDER_POLLING_BATCH_SIZE}")
    print(f"  • Max Pages: {settings.ORDER_POLLING_MAX_PAGES}")
    print(f"  • Allowed Financial Statuses: {settings.ALLOWED_ORDER_FINANCIAL_STATUSES}")
    print("=" * 80 + "\n")


def print_report(result: dict):
    """Print formatted polling report."""
    print("\n" + "=" * 80)
    print("ORDER POLLING REPORT")
    print("=" * 80)
    print(f"Status: {result['status'].upper()}")
    print(f"Timestamp: {result['timestamp']}")
    print(f"Duration: {result['duration_seconds']:.2f} seconds")
    print(f"Message: {result['message']}")

    print("\n--- Statistics ---")
    stats = result['statistics']
    print(f"Total Polled: {stats['total_polled']}")
    print(f"Already Synced: {stats['already_synced']}")
    print(f"Newly Synced: {stats['newly_synced']}")
    print(f"Sync Errors: {stats['sync_errors']}")
    print(f"Success Rate: {stats['success_rate']:.2f}%")

    # Print sync details if available
    if result.get('sync_details'):
        print("\n--- Sync Details ---")
        sync_details = result['sync_details']
        print(f"Synced Count: {sync_details.get('synced_count', 0)}")
        print(f"Error Count: {sync_details.get('error_count', 0)}")

    # Print new order IDs for dry-run
    if result.get('new_order_ids'):
        print("\n--- New Orders (Dry Run) ---")
        for order_id in result['new_order_ids'][:10]:  # Show first 10
            print(f"  • Order ID: {order_id}")
        if len(result['new_order_ids']) > 10:
            print(f"  ... and {len(result['new_order_ids']) - 10} more")

    # Print error if present
    if result.get('error'):
        print(f"\n--- Error ---")
        print(f"Error: {result['error']}")

    print("=" * 80 + "\n")


def print_statistics(stats: dict):
    """Print cumulative statistics."""
    print("\n" + "=" * 80)
    print("CUMULATIVE STATISTICS")
    print("=" * 80)
    print(f"Total Polled: {stats['total_polled']}")
    print(f"Already Synced: {stats['already_synced']}")
    print(f"Newly Synced: {stats['newly_synced']}")
    print(f"Sync Errors: {stats['sync_errors']}")
    print(f"Last Poll Time: {stats['last_poll_time'] or 'Never'}")

    # Print error aggregator if available
    if stats.get('error_aggregator'):
        error_agg = stats['error_aggregator']
        print(f"\n--- Error Summary ---")
        print(f"Total Errors: {error_agg.get('total_errors', 0)}")
        if error_agg.get('error_types'):
            print("Error Types:")
            for error_type, count in error_agg['error_types'].items():
                print(f"  • {error_type}: {count}")

    print("=" * 80 + "\n")


async def main():
    """Main test function."""
    parser = argparse.ArgumentParser(
        description="Test Order Polling Service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode (only check for new orders, don't sync)",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=None,
        help=f"Lookback window in minutes (default: {settings.ORDER_POLLING_LOOKBACK_MINUTES})",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help=f"Batch size for GraphQL queries (default: {settings.ORDER_POLLING_BATCH_SIZE})",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help=f"Maximum pages to fetch (default: {settings.ORDER_POLLING_MAX_PAGES})",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only show cumulative statistics (don't execute polling)",
    )
    parser.add_argument(
        "--reset-stats",
        action="store_true",
        help="Reset cumulative statistics before polling",
    )

    args = parser.parse_args()

    # Print header
    print_header()

    try:
        # Check if order polling is enabled
        if not settings.ENABLE_ORDER_POLLING:
            print("⚠️  WARNING: Order polling is disabled in configuration")
            print("   Set ENABLE_ORDER_POLLING=true in .env to enable")
            print()

        # Get polling service
        logger.info("Initializing order polling service...")
        polling_service = await get_polling_service()
        logger.info("✅ Order polling service initialized")

        # Show statistics only
        if args.stats_only:
            stats = polling_service.get_statistics()
            print_statistics(stats)
            return

        # Reset statistics if requested
        if args.reset_stats:
            polling_service.reset_statistics()
            logger.info("✅ Statistics reset")

        # Execute polling
        logger.info("Starting order polling...")

        result = await polling_service.poll_and_sync(
            lookback_minutes=args.lookback,
            batch_size=args.batch_size or settings.ORDER_POLLING_BATCH_SIZE,
            max_pages=args.max_pages or settings.ORDER_POLLING_MAX_PAGES,
            dry_run=args.dry_run,
        )

        # Print report
        print_report(result)

        # Print cumulative statistics
        stats = polling_service.get_statistics()
        print_statistics(stats)

        # Summary
        if result['status'] == 'success':
            logger.info("✅ Test completed successfully")
            return 0
        elif result['status'] == 'dry_run':
            logger.info("✅ Dry run completed successfully")
            return 0
        else:
            logger.error("❌ Test completed with errors")
            return 1

    except KeyboardInterrupt:
        logger.info("\n⚠️  Test interrupted by user")
        return 130

    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup
        try:
            from app.services.order_polling_service import close_polling_service

            await close_polling_service()
            logger.info("✅ Polling service closed")
        except Exception as e:
            logger.error(f"Error closing polling service: {e}")


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
