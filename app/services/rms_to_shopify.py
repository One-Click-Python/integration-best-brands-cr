"""
Microservicio de sincronización RMS → Shopify.

Este módulo maneja la sincronización de productos, inventarios y precios
desde Microsoft Retail Management System hacia Shopify.
"""

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.core.config import get_settings
from app.core.logging_config import LogContext, log_sync_operation
from app.utils.error_handler import (
    ErrorAggregator,
    SyncException,
)

settings = get_settings()
logger = logging.getLogger(__name__)


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

            logger.info(f"Sync service initialized - ID: {self.sync_id}")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize sync service: {str(e)}",
                service="rms_to_shopify",
                operation="initialize",
            ) from e

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
                logger.info(f"❗️Extracted {len(rms_products)} products from RMS")

                # 2. Obtener productos existentes de Shopify
                shopify_products = await self._get_existing_shopify_products()
                logger.info(f"💎Found {len(shopify_products)} existing products in Shopify")

                # 3. Procesar en lotes
                sync_stats = await self._process_products_in_batches(
                    rms_products, shopify_products, force_update, batch_size
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
                Price, SalePrice, ExtendedCategory, Tax,
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

            # Agregar filtro para productos con stock (opcional)
            if not getattr(self, "_include_zero_stock", True):
                query += " AND Quantity > 0"

            query += " ORDER BY CCOD, talla"

            logger.info("📋 Ejecutando query para extraer items de RMS...")
            items_data = await self.rms_handler.execute_custom_query(query)
            logger.info(f"📊 Extraídos {len(items_data)} items de RMS")

            # Convertir a RMSViewItem objects
            rms_items = []
            for item_data in items_data:
                try:
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
                        quantity=int(item_data.get("Quantity", 0)),
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

    async def _get_existing_shopify_products(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene productos existentes de Shopify indexados por CCOD y SKU.

        Returns:
            Dict: Productos existentes con doble indexación:
            {
                "by_ccod": {ccod: product},
                "by_sku": {sku: product}
            }
        """
        try:
            logger.info("🔍 Starting to fetch all existing Shopify products...")
            products = await self.shopify_client.get_all_products()
            logger.info(f"✅ Successfully fetched {len(products)} products from Shopify")

            # Indexación dual: por handle y por SKU individual
            indexed_products = {"by_handle": {}, "by_sku": {}}

            for _, product in enumerate(products):
                product_title = product.get("title", "Unknown")
                product_handle = product.get("handle", "")

                # Indexar por handle (más eficiente que buscar en tags)
                if product_handle:
                    indexed_products["by_handle"][product_handle] = product
                    logger.debug(f"  Indexed product with handle: {product_handle}")
                else:
                    logger.debug(f"  Product {product_title} has no handle")

            sku_count = len(indexed_products["by_sku"])
            handle_count = len(indexed_products["by_handle"])

            logger.info(f"📋 Indexed {sku_count} products by SKU and {handle_count} by handle")

            # Log some examples if available
            if sku_count > 0:
                sample_skus = list(indexed_products["by_sku"].keys())[:5]
                logger.info(f"   Sample SKUs: {sample_skus}")

            if handle_count > 0:
                sample_handles = list(indexed_products["by_handle"].keys())[:5]
                logger.info(f"   Sample handles: {sample_handles}")

            return indexed_products

        except Exception as e:
            raise SyncException(
                message=f"Failed to fetch existing Shopify products: {str(e)}",
                service="shopify",
                operation="get_products",
            ) from e

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

        # Procesar en lotes
        for i in range(0, len(rms_products), batch_size):
            batch = rms_products[i : i + batch_size]
            batch_number = (i // batch_size) + 1

            logger.info(f"Processing batch {batch_number} ({len(batch)} products)")

            # Procesar lote
            batch_stats = await self._process_product_batch(batch, shopify_products, force_update)

            # Agregar estadísticas
            for key in stats:
                stats[key] += batch_stats.get(key, 0)

            # Pausa entre lotes para no sobrecargar la API
            if i + batch_size < len(rms_products):
                # Rate limiting condicional basado en batch_size
                if batch_size > 2:
                    # Para lotes grandes, aplicar rate limit más estricto
                    sleep_time = 5  # 5 segundos entre lotes grandes
                    logger.info(f"🕐 Rate limiting: sleeping {sleep_time}s (batch_size={batch_size} > 2)")
                else:
                    # Para lotes pequeños, pausa mínima
                    sleep_time = 1
                    logger.debug(f"🕐 Minimal pause: {sleep_time}s (batch_size={batch_size} <= 2)")

                await asyncio.sleep(sleep_time)

        return stats

    async def _process_product_batch(
        self,
        batch: List[ShopifyProductInput],
        shopify_products: Dict[str, Dict[str, Any]],
        force_update: bool,
    ) -> Dict[str, Any]:
        """
        Procesa un lote de productos con múltiples variantes.

        Args:
            batch: Lote de ShopifyProductInput con múltiples variantes
            shopify_products: Productos existentes indexados por CCOD y SKU
            force_update: Forzar actualización

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

        for shopify_input in batch:
            ccod = None  # Initialize ccod before try block
            categoria = None
            familia = None
            extended_category = None
            
            try:
                # A. SINCRONIZACIÓN RMS→SHOPIFY - Preparar datos
                logger.info("=" * 50)
                logger.info(
                    f"🔄 STEP A: Starting RMS→Shopify sync for product, restore of shopify: {shopify_input.title}"
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

                logger.info(
                    f"✅ STEP A: Prepared sync data for CCOD: {ccod}, handle: {shopify_input.handle}, "
                    f"categoria: {categoria}, familia: {familia}"
                )

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
                            logger.info(
                                f"✅ Updated existing product: {ccod} (handle: "
                                f"{shopify_input.handle}) - {shopify_input.title}"
                            )
                            
                            # Sincronizar colecciones del producto
                            if self.collection_manager and updated_product.get("id"):
                                try:
                                    # Obtener colecciones actuales del producto
                                    # Por ahora, simplemente agregar a las colecciones apropiadas
                                    collections_added = await self.collection_manager.add_product_to_collections(
                                        product_id=updated_product["id"],
                                        categoria=categoria,
                                        familia=familia,
                                        extended_category=extended_category
                                    )
                                    if collections_added:
                                        logger.info(
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
                    # FLUJO COMPLETO: Crear producto siguiendo el flujo especificado
                    # A→B→C→D→E→F→G→H/I→J (Sync → Create Product → Create Variants → Update Inventory →
                    # Create Metafields → Verify Sale Price → Create Discount → Complete)
                    created_product = await self._create_shopify_product(shopify_input)

                    if created_product:
                        stats["created"] += 1
                        stats["inventory_updated"] += 1  # El inventario se actualiza dentro del MultipleVariantsCreator
                        log_sync_operation("create", "shopify", ccod=ccod)
                        logger.info(
                            f"✅ Created new product: {ccod} (handle: {shopify_input.handle}) - {shopify_input.title} "
                            f"({len(shopify_input.variants)} variants)"
                        )
                        
                        # Agregar producto a colecciones basadas en categorías
                        if self.collection_manager and created_product.get("id"):
                            try:
                                collections_added = await self.collection_manager.add_product_to_collections(
                                    product_id=created_product["id"],
                                    categoria=categoria,
                                    familia=familia,
                                    extended_category=extended_category
                                )
                                if collections_added:
                                    logger.info(
                                        f"✅ Product added to {len(collections_added)} collections"
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to add product to collections: {e}")
                    else:
                        stats["errors"] += 1
                        logger.error(
                            f"❌ Failed to create product: {ccod} "
                            f"(handle: {shopify_input.handle}) - {shopify_input.title}"
                        )

                stats["total_processed"] += 1

            except Exception as e:
                stats["errors"] += 1
                self.error_aggregator.add_error(
                    e,
                    {"ccod": ccod or "unknown", "title": shopify_input.title},
                )

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
            logger.info(f"✅ Updated product with multiple variants in Shopify: {sku}")
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

        # Log reporte final
        logger.info(f"Sync completed - ID: {self.sync_id} - Success rate: {report['success_rate']:.1f}%")

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
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronización RMS → Shopify.

    Args:
        force_update: Forzar actualización
        batch_size: Tamaño del lote
        filter_categories: Categorías a filtrar
        include_zero_stock: Incluir productos sin stock
        ccod: CCOD específico a sincronizar (opcional)

    Returns:
        Dict: Resultado de la sincronización
    """
    sync_service = RMSToShopifySync()

    try:
        await sync_service.initialize()
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
