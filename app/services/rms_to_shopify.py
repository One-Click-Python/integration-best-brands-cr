"""
Microservicio de sincronización RMS → Shopify.

Este módulo maneja la sincronización de productos, inventarios y precios
desde Microsoft Retail Management System hacia Shopify.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.core.config import get_settings
from app.core.logging_config import LogContext, log_sync_operation
from app.services.sync_checkpoint import SyncCheckpointManager
from app.utils.error_handler import (
    ErrorAggregator,
    SyncException,
)

settings = get_settings()
logger = logging.getLogger(__name__)


class SyncProgressTracker:
    """Tracker para progreso de sincronización con ETA y métricas."""

    def __init__(self, total_items: int, operation_name: str = "Sync"):
        self.total_items = total_items
        self.operation_name = operation_name
        self.processed_items = 0
        self.start_time = time.time()
        self.last_log_time = self.start_time
        self.stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    def update(self, created: int = 0, updated: int = 0, skipped: int = 0, errors: int = 0):
        """Actualiza las estadísticas y el progreso."""
        self.processed_items += 1
        self.stats["created"] += created
        self.stats["updated"] += updated
        self.stats["skipped"] += skipped
        self.stats["errors"] += errors

    def get_progress_info(self) -> Dict[str, Any]:
        """Obtiene información completa del progreso."""
        current_time = time.time()
        elapsed = current_time - self.start_time

        if self.processed_items == 0:
            return {"percentage": 0.0, "eta_seconds": 0, "rate_per_minute": 0.0, "elapsed_str": "00:00:00"}

        percentage = (self.processed_items / self.total_items) * 100
        rate_per_minute = (self.processed_items / elapsed) * 60 if elapsed > 0 else 0

        remaining_items = self.total_items - self.processed_items
        eta_seconds = (remaining_items / rate_per_minute) * 60 if rate_per_minute > 0 else 0

        return {
            "percentage": percentage,
            "eta_seconds": eta_seconds,
            "rate_per_minute": rate_per_minute,
            "elapsed_str": self._format_duration(elapsed),
            "eta_str": self._format_duration(eta_seconds),
            "processed": self.processed_items,
            "total": self.total_items,
        }

    def should_log_progress(self, force: bool = False) -> bool:
        """Determina si debe hacer log del progreso (cada 10% o cada 30 segundos)."""
        current_time = time.time()
        progress_info = self.get_progress_info()

        # Log cada 10% de progreso o cada 30 segundos
        percentage_milestone = int(progress_info["percentage"]) % 10 == 0
        time_milestone = (current_time - self.last_log_time) >= 30

        if force or percentage_milestone or time_milestone:
            self.last_log_time = current_time
            return True
        return False

    def log_progress(self, prefix: str = ""):
        """Hace log del progreso actual."""
        info = self.get_progress_info()

        logger.info(
            f"{prefix}📊 {self.operation_name}: "
            f"{info['processed']}/{info['total']} ({info['percentage']:.1f}%) | "
            f"⏱️ {info['elapsed_str']} elapsed, ETA: {info['eta_str']} | "
            f"⚡ {info['rate_per_minute']:.1f}/min | "
            f"✅ {self.stats['created']} created, "
            f"🔄 {self.stats['updated']} updated, "
            f"⏭️ {self.stats['skipped']} skipped, "
            f"❌ {self.stats['errors']} errors"
        )

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Formatea duración en formato HH:MM:SS."""
        if seconds < 0:
            return "00:00:00"
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"


