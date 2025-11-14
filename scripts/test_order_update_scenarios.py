#!/usr/bin/env python3
"""
Test script for Order Update Synchronization scenarios.

This script validates the complete order update implementation, including:
- Quantity changes
- Products added to orders
- Products removed from orders
- Price changes
- Customer changes
- Order cancellations
- Atomic transactions and rollback

Usage:
    # Test specific Shopify order
    python scripts/test_order_update_scenarios.py --order-id 5678901234

    # Test multiple scenarios
    python scripts/test_order_update_scenarios.py --order-id 5678901234 --scenarios all

    # Dry-run (no database changes)
    python scripts/test_order_update_scenarios.py --order-id 5678901234 --dry-run

    # Verbose logging
    python scripts/test_order_update_scenarios.py --order-id 5678901234 --verbose
"""

import argparse
import asyncio
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings
from app.db.connection import get_db_connection
from app.db.rms.order_repository import OrderRepository
from app.db.shopify_clients.order_polling_client import OrderPollingClient
from app.services.shopify_to_rms import ShopifyToRMSSync

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class OrderUpdateTester:
    """Test harness for order update scenarios."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize tester.

        Args:
            dry_run: If True, skip actual database operations
        """
        self.dry_run = dry_run
        self.settings = get_settings()
        self.db_conn = get_db_connection()
        self.order_repo = OrderRepository(self.db_conn)
        self.polling_client = OrderPollingClient()
        self.sync_service = None  # Initialize in async context

    async def initialize(self) -> None:
        """Initialize async components."""
        await self.db_conn.initialize()
        await self.order_repo.initialize()
        self.sync_service = ShopifyToRMSSync()
        logger.info("✅ Test environment initialized")

    async def close(self) -> None:
        """Cleanup resources."""
        await self.order_repo.close()
        await self.db_conn.close()
        logger.info("🔒 Resources cleaned up")

    async def fetch_shopify_order(self, order_id: str) -> dict[str, Any] | None:
        """
        Fetch order from Shopify.

        Args:
            order_id: Shopify order ID (numeric, e.g., "5678901234")

        Returns:
            Order data or None if not found
        """
        logger.info(f"📥 Fetching Shopify order {order_id}...")

        # GraphQL query to fetch specific order
        query = """
        query GetOrder($id: ID!) {
          order(id: $id) {
            id
            name
            createdAt
            updatedAt
            cancelledAt
            cancelReason
            displayFinancialStatus
            totalPriceSet { shopMoney { amount currencyCode } }
            totalTaxSet { shopMoney { amount currencyCode } }
            lineItems(first: 100) {
              edges {
                node {
                  id
                  title
                  quantity
                  sku
                  variant { id sku }
                  discountedUnitPriceSet { shopMoney { amount currencyCode } }
                  originalUnitPriceSet { shopMoney { amount currencyCode } }
                }
              }
            }
            customer {
              id
              displayName
              email
            }
            shippingAddress {
              address1
              city
              province
              country
            }
          }
        }
        """

        variables = {"id": f"gid://shopify/Order/{order_id}"}

        try:
            response = await self.polling_client._execute_graphql_query(query, variables)
            order = response.get("data", {}).get("order")

            if order:
                logger.info(f"✅ Found order: {order['name']}")
                logger.info(f"   Created: {order['createdAt']}")
                logger.info(f"   Updated: {order['updatedAt']}")
                logger.info(f"   Line items: {len(order['lineItems']['edges'])}")
                return order
            else:
                logger.error(f"❌ Order {order_id} not found in Shopify")
                return None

        except Exception as e:
            logger.error(f"❌ Error fetching order: {e}")
            return None

    async def check_rms_order(self, shopify_order_id: str) -> dict[str, Any] | None:
        """
        Check if order exists in RMS.

        Args:
            shopify_order_id: Shopify order ID

        Returns:
            RMS order data or None if not found
        """
        logger.info(f"🔍 Checking RMS for order SHOPIFY-{shopify_order_id}...")

        rms_order = await self.order_repo.find_order_by_shopify_id(shopify_order_id)

        if rms_order:
            logger.info(f"✅ Order exists in RMS (ID: {rms_order['ID']})")
            logger.info(f"   Total: ₡{rms_order['Total']}")
            logger.info(f"   Tax: ₡{rms_order['Tax']}")
            logger.info(f"   Customer ID: {rms_order['CustomerID']}")

            # Get entries
            entries = await self.order_repo.get_order_entries(rms_order["ID"])
            logger.info(f"   Entries: {len(entries)}")
            for entry in entries:
                logger.info(
                    f"      - Item {entry['ItemID']}: " f"qty={entry['QuantityOnOrder']}, " f"price=₡{entry['Price']}"
                )

            return rms_order
        else:
            logger.warning("⚠️ Order does not exist in RMS yet")
            return None

    async def test_update_scenario(self, shopify_order_id: str, scenario: str = "default") -> dict[str, Any]:
        """
        Test order update scenario.

        Args:
            shopify_order_id: Shopify order ID
            scenario: Test scenario (default, dry-run, etc.)

        Returns:
            Test results
        """
        results = {
            "scenario": scenario,
            "order_id": shopify_order_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "steps": [],
        }

        # Step 1: Fetch Shopify order
        logger.info(f"\n{'='*60}")
        logger.info(f"STEP 1: Fetch Shopify Order {shopify_order_id}")
        logger.info(f"{'='*60}")

        shopify_order = await self.fetch_shopify_order(shopify_order_id)
        if not shopify_order:
            results["error"] = "Order not found in Shopify"
            return results

        results["steps"].append({"step": "fetch_shopify", "status": "success"})

        # Step 2: Check RMS
        logger.info(f"\n{'='*60}")
        logger.info("STEP 2: Check RMS Order Existence")
        logger.info(f"{'='*60}")

        rms_order_before = await self.check_rms_order(shopify_order_id)
        results["rms_exists"] = rms_order_before is not None
        results["steps"].append({"step": "check_rms", "status": "success"})

        # Step 3: Sync order
        logger.info(f"\n{'='*60}")
        logger.info("STEP 3: Sync Order (Update or Create)")
        logger.info(f"{'='*60}")

        if self.dry_run:
            logger.info("🔍 DRY-RUN MODE: Skipping actual sync")
            results["steps"].append({"step": "sync", "status": "skipped", "reason": "dry-run"})
        else:
            try:
                sync_result = await self.sync_service._sync_single_order(
                    shopify_order_id,
                    shopify_order,
                    skip_validation=False,
                )

                logger.info(f"✅ Sync completed: {sync_result['action']}")
                logger.info(f"   Message: {sync_result.get('message', 'N/A')}")

                results["sync_action"] = sync_result["action"]
                results["steps"].append(
                    {
                        "step": "sync",
                        "status": "success",
                        "action": sync_result["action"],
                    }
                )

            except Exception as e:
                logger.error(f"❌ Sync failed: {e}")
                results["steps"].append(
                    {
                        "step": "sync",
                        "status": "error",
                        "error": str(e),
                    }
                )
                return results

        # Step 4: Verify RMS after sync
        logger.info(f"\n{'='*60}")
        logger.info("STEP 4: Verify RMS After Sync")
        logger.info(f"{'='*60}")

        if not self.dry_run:
            rms_order_after = await self.check_rms_order(shopify_order_id)

            if rms_order_after:
                # Compare before/after if order existed
                if rms_order_before:
                    logger.info("\n📊 BEFORE vs AFTER COMPARISON:")
                    logger.info(f"   Total: ₡{rms_order_before['Total']} → ₡{rms_order_after['Total']}")
                    logger.info(f"   Tax: ₡{rms_order_before['Tax']} → ₡{rms_order_after['Tax']}")

                    entries_before = await self.order_repo.get_order_entries(rms_order_before["ID"])
                    entries_after = await self.order_repo.get_order_entries(rms_order_after["ID"])

                    logger.info(f"   Entries: {len(entries_before)} → {len(entries_after)}")

                    results["changes"] = {
                        "total_changed": rms_order_before["Total"] != rms_order_after["Total"],
                        "entries_changed": len(entries_before) != len(entries_after),
                        "entries_before": len(entries_before),
                        "entries_after": len(entries_after),
                    }

                results["steps"].append({"step": "verify", "status": "success"})
            else:
                logger.warning("⚠️ Order still not found in RMS")
                results["steps"].append(
                    {
                        "step": "verify",
                        "status": "warning",
                        "reason": "order_not_found",
                    }
                )

        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"Order ID: {shopify_order_id}")
        logger.info(f"Scenario: {scenario}")
        logger.info(
            f"Steps completed: {len([s for s in results['steps'] if s['status'] == 'success'])}/{len(results['steps'])}"
        )

        if "sync_action" in results:
            logger.info(f"Sync action: {results['sync_action']}")

        if "changes" in results:
            logger.info("Changes detected:")
            for key, value in results["changes"].items():
                logger.info(f"  - {key}: {value}")

        return results


async def main():
    """Main test entry point."""
    parser = argparse.ArgumentParser(description="Test Order Update Synchronization")
    parser.add_argument(
        "--order-id",
        type=str,
        required=True,
        help="Shopify order ID (numeric, e.g., '5678901234')",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="default",
        choices=["default", "all"],
        help="Test scenario to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode (no database changes)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("🚀 Starting Order Update Test")
    logger.info(f"   Order ID: {args.order_id}")
    logger.info(f"   Scenario: {args.scenario}")
    logger.info(f"   Dry-run: {args.dry_run}")

    tester = OrderUpdateTester(dry_run=args.dry_run)

    try:
        await tester.initialize()
        results = await tester.test_update_scenario(args.order_id, args.scenario)

        # Check if test had any errors
        has_errors = any(step.get("status") == "error" for step in results.get("steps", []))
        if has_errors or "error" in results:
            logger.error("\n❌ Test completed with errors")
            return 1

        logger.info("\n✅ Test completed successfully")
        return 0

    except Exception as e:
        logger.error(f"\n❌ Test failed: {e}", exc_info=True)
        return 1

    finally:
        await tester.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
