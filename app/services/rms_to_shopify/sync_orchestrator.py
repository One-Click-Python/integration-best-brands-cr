import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.core.logging_config import LogContext
from app.db.rms.product_repository import ProductRepository
from app.db.rms.query_executor import QueryExecutor
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.rms_to_shopify.data_extractor import RMSExtractor
from app.services.rms_to_shopify.product_processor import ProductProcessor
from app.services.rms_to_shopify.report_generator import ReportGenerator
from app.services.rms_to_shopify.shopify_updater import ShopifyUpdater
from app.services.sync_checkpoint import SyncCheckpointManager
from app.utils.error_handler import ErrorAggregator, SyncException
from app.utils.update_checkpoint import UpdateCheckpointManager

settings = get_settings()
logger = logging.getLogger(__name__)


async def get_sync_status() -> Dict[str, Any]:
    """
    Obtiene estado actual de sincronización.

    Returns:
        Dict: Estado de sincronización
    """
    return {"status": "ready", "last_sync": None, "next_scheduled": None}


class RMSToShopifySyncOrchestrator:
    """Orchestrates the RMS to Shopify sync process."""

    def __init__(
        self,
        sync_id: Optional[str] = None,
        checkpoint_frequency: int = 100,
        resume_from_checkpoint: bool = True,
        force_fresh_start: bool = False,
        use_update_checkpoint: bool = False,
        checkpoint_success_threshold: float = 0.95,
    ):
        self.sync_id = sync_id or f"rms_to_shopify_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        self.error_aggregator = ErrorAggregator()
        self.checkpoint_manager = SyncCheckpointManager(self.sync_id)
        self.update_checkpoint_manager = UpdateCheckpointManager()
        # SOLID repositories instead of monolithic handler
        self.query_executor = QueryExecutor()
        self.product_repository = ProductRepository()
        self.shopify_client = ShopifyGraphQLClient()
        self.primary_location_id = None
        self.shopify_updater: Optional[ShopifyUpdater] = None
        self.rms_extractor: Optional[RMSExtractor] = None
        self.product_processor: Optional[ProductProcessor] = None
        self.report_generator: Optional[ReportGenerator] = None
        self.checkpoint_frequency = checkpoint_frequency
        self.resume_from_checkpoint = resume_from_checkpoint
        self.force_fresh_start = force_fresh_start
        self.use_update_checkpoint = use_update_checkpoint
        self.checkpoint_success_threshold = checkpoint_success_threshold
        self.sync_start_time = None

    async def initialize(self):
        """Initializes the required clients and services."""
        try:
            # Initialize SOLID repositories
            await self.query_executor.initialize()
            await self.product_repository.initialize()
            await self.shopify_client.initialize()
            self.primary_location_id = await self.shopify_client.get_primary_location_id()
            if not self.primary_location_id:
                logger.warning("No primary location found - inventory updates may fail")

            self.shopify_updater = ShopifyUpdater(
                self.shopify_client, self.primary_location_id, self.product_repository
            )
            self.rms_extractor = RMSExtractor(
                self.query_executor, self.product_repository, self.shopify_client, self.primary_location_id
            )
            self.product_processor = ProductProcessor(
                self.sync_id,
                self.shopify_updater,
                self.checkpoint_manager,
                self.error_aggregator,
                self.checkpoint_frequency,
            )
            self.report_generator = ReportGenerator(self.sync_id, self.error_aggregator)

            await self.checkpoint_manager.initialize()
            logger.info(f"🚀 Sync orchestrator initialized [sync_id: {self.sync_id}]")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize sync orchestrator: {str(e)}",
                service="sync_orchestrator",
                operation="initialize",
            ) from e

    async def close(self):
        """Closes the connections and cleans up resources."""
        try:
            # Close SOLID repositories
            if self.query_executor:
                await self.query_executor.close()
            if self.product_repository:
                await self.product_repository.close()
            if self.shopify_client:
                await self.shopify_client.close()
            if self.checkpoint_manager:
                await self.checkpoint_manager.close()
            logger.info(f"Sync orchestrator closed successfully - ID: {self.sync_id}")
        except Exception as e:
            logger.error(f"Error closing sync orchestrator: {e}")

    async def sync_products(
        self,
        force_update: bool = False,
        batch_size: int = None,
        filter_categories: Optional[List[str]] = None,
        include_zero_stock: bool = False,
        cod_product: Optional[str] = None,
        use_streaming: bool = True,
        page_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Synchronizes products from RMS to Shopify.

        Args:
            force_update: Whether to force update existing products.
            batch_size: The size of each batch.
            filter_categories: A list of categories to filter by.
            include_zero_stock: Whether to include products with zero stock.
            cod_product: A specific CCOD to sync.
            use_streaming: Whether to use streaming for large volumes.
            page_size: The number of products (CCODs) per page for RMS extraction.

        Returns:
            A dictionary with the synchronization result.
        """
        batch_size = batch_size or settings.SYNC_BATCH_SIZE
        self.sync_start_time = datetime.now(timezone.utc)

        with LogContext(sync_id=self.sync_id, operation="sync_products"):
            logger.info(
                f"Starting product sync - Force: {force_update}, Batch: {batch_size}, "
                f"Include zero stock: {include_zero_stock}, CCOD: {cod_product or 'ALL'}, "
                f"Streaming: {use_streaming}, Page size: {page_size} products/CCODs per page, "
                f"Use update checkpoint: {self.use_update_checkpoint}"
            )

            # Log current update checkpoint status if enabled
            if self.use_update_checkpoint:
                checkpoint_status = self.update_checkpoint_manager.get_checkpoint_status()
                logger.info(f"📅 Update checkpoint status: {checkpoint_status}")

            try:
                if cod_product or not use_streaming:
                    return await self._sync_products_traditional(
                        force_update, batch_size, filter_categories, include_zero_stock, cod_product
                    )
                else:
                    return await self._sync_products_streaming(
                        force_update, batch_size, filter_categories, include_zero_stock, page_size
                    )

            except Exception as e:
                self.error_aggregator.add_error(e)
                logger.critical(f"CRITICAL ERROR in sync_products: {e}", exc_info=True)
                return {
                    "sync_id": self.sync_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "statistics": {
                        "total_processed": 0,
                        "created": 0,
                        "updated": 0,
                        "errors": 1,
                        "skipped": 0,
                    },
                    "errors": self.error_aggregator.get_summary(),
                    "success_rate": 0.0,
                    "recommendations": ["Fix critical sync errors before retrying"],
                }

    async def _sync_products_streaming(
        self,
        force_update: bool,
        batch_size: int,
        filter_categories: Optional[List[str]],
        include_zero_stock: bool,
        page_size: int,
    ) -> Dict[str, Any]:
        """Synchronizes products using streaming for large volumes."""
        start_time = time.time()

        total_products = await self.rms_extractor.count_rms_products(
            filter_categories, include_zero_stock=include_zero_stock
        )
        logger.info(f"📊 Total products to sync: {total_products} [sync_id: {self.sync_id}]")

        if total_products == 0:
            return {
                "sync_id": self.sync_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "statistics": {"total_processed": 0, "created": 0, "updated": 0, "errors": 0, "skipped": 0},
                "message": "No products found to sync",
                "success_rate": 100.0,
            }

        checkpoint = await self.checkpoint_manager.load_checkpoint()
        current_page = 1  # Changed from 0 to 1 for 1-based page indexing
        stats = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0,
            "inventory_updated": 0,
            "inventory_failed": 0,
        }

        if self.resume_from_checkpoint and checkpoint and await self.checkpoint_manager.should_resume():
            current_page = checkpoint.get("additional_data", {}).get("current_page", 1)  # Default to 1, not 0
            stats = checkpoint["stats"]
            logger.info(
                f"📊 Resuming from checkpoint - Page: {current_page}, "
                f"Processed: {stats['total_processed']} [sync_id: {self.sync_id}]"
            )
        else:
            if self.force_fresh_start:
                await self.checkpoint_manager.delete_checkpoint()

        # Calculate total pages correctly using ceiling division
        import math

        total_pages = math.ceil(total_products / page_size)

        logger.info(
            f"""PAGINATION DEBUGGING:
        - Total Products (from RMS count): {total_products}
        - Page Size (products per page): {page_size}
        - Calculated Total Pages: {total_pages}
        - Initial Loop Condition: `while {current_page} <= {total_pages}`
        """
        )

        logger.info(
            f"📚 Total pages to process: {total_pages} (page_size: {page_size} products/CCODs per page) [sync_id: {
                self.sync_id
            }]"
        )

        while current_page <= total_pages:  # Fixed condition: iterate through all pages
            logger.info(f"--- LOOP START: current_page = {current_page} ---")
            offset = (current_page - 1) * page_size  # Adjusted for 1-based indexing

            logger.info(
                f"📄 Processing page {current_page}/{total_pages} "
                f"(offset: {offset}, limit: {page_size}) [sync_id: {self.sync_id}]"
            )

            # --- STEP 1: Data Extraction ---
            logger.info(">>> STARTING STEP 1: Data Extraction...")
            page_products = await self.rms_extractor.extract_rms_products_paginated(
                offset, page_size, filter_categories, include_zero_stock=include_zero_stock
            )
            logger.info(f"<<< COMPLETED STEP 1: Data Extraction. Found {len(page_products)} products.")

            if not page_products:
                logger.warning(f"Empty page {current_page}, continuing...")
                current_page += 1
                continue

            # --- STEP 2: Product Processing ---
            logger.info(">>> STARTING STEP 2: Product Processing...")
            try:
                page_stats = await self.product_processor.process_products_in_batches_optimized(
                    page_products,
                    force_update,
                    batch_size,
                    start_index=0,
                    initial_stats={},
                    total_products_global=total_products,
                    is_page_processing=True,
                )
                logger.info(
                    f"<<< COMPLETED STEP 2: Product Processing. Page stats: Created={
                        page_stats.get('created', 0)
                    }, Updated={page_stats.get('updated', 0)}, Errors={page_stats.get('errors', 0)}"
                )
            except Exception as e:
                logger.error(f"❌ Error in STEP 2 (Product Processing): {e}", exc_info=True)
                # Continue with empty stats rather than failing completely
                page_stats = {
                    "total_processed": 0,
                    "created": 0,
                    "updated": 0,
                    "errors": len(page_products),
                    "skipped": 0,
                }
                logger.warning(f"⚠️ Continuing despite error, marked {len(page_products)} products as errors")

            # Update cumulative stats
            for key in stats:
                stats[key] += page_stats.get(key, 0)

            progress_percentage = (stats["total_processed"] / total_products * 100) if total_products > 0 else 0
            logger.info(
                f"📊 Page {current_page}/{total_pages} completed - "
                f"Total progress: {stats['total_processed']}/{total_products} ({progress_percentage:.1f}%) "
                f"[sync_id: {self.sync_id}]"
            )

            # --- STEP 3: Checkpoint Saving ---
            logger.info(">>> STARTING STEP 3: Checkpoint Saving...")
            await self.checkpoint_manager.save_checkpoint(
                last_processed_ccod=(
                    page_products[-1].tags[0].replace("ccod_", "") if page_products[-1].tags else "unknown"
                ),
                processed_count=stats["total_processed"],
                total_count=total_products,
                stats=stats,
                batch_number=current_page,
                additional_data={"current_page": current_page + 1, "total_pages": total_pages},
            )
            logger.info("<<< COMPLETED STEP 3: Checkpoint Saving.")

            current_page += 1

            # Add delay between pages only if there are more pages to process
            if current_page <= total_pages:
                await asyncio.sleep(2)

            logger.info(f"--- LOOP END: current_page is now {current_page} ---")

            # Log clear pagination progress
            if current_page <= total_pages:
                logger.info(
                    f"\n{'=' * 60}\n"
                    f"📊 PAGE {current_page - 1}/{total_pages} COMPLETED\n"
                    f"✅ Products synced so far: {stats['total_processed']}/{total_products}\n"
                    f"➡️  Continuing to page {current_page}...\n"
                    f"{'=' * 60}\n"
                )
            else:
                logger.info(
                    f"\n{'=' * 60}\n"
                    f"🎉 ALL PAGES PROCESSED!\n"
                    f"✅ Total products synced: {stats['total_processed']}/{total_products}\n"
                    f"📄 Pages processed: {current_page - 1}/{total_pages}\n"
                    f"{'=' * 60}\n"
                )

        final_report = self.report_generator.generate_sync_report(stats)
        final_report["duration_seconds"] = time.time() - start_time
        final_report["pages_processed"] = current_page - 1  # Actual pages processed
        final_report["page_size"] = page_size
        final_report["total_pages"] = total_pages
        final_report["total_products_expected"] = total_products
        final_report["total_products_synced"] = stats["total_processed"]

        # Only delete checkpoint if we actually processed all products
        if stats["total_processed"] >= total_products:
            await self.checkpoint_manager.delete_checkpoint()
            logger.info(
                f"🎉 Streaming sync completed successfully - "
                f"Synced {stats['total_processed']}/{total_products} products across {current_page - 1} pages "
                f"[sync_id: {self.sync_id}]"
            )

            # Update the update checkpoint if enabled and sync was successful
            await self._update_checkpoint_if_successful(final_report)
        else:
            logger.warning(
                f"⚠️ Streaming sync incomplete - "
                f"Synced {stats['total_processed']}/{total_products} products "
                f"[sync_id: {self.sync_id}]"
            )

        return final_report

    async def _sync_products_traditional(
        self,
        force_update: bool,
        batch_size: int,
        filter_categories: Optional[List[str]],
        include_zero_stock: bool,
        cod_product: Optional[str],
    ) -> Dict[str, Any]:
        """Traditional sync method for compatibility."""
        rms_products = await self.rms_extractor.extract_rms_products_with_variants(
            filter_categories, cod_product, include_zero_stock=include_zero_stock
        )
        logger.info(f"📦 Extracted {len(rms_products)} products from RMS [sync_id: {self.sync_id}]")

        checkpoint = await self.checkpoint_manager.load_checkpoint()
        start_index = 0
        initial_stats = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0,
            "inventory_updated": 0,
            "inventory_failed": 0,
        }

        if self.resume_from_checkpoint and checkpoint and await self.checkpoint_manager.should_resume():
            progress_pct = (
                (checkpoint["processed_count"] / checkpoint["total_count"] * 100)
                if checkpoint["total_count"] > 0
                else 0
            )
            logger.info(
                f"📊 Resuming sync from checkpoint [sync_id: {self.sync_id}]: {checkpoint['processed_count']}/{
                    checkpoint['total_count']
                } products ({progress_pct:.1f}%)"
            )
            start_index = checkpoint["processed_count"]
            initial_stats = checkpoint["stats"]
            initial_stats["resumed_from_checkpoint"] = True
        else:
            if self.force_fresh_start:
                logger.info(f"🚀 Starting fresh sync [sync_id: {self.sync_id}] - forced fresh start")
                await self.checkpoint_manager.delete_checkpoint()
            elif not self.resume_from_checkpoint:
                logger.info(f"🚀 Starting fresh sync [sync_id: {self.sync_id}] - resume disabled")
            else:
                logger.info(f"🚀 Starting fresh sync [sync_id: {self.sync_id}] - no valid checkpoint found")

        sync_stats = await self.product_processor.process_products_in_batches_optimized(
            rms_products,
            force_update,
            batch_size,
            start_index,
            initial_stats,
            total_products_global=None,  # Not using pagination, so no global total
            is_page_processing=False,  # Traditional processing, not page-based
        )

        final_report = self.report_generator.generate_sync_report(sync_stats)

        if final_report.get("success_rate", 0) > 0:
            logger.info(f"🎉 Sync completed successfully [sync_id: {self.sync_id}] - Cleaning up checkpoint")
            await self.checkpoint_manager.delete_checkpoint()

            # Update the update checkpoint if enabled and sync was successful
            await self._update_checkpoint_if_successful(final_report)
        else:
            logger.warning(f"⚠️ Sync completed with issues [sync_id: {self.sync_id}] - Keeping checkpoint for retry")

        return final_report

    async def _update_checkpoint_if_successful(self, final_report: Dict[str, Any]) -> None:
        """
        Update the update checkpoint if sync was successful and notify scheduler.

        Args:
            final_report: The final sync report containing statistics and success rate
        """
        try:
            success_rate = final_report.get("success_rate", 0) / 100  # Convert percentage to decimal
            sync_successful = success_rate >= self.checkpoint_success_threshold

            # Update checkpoint only if feature is enabled
            if self.use_update_checkpoint:
                if sync_successful:
                    # Update checkpoint with current timestamp
                    if self.update_checkpoint_manager.save_checkpoint(self.sync_start_time):
                        logger.info(
                            f"✅ Update checkpoint saved successfully - "
                            f"Success rate: {success_rate:.2%} >= {self.checkpoint_success_threshold:.2%} threshold"
                        )
                        final_report["update_checkpoint_saved"] = True
                        final_report["update_checkpoint_timestamp"] = self.sync_start_time.isoformat()
                    else:
                        logger.warning("⚠️ Failed to save update checkpoint")
                        final_report["update_checkpoint_saved"] = False
                        sync_successful = False  # Mark as unsuccessful if checkpoint save failed
                else:
                    logger.info(
                        f"ℹ️ Update checkpoint not saved - "
                        f"Success rate: {success_rate:.2%} < {self.checkpoint_success_threshold:.2%} threshold"
                    )
                    final_report["update_checkpoint_saved"] = False
                    final_report["update_checkpoint_reason"] = "Success rate below threshold"

            # ALWAYS notify scheduler about sync completion (regardless of checkpoint setting)
            # This triggers reverse stock sync after configured delay
            try:
                from app.core.scheduler import notify_rms_sync_completed
                notify_rms_sync_completed(success=sync_successful)
                logger.info(f"📝 Scheduler notified of RMS→Shopify sync (success: {sync_successful})")
                final_report["scheduler_notified"] = True
            except Exception as notify_error:
                logger.error(f"Error notifying scheduler: {notify_error}")
                final_report["scheduler_notified"] = False
                final_report["scheduler_notification_error"] = str(notify_error)

        except Exception as e:
            logger.error(f"❌ Error updating checkpoint: {e}")
            final_report["update_checkpoint_error"] = str(e)

            # Notify scheduler about failed sync
            try:
                from app.core.scheduler import notify_rms_sync_completed
                notify_rms_sync_completed(success=False)
            except Exception as notify_error:
                logger.error(f"Error notifying scheduler about failed sync: {notify_error}")


async def sync_rms_to_shopify(
    force_update: bool = False,
    batch_size: int = None,
    filter_categories: Optional[List[str]] = None,
    include_zero_stock: bool = False,
    ccod: Optional[str] = None,
    resume_from_checkpoint: bool = True,
    checkpoint_frequency: int = 100,
    force_fresh_start: bool = False,
    sync_id: Optional[str] = None,
    use_streaming: bool = True,
    page_size: int = 100,
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronización RMS → Shopify.

    Args:
        force_update: Forzar actualización
        batch_size: Tamaño del lote para procesamiento
        filter_categories: Categorías a filtrar
        include_zero_stock: Incluir productos sin stock
        ccod: CCOD específico a sincronizar (opcional)
        resume_from_checkpoint: Reanudar desde checkpoint si existe
        checkpoint_frequency: Frecuencia de guardado de checkpoint
        force_fresh_start: Forzar inicio desde cero ignorando checkpoints
        sync_id: ID único de la sincronización (se genera automáticamente si no se proporciona)
        use_streaming: Usar procesamiento por streaming (recomendado para grandes volúmenes)
        page_size: Número de productos (CCODs) por página para extracción de RMS (default: 100)

    Returns:
        Dict: Resultado de la sincronización con información de checkpoint
    """
    sync_service = RMSToShopifySyncOrchestrator(
        sync_id=sync_id,
        checkpoint_frequency=checkpoint_frequency,
        resume_from_checkpoint=resume_from_checkpoint,
        force_fresh_start=force_fresh_start,
    )

    try:
        await sync_service.initialize()

        result = await sync_service.sync_products(
            force_update=force_update,
            batch_size=batch_size,
            filter_categories=filter_categories,
            include_zero_stock=include_zero_stock,
            cod_product=ccod,
            use_streaming=use_streaming,
            page_size=page_size,
        )
        return result

    finally:
        await sync_service.close()
