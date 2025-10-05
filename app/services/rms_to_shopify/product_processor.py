import asyncio
import logging
import time
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.core.config import get_settings
from app.core.logging_config import log_sync_operation
from app.services.rms_to_shopify.progress_tracker import SyncProgressTracker
from app.services.rms_to_shopify.shopify_updater import ShopifyUpdater
from app.services.sync_checkpoint import SyncCheckpointManager
from app.utils.error_handler import ErrorAggregator

settings = get_settings()
logger = logging.getLogger(__name__)


class ProductProcessor:
    """Processes products in batches."""

    def __init__(
        self,
        sync_id: str,
        shopify_updater: ShopifyUpdater,
        checkpoint_manager: SyncCheckpointManager,
        error_aggregator: ErrorAggregator,
        checkpoint_frequency: int = 100,
    ):
        self.sync_id = sync_id
        self.shopify_updater = shopify_updater
        self.checkpoint_manager = checkpoint_manager
        self.error_aggregator = error_aggregator
        self.checkpoint_frequency = checkpoint_frequency

    async def process_products_in_batches_optimized(
        self,
        rms_products: List[ShopifyProductInput],
        force_update: bool,
        batch_size: int,
        start_index: int = 0,
        initial_stats: Optional[Dict[str, int]] = None,
        total_products_global: Optional[int] = None,
        is_page_processing: bool = False,
    ) -> Dict[str, Any]:
        """
        Processes products with optimized batch search and checkpoints.

        Args:
            rms_products: A list of RMS products to sync.
            force_update: Whether to force update existing products.
            batch_size: The size of each batch.
            start_index: The starting index for resuming a sync.
            initial_stats: The initial statistics for resuming a sync.
            total_products_global: Total products across all pages (for pagination).
            is_page_processing: Whether this is processing a single page of a multi-page sync.

        Returns:
            A dictionary with the synchronization statistics.
        """
        stats = initial_stats or {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "inventory_updated": 0,
            "inventory_failed": 0,
        }

        # Use global total if processing pages, otherwise use current batch size
        total_products = total_products_global if total_products_global else len(rms_products)
        page_products = len(rms_products)
        
        # Handle empty product list
        if not rms_products or len(rms_products) == 0:
            logger.info(f"📭 No products to process [sync_id: {self.sync_id}]")
            return stats
        
        progress_tracker = SyncProgressTracker(
            total_items=max(1, total_products),  # Ensure at least 1 to avoid division by zero
            operation_name="Optimized Product Sync", 
            sync_id=self.sync_id
        )

        products_to_process = rms_products[start_index:]

        if is_page_processing:
            logger.info(
                f"🚀 Processing page with {len(products_to_process)} products "
                f"(global progress: {stats.get('total_processed', 0)}/{total_products})"
            )
        elif products_to_process:
            logger.info(
                f"🚀 Starting optimized sync: {len(products_to_process)} products "
                f"(starting from index {start_index}/{total_products})"
            )

        for i in range(0, len(products_to_process), batch_size):
            batch = products_to_process[i : i + batch_size]
            batch_number = (start_index + i) // batch_size + 1
            # Calculate total batches based on current page when processing pages
            total_batches = (page_products + batch_size - 1) // batch_size if is_page_processing else (total_products + batch_size - 1) // batch_size

            batch_start_time = time.time()
            logger.info(f"🔄 Processing batch {batch_number}/{total_batches} ({len(batch)} products)")

            batch_handles = [product.handle for product in batch if product.handle]

            existing_products = await self.shopify_updater.check_products_exist_batch(batch_handles)

            batch_stats = await self._process_product_batch_optimized(
                batch, existing_products, force_update, progress_tracker
            )

            for key in stats:
                stats[key] += batch_stats.get(key, 0)

            # For page processing, use global stats count; otherwise use local count
            if is_page_processing:
                processed_count = stats["total_processed"]  # Use cumulative count
                should_save_checkpoint = (
                    processed_count % self.checkpoint_frequency == 0 or 
                    i + batch_size >= len(products_to_process)
                )
            else:
                processed_count = start_index + i + len(batch)
                should_save_checkpoint = (
                    processed_count % self.checkpoint_frequency == 0 or 
                    i + batch_size >= len(products_to_process)
                )

            if should_save_checkpoint and not is_page_processing:  # Only save checkpoint if not page processing
                last_ccod = batch[-1].tags[0].replace("ccod_", "") if batch and batch[-1].tags else "unknown"

                logger.info(
                    f"💾 Saving checkpoint [sync_id: {self.sync_id}]: {processed_count}/{total_products} "
                    f"products ({processed_count / total_products * 100:.1f}%) - Last CCOD: {last_ccod}"
                )

                checkpoint_saved = await self.checkpoint_manager.save_checkpoint(
                    last_processed_ccod=last_ccod,
                    processed_count=processed_count,
                    total_count=total_products,
                    stats=stats,
                    batch_number=batch_number,
                )

                if checkpoint_saved:
                    logger.info(f"✅ Checkpoint saved successfully [sync_id: {self.sync_id}]")
                else:
                    logger.warning(f"❌ Failed to save checkpoint [sync_id: {self.sync_id}]")

            batch_duration = time.time() - batch_start_time
            
            if is_page_processing:
                # Show progress relative to global total
                logger.info(
                    f"✅ Batch {batch_number} completed [sync_id: {self.sync_id}] in {batch_duration:.1f}s | "
                    f"Created: {batch_stats['created']}, Updated: {batch_stats['updated']}, "
                    f"Skipped: {batch_stats['skipped']}, Errors: {batch_stats['errors']} | "
                    f"Global Progress: {stats['total_processed']}/{total_products} ({stats['total_processed'] / total_products * 100:.1f}%)"
                )
            else:
                processed_so_far = i + len(batch)
                logger.info(
                    f"✅ Batch {batch_number} completed [sync_id: {self.sync_id}] in {batch_duration:.1f}s | "
                    f"Created: {batch_stats['created']}, Updated: {batch_stats['updated']}, "
                    f"Skipped: {batch_stats['skipped']}, Errors: {batch_stats['errors']} | "
                    f"Progress: {processed_so_far}/{page_products} ({processed_so_far / page_products * 100:.1f}%)"
                )

            progress_tracker.log_progress("Batch Progress - ")

            if i + batch_size < len(products_to_process):
                if batch_size > 2:
                    sleep_time = 3
                    logger.debug(f"🕐 Rate limiting: {sleep_time}s pause")
                else:
                    sleep_time = 1
                    logger.debug(f"🕐 Minimal pause: {sleep_time}s")

                await asyncio.sleep(sleep_time)

        # Only log final progress if there were products to process
        if products_to_process:
            progress_tracker.log_progress("Final Progress - ")

        # Only delete checkpoint if not processing pages (let orchestrator handle it)
        if not is_page_processing and stats["total_processed"] >= total_products:
            await self.checkpoint_manager.delete_checkpoint()
            logger.info("🎉 Sync completed successfully - checkpoint deleted")

        return stats

    async def _process_product_batch_optimized(
        self,
        batch: List[ShopifyProductInput],
        existing_products: Dict[str, Optional[Dict[str, Any]]],
        force_update: bool,
        progress_tracker: Optional[SyncProgressTracker] = None,
    ) -> Dict[str, Any]:
        """
        Processes a batch of products with optimized search.

        Args:
            batch: The batch of products to process.
            existing_products: The existing products found by handle.
            force_update: Whether to force update existing products.
            progress_tracker: The optional progress tracker.

        Returns:
            A dictionary with the batch statistics.
        """
        stats = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            "inventory_updated": 0,
            "inventory_failed": 0,
        }

        for shopify_input in batch:
            await self._process_single_product(
                shopify_input,
                existing_products.get(shopify_input.handle),
                force_update,
                stats,
                progress_tracker,
            )

        return stats

    async def _process_single_product(
        self,
        shopify_input: ShopifyProductInput,
        existing_product: Optional[Dict[str, Any]],
        force_update: bool,
        stats: Dict[str, Any],
        progress_tracker: Optional[SyncProgressTracker] = None,
    ):
        """
        Processes a single product.

        Args:
            shopify_input: The Shopify product input.
            existing_product: The existing product, if any.
            force_update: Whether to force update the existing product.
            stats: The statistics dictionary.
            progress_tracker: The optional progress tracker.
        """
        ccod = None
        try:
            for tag in shopify_input.tags or []:
                if tag.startswith("ccod_"):
                    ccod = tag.replace("ccod_", "").upper()
            if not ccod:
                logger.warning(f"⚠️ No CCOD found in product tags: {shopify_input.title}")
                stats["errors"] += 1
                return

            if existing_product:
                if force_update:
                    updated_product = await self.shopify_updater.update_shopify_product(shopify_input, existing_product)
                    if updated_product:
                        stats["updated"] += 1
                        stats["inventory_updated"] += 1
                        log_sync_operation("update", "shopify", ccod=ccod)
                    else:
                        stats["errors"] += 1
                else:
                    stats["skipped"] += 1
            else:
                total_stock = 0
                for variant in shopify_input.variants or []:
                    if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                        for inv_qty in variant.inventoryQuantities:
                            total_stock += inv_qty.get("availableQuantity", 0)
                if total_stock > 0 or settings.SYNC_CREATE_ZERO_STOCK_PRODUCTS:
                    created_product = await self.shopify_updater.create_shopify_product(shopify_input)
                    if created_product:
                        stats["created"] += 1
                        stats["inventory_updated"] += 1
                        log_sync_operation("create", "shopify", ccod=ccod)
                    else:
                        stats["errors"] += 1
                else:
                    stats["skipped"] += 1
            stats["total_processed"] += 1
            if progress_tracker:
                progress_tracker.update(
                    created=stats["created"],
                    updated=stats["updated"],
                    skipped=stats["skipped"],
                    errors=stats["errors"],
                )
        except Exception as e:
            stats["errors"] += 1
            self.error_aggregator.add_error(
                e,
                {"ccod": ccod or "unknown", "title": shopify_input.title},
            )
            if progress_tracker:
                progress_tracker.update(errors=1)
            logger.error(f"❌ Error processing {ccod or 'unknown'}: {str(e)}")

