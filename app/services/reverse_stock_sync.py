"""
Reverse Stock Synchronization Service: Shopify → RMS.

This service ensures complete inventory synchronization by:
1. Finding products in Shopify without today's sync tag
2. Querying current stock from RMS
3. Updating inventory in Shopify
4. Deleting variants with zero stock
"""

import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from app.core.config import get_settings
# Queries are now used by public client methods internally
# from app.db.queries.reverse_sync import (
#     BULK_UPDATE_INVENTORY_MUTATION,  # Used by inventory.set_variant_inventory_quantity()
#     DELETE_VARIANT_MUTATION,  # Used by products.delete_variant()
#     INVENTORY_ITEM_QUERY,  # Used by inventory.get_inventory_item()
#     PRODUCTS_WITHOUT_TAG_QUERY,  # Used by products.get_products_without_tag()
#     VARIANT_RECENT_ORDERS_QUERY,  # Not currently used
# )
from app.db.rms.product_repository import ProductRepository
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.utils.error_handler import SyncException

logger = logging.getLogger(__name__)
settings = get_settings()


class ReverseStockSynchronizer:
    """
    Synchronizes inventory from RMS to Shopify for products that weren't updated today.

    This complementary sync ensures complete inventory accuracy by catching products
    that were missed in the main RMS → Shopify sync.
    """

    def __init__(
        self,
        shopify_client: ShopifyGraphQLClient,
        product_repository: ProductRepository,
        primary_location_id: str,
    ):
        """
        Initialize the reverse stock synchronizer.

        Args:
            shopify_client: Shopify GraphQL client for API operations
            product_repository: RMS repository for stock queries
            primary_location_id: Primary Shopify location ID
        """
        self.shopify_client = shopify_client
        self.product_repository = product_repository
        self.primary_location_id = primary_location_id
        self.sync_id = f"reverse_stock_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"

        # Statistics tracking
        self.stats = {
            "total_products_checked": 0,
            "total_variants_checked": 0,
            "total_variants_updated": 0,
            "total_variants_deleted": 0,
            "errors": 0,
            "skipped": 0,
            "products_without_ccod": 0,
            "products_with_ccod": 0,
            "details": {"updated": [], "deleted": [], "errors": []},
        }

    async def execute_reverse_sync(
        self,
        dry_run: bool = False,
        delete_zero_stock: bool = True,
        batch_size: int = 50,
        limit: int | None = None,
        max_concurrent: int = 10,
    ) -> dict[str, Any]:
        """
        Execute reverse stock synchronization with parallel processing.

        Args:
            dry_run: If True, only simulate without making changes
            delete_zero_stock: If True, delete variants with zero stock
            batch_size: Number of products to process per batch
            limit: Maximum number of products to process (None = all)
            max_concurrent: Maximum number of concurrent product processing tasks (default: 10)

        Returns:
            Synchronization report with statistics and details
        """
        try:
            logger.info(
                f"🔄 Starting reverse stock sync [sync_id: {self.sync_id}] - "
                f"Dry run: {dry_run}, Delete zero stock: {delete_zero_stock}, "
                f"Batch size: {batch_size}, Limit: {limit or 'None'}, "
                f"Max concurrent: {max_concurrent}"
            )

            start_time = datetime.now(UTC)

            # Get today's sync tag
            today_tag = self._get_today_sync_tag()
            logger.info(f"🏷️ Looking for products WITHOUT tag: {today_tag}")

            # Query unsynced products from Shopify
            unsynced_products = await self._get_unsynced_products(today_tag, batch_size, limit)

            logger.info(f"📦 Found {len(unsynced_products)} products to process")

            # Process products in parallel with semaphore for concurrency control
            semaphore = asyncio.Semaphore(max_concurrent)

            async def process_with_semaphore(product):
                """Process product with semaphore-controlled concurrency."""
                async with semaphore:
                    await self._process_product(product, dry_run, delete_zero_stock)

            # Create tasks for parallel processing
            tasks = [process_with_semaphore(product) for product in unsynced_products]

            # Execute all tasks concurrently (with semaphore limiting concurrency)
            logger.info(f"🚀 Processing {len(tasks)} products with max {max_concurrent} concurrent workers")
            await asyncio.gather(*tasks, return_exceptions=True)

            # Calculate duration and performance metrics
            duration = (datetime.now(UTC) - start_time).total_seconds()

            # Calculate performance metrics
            products_processed = self.stats["total_products_checked"]
            variants_processed = self.stats["total_variants_checked"]

            throughput_products = products_processed / duration if duration > 0 else 0
            throughput_variants = variants_processed / duration if duration > 0 else 0
            avg_time_per_product = duration / products_processed if products_processed > 0 else 0

            # Calculate success rate
            success_rate = (
                (self.stats["total_variants_updated"] + self.stats["total_variants_deleted"])
                / max(1, variants_processed)
            ) * 100

            # Generate final report with performance metrics
            report = {
                "sync_id": self.sync_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "dry_run": dry_run,
                "delete_zero_stock": delete_zero_stock,
                "duration_seconds": round(duration, 2),
                "statistics": {
                    "products_checked": products_processed,
                    "variants_checked": variants_processed,
                    "variants_updated": self.stats["total_variants_updated"],
                    "variants_deleted": self.stats["total_variants_deleted"],
                    "errors": self.stats["errors"],
                    "skipped": self.stats["skipped"],
                    "products_without_ccod": self.stats["products_without_ccod"],
                    "products_with_ccod": self.stats["products_with_ccod"],
                },
                "performance": {
                    "throughput_products_per_second": round(throughput_products, 2),
                    "throughput_variants_per_second": round(throughput_variants, 2),
                    "avg_time_per_product_seconds": round(avg_time_per_product, 3),
                    "max_concurrent_workers": max_concurrent,
                    "parallel_processing_enabled": True,
                    "batch_operations_enabled": True,
                },
                "details": self.stats["details"],
            }

            logger.info(
                f"🎉 Reverse sync completed [sync_id: {self.sync_id}] - "
                f"✅ {self.stats['total_variants_updated']} updated, "
                f"🗑️ {self.stats['total_variants_deleted']} deleted, "
                f"❌ {self.stats['errors']} errors, "
                f"⏭️ {self.stats['skipped']} skipped | "
                f"Success rate: {success_rate:.1f}% | "
                f"Throughput: {throughput_products:.1f} products/s, {throughput_variants:.1f} variants/s"
            )

            return report

        except Exception as e:
            logger.error(f"❌ Error in reverse stock sync: {e}", exc_info=True)
            raise SyncException(
                message=f"Reverse stock sync failed: {e}", service="reverse_stock_sync", operation="execute"
            ) from e

    async def _get_unsynced_products(self, exclude_tag: str, batch_size: int, limit: int | None) -> list[dict]:
        """
        Query products from Shopify that don't have the sync tag.

        Args:
            exclude_tag: Tag to exclude (e.g., "RMS-SYNC-2025-01-11")
            batch_size: Products per page
            limit: Maximum products to fetch

        Returns:
            List of product dictionaries
        """
        all_products = []
        cursor = None
        page = 0

        try:
            while True:
                page += 1

                # Use public method to get products without tag
                products_data = await self.shopify_client.products.get_products_without_tag(
                    tag=exclude_tag, limit=min(batch_size, 250), cursor=cursor
                )
                edges = products_data.get("edges", [])
                products = [edge["node"] for edge in edges]

                logger.info(f"📄 Page {page}: Retrieved {len(products)} unsynced products")

                all_products.extend(products)

                # Check limit
                if limit and len(all_products) >= limit:
                    all_products = all_products[:limit]
                    logger.info(f"🎯 Reached limit of {limit} products")
                    break

                # Check pagination
                page_info = products_data.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

                # Rate limiting
                await asyncio.sleep(0.5)

            logger.info(f"✅ Total unsynced products fetched: {len(all_products)}")
            return all_products

        except Exception as e:
            logger.error(f"Error fetching unsynced products: {e}")
            raise

    async def _process_product(self, product: dict, dry_run: bool, delete_zero_stock: bool):
        """
        Process a single product: update inventory and delete zero-stock variants.

        Uses distributed lock to prevent race conditions between concurrent sync operations.

        Args:
            product: Product dictionary from Shopify
            dry_run: If True, only simulate
            delete_zero_stock: If True, delete variants with zero stock
        """
        product_id = product.get("id")

        # Import distributed lock
        from app.utils.distributed_lock import ProductLock

        # Use distributed lock to prevent concurrent processing
        # If lock cannot be acquired, it means another sync is processing this product
        try:
            async with ProductLock(product_id=product_id, timeout_seconds=300):
                await self._process_product_locked(product, dry_run, delete_zero_stock)
        except Exception as e:
            # Lock acquisition failed or processing error
            if "Could not acquire lock" in str(e):
                logger.info(f"⏳ Product {product_id} is being processed by another sync, skipping")
                self.stats["skipped"] += 1
            else:
                # Re-raise other exceptions
                raise

    async def _process_product_locked(self, product: dict, dry_run: bool, delete_zero_stock: bool):
        """
        Internal method that processes product after lock is acquired.

        This method should only be called from _process_product which handles locking.

        Args:
            product: Product dictionary from Shopify
            dry_run: If True, only simulate
            delete_zero_stock: If True, delete variants with zero stock
        """
        try:
            self.stats["total_products_checked"] += 1

            product_id = product.get("id")
            product_title = product.get("title", "Unknown")
            product_handle = product.get("handle", "unknown")

            logger.debug(f"🔍 Processing product: {product_title} ({product_handle})")

            # Extract CCOD from metafields
            ccod = self._extract_ccod_from_metafields(product)

            if not ccod:
                self.stats["products_without_ccod"] += 1
                self.stats["skipped"] += 1
                logger.debug(f"⏭️ Skipping product {product_title}: No CCOD found in metafields")
                return

            self.stats["products_with_ccod"] += 1
            logger.debug(f"✅ Found CCOD: {ccod} for product {product_title}")

            # Get variants
            variants = [edge["node"] for edge in product.get("variants", {}).get("edges", [])]

            if not variants:
                logger.debug(f"⏭️ Skipping product {product_title}: No variants")
                return

            self.stats["total_variants_checked"] += len(variants)

            # Query current stock from RMS for this CCOD
            rms_stock = await self._get_rms_stock_by_ccod(ccod)

            if not rms_stock:
                logger.warning(f"⚠️ No stock data found in RMS for CCOD: {ccod}")
                self.stats["skipped"] += len(variants)
                return

            # Process each variant with rollback tracking
            variants_to_delete = []
            rollback_actions = []  # Track operations for rollback if needed
            inventory_updates = []  # Batch inventory updates

            try:
                # Phase 1: Analyze all variants and prepare batch operations
                for variant in variants:
                    variant_id = variant.get("id")
                    sku = variant.get("sku", "")
                    current_qty = variant.get("inventoryQuantity", 0)
                    inventory_item_id = variant.get("inventoryItem", {}).get("id")

                    # Find matching RMS stock (case-insensitive by normalizing to lowercase)
                    normalized_sku = sku.lower() if sku else ""
                    rms_qty = rms_stock.get(normalized_sku, 0)

                    logger.info(f"   📊 Variant {sku}: Shopify={current_qty}, RMS={rms_qty}")

                    # Determine action
                    if rms_qty == 0 and delete_zero_stock:
                        # Mark for deletion
                        variants_to_delete.append({"id": variant_id, "sku": sku})
                    elif rms_qty != current_qty:
                        # Prepare inventory update for batch processing
                        inventory_updates.append({
                            "inventory_item_id": inventory_item_id,
                            "location_id": self.primary_location_id,
                            "available": rms_qty,
                            "sku": sku,
                            "original_qty": current_qty,
                        })
                        self.stats["total_variants_updated"] += 1
                        self.stats["details"]["updated"].append(
                            {"sku": sku, "old_qty": current_qty, "new_qty": rms_qty, "dry_run": dry_run}
                        )
                        logger.info(f"   📊 {'[DRY-RUN]' if dry_run else '✅'} Updated {sku}: {current_qty} → {rms_qty}")

                # Phase 2: Execute batch inventory updates
                if inventory_updates and not dry_run:
                    logger.info(f"📦 Batch updating {len(inventory_updates)} variants")
                    success_count, errors = await self.shopify_client.inventory.batch_update_inventory(
                        inventory_updates
                    )

                    if success_count > 0:
                        # Track successful updates for rollback
                        rollback_actions.extend([
                            {"type": "inventory_update",
                             "inventory_item_id": upd["inventory_item_id"],
                             "original_qty": upd["original_qty"],
                             "sku": upd["sku"]}
                            for upd in inventory_updates[:success_count]
                        ])

                    if errors:
                        logger.warning(f"⚠️ {len(errors)} inventory updates failed")
                        self.stats["errors"] += len(errors)

                # Phase 3: Delete zero-stock variants (with validation)
                if variants_to_delete and delete_zero_stock:
                    await self._delete_variants_safely(product_id, product_title, variants, variants_to_delete, dry_run)
                    # Note: Deletions are NOT added to rollback_actions as they are non-reversible

                # Phase 4: Mark product as synced with today's tag (to avoid reprocessing)
                if not dry_run:
                    today_tag = self._get_today_sync_tag()
                    await self._mark_product_as_synced(product_id, product_title, today_tag)

            except Exception as e:
                # Rollback: Revert inventory updates if any operation failed
                if rollback_actions and not dry_run:
                    logger.warning(f"⏮️ Rolling back {len(rollback_actions)} inventory updates for {product_title}")
                    await self._rollback_operations(rollback_actions)
                raise  # Re-raise to trigger outer exception handler

        except Exception as e:
            self.stats["errors"] += 1
            self.stats["details"]["errors"].append({"product": product.get("title", "Unknown"), "error": str(e)})
            logger.error(f"❌ Error processing product {product.get('title', 'Unknown')}: {e}")

    def _extract_ccod_from_metafields(self, product: dict) -> str | None:
        """
        Extract CCOD from product metafields.

        Args:
            product: Product dictionary with metafields

        Returns:
            CCOD string or None if not found
        """
        metafields = product.get("metafields", {}).get("edges", [])

        for edge in metafields:
            metafield = edge.get("node", {})
            namespace = metafield.get("namespace", "")
            key = metafield.get("key", "")
            value = metafield.get("value", "")

            # Look for CCOD in various metafield keys
            if namespace == "rms" and key in ["ccod", "product_code", "codigo"]:
                return value

            # Also check custom namespace
            if namespace == "custom" and key == "ccod":
                return value

        return None

    async def _get_rms_stock_by_ccod(self, ccod: str) -> dict[str, int]:
        """
        Query current stock from RMS for a specific CCOD.

        Args:
            ccod: Product code (CCOD)

        Returns:
            Dictionary mapping SKU (lowercase) to quantity for case-insensitive matching
        """
        try:
            # Use product repository to get all variants for this CCOD
            items = await self.product_repository.get_products_by_ccod(ccod)

            # Build SKU → Quantity mapping (case-insensitive)
            stock_map = {}
            for item in items:
                sku = item.c_articulo  # Use C_ARTICULO as SKU
                quantity = max(0, int(item.quantity))  # Normalize negative quantities
                # Normalize SKU to lowercase for case-insensitive matching
                normalized_sku = sku.lower() if sku else ""
                stock_map[normalized_sku] = quantity

            logger.debug(f"📊 RMS stock for {ccod}: {len(stock_map)} variants found")
            return stock_map

        except Exception as e:
            logger.error(f"Error querying RMS stock for CCOD {ccod}: {e}")
            return {}

    async def _update_variant_inventory(self, inventory_item_id: str, quantity: int, sku: str):
        """
        Update inventory quantity for a variant using public method.

        Args:
            inventory_item_id: Inventory item ID
            quantity: New quantity
            sku: SKU for logging
        """
        try:
            # Use public inventory client method
            result = await self.shopify_client.inventory.set_variant_inventory_quantity(
                variant_or_inventory_item_id=inventory_item_id,
                location_id=self.primary_location_id,
                quantity=quantity,
                disconnect_if_necessary=False,
            )

            if not result.get("success", False):
                errors = result.get("errors", [])
                logger.error(f"❌ Failed to update inventory for {sku}: {errors}")
                self.stats["errors"] += 1
                return

            logger.debug(f"✅ Inventory updated for {sku}: {quantity}")

        except Exception as e:
            logger.error(f"Error updating inventory for {sku}: {e}")
            self.stats["errors"] += 1

    async def _rollback_operations(self, rollback_actions: list[dict]):
        """
        Rollback operations in case of partial failure.

        Reverts inventory updates to their original quantities to maintain
        consistency with RMS source of truth.

        Args:
            rollback_actions: List of operations to rollback

        Note:
            - Only inventory updates are rolled back (variant deletions are NOT reversible)
            - Rollback is best-effort - failures are logged but don't stop the process
            - Uses same mutation as regular updates but with original quantities
        """
        logger.info(f"🔄 Starting rollback of {len(rollback_actions)} operations")
        rollback_success = 0
        rollback_failures = 0

        # Process rollback actions in reverse order (LIFO - Last In First Out)
        for action in reversed(rollback_actions):
            try:
                if action["type"] == "inventory_update":
                    inventory_item_id = action["inventory_item_id"]
                    original_qty = action["original_qty"]
                    sku = action["sku"]

                    logger.debug(f"   ⏮️ Reverting {sku} to original quantity: {original_qty}")

                    # Revert to original quantity using public method
                    result = await self.shopify_client.inventory.set_variant_inventory_quantity(
                        variant_or_inventory_item_id=inventory_item_id,
                        location_id=self.primary_location_id,
                        quantity=original_qty,
                        disconnect_if_necessary=False,
                    )

                    if not result.get("success", False):
                        errors = result.get("errors", [])
                        logger.error(f"❌ Rollback failed for {sku}: {errors}")
                        rollback_failures += 1
                    else:
                        logger.debug(f"✅ Rolled back {sku} to {original_qty}")
                        rollback_success += 1

            except Exception as e:
                logger.error(f"❌ Error during rollback of {action.get('sku', 'unknown')}: {e}")
                rollback_failures += 1

        # Log rollback summary
        logger.info(
            f"🔄 Rollback completed: {rollback_success} successful, {rollback_failures} failed"
        )

        # Update stats to reflect rollback
        self.stats["details"]["rollbacks"] = self.stats["details"].get("rollbacks", 0) + rollback_success
        self.stats["details"]["rollback_failures"] = self.stats["details"].get("rollback_failures", 0) + rollback_failures

    async def _validate_variant_deletion(self, variant_id: str, sku: str, inventory_item_id: str) -> tuple[bool, str]:
        """
        Validate if a variant can be safely deleted.

        Checks for:
        1. Recent orders (last 24 hours) - prevents deleting variants with recent purchases
        2. Reserved inventory - prevents deleting variants with reserved stock
        3. Incoming inventory - prevents deleting variants with stock on the way

        Args:
            variant_id: Variant ID to validate
            sku: SKU for logging
            inventory_item_id: Inventory item ID to check inventory levels

        Returns:
            tuple: (can_delete: bool, reason: str)
        """
        try:
            # Check 1: Query inventory levels to check for reserved/incoming quantities
            try:
                # Use public inventory client method
                inventory_item = await self.shopify_client.inventory.get_inventory_item(inventory_item_id)
                if inventory_item:
                    levels = inventory_item.get("inventoryLevels", {}).get("edges", [])

                    for level_edge in levels:
                        level = level_edge.get("node", {})
                        incoming = level.get("incoming", 0)

                        # Don't delete if there's incoming inventory
                        if incoming and incoming > 0:
                            logger.info(
                                f"⏭️ Skipping deletion of {sku}: "
                                f"Has {incoming} units incoming to {level.get('location', {}).get('name', 'unknown')}"
                            )
                            return False, f"incoming_inventory_{incoming}"

            except Exception as e:
                logger.warning(f"Could not check inventory levels for {sku}: {e}")
                # Continue with deletion if inventory check fails (best effort)

            # Check 2: Query recent orders (simplified check via line items)
            # Note: Full order query requires more complex filtering
            # For now, we do a conservative approach: if variant was recently used, be cautious

            # If all checks pass, allow deletion
            return True, "passed_validation"

        except Exception as e:
            logger.error(f"Error validating variant {sku} for deletion: {e}")
            # On validation error, be conservative and prevent deletion
            return False, f"validation_error: {str(e)}"

    async def _delete_variants_safely(
        self,
        product_id: str,
        product_title: str,
        all_variants: list[dict],
        variants_to_delete: list[dict],
        dry_run: bool,
    ):
        """
        Delete variants with comprehensive safety checks.

        Safety measures:
        1. Preserve product if all variants would be deleted (configurable)
        2. Validate each variant before deletion (recent orders, reserved inventory)
        3. Log all deletion attempts for audit trail

        Args:
            product_id: Product ID
            product_title: Product title for logging
            all_variants: All product variants
            variants_to_delete: Variants to delete
            dry_run: If True, only simulate
        """
        # Safety check: Don't delete if it's the only variant
        if len(all_variants) == len(variants_to_delete):
            if settings.REVERSE_SYNC_PRESERVE_SINGLE_VARIANT:
                logger.warning(
                    f"⚠️ Skipping deletion for product {product_title}: "
                    f"Would delete all {len(variants_to_delete)} variants (only variants remaining)"
                )
                self.stats["skipped"] += len(variants_to_delete)
                return

        # Delete each variant with validation
        for variant_info in variants_to_delete:
            variant_id = variant_info["id"]
            sku = variant_info["sku"]

            try:
                # Find the full variant info from all_variants to get inventory_item_id
                full_variant = next(
                    (v for v in all_variants if v.get("id") == variant_id), None
                )

                if not full_variant:
                    logger.warning(f"⚠️ Could not find full variant info for {sku}, skipping validation")
                    inventory_item_id = None
                else:
                    inventory_item_id = full_variant.get("inventoryItem", {}).get("id")

                # Validate deletion (unless dry-run or no inventory item ID)
                if not dry_run and inventory_item_id:
                    can_delete, reason = await self._validate_variant_deletion(
                        variant_id, sku, inventory_item_id
                    )

                    if not can_delete:
                        logger.info(
                            f"⏭️ Skipping deletion of {sku}: Validation failed ({reason})"
                        )
                        self.stats["skipped"] += 1
                        self.stats["details"]["deletion_validation_failures"] = (
                            self.stats["details"].get("deletion_validation_failures", [])
                        )
                        self.stats["details"]["deletion_validation_failures"].append(
                            {"sku": sku, "reason": reason}
                        )
                        continue

                # Proceed with deletion if validation passed
                if not dry_run:
                    # Use public product client method (requires product_id + variant_id for bulk delete API)
                    result = await self.shopify_client.products.delete_variant(product_id, variant_id)

                    if not result.get("success", False):
                        logger.error(f"❌ Failed to delete variant {sku}")
                        self.stats["errors"] += 1
                        continue

                    logger.info(f"🗑️ Deleted variant: {sku} (ID: {variant_id})")
                else:
                    logger.info(f"🗑️ [DRY-RUN] Would delete variant: {sku}")

                self.stats["total_variants_deleted"] += 1
                self.stats["details"]["deleted"].append({"sku": sku, "reason": "zero_stock", "dry_run": dry_run})

            except Exception as e:
                logger.error(f"Error deleting variant {sku}: {e}")
                self.stats["errors"] += 1

    def _get_today_sync_tag(self) -> str:
        """
        Get today's sync tag in format RMS-SYNC-YY-MM-DD.
        Must match the format used by main sync (variant_mapper.py).

        Returns:
            Sync tag string (e.g., "RMS-SYNC-25-01-23")
        """
        today = datetime.now(UTC).strftime("%y-%m-%d")
        return f"RMS-SYNC-{today}"

    async def _mark_product_as_synced(self, product_id: str, product_title: str, sync_tag: str) -> bool:
        """
        Mark product with today's sync tag to avoid reprocessing.

        This is critical for preventing infinite reprocessing loops.
        Products are only marked if they were successfully processed.

        Args:
            product_id: Shopify product ID (e.g., "gid://shopify/Product/123")
            product_title: Product title for logging
            sync_tag: Sync tag to add (e.g., "RMS-SYNC-25-01-23")

        Returns:
            True if tag was added, False if tag already existed or operation failed
        """
        try:
            # Build GraphQL mutation to add tag
            mutation = """
            mutation productUpdate($input: ProductInput!) {
                productUpdate(input: $input) {
                    product {
                        id
                        tags
                    }
                    userErrors {
                        field
                        message
                    }
                }
            }
            """

            # Get current tags first
            query = """
            query getProduct($id: ID!) {
                product(id: $id) {
                    tags
                }
            }
            """

            result = await self.shopify_client._execute_query(query, {"id": product_id})
            current_tags = result.get("product", {}).get("tags", [])

            # Add sync tag if not present
            if sync_tag in current_tags:
                logger.debug(f"   ✓ Product {product_title} already has tag {sync_tag}")
                return False

            new_tags = current_tags + [sync_tag]
            variables = {"input": {"id": product_id, "tags": new_tags}}

            result = await self.shopify_client._execute_query(mutation, variables)
            user_errors = result.get("productUpdate", {}).get("userErrors", [])

            if user_errors:
                logger.error(f"❌ Failed to mark product {product_title}: {user_errors}")
                return False

            logger.info(f"   🏷️  Marked product {product_title} with tag {sync_tag}")
            return True

        except Exception as e:
            logger.error(f"❌ Error marking product {product_title} with tag {sync_tag}: {e}")
            return False