class RMSToShopifySync:
    """
    Servicio principal para sincronización de RMS a Shopify.
    """

    def __init__(self):
        """Inicializa el servicio de sincronización."""
        self.rms_handler = None
        self.shopify_client = None
        self.inventory_manager = None
        self.collection_manager = None
        self.primary_location_id = None
        self.error_aggregator = ErrorAggregator()
        self.sync_id = f"rms_to_shopify_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"  # noqa: F821
        self._include_zero_stock = False
        self.checkpoint_manager = SyncCheckpointManager(self.sync_id)
        self.batch_handle_cache = {}  # Cache para búsquedas por handle

        # Checkpoint configuration
        self._resume_from_checkpoint = True
        self._checkpoint_frequency = 100
        self._force_fresh_start = False

    async def initialize(self):
        """
        Inicializa las conexiones necesarias.

        Raises:
            SyncException: Si falla la inicialización
        """
        try:
            # Inicializar handler RMS
            from app.db.rms_handler import RMSHandler

            self.rms_handler = RMSHandler()
            await self.rms_handler.initialize()

            # Inicializar cliente Shopify GraphQL
            from app.db.shopify_graphql_client import ShopifyGraphQLClient

            self.shopify_client = ShopifyGraphQLClient()
            await self.shopify_client.initialize()

            # Inicializar gestor de inventario
            from app.services.inventory_manager import InventoryManager

            self.inventory_manager = InventoryManager(self.shopify_client)
            await self.inventory_manager.initialize()

            # Inicializar gestor de colecciones
            from app.services.collection_manager import CollectionManager

            self.collection_manager = CollectionManager(self.shopify_client)
            await self.collection_manager.initialize()

            # Obtener ubicación principal para inventario
            self.primary_location_id = await self.shopify_client.get_primary_location_id()
            if self.primary_location_id:
                logger.info(f"Using primary location: {self.primary_location_id}")
            else:
                logger.warning("No primary location found - inventory updates may fail")

            # Inicializar checkpoint manager
            await self.checkpoint_manager.initialize()

            logger.info(f"Sync service initialized - ID: {self.sync_id}")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize sync service: {str(e)}",
                service="rms_to_shopify",
                operation="initialize",
            ) from e

    def configure_checkpoint_behavior(
        self, resume_from_checkpoint: bool = True, checkpoint_frequency: int = 100, force_fresh_start: bool = False
    ):
        """
        Configura el comportamiento de checkpoints.

        Args:
            resume_from_checkpoint: Reanudar desde checkpoint si existe
            checkpoint_frequency: Frecuencia de guardado de checkpoint
            force_fresh_start: Forzar inicio desde cero ignorando checkpoints
        """
        self._resume_from_checkpoint = resume_from_checkpoint
        self._checkpoint_frequency = checkpoint_frequency
        self._force_fresh_start = force_fresh_start

        logger.info(
            f"📋 Checkpoint configuration: resume={resume_from_checkpoint}, "
            f"frequency={checkpoint_frequency}, fresh_start={force_fresh_start}"
        )

    async def close(self):
        """
        Cierra el servicio de sincronización y libera recursos.
        """
        try:
            logger.info(f"Closing sync service - ID: {self.sync_id}")

            # Cerrar handler RMS
            if self.rms_handler:
                await self.rms_handler.close()
                logger.debug("RMS handler closed")

            # Cerrar cliente Shopify
            if self.shopify_client:
                await self.shopify_client.close()
                logger.debug("Shopify client closed")

            # Cerrar checkpoint manager
            if self.checkpoint_manager:
                await self.checkpoint_manager.close()
                logger.debug("Checkpoint manager closed")

            # El inventory_manager no necesita cleanup específico
            # ya que usa el shopify_client que ya se cerró

            logger.info(f"Sync service closed successfully - ID: {self.sync_id}")

        except Exception as e:
            logger.error(f"Error closing sync service: {e}")
            # No re-raise para evitar problemas en el shutdown

    async def sync_products(
        self,
        force_update: bool = False,
        batch_size: int = None,
        filter_categories: Optional[List[str]] = None,
        include_zero_stock: bool = False,
        cod_product: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Sincroniza productos de RMS a Shopify.

        Args:
            force_update: Forzar actualización de productos existentes
            batch_size: Tamaño del lote para procesamiento
            filter_categories: Filtrar por categorías específicas
            include_zero_stock: Incluir productos sin stock
            cod_product: CCOD específico a sincronizar (opcional)

        Returns:
            Dict: Resultado de la sincronización

        Raises:
            SyncException: Sí falla la sincronización
        """
        batch_size = batch_size or settings.SYNC_BATCH_SIZE

        self._include_zero_stock = include_zero_stock

        with LogContext(sync_id=self.sync_id, operation="sync_products"):
            logger.info(
                f"Starting product sync - Force: {force_update}, Batch: {batch_size}, "
                f"Include zero stock: {include_zero_stock}, CCOD: {cod_product or 'ALL'}"
            )

            try:
                # 1. Extraer productos de RMS
                rms_products = await self._extract_rms_products(filter_categories, cod_product)
                logger.info(f"📦 Extracted {len(rms_products)} products from RMS")

                # 2. Verificar si existe checkpoint para reanudar
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

                # Check checkpoint configuration
                should_resume = (
                    self._resume_from_checkpoint
                    and not self._force_fresh_start
                    and checkpoint
                    and await self.checkpoint_manager.should_resume()
                )

                if should_resume and checkpoint:
                    logger.info(
                        f"📊 Resuming sync from checkpoint: {checkpoint['processed_count']}/{
                            checkpoint['total_count']
                        } products"
                    )
                    start_index = checkpoint["processed_count"]
                    initial_stats = checkpoint["stats"]
                    initial_stats["resumed_from_checkpoint"] = True
                else:
                    if self._force_fresh_start:
                        logger.info("🚀 Starting fresh sync - forced fresh start")
                        # Clear any existing checkpoint
                        await self.checkpoint_manager.delete_checkpoint()
                    elif not self._resume_from_checkpoint:
                        logger.info("🚀 Starting fresh sync - resume disabled")
                    else:
                        logger.info("🚀 Starting fresh sync - no valid checkpoint found")

                # 3. Procesar en lotes (sin cargar todos los productos en memoria)
                sync_stats = await self._process_products_in_batches_optimized(
                    rms_products, force_update, batch_size, start_index, initial_stats
                )

                # 4. Generar reporte final
                return self._generate_sync_report(sync_stats)

            except Exception as e:
                self.error_aggregator.add_error(e)
                logger.error(f"Critical error in sync_products: {e}")

                # Return error report instead of raising
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

    async def _extract_rms_products_with_variants(
        self, filter_categories: Optional[List[str]] = None, ccod: Optional[str] = None
    ) -> List[ShopifyProductInput]:
        """
        Extrae productos de RMS usando el nuevo sistema de múltiples variantes por CCOD.

        Args:
            filter_categories: Categorías a filtrar
            ccod: CCOD específico a sincronizar (opcional)

        Returns:
            List: Lista de productos Shopify con múltiples variantes
        """
        try:
            logger.info("🔄 Extrayendo productos con sistema de múltiples variantes por CCOD")

            # Query para extraer TODOS los items de RMS para agrupar por CCOD
            query = """
            SELECT 
                Familia, Genero, Categoria, CCOD, C_ARTICULO,
                ItemID, Description, color, talla, Quantity,
                -- Calcular precios con tax incluido y redondear a 2 decimales
                ROUND(Price * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2) AS Price,
                CASE 
                    WHEN SalePrice IS NOT NULL AND SalePrice > 0 
                    THEN ROUND(SalePrice * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2)
                    ELSE NULL
                END AS SalePrice,
                ExtendedCategory, Tax,
                SaleStartDate, SaleEndDate
            FROM View_Items 
            WHERE CCOD IS NOT NULL 
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            """

            # Agregar filtro de CCOD específico si se especifica
            if ccod:
                query += f" AND CCOD = '{ccod}'"

            # Agregar filtro de categorías si se especifica
            if filter_categories:
                categories_str = "', '".join(filter_categories)
                query += f" AND Categoria IN ('{categories_str}')"

            # NOTA: Siempre incluir productos con stock 0 para poder actualizar productos existentes
            # La lógica de crear vs actualizar se maneja después de verificar si existe en Shopify

            query += " ORDER BY CCOD, talla"

            logger.info("📋 Ejecutando query para extraer items de RMS...")
            items_data = await self.rms_handler.execute_custom_query(query)
            logger.info(f"📊 Extraídos {len(items_data)} items de RMS")

            # Logging detallado de CCODs extraídos
            ccods_extracted = set(item.get("CCOD") for item in items_data if item.get("CCOD"))
            logger.info(f"📋 CCODs únicos extraídos: {len(ccods_extracted)}")

            # Convertir a RMSViewItem objects
            rms_items = []
            negative_quantity_count = 0
            for item_data in items_data:
                try:
                    # Normalizar cantidad: convertir valores negativos a 0
                    raw_quantity = item_data.get("Quantity", 0)
                    normalized_quantity = max(0, int(raw_quantity))

                    # Log de normalizaciones de cantidades negativas
                    if raw_quantity < 0:
                        negative_quantity_count += 1
                        c_articulo = item_data.get("C_ARTICULO", "unknown")
                        logger.debug(
                            f"📊 Cantidad negativa normalizada: {raw_quantity} → {normalized_quantity}\
                                para item {c_articulo}"
                        )

                    rms_item = RMSViewItem(
                        familia=item_data.get("Familia", ""),
                        genero=item_data.get("Genero", ""),
                        categoria=item_data.get("Categoria", ""),
                        ccod=item_data.get("CCOD", ""),
                        c_articulo=item_data.get("C_ARTICULO", ""),
                        item_id=item_data.get("ItemID", 0),
                        description=item_data.get("Description", ""),
                        color=item_data.get("color", ""),
                        talla=item_data.get("talla", ""),
                        quantity=normalized_quantity,
                        price=Decimal(str(item_data.get("Price", 0))),
                        sale_price=Decimal(str(item_data.get("SalePrice", 0))) if item_data.get("SalePrice") else None,
                        extended_category=item_data.get("ExtendedCategory", ""),
                        tax=int(item_data.get("Tax", 13)),
                        sale_start_date=item_data.get("SaleStartDate"),
                        sale_end_date=item_data.get("SaleEndDate"),
                    )
                    rms_items.append(rms_item)
                except Exception as e:
                    logger.warning(f"❌ --> (RMSViewItem) Error procesando item RMS: {e}")
                    continue

            logger.info(f"✅ Procesados {len(rms_items)} items válidos de RMS")
            if negative_quantity_count > 0:
                logger.info(f"📊 Normalizadas {negative_quantity_count} cantidades negativas a 0")

            # Usar el nuevo sistema de variantes para agrupar por CCOD
            from app.services.variant_mapper import create_products_with_variants

            logger.info("🔄 Agrupando items por CCOD y creando productos con variantes...")
            shopify_products = await create_products_with_variants(
                rms_items, self.shopify_client, self.primary_location_id
            )

            logger.info(f"🎯 Generados {len(shopify_products)} productos con múltiples variantes")
            logger.info(f"📈 Reducción: {len(rms_items)} items → {len(shopify_products)} productos")

            return shopify_products

        except Exception as e:
            logger.error(f"❌ Error extracting RMS products with variants: {e}")
            raise SyncException(f"Failed to extract RMS products: {e}") from e

    async def _extract_rms_products(
        self, filter_categories: Optional[List[str]] = None, ccod: Optional[str] = None
    ) -> List[ShopifyProductInput]:
        """
        Extrae productos de RMS usando el sistema de múltiples variantes por CCOD.

        Args:
            filter_categories: Categorías a filtrar
            ccod: CCOD específico a sincronizar (opcional)

        Returns:
            List[ShopifyProductInput]: Lista de productos con múltiples variantes
        """
        if ccod:
            logger.info(f"🎯 Using new variants system for single CCOD: {ccod}")
        else:
            logger.info("🔄 Using new variants system for product extraction")
        return await self._extract_rms_products_with_variants(filter_categories, ccod)

    async def _check_products_exist_batch(self, handles: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Verifica la existencia de productos por sus handles usando búsqueda por lotes.

        Args:
            handles: Lista de handles de productos a verificar

        Returns:
            Dict: Mapping handle -> producto existente (o None si no existe)
        """
        if not handles:
            return {}

        # Usar cache para evitar búsquedas duplicadas
        cached_results = {}
        uncached_handles = []

        for handle in handles:
            if handle in self.batch_handle_cache:
                cached_results[handle] = self.batch_handle_cache[handle]
            else:
                uncached_handles.append(handle)

        results = cached_results.copy()

        # Buscar handles no cacheados
        if uncached_handles:
            try:
                # Usar el nuevo método de búsqueda por lotes
                batch_results = await self.shopify_client.get_products_by_handles_batch(uncached_handles)

                # Actualizar cache y resultados
                for handle, product in batch_results.items():
                    self.batch_handle_cache[handle] = product
                    results[handle] = product

                # Log de resultados
                found_count = sum(1 for p in batch_results.values() if p is not None)
                logger.debug(f"🔍 Batch check: {found_count}/{len(uncached_handles)} products found in Shopify")

            except Exception as e:
                logger.error(f"Error in batch product check: {e}")
                # En caso de error, asumir que no existen
                for handle in uncached_handles:
                    results[handle] = None

        return results

    async def _process_products_in_batches_optimized(
        self,
        rms_products: List[ShopifyProductInput],
        force_update: bool,
        batch_size: int,
        start_index: int = 0,
        initial_stats: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Procesa productos con búsqueda optimizada por lotes y checkpoints.

        Args:
            rms_products: Lista de productos de RMS a sincronizar
            force_update: Forzar actualización
            batch_size: Tamaño del lote
            start_index: Índice de inicio (para reanudar)
            initial_stats: Estadísticas iniciales (para reanudar)

        Returns:
            Dict: Estadísticas de sincronización
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

        # Inicializar progress tracker
        progress_tracker = SyncProgressTracker(total_items=len(rms_products), operation_name="Optimized Product Sync")

        total_products = len(rms_products)
        products_to_process = rms_products[start_index:]

        logger.info(
            f"🚀 Starting optimized sync: {len(products_to_process)} products "
            f"(starting from index {start_index}/{total_products})"
        )

        # Procesar en lotes
        for i in range(0, len(products_to_process), batch_size):
            batch = products_to_process[i : i + batch_size]
            batch_number = (start_index + i) // batch_size + 1
            total_batches = (total_products + batch_size - 1) // batch_size
            current_index = start_index + i

            batch_start_time = time.time()
            logger.info(f"🔄 Processing batch {batch_number}/{total_batches} ({len(batch)} products)")

            # Extraer handles del lote para verificar existencia
            batch_handles = [product.handle for product in batch if product.handle]

            # Verificar existencia de productos en Shopify
            existing_products = await self._check_products_exist_batch(batch_handles)

            # Procesar lote con información de productos existentes
            batch_stats = await self._process_product_batch_optimized(
                batch, existing_products, force_update, progress_tracker
            )

            # Agregar estadísticas
            for key in stats:
                stats[key] += batch_stats.get(key, 0)

            # Guardar checkpoint según frecuencia configurada
            if (current_index + len(batch)) % self._checkpoint_frequency == 0 or (
                i + batch_size >= len(products_to_process)
            ):
                last_ccod = batch[-1].tags[0].replace("ccod_", "") if batch and batch[-1].tags else "unknown"

                await self.checkpoint_manager.save_checkpoint(
                    last_processed_ccod=last_ccod,
                    processed_count=start_index + i + len(batch),
                    total_count=total_products,
                    stats=stats,
                    batch_number=batch_number,
                )

            # Log de estadísticas del batch
            batch_duration = time.time() - batch_start_time
            logger.info(
                f"✅ Batch {batch_number} completed in {batch_duration:.1f}s | "
                f"Created: {batch_stats['created']}, Updated: {batch_stats['updated']}, "
                f"Skipped: {batch_stats['skipped']}, Errors: {batch_stats['errors']}"
            )

            # Log de progreso general
            progress_tracker.log_progress("Batch Progress - ")

            # Pausa entre lotes para no sobrecargar la API
            if i + batch_size < len(products_to_process):
                # Rate limiting condicional basado en batch_size
                if batch_size > 2:
                    sleep_time = 3  # Para lotes grandes (reducido de 5s)
                    logger.debug(f"🕐 Rate limiting: {sleep_time}s pause")
                else:
                    sleep_time = 1  # Para lotes pequeños
                    logger.debug(f"🕐 Minimal pause: {sleep_time}s")

                await asyncio.sleep(sleep_time)

        # Log final del progreso
        progress_tracker.log_progress("Final Progress - ")

        # Eliminar checkpoint al completar exitosamente
        if stats["total_processed"] >= total_products:
            await self.checkpoint_manager.delete_checkpoint()
            logger.info("🎉 Sync completed successfully - checkpoint deleted")

        return stats

    async def _process_products_in_batches(
        self,
        rms_products: List[ShopifyProductInput],
        shopify_products: Dict[str, Dict[str, Any]],
        force_update: bool,
        batch_size: int,
    ) -> Dict[str, Any]:
        """
        Procesa productos con múltiples variantes en lotes.

        Args:
            rms_products: Lista de ShopifyProductInput con múltiples variantes
            shopify_products: Productos existentes indexados por CCOD y SKU
            force_update: Forzar actualización
            batch_size: Tamaño del lote

        Returns:
            Dict: Estadísticas de sincronización
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

        # Inicializar progress tracker
        progress_tracker = SyncProgressTracker(total_items=len(rms_products), operation_name="Product Sync")

        logger.info(f"🚀 Starting sync of {len(rms_products)} products in batches of {batch_size}")

        # Procesar en lotes
        for i in range(0, len(rms_products), batch_size):
            batch = rms_products[i : i + batch_size]
            batch_number = (i // batch_size) + 1
            total_batches = (len(rms_products) + batch_size - 1) // batch_size

            batch_start_time = time.time()
            logger.info(f"🔄 Processing batch {batch_number}/{total_batches} ({len(batch)} products)")

            # Procesar lote
            batch_stats = await self._process_product_batch(batch, shopify_products, force_update, progress_tracker)

            # Agregar estadísticas
            for key in stats:
                stats[key] += batch_stats.get(key, 0)

            # Log de estadísticas del batch
            batch_duration = time.time() - batch_start_time
            logger.info(
                f"✅ Batch {batch_number} completed in {batch_duration:.1f}s | "
                f"Created: {batch_stats['created']}, Updated: {batch_stats['updated']}, "
                f"Skipped: {batch_stats['skipped']}, Errors: {batch_stats['errors']}"
            )

            # Log de progreso general
            progress_tracker.log_progress("Batch Progress - ")

            # Pausa entre lotes para no sobrecargar la API
            if i + batch_size < len(rms_products):
                # Rate limiting condicional basado en batch_size
                if batch_size > 2:
                    sleep_time = 5  # Para lotes grandes
                    logger.debug(f"🕐 Rate limiting: {sleep_time}s pause (batch_size={batch_size})")
                else:
                    sleep_time = 1  # Para lotes pequeños
                    logger.debug(f"🕐 Minimal pause: {sleep_time}s")

                await asyncio.sleep(sleep_time)

        # Log final del progreso
        progress_tracker.log_progress("Final Progress - ")

        return stats

    async def _process_product_batch_optimized(
        self,
        batch: List[ShopifyProductInput],
        existing_products: Dict[str, Optional[Dict[str, Any]]],
        force_update: bool,
        progress_tracker: Optional[SyncProgressTracker] = None,
    ) -> Dict[str, Any]:
        """
        Procesa un lote de productos con búsqueda optimizada.

        Args:
            batch: Lote de productos a procesar
            existing_products: Productos existentes encontrados por handle
            force_update: Forzar actualización
            progress_tracker: Tracker de progreso opcional

        Returns:
            Dict: Estadísticas del lote
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

        # Track progress for this batch
        batch_total = len(batch)

        for idx, shopify_input in enumerate(batch, 1):
            # Calculate progress percentage
            progress_percentage = (idx / batch_total) * 100

            ccod = None  # Initialize ccod before try block
            categoria = None
            familia = None
            extended_category = None

            try:
                # Log detallado solo si el nivel de logging es DEBUG
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"🔄 Processing product [{idx}/{batch_total}] ({progress_percentage:.1f}%): "
                        f"{shopify_input.title}"
                    )

                # Extraer CCOD y categorías de los tags del producto
                for tag in shopify_input.tags or []:
                    if tag.startswith("ccod_"):
                        ccod = tag.replace("ccod_", "").upper()

                # Extraer categorías de los metafields
                for metafield in shopify_input.metafields or []:
                    if metafield.get("namespace") == "rms":
                        if metafield.get("key") == "categoria":
                            categoria = metafield.get("value")
                        elif metafield.get("key") == "familia":
                            familia = metafield.get("value")
                        elif metafield.get("key") == "extended_category":
                            extended_category = metafield.get("value")

                if not ccod:
                    logger.warning(f"⚠️ No CCOD found in product tags: {shopify_input.title}")
                    stats["errors"] += 1
                    continue

                # Buscar producto existente usando el resultado de la búsqueda por lotes
                existing_product = existing_products.get(shopify_input.handle)

                if existing_product:
                    # Producto existe - decidir si actualizar
                    if force_update:
                        # Actualizar producto siguiendo el flujo especificado
                        updated_product = await self._update_shopify_product(shopify_input, existing_product)

                        if updated_product:
                            stats["updated"] += 1
                            stats["inventory_updated"] += 1
                            log_sync_operation("update", "shopify", ccod=ccod)

                            # Calcular stock total para logging mejorado
                            total_stock = 0
                            for variant in shopify_input.variants or []:
                                if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                                    for inv_qty in variant.inventoryQuantities:
                                        total_stock += inv_qty.get("availableQuantity", 0)
                            stock_status = f" (stock: {total_stock})"

                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(f"✅ Updated: {ccod} - {shopify_input.title}{stock_status}")

                            # Sincronizar colecciones del producto
                            if self.collection_manager and updated_product.get("id"):
                                try:
                                    collections_added = await self.collection_manager.add_product_to_collections(
                                        product_id=updated_product["id"],
                                        product_handle=shopify_input.handle,
                                        categoria=categoria,
                                        familia=familia,
                                        extended_category=extended_category,
                                    )
                                    if collections_added and logger.isEnabledFor(logging.DEBUG):
                                        logger.debug(
                                            f"✅ Product collections updated: {len(collections_added)} collections"
                                        )
                                except Exception as e:
                                    logger.warning(f"Failed to update product collections: {e}")
                        else:
                            stats["errors"] += 1
                            logger.error(
                                f"❌ Failed to update product: {ccod} "
                                f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                            )
                    else:
                        # Skip si no es force_update
                        stats["skipped"] += 1
                        logger.info(
                            f"⏭️ Skipped existing product: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                        )
                else:
                    # Verificar si tiene stock antes de crear producto nuevo
                    total_stock = 0
                    for variant in shopify_input.variants or []:
                        if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                            for inv_qty in variant.inventoryQuantities:
                                total_stock += inv_qty.get("availableQuantity", 0)

                    if total_stock > 0 or settings.SYNC_CREATE_ZERO_STOCK_PRODUCTS:
                        # Crear producto siguiendo el flujo especificado
                        created_product = await self._create_shopify_product(shopify_input)
                    else:
                        # No crear productos nuevos con stock 0 (configurable)
                        created_product = None
                        stats["skipped"] += 1
                        logger.info(
                            f"⏭️ Skipped creating new product with zero stock: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title} (total_stock: {total_stock})"
                        )

                    if created_product:
                        stats["created"] += 1
                        stats["inventory_updated"] += 1
                        log_sync_operation("create", "shopify", ccod=ccod)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                f"✅ Created: {ccod} - {shopify_input.title} ({len(shopify_input.variants)} variants)"
                            )

                        # Agregar producto a colecciones basadas en categorías
                        if self.collection_manager and created_product.get("id"):
                            try:
                                collections_added = await self.collection_manager.add_product_to_collections(
                                    product_id=created_product["id"],
                                    categoria=categoria,
                                    familia=familia,
                                    extended_category=extended_category,
                                )
                                if collections_added and logger.isEnabledFor(logging.DEBUG):
                                    logger.debug(f"✅ Product added to {len(collections_added)} collections")
                            except Exception as e:
                                logger.warning(f"Failed to add product to collections: {e}")
                    else:
                        stats["errors"] += 1
                        logger.error(
                            f"❌ Failed to create product: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                        )

                stats["total_processed"] += 1

                # Actualizar progress tracker
                if progress_tracker:
                    # Determinar qué acción se realizó en este producto
                    created = 1 if stats["created"] > stats.get("_prev_created", 0) else 0
                    updated = 1 if stats["updated"] > stats.get("_prev_updated", 0) else 0
                    skipped = 1 if stats["skipped"] > stats.get("_prev_skipped", 0) else 0
                    errors = 1 if stats["errors"] > stats.get("_prev_errors", 0) else 0

                    progress_tracker.update(created=created, updated=updated, skipped=skipped, errors=errors)

                    # Log progreso inteligente (solo en hitos importantes)
                    if progress_tracker.should_log_progress():
                        progress_tracker.log_progress()

                    # Guardar estadísticas previas para la siguiente comparación
                    stats["_prev_created"] = stats["created"]
                    stats["_prev_updated"] = stats["updated"]
                    stats["_prev_skipped"] = stats["skipped"]
                    stats["_prev_errors"] = stats["errors"]

            except Exception as e:
                stats["errors"] += 1
                self.error_aggregator.add_error(
                    e,
                    {"ccod": ccod or "unknown", "title": shopify_input.title},
                )

                # Actualizar progress tracker con error
                if progress_tracker:
                    progress_tracker.update(errors=1)

                # Log error simplificado
                logger.error(f"❌ Error processing {ccod or 'unknown'}: {str(e)}")

        return stats

    async def _process_product_batch(
        self,
        batch: List[ShopifyProductInput],
        shopify_products: Dict[str, Dict[str, Any]],
        force_update: bool,
        progress_tracker: Optional[SyncProgressTracker] = None,
    ) -> Dict[str, Any]:
        """
        Procesa un lote de productos con múltiples variantes.

        Args:
            batch: Lote de ShopifyProductInput con múltiples variantes
            shopify_products: Productos existentes indexados por CCOD y SKU
            force_update: Forzar actualización
            progress_tracker: Tracker de progreso opcional

        Returns:
            Dict: Estadísticas del lote
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

        # Track progress for this batch
        batch_total = len(batch)

        for idx, shopify_input in enumerate(batch, 1):
            # Calculate progress percentage
            progress_percentage = (idx / batch_total) * 100

            ccod = None  # Initialize ccod before try block
            categoria = None
            familia = None
            extended_category = None

            try:
                # Solo log detallado si el nivel de logging es DEBUG
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        f"🔄 Processing product [{idx}/{batch_total}] ({progress_percentage:.1f}%): "
                        f"{shopify_input.title}"
                    )

                # Extraer CCOD y categorías de los tags del producto
                for tag in shopify_input.tags or []:
                    if tag.startswith("ccod_"):
                        ccod = tag.replace("ccod_", "").upper()
                    # Las categorías también vienen como tags desde el mapper

                # Extraer categorías de los metafields
                for metafield in shopify_input.metafields or []:
                    if metafield.get("namespace") == "rms":
                        if metafield.get("key") == "categoria":
                            categoria = metafield.get("value")
                        elif metafield.get("key") == "familia":
                            familia = metafield.get("value")
                        elif metafield.get("key") == "extended_category":
                            extended_category = metafield.get("value")

                if not ccod:
                    logger.warning(f"⚠️ No CCOD found in product tags: {shopify_input.title}")
                    stats["errors"] += 1
                    continue

                # Log de preparación solo en modo DEBUG
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(f"✅ Prepared CCOD: {ccod}, handle: {shopify_input.handle}, categoria: {categoria}")

                # Buscar producto existente por handle (más eficiente)
                existing_product = shopify_products["by_handle"].get(shopify_input.handle)

                if existing_product:
                    # Producto existe - decidir si actualizar
                    if force_update:
                        # FLUJO COMPLETO: Actualizar producto siguiendo el flujo especificado
                        # B→C→D→E→F→G→H/I→J (Update → Create Variants → Update Inventory → Create Metafields
                        # → Verify Sale Price → Create Discount → Complete)
                        updated_product = await self._update_shopify_product(shopify_input, existing_product)

                        if updated_product:
                            stats["updated"] += 1
                            # El inventario se actualiza dentro del MultipleVariantsCreator
                            stats["inventory_updated"] += 1
                            log_sync_operation("update", "shopify", ccod=ccod)

                            # Calcular stock total para logging mejorado
                            total_stock = 0
                            for variant in shopify_input.variants or []:
                                if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                                    for inv_qty in variant.inventoryQuantities:
                                        total_stock += inv_qty.get("availableQuantity", 0)
                            stock_status = f" (stock: {total_stock})"

                            if logger.isEnabledFor(logging.DEBUG):
                                logger.debug(f"✅ Updated: {ccod} - {shopify_input.title}{stock_status}")

                            # Sincronizar colecciones del producto
                            if self.collection_manager and updated_product.get("id"):
                                try:
                                    # Obtener colecciones actuales del producto
                                    # Por ahora, simplemente agregar a las colecciones apropiadas
                                    collections_added = await self.collection_manager.add_product_to_collections(
                                        product_id=updated_product["id"],
                                        product_handle=shopify_input.handle,
                                        categoria=categoria,
                                        familia=familia,
                                        extended_category=extended_category,
                                    )
                                    if collections_added and logger.isEnabledFor(logging.DEBUG):
                                        logger.debug(
                                            f"✅ Product collections updated: {len(collections_added)} collections"
                                        )
                                except Exception as e:
                                    logger.warning(f"Failed to update product collections: {e}")
                        else:
                            stats["errors"] += 1
                            logger.error(
                                f"❌ Failed to update product: {ccod} "
                                f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                            )
                    else:
                        # TODO: Implementar comparación inteligente para productos con múltiples variantes
                        # Por ahora, skip si no es force_update
                        stats["skipped"] += 1
                        logger.info(
                            f"⏭️ Skipped existing product: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                        )
                else:
                    # Verificar si tiene stock antes de crear producto nuevo
                    total_stock = 0
                    for variant in shopify_input.variants or []:
                        if hasattr(variant, "inventoryQuantities") and variant.inventoryQuantities:
                            for inv_qty in variant.inventoryQuantities:
                                total_stock += inv_qty.get("availableQuantity", 0)

                    if total_stock > 0 or settings.SYNC_CREATE_ZERO_STOCK_PRODUCTS:
                        # FLUJO COMPLETO: Crear producto siguiendo el flujo especificado
                        # A→B→C→D→E→F→G→H/I→J (Sync → Create Product → Create Variants → Update Inventory →
                        # Create Metafields → Verify Sale Price → Create Discount → Complete)
                        created_product = await self._create_shopify_product(shopify_input)
                    else:
                        # No crear productos nuevos con stock 0 (configurable)
                        created_product = None
                        stats["skipped"] += 1
                        logger.info(
                            f"⏭️ Skipped creating new product with zero stock: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title} (total_stock: {total_stock})"
                        )

                    if created_product:
                        stats["created"] += 1
                        stats["inventory_updated"] += 1  # El inventario se actualiza dentro del MultipleVariantsCreator
                        log_sync_operation("create", "shopify", ccod=ccod)
                        if logger.isEnabledFor(logging.DEBUG):
                            logger.debug(
                                f"✅ Created: {ccod} - {shopify_input.title} ({len(shopify_input.variants)} variants)"
                            )

                        # Agregar producto a colecciones basadas en categorías
                        if self.collection_manager and created_product.get("id"):
                            try:
                                collections_added = await self.collection_manager.add_product_to_collections(
                                    product_id=created_product["id"],
                                    categoria=categoria,
                                    familia=familia,
                                    extended_category=extended_category,
                                )
                                if collections_added and logger.isEnabledFor(logging.DEBUG):
                                    logger.debug(f"✅ Product added to {len(collections_added)} collections")
                            except Exception as e:
                                logger.warning(f"Failed to add product to collections: {e}")
                    else:
                        stats["errors"] += 1
                        logger.error(
                            f"❌ Failed to create product: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                        )

                stats["total_processed"] += 1

                # Actualizar progress tracker
                if progress_tracker:
                    # Determinar qué acción se realizó en este producto
                    created = 1 if stats["created"] > stats.get("_prev_created", 0) else 0
                    updated = 1 if stats["updated"] > stats.get("_prev_updated", 0) else 0
                    skipped = 1 if stats["skipped"] > stats.get("_prev_skipped", 0) else 0
                    errors = 1 if stats["errors"] > stats.get("_prev_errors", 0) else 0

                    progress_tracker.update(created=created, updated=updated, skipped=skipped, errors=errors)

                    # Log progreso inteligente (solo en hitos importantes)
                    if progress_tracker.should_log_progress():
                        progress_tracker.log_progress()

                    # Guardar estadísticas previas para la siguiente comparación
                    stats["_prev_created"] = stats["created"]
                    stats["_prev_updated"] = stats["updated"]
                    stats["_prev_skipped"] = stats["skipped"]
                    stats["_prev_errors"] = stats["errors"]

            except Exception as e:
                stats["errors"] += 1
                self.error_aggregator.add_error(
                    e,
                    {"ccod": ccod or "unknown", "title": shopify_input.title},
                )

                # Actualizar progress tracker con error
                if progress_tracker:
                    progress_tracker.update(errors=1)

                # Log error simplificado
                logger.error(f"❌ Error processing {ccod or 'unknown'}: {str(e)}")

        return stats

    async def _create_shopify_product(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Crea un producto en Shopify siguiendo el flujo completo especificado:
        B. Crear Producto →
        C. Crear Variantes →
        D. Actualizar Inventario →
        E. Crear Metafields →
        F. Verificar Precio de Oferta →
        G. ¿Tiene Sale Price? →
        H. Crear Descuento Automático (si aplica) →
        J. Producto Completo

        Args:
            shopify_input: Input del producto validado con variantes

        Returns:
            Dict: Producto creado con todas las variantes y flujo completo
        """
        try:
            # Usar el nuevo creador de múltiples variantes
            from app.services.multiple_variants_creator import MultipleVariantsCreator

            variants_creator = MultipleVariantsCreator(self.shopify_client, self.primary_location_id)
            created_product = await variants_creator.create_product_with_variants(shopify_input)

            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"

            logger.info(f"🎉 Successfully created product with multiple variants: {sku}")
            return created_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to create product in Shopify: {str(e)}",
                service="shopify",
                operation="create_product",
                failed_records=[shopify_input.model_dump()],
            ) from e

    async def _update_shopify_product(
        self, shopify_input: ShopifyProductInput, shopify_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza un producto en Shopify siguiendo el flujo completo especificado:
        B. Actualizar Producto →
        C. Sincronizar Variantes (crear nuevas, actualizar existentes) →
        D. Actualizar Inventario →
        E. Actualizar Metafields →
        F. Verificar Precio de Oferta →
        G. ¿Tiene Sale Price? →
        H. Actualizar Descuento Automático (si aplica) →
        J. Producto Completo

        Args:
            shopify_input: Datos actualizados del producto
            shopify_product: Producto existente

        Returns:
            Dict: Producto actualizado con flujo completo
        """
        try:
            # Usar el actualizador de múltiples variantes
            from app.services.multiple_variants_creator import MultipleVariantsCreator

            variants_creator = MultipleVariantsCreator(self.shopify_client, self.primary_location_id)

            # Obtener ID del producto existente
            product_id = shopify_product.get("id")
            if not product_id:
                raise ValueError("Product ID not found in existing product")

            # Actualizar producto con manejo de variantes múltiples
            updated_product = await variants_creator.update_product_with_variants(
                product_id, shopify_input, shopify_product
            )

            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"✅ Updated product with multiple variants in Shopify: {sku}")
            return updated_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to update product in Shopify: {str(e)}",
                service="shopify",
                operation="update_product",
                failed_records=[shopify_input.model_dump()],
            ) from e

    def _generate_sync_report(self, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        Genera reporte final de sincronización.

        Args:
            stats: Estadísticas de sincronización

        Returns:
            Dict: Reporte completo
        """
        error_summary = self.error_aggregator.get_summary()

        report = {
            "sync_id": self.sync_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "statistics": stats,
            "errors": error_summary,
            "success_rate": ((stats["total_processed"] - stats["errors"]) / max(stats["total_processed"], 1) * 100),
            "recommendations": self._generate_recommendations(stats, error_summary),
        }

        # Log reporte final mejorado
        logger.info(
            f"🎉 Sync completed - ID: {self.sync_id} | "
            f"✅ {stats['created']} created, 🔄 {stats['updated']} updated, "
            f"⏭️ {stats['skipped']} skipped, ❌ {stats['errors']} errors | "
            f"Success rate: {report['success_rate']:.1f}%"
        )

        return report

    def _generate_recommendations(self, stats: Dict[str, Any], error_summary: Dict[str, Any]) -> List[str]:
        """
        Genera recomendaciones basadas en resultados.

        Args:
            stats: Estadísticas de sync
            error_summary: Resumen de errores

        Returns:
            List: Lista de recomendaciones
        """
        recommendations = []

        if error_summary["error_count"] > 0:
            recommendations.append("Review error logs and fix data quality issues")

        if stats["skipped"] > stats["updated"]:
            recommendations.append("Consider force update if products seem outdated")

        if error_summary["error_count"] / max(stats["total_processed"], 1) > 0.1:
            recommendations.append("High error rate detected - review data mapping")

        return recommendations

    async def cleanup(self):
        """Limpia recursos utilizados."""
        try:
            if self.rms_handler:
                await self.rms_handler.close()

            if self.shopify_client:
                await self.shopify_client.close()

            logger.info(f"Sync service cleaned up - ID: {self.sync_id}")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# === FUNCIONES DE CONVENIENCIA ===


async def sync_rms_to_shopify(
    force_update: bool = False,
    batch_size: int = None,
    filter_categories: Optional[List[str]] = None,
    include_zero_stock: bool = False,
    ccod: Optional[str] = None,
    # Checkpoint parameters
    resume_from_checkpoint: bool = True,
    checkpoint_frequency: int = 100,
    force_fresh_start: bool = False,
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronización RMS → Shopify.

    Args:
        force_update: Forzar actualización
        batch_size: Tamaño del lote
        filter_categories: Categorías a filtrar
        include_zero_stock: Incluir productos sin stock
        ccod: CCOD específico a sincronizar (opcional)
        resume_from_checkpoint: Reanudar desde checkpoint si existe
        checkpoint_frequency: Frecuencia de guardado de checkpoint
        force_fresh_start: Forzar inicio desde cero ignorando checkpoints

    Returns:
        Dict: Resultado de la sincronización con información de checkpoint
    """
    sync_service = RMSToShopifySync()

    try:
        await sync_service.initialize()

        # Configure checkpoint behavior
        sync_service.configure_checkpoint_behavior(
            resume_from_checkpoint=resume_from_checkpoint,
            checkpoint_frequency=checkpoint_frequency,
            force_fresh_start=force_fresh_start,
        )

        result = await sync_service.sync_products(
            force_update=force_update,
            batch_size=batch_size,
            filter_categories=filter_categories,
            include_zero_stock=include_zero_stock,
            cod_product=ccod,
        )
        return result

    finally:
        await sync_service.cleanup()


async def get_sync_status() -> Dict[str, Any]:
    """
    Obtiene estado actual de sincronización.

    Returns:
        Dict: Estado de sincronización
    """
    # Implementar lógica para obtener estado
    # (consultar base de datos, archivos de estado, etc.)
    return {"status": "ready", "last_sync": None, "next_scheduled": None}
