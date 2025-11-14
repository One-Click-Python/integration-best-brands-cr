#!/usr/bin/env python3
"""
Script de prueba para Reverse Stock Synchronization.

Este script permite probar la sincronización reversa de stock Shopify → RMS
de forma independiente para validar su funcionamiento antes de integrar
con el scheduler automático.

Uso:
    # Dry-run con 10 productos
    python scripts/test_reverse_stock_sync.py --dry-run --limit 10

    # Ejecución real con 50 productos
    python scripts/test_reverse_stock_sync.py --limit 50

    # Ejecución completa (todos los productos)
    python scripts/test_reverse_stock_sync.py

    # Sin eliminar variantes con stock 0
    python scripts/test_reverse_stock_sync.py --no-delete-zero-stock
"""

import asyncio
import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.db.connection import ConnDB
from app.db.rms.product_repository import ProductRepository
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.reverse_stock_sync import ReverseStockSynchronizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/reverse_sync_test.log"),
    ],
)

logger = logging.getLogger(__name__)
settings = get_settings()


def print_header():
    """Print test header."""
    print("\n" + "=" * 80)
    print("REVERSE STOCK SYNCHRONIZATION - TEST SCRIPT")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Shopify Shop: {settings.SHOPIFY_SHOP_URL}")
    print(f"Shopify API Version: {settings.SHOPIFY_API_VERSION}")
    print("=" * 80 + "\n")


def print_report(report: dict):
    """Print formatted sync report."""
    print("\n" + "=" * 80)
    print("REVERSE SYNC REPORT")
    print("=" * 80)
    print(f"Sync ID: {report['sync_id']}")
    print(f"Timestamp: {report['timestamp']}")
    print(f"Dry Run: {report['dry_run']}")
    print(f"Delete Zero Stock: {report['delete_zero_stock']}")
    print(f"Duration: {report['duration_seconds']:.2f} seconds")
    print("\n--- Statistics ---")
    stats = report['statistics']
    print(f"Products Checked: {stats['products_checked']}")
    print(f"Variants Checked: {stats['variants_checked']}")
    print(f"Variants Updated: {stats['variants_updated']}")
    print(f"Variants Deleted: {stats['variants_deleted']}")
    print(f"Errors: {stats['errors']}")
    print(f"Skipped: {stats['skipped']}")
    print(f"Products without CCOD: {stats['products_without_ccod']}")
    print(f"Products with CCOD: {stats['products_with_ccod']}")

    # Calculate success rate
    total_operations = stats['variants_updated'] + stats['variants_deleted']
    if stats['variants_checked'] > 0:
        success_rate = (total_operations / stats['variants_checked']) * 100
        print(f"\nSuccess Rate: {success_rate:.2f}%")

    # Print details if available
    if report['details']['updated']:
        print("\n--- Updated Variants ---")
        for item in report['details']['updated'][:5]:  # Show first 5
            print(f"  • {item['sku']}: {item['old_qty']} → {item['new_qty']}")
        if len(report['details']['updated']) > 5:
            print(f"  ... and {len(report['details']['updated']) - 5} more")

    if report['details']['deleted']:
        print("\n--- Deleted Variants ---")
        for item in report['details']['deleted'][:5]:  # Show first 5
            print(f"  • {item['sku']} (Reason: {item['reason']})")
        if len(report['details']['deleted']) > 5:
            print(f"  ... and {len(report['details']['deleted']) - 5} more")

    if report['details']['errors']:
        print("\n--- Errors ---")
        for item in report['details']['errors'][:5]:  # Show first 5
            print(f"  • {item['product']}: {item['error']}")
        if len(report['details']['errors']) > 5:
            print(f"  ... and {len(report['details']['errors']) - 5} more")

    print("=" * 80 + "\n")


async def run_test(args):
    """Run reverse stock sync test."""
    print_header()

    # Initialize connections
    logger.info("🔧 Initializing connections...")

    # Shopify client
    shopify_client = ShopifyGraphQLClient()
    await shopify_client.initialize()

    # Get primary location ID
    primary_location_id = await shopify_client.products.get_primary_location_id()

    if not primary_location_id:
        logger.error("❌ Could not get primary location from Shopify")
        return

    logger.info(f"✅ Primary location ID: {primary_location_id}")

    # RMS connection
    conn_db = ConnDB()
    await conn_db.initialize()
    product_repository = ProductRepository(conn_db)
    await product_repository.initialize()
    logger.info("✅ RMS connection established")

    # Verify we're using the correct database
    async with conn_db.get_session() as session:
        from sqlalchemy import text
        result = await session.execute(text('SELECT DB_NAME() as db'))
        db_name = result.scalar()
        logger.info(f"✅ Connected to database: {db_name}")

        # Verify against settings
        if db_name != settings.RMS_DB_NAME:
            logger.error(
                f"❌ DATABASE MISMATCH! Connected to '{db_name}' "
                f"but expected '{settings.RMS_DB_NAME}'"
            )
            print(f"\n❌ ERROR: Connected to wrong database!")
            print(f"   Expected: {settings.RMS_DB_NAME}")
            print(f"   Connected: {db_name}")
            print(f"   Check your .env file and system environment variables\n")
            sys.exit(1)

    try:
        # Create synchronizer
        synchronizer = ReverseStockSynchronizer(
            shopify_client=shopify_client,
            product_repository=product_repository,
            primary_location_id=primary_location_id,
        )

        logger.info(
            f"🚀 Starting reverse sync - "
            f"Dry run: {args.dry_run}, "
            f"Delete zero stock: {args.delete_zero_stock}, "
            f"Limit: {args.limit or 'None'}"
        )

        # Execute sync
        report = await synchronizer.execute_reverse_sync(
            dry_run=args.dry_run,
            delete_zero_stock=args.delete_zero_stock,
            batch_size=args.batch_size,
            limit=args.limit,
        )

        # Print report
        print_report(report)

        # Summary
        if args.dry_run:
            print("ℹ️  This was a DRY RUN - No changes were made to Shopify")
        else:
            print("✅ Reverse sync completed successfully")

    except Exception as e:
        logger.error(f"❌ Error during reverse sync: {e}", exc_info=True)
        raise

    finally:
        await conn_db.close()
        logger.info("🔌 Connections closed")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Reverse Stock Synchronization (Shopify → RMS)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without making actual changes",
    )

    parser.add_argument(
        "--no-delete-zero-stock",
        dest="delete_zero_stock",
        action="store_false",
        default=True,
        help="Don't delete variants with zero stock",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of products per batch (default: 50)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of products to process (default: all)",
    )

    args = parser.parse_args()

    # Run async test
    asyncio.run(run_test(args))


if __name__ == "__main__":
    main()
