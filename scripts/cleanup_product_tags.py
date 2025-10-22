#!/usr/bin/env python3
"""
Clean up product tags in Shopify - Keep only ccod_ tags.

This script removes all tags from products in Shopify except those
starting with 'ccod_'. It's designed to clean up automatically generated
tags while preserving essential CCOD identifiers.

Safety Features:
- Dry-run by default (requires --execute flag)
- Operates on DRAFT products by default (can specify ACTIVE with --status)
- Detailed before/after reporting
- Specific product testing with --ccod flag
- Progress indicators for batch operations

Usage:
    # Test with specific DRAFT product
    python scripts/cleanup_product_tags.py --ccod 24RX04

    # Preview changes for limited batch of DRAFT products
    python scripts/cleanup_product_tags.py --limit 50

    # Execute cleanup for specific DRAFT product
    python scripts/cleanup_product_tags.py --ccod 24RX04 --execute

    # Execute cleanup for all DRAFT products
    python scripts/cleanup_product_tags.py --execute

    # Preview changes for ACTIVE products
    python scripts/cleanup_product_tags.py --status active --limit 10

    # Execute cleanup for all ACTIVE products
    python scripts/cleanup_product_tags.py --status active --execute
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.shopify_clients.unified_client import ShopifyGraphQLClient  # noqa: E402
from app.utils.error_handler import ShopifyAPIException  # noqa: E402

# Configure logging
log_dir = project_root / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_dir / f"tag_cleanup_{datetime.now():%Y%m%d_%H%M%S}.log"),
    ],
)
logger = logging.getLogger(__name__)


class TagCleanupReport:
    """Report generator for tag cleanup operations."""

    def __init__(self):
        self.products_analyzed = 0
        self.products_needing_cleanup = 0
        self.products_updated = 0
        self.products_skipped = 0
        self.errors = []
        self.changes = []

    def add_change(self, product_id: str, product_title: str, old_tags: List[str], new_tags: List[str]):
        """Record a tag change."""
        self.changes.append(
            {
                "product_id": product_id,
                "product_title": product_title,
                "old_tags": old_tags,
                "new_tags": new_tags,
                "removed_tags": list(set(old_tags) - set(new_tags)),
                "removed_count": len(old_tags) - len(new_tags),
            }
        )

    def add_error(self, product_id: str, error: str):
        """Record an error."""
        self.errors.append({"product_id": product_id, "error": error})

    def print_summary(self, dry_run: bool = True):
        """Print formatted summary report."""
        mode = "DRY-RUN" if dry_run else "EXECUTION"

        print("\n" + "=" * 80)
        print(f"TAG CLEANUP REPORT - {mode}")
        print("=" * 80)
        print(f"\nProducts analyzed: {self.products_analyzed}")
        print(f"Products needing cleanup: {self.products_needing_cleanup}")
        print(
            f"Products would be updated: {self.products_updated}"
            if dry_run
            else f"Products updated: {self.products_updated}"
        )
        print(f"Products skipped (already clean): {self.products_skipped}")
        print(f"Errors encountered: {len(self.errors)}")

        if self.changes:
            print(f"\n{'PREVIEW OF' if dry_run else 'COMPLETED'} TAG CHANGES:")
            print("-" * 80)
            for change in self.changes[:20]:  # Show first 20
                print(f"\nProduct: {change['product_title']}")
                print(f"  ID: {change['product_id']}")
                print(f"  Old tags ({len(change['old_tags'])}): {change['old_tags']}")
                print(f"  New tags ({len(change['new_tags'])}): {change['new_tags']}")
                print(f"  Removed ({change['removed_count']}): {change['removed_tags']}")

            if len(self.changes) > 20:
                print(f"\n... and {len(self.changes) - 20} more changes")

        if self.errors:
            print("\nERRORS:")
            print("-" * 80)
            for error in self.errors:
                print(f"Product {error['product_id']}: {error['error']}")

        print("\n" + "=" * 80)

        if dry_run:
            print("\n⚠️  This was a DRY-RUN. Use --execute to apply changes.")
        else:
            print("\n✅ Cleanup completed successfully!")
        print("=" * 80 + "\n")


def filter_tags(tags: List[str]) -> Tuple[List[str], bool]:
    """
    Filter tags to keep only those starting with 'ccod_'.

    Args:
        tags: Original list of tags

    Returns:
        Tuple of (filtered_tags, needs_cleanup)
    """
    ccod_tags = [tag for tag in tags if tag.startswith("ccod_")]
    needs_cleanup = len(ccod_tags) != len(tags)
    return ccod_tags, needs_cleanup


async def cleanup_product_tags(
    client: ShopifyGraphQLClient,
    ccod_filter: str = None,
    limit: int = None,
    dry_run: bool = True,
    status: str = "draft",
) -> TagCleanupReport:
    """
    Clean up tags for products (DRAFT or ACTIVE).

    Args:
        client: Shopify GraphQL client
        ccod_filter: Optional CCOD to filter products
        limit: Optional limit on number of products to process
        dry_run: If True, don't actually update (preview only)
        status: Product status to clean - "draft" or "active" (default: "draft")

    Returns:
        TagCleanupReport with operation results
    """
    report = TagCleanupReport()
    status_upper = status.upper()

    try:
        # Fetch products based on status
        logger.info(
            f"Fetching {status_upper} products "
            f"(CCOD filter: {ccod_filter or 'None'}, limit: {limit or 'None'})..."
        )

        if limit:
            # Fetch single page with limit
            if status == "draft":
                result = await client.products.get_draft_products(limit=limit, ccod_filter=ccod_filter)
            else:  # active
                result = await client.products.get_active_products(limit=limit, ccod_filter=ccod_filter)
            products = [edge["node"] for edge in result.get("edges", [])]
        else:
            # Fetch all products with pagination
            if status == "draft":
                products = await client.products.get_all_draft_products(ccod_filter=ccod_filter)
            else:  # active
                products = await client.products.get_all_active_products(ccod_filter=ccod_filter)

        report.products_analyzed = len(products)
        logger.info(f"Found {len(products)} {status_upper} products to analyze")

        if not products:
            logger.warning(f"No {status_upper} products found matching criteria")
            return report

        # Process each product
        for idx, product in enumerate(products, 1):
            product_id = product.get("id")
            product_title = product.get("title", "Unknown")
            product_handle = product.get("handle", "Unknown")
            current_tags = product.get("tags", [])

            # Filter tags
            new_tags, needs_cleanup = filter_tags(current_tags)

            # Progress indicator
            if idx % 10 == 0 or idx == 1:
                logger.info(f"Progress: {idx}/{len(products)} products analyzed...")

            if not needs_cleanup:
                # Product already clean
                report.products_skipped += 1
                logger.debug(f"✓ Product '{product_title}' already has clean tags: {current_tags}")
                continue

            # Product needs cleanup
            report.products_needing_cleanup += 1
            report.add_change(product_id, product_title, current_tags, new_tags)

            logger.info(
                f"\n{'[DRY-RUN]' if dry_run else '[UPDATING]'} Product: {product_title} ({product_handle})\n"
                f"  Before ({len(current_tags)}): {current_tags}\n"
                f"  After  ({len(new_tags)}): {new_tags}\n"
                f"  Removed: {list(set(current_tags) - set(new_tags))}"
            )

            if not dry_run:
                try:
                    # Execute the update
                    await client.products.update_product_tags(product_id, new_tags)
                    report.products_updated += 1
                    logger.info(f"✅ Successfully updated product: {product_title}")

                    # Small delay to respect rate limits
                    await asyncio.sleep(0.5)

                except ShopifyAPIException as e:
                    error_msg = f"Failed to update product: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    report.add_error(product_id, error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    report.add_error(product_id, error_msg)
            else:
                # Dry-run mode - just count it
                report.products_updated += 1

        return report

    except Exception as e:
        logger.error(f"Critical error during tag cleanup: {e}")
        raise


async def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Clean up Shopify product tags - Keep only ccod_ tags",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Preview changes for specific DRAFT product
  python scripts/cleanup_product_tags.py --ccod 24RX04

  # Preview changes for limited batch of DRAFT products
  python scripts/cleanup_product_tags.py --limit 50

  # Execute cleanup for specific DRAFT product
  python scripts/cleanup_product_tags.py --ccod 24RX04 --execute

  # Execute cleanup for all DRAFT products
  python scripts/cleanup_product_tags.py --execute

  # Preview changes for ACTIVE products
  python scripts/cleanup_product_tags.py --status active --limit 10

  # Execute cleanup for all ACTIVE products
  python scripts/cleanup_product_tags.py --status active --execute
        """,
    )

    parser.add_argument("--ccod", type=str, help="Filter by specific CCOD (e.g., 24RX04)")

    parser.add_argument("--limit", type=int, help="Limit number of products to process (for testing)")

    parser.add_argument(
        "--status",
        type=str,
        choices=["draft", "active"],
        default="draft",
        help="Product status to clean - 'draft' or 'active' (default: draft)",
    )

    parser.add_argument("--execute", action="store_true", help="Actually execute the cleanup (default is dry-run)")

    args = parser.parse_args()

    # Validate arguments
    dry_run = not args.execute
    status_upper = args.status.upper()

    if dry_run:
        logger.info("=" * 80)
        logger.info(f"DRY-RUN MODE - No changes will be made to {status_upper} products")
        logger.info("Use --execute flag to apply changes")
        logger.info("=" * 80)
    else:
        logger.warning("=" * 80)
        logger.warning(f"EXECUTION MODE - Changes will be applied to {status_upper} products in Shopify!")
        logger.warning("=" * 80)

        # Confirmation for execution mode
        if not args.ccod:
            # Extra warning for ACTIVE products
            if args.status == "active":
                response = input(
                    f"\n⚠️  WARNING: You are about to modify ALL {status_upper} products (LIVE on store)!\n"
                    "This will affect products visible to customers.\n"
                    "Continue? (yes/no): "
                )
            else:
                response = input(f"\n⚠️  You are about to modify ALL {status_upper} products. Continue? (yes/no): ")

            if response.lower() != "yes":
                logger.info("Operation cancelled by user")
                return

    # Initialize Shopify client
    client = ShopifyGraphQLClient()

    try:
        logger.info("Initializing Shopify GraphQL client...")
        await client.initialize()

        # Run cleanup
        report = await cleanup_product_tags(
            client=client, ccod_filter=args.ccod, limit=args.limit, dry_run=dry_run, status=args.status
        )

        # Print summary report
        report.print_summary(dry_run=dry_run)

        # Exit code based on results
        if report.errors:
            sys.exit(1)  # Errors occurred
        elif report.products_updated == 0:
            logger.info("No products needed cleanup")
            sys.exit(0)
        else:
            sys.exit(0)  # Success

    except KeyboardInterrupt:
        logger.warning("\nOperation interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
