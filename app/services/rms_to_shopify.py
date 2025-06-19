"""
Microservicio de sincronización RMS → Shopify.

Este módulo maneja la sincronización de productos, inventarios y precios
desde Microsoft Retail Management System hacia Shopify.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.core.config import get_settings
from app.core.logging_config import LogContext, log_sync_operation
from app.services.data_mapper import (
    DataComparator,
    RMSToShopifyMapper,
    ShopifyToRMSMapper,
)
from app.utils.error_handler import (
    ErrorAggregator,
    SyncException,
    ValidationException,
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
        self.error_aggregator = ErrorAggregator()
        self.sync_id = f"rms_to_shopify_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"  # noqa: F821

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

            logger.info(f"Sync service initialized - ID: {self.sync_id}")

        except Exception as e:
            raise SyncException(
                message=f"Failed to initialize sync service: {str(e)}",
                service="rms_to_shopify",
                operation="initialize",
            ) from e

    async def get_status(self) -> Dict[str, Any]:
        """
        Obtiene el estado actual del servicio de sincronización.

        Returns:
            Dict: Estado del servicio
        """
        return {
            "sync_id": self.sync_id,
            "status": "idle",  # idle, running, error
            "last_sync": None,
            "errors": self.error_aggregator.get_summary(),
        }

    async def sync_products(
        self,
        force_update: bool = False,
        batch_size: int = None,
        filter_categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Sincroniza productos de RMS a Shopify.

        Args:
            force_update: Forzar actualización de productos existentes
            batch_size: Tamaño del lote para procesamiento
            filter_categories: Filtrar por categorías específicas

        Returns:
            Dict: Resultado de la sincronización

        Raises:
            SyncException: Si falla la sincronización
        """
        batch_size = batch_size or settings.SYNC_BATCH_SIZE

        with LogContext(sync_id=self.sync_id, operation="sync_products"):
            logger.info(f"Starting product sync - Force: {force_update}, Batch: {batch_size}")

            try:
                # 1. Extraer productos de RMS
                rms_products = await self._extract_rms_products(filter_categories)
                logger.info(f"Extracted {len(rms_products)} products from RMS")

                # 2. Obtener productos existentes de Shopify
                shopify_products = await self._get_existing_shopify_products()
                logger.info(f"Found {len(shopify_products)} existing products in Shopify")

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

    async def _extract_rms_products(self, filter_categories: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Extrae productos de la vista RMS.

        Args:
            filter_categories: Categorías a filtrar

        Returns:
            List: Lista de productos RMS
        """
        try:
            # Query para extraer productos de View_Items
            query = """
            SELECT 
                C_ARTICULO as sku,
                Name as title,
                Category,
                Family,
                Color,
                Size,
                Price,
                SalePrice,
                SaleStartDate,
                SaleEndDate,
                Quantity,
                Tax,
                Gender,
                Description,
                ExtendedCategory,
                LastModified
            FROM View_Items 
            WHERE Active = 1
            """

            # Agregar filtro de categorías si se especifica
            if filter_categories:
                categories_str = "', '".join(filter_categories)
                query += f" AND Category IN ('{categories_str}')"

            # Agregar filtro de fecha para sync incremental
            if not getattr(self, "_force_full_sync", False):
                cutoff_date = datetime.now(timezone.utc) - timedelta(hours=24)
                query += f" AND LastModified >= '{cutoff_date.isoformat()}'"

            query += " ORDER BY LastModified DESC"

            products = await self.rms_handler.execute_custom_query(query)

            # Validar y procesar productos usando Pydantic schemas
            processed_products = []
            for product_data in products:
                try:
                    # Convertir a RMSViewItem para validación
                    rms_item = RMSViewItem(
                        familia=product_data.get("Family"),
                        genero=product_data.get("Gender"),
                        categoria=product_data.get("Category"),
                        ccod=product_data.get("sku", ""),  # Usar sku como ccod por ahora
                        c_articulo=product_data.get("sku"),
                        item_id=product_data.get("item_id", 0),
                        description=product_data.get("title"),
                        color=product_data.get("Color"),
                        talla=product_data.get("Size"),
                        quantity=int(product_data.get("Quantity", 0)),
                        price=Decimal(str(product_data.get("Price", 0))),
                        sale_price=Decimal(str(product_data.get("SalePrice", 0)))
                        if product_data.get("SalePrice")
                        else None,
                        extended_category=product_data.get("ExtendedCategory"),
                        tax=int(product_data.get("Tax", 13)),
                    )

                    # Mapear a formato Shopify GraphQL
                    shopify_product = RMSToShopifyMapper.map_product_to_shopify(rms_item)
                    processed_products.append({"rms_item": rms_item, "shopify_input": shopify_product})
                    self.error_aggregator.increment_processed()

                except (ValidationException, ValueError) as e:
                    self.error_aggregator.add_error(e, {"sku": product_data.get("sku")})

            return processed_products

        except Exception as e:
            raise SyncException(
                message=f"Failed to extract RMS products: {str(e)}",
                service="rms",
                operation="extract_products",
            ) from e

    def _convert_to_graphql_input(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Convierte ShopifyProductInput a formato dict para la API GraphQL.

        Args:
            shopify_input: Input de producto validado

        Returns:
            Dict: Producto en formato GraphQL
        """
        return shopify_input.to_graphql_input()

    async def _get_existing_shopify_products(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene productos existentes de Shopify indexados por SKU.

        Returns:
            Dict: Productos existentes indexados por SKU
        """
        try:
            products = await self.shopify_client.get_all_products()

            # Indexar por SKU usando el nuevo parser
            indexed_products = {}
            for product in products:
                parsed_product = ShopifyToRMSMapper.parse_product_for_updates(product)
                for variant in parsed_product.get("variants", []):
                    sku = variant.get("sku")
                    if sku:
                        indexed_products[sku] = product
                        break  # Solo necesitamos el primer SKU válido

            return indexed_products

        except Exception as e:
            raise SyncException(
                message=f"Failed to fetch existing Shopify products: {str(e)}",
                service="shopify",
                operation="get_products",
            ) from e

    async def _process_products_in_batches(
        self,
        rms_products: List[Dict[str, Any]],
        shopify_products: Dict[str, Dict[str, Any]],
        force_update: bool,
        batch_size: int,
    ) -> Dict[str, Any]:
        """
        Procesa productos en lotes.

        Args:
            rms_products: Productos de RMS
            shopify_products: Productos existentes de Shopify
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
                await asyncio.sleep(1)

        return stats

    async def _process_product_batch(
        self,
        batch: List[Dict[str, Any]],
        shopify_products: Dict[str, Dict[str, Any]],
        force_update: bool,
    ) -> Dict[str, Any]:
        """
        Procesa un lote de productos.

        Args:
            batch: Lote de productos
            shopify_products: Productos existentes
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
        }

        for product_data in batch:
            try:
                rms_item = product_data["rms_item"]
                shopify_input = product_data["shopify_input"]
                sku = rms_item.c_articulo
                existing_product = shopify_products.get(sku)

                if existing_product:
                    # Producto existe - decidir si actualizar
                    if force_update or DataComparator.needs_update(rms_item, existing_product):
                        await self._update_shopify_product(shopify_input, existing_product)
                        stats["updated"] += 1
                        log_sync_operation("update", "shopify", sku=sku)
                    else:
                        stats["skipped"] += 1
                else:
                    # Producto nuevo - crear
                    await self._create_shopify_product(shopify_input)
                    stats["created"] += 1
                    log_sync_operation("create", "shopify", sku=sku)

                stats["total_processed"] += 1

            except Exception as e:
                stats["errors"] += 1
                self.error_aggregator.add_error(
                    e,
                    {"sku": rms_item.c_articulo if "rms_item" in product_data else "unknown"},  # type: ignore
                )

        return stats

    def _should_update_product_legacy(self, rms_product: Dict[str, Any], shopify_product: Dict[str, Any]) -> bool:
        """
        Método legacy para compatibilidad. Usa DataComparator en su lugar.
        """
        logger.warning("Using legacy comparison method. Consider updating to DataComparator.")
        return True  # Forzar actualización para métodos legacy

    async def _create_shopify_product(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Crea un producto en Shopify usando GraphQL.

        Args:
            shopify_input: Input del producto validado

        Returns:
            Dict: Producto creado
        """
        try:
            # Convertir a formato GraphQL
            product_data = self._convert_to_graphql_input(shopify_input)

            created_product = await self.shopify_client.create_product(product_data)
            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"
            logger.info(f"Created product in Shopify: {sku}")
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
        Actualiza un producto en Shopify usando GraphQL.

        Args:
            shopify_input: Datos actualizados del producto
            shopify_product: Producto existente

        Returns:
            Dict: Producto actualizado
        """
        try:
            # Preparar datos de actualización con ID del producto existente
            update_data = self._convert_to_graphql_input(shopify_input)

            # Obtener ID del producto existente
            product_id = shopify_product.get("id")
            if not product_id:
                raise ValueError("Product ID not found in existing product")

            # Actualizar producto
            updated_product = await self.shopify_client.update_product(product_id, update_data)

            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"
            logger.info(f"Updated product in Shopify: {sku}")
            return updated_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to update product in Shopify: {str(e)}",
                service="shopify",
                operation="update_product",
                failed_records=[shopify_input.model_dump()],
            ) from e

    def _prepare_update_data_legacy(
        self, rms_product: Dict[str, Any], shopify_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Método legacy mantenido para compatibilidad.
        """
        logger.warning("Using legacy update data preparation. Consider updating to use ShopifyProductInput.")
        return {}

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
) -> Dict[str, Any]:
    """
    Función de conveniencia para sincronización RMS → Shopify.

    Args:
        force_update: Forzar actualización
        batch_size: Tamaño del lote
        filter_categories: Categorías a filtrar

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
