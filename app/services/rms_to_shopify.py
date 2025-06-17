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

from app.core.config import get_settings
from app.core.logging_config import LogContext, log_sync_operation
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

            # Inicializar cliente Shopify
            from app.db.shopify_client import ShopifyClient

            self.shopify_client = ShopifyClient()
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

            products = await self.rms_handler.execute_query(query)

            # Validar y procesar productos
            processed_products = []
            for product in products:
                try:
                    processed_product = self._validate_and_process_rms_product(product)
                    processed_products.append(processed_product)
                    self.error_aggregator.increment_processed()
                except ValidationException as e:
                    self.error_aggregator.add_error(e, {"sku": product.get("sku")})

            return processed_products

        except Exception as e:
            raise SyncException(
                message=f"Failed to extract RMS products: {str(e)}",
                service="rms",
                operation="extract_products",
            ) from e

    def _validate_and_process_rms_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida y procesa un producto RMS.

        Args:
            product: Datos del producto RMS

        Returns:
            Dict: Producto procesado

        Raises:
            ValidationException: Si la validación falla
        """
        # Validaciones básicas
        if not product.get("sku"):
            raise ValidationException(message="SKU is required", field="sku", invalid_value=product.get("sku"))

        if not product.get("title"):
            raise ValidationException(
                message="Product title is required",
                field="title",
                invalid_value=product.get("title"),
            )

        # Procesar precios
        price = self._process_price(product.get("Price"))
        sale_price = self._process_price(product.get("SalePrice"))

        # Procesar inventario
        quantity = max(0, int(product.get("Quantity", 0)))

        # Mapear a formato Shopify
        shopify_product = {
            "title": product["title"],
            "handle": self._generate_handle(product["title"], product["sku"]),
            "product_type": product.get("Category", ""),
            "vendor": product.get("Family", ""),
            "tags": self._generate_tags(product),
            "variants": [
                {
                    "sku": product["sku"],
                    "price": str(price),
                    "compare_at_price": str(sale_price) if sale_price and sale_price > price else None,
                    "inventory_quantity": quantity,
                    "inventory_management": "shopify",
                    "inventory_policy": "deny",
                    "weight": 0,
                    "weight_unit": "kg",
                    "requires_shipping": True,
                    "taxable": bool(product.get("Tax", False)),
                    "option1": product.get("Color") or "Default",
                    "option2": product.get("Size") if product.get("Size") else None,
                    "option3": product.get("Gender") if product.get("Gender") else None,
                }
            ],
            "options": self._generate_options(product),
            "status": "active",
            "published": True,
            "meta_fields": {
                "rms_sync": {
                    "last_synced": datetime.now(timezone.utc).isoformat(),
                    "rms_category": product.get("Category"),
                    "rms_family": product.get("Family"),
                    "rms_extended_category": product.get("ExtendedCategory"),
                }
            },
        }

        # Agregar descripción si existe
        if product.get("Description"):
            shopify_product["body_html"] = self._format_description(product["Description"])

        return shopify_product

    def _process_price(self, price: Any) -> Decimal:
        """
        Procesa y valida un precio.

        Args:
            price: Precio a procesar

        Returns:
            Decimal: Precio procesado
        """
        if price is None:
            return Decimal("0.00")

        try:
            decimal_price = Decimal(str(price))
            return max(decimal_price, Decimal("0.00"))
        except (ValueError, TypeError):
            return Decimal("0.00")

    def _generate_handle(self, title: str, sku: str) -> str:
        """
        Genera un handle único para Shopify.

        Args:
            title: Título del producto
            sku: SKU del producto

        Returns:
            str: Handle generado
        """
        import re

        # Limpiar título
        handle = title.lower().strip()
        handle = re.sub(r"[^\w\s-]", "", handle)
        handle = re.sub(r"\s+", "-", handle)
        handle = re.sub(r"-+", "-", handle)
        handle = handle.strip("-")

        # Agregar SKU para unicidad
        handle = f"{handle}-{sku.lower()}"

        return handle[:100]  # Límite de Shopify

    def _generate_tags(self, product: Dict[str, Any]) -> str:
        """
        Genera tags para el producto.

        Args:
            product: Datos del producto

        Returns:
            str: Tags separados por coma
        """
        tags = []

        if product.get("Category"):
            tags.append(product["Category"])

        if product.get("Family"):
            tags.append(product["Family"])

        if product.get("Gender"):
            tags.append(product["Gender"])

        if product.get("Color"):
            tags.append(f"Color-{product['Color']}")

        if product.get("Size"):
            tags.append(f"Size-{product['Size']}")

        # Tag de origen
        tags.append("RMS-Sync")

        return ", ".join(tags)

    def _generate_options(self, product: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Genera opciones de variante para Shopify.

        Args:
            product: Datos del producto

        Returns:
            List: Opciones de variante
        """
        options = []

        # Opción 1: Color (siempre presente)
        options.append({"name": "Color", "values": [product.get("Color") or "Default"]})

        # Opción 2: Talla (si existe)
        if product.get("Size"):
            options.append({"name": "Talla", "values": [product["Size"]]})

        # Opción 3: Género (si existe y no hay talla)
        elif product.get("Gender"):
            options.append({"name": "Género", "values": [product["Gender"]]})

        return options

    def _format_description(self, description: str) -> str:
        """
        Formatea la descripción para HTML.

        Args:
            description: Descripción original

        Returns:
            str: Descripción formateada en HTML
        """
        if not description:
            return ""

        # Escapar HTML básico y convertir saltos de línea
        import html

        escaped = html.escape(description)
        formatted = escaped.replace("\n", "<br>")

        return f"<p>{formatted}</p>"

    async def _get_existing_shopify_products(self) -> Dict[str, Dict[str, Any]]:
        """
        Obtiene productos existentes de Shopify indexados por SKU.

        Returns:
            Dict: Productos existentes indexados por SKU
        """
        try:
            products = await self.shopify_client.get_all_products()

            # Indexar por SKU de la primera variante
            indexed_products = {}
            for product in products:
                if product.get("variants"):
                    first_variant = product["variants"][0]
                    sku = first_variant.get("sku")
                    if sku:
                        indexed_products[sku] = product

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

        for product in batch:
            try:
                sku = product["variants"][0]["sku"]
                existing_product = shopify_products.get(sku)

                if existing_product:
                    # Producto existe - decidir si actualizar
                    if force_update or self._should_update_product(product, existing_product):
                        await self._update_shopify_product(product, existing_product)
                        stats["updated"] += 1
                        log_sync_operation("update", "shopify", sku=sku)
                    else:
                        stats["skipped"] += 1
                else:
                    # Producto nuevo - crear
                    await self._create_shopify_product(product)
                    stats["created"] += 1
                    log_sync_operation("create", "shopify", sku=sku)

                stats["total_processed"] += 1

            except Exception as e:
                stats["errors"] += 1
                self.error_aggregator.add_error(e, {"sku": product.get("variants", [{}])[0].get("sku", "unknown")})

        return stats

    def _should_update_product(self, rms_product: Dict[str, Any], shopify_product: Dict[str, Any]) -> bool:
        """
        Determina si un producto debe actualizarse.

        Args:
            rms_product: Producto de RMS
            shopify_product: Producto existente en Shopify

        Returns:
            bool: True si debe actualizarse
        """
        # Comparar campos importantes
        rms_variant = rms_product["variants"][0]
        shopify_variant = shopify_product.get("variants", [{}])[0]

        # Comparar precios
        if str(rms_variant.get("price", "0")) != str(shopify_variant.get("price", "0")):
            return True

        # Comparar inventario
        if rms_variant.get("inventory_quantity", 0) != shopify_variant.get("inventory_quantity", 0):
            return True

        # Comparar título
        if rms_product.get("title") != shopify_product.get("title"):
            return True

        return False

    async def _create_shopify_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un producto en Shopify.

        Args:
            product: Datos del producto

        Returns:
            Dict: Producto creado
        """
        try:
            created_product = await self.shopify_client.create_product(product)
            sku = product["variants"][0]["sku"]
            logger.info(f"Created product in Shopify: {sku}")
            return created_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to create product in Shopify: {str(e)}",
                service="shopify",
                operation="create_product",
                failed_records=[product],
            ) from e

    async def _update_shopify_product(
        self, rms_product: Dict[str, Any], shopify_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza un producto en Shopify.

        Args:
            rms_product: Datos actualizados del producto
            shopify_product: Producto existente

        Returns:
            Dict: Producto actualizado
        """
        try:
            # Preparar datos de actualización
            update_data = self._prepare_update_data(rms_product, shopify_product)

            # Actualizar producto
            updated_product = await self.shopify_client.update_product(shopify_product["id"], update_data)

            sku = rms_product["variants"][0]["sku"]
            logger.info(f"Updated product in Shopify: {sku}")
            return updated_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to update product in Shopify: {str(e)}",
                service="shopify",
                operation="update_product",
                failed_records=[rms_product],
            ) from e

    def _prepare_update_data(self, rms_product: Dict[str, Any], shopify_product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara datos para actualización de producto.

        Args:
            rms_product: Producto RMS
            shopify_product: Producto Shopify existente

        Returns:
            Dict: Datos de actualización
        """
        update_data = {
            "title": rms_product["title"],
            "product_type": rms_product["product_type"],
            "vendor": rms_product["vendor"],
            "tags": rms_product["tags"],
        }

        # Actualizar descripción si existe
        if rms_product.get("body_html"):
            update_data["body_html"] = rms_product["body_html"]

        # Actualizar variante
        rms_variant = rms_product["variants"][0]
        shopify_variant = shopify_product["variants"][0]

        update_data["variants"] = [
            {
                "id": shopify_variant["id"],
                "price": rms_variant["price"],
                "compare_at_price": rms_variant.get("compare_at_price"),
                "inventory_quantity": rms_variant["inventory_quantity"],
                "option1": rms_variant["option1"],
                "option2": rms_variant.get("option2"),
                "option3": rms_variant.get("option3"),
            }
        ]

        return update_data

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
