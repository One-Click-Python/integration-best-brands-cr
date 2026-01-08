#!/usr/bin/env python3
"""
Creador de productos con múltiples variantes para Shopify - Clase principal.

Este es el módulo orquestador que coordina todas las operaciones
utilizando los módulos especializados.
"""

import logging
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.db.rms.product_repository import ProductRepository
from app.services.zero_stock_variant_cleanup import ZeroStockVariantCleanupService

from .data_preparator import DataPreparator
from .inventory_manager import InventoryManager
from .metafields_manager import MetafieldsManager
from .variant_manager import VariantManager

logger = logging.getLogger(__name__)


class MultipleVariantsCreator:
    """
    Clase principal que orquesta la creación de productos con múltiples variantes en Shopify.

    Utiliza el patrón de composición para delegar responsabilidades específicas
    a módulos especializados siguiendo el principio de Single Responsibility.
    """

    def __init__(
        self,
        shopify_client,
        primary_location_id: str,
        product_repository: Optional[ProductRepository] = None,
        enable_cleanup: bool = True,
    ):
        """
        Inicializa el creador de variantes múltiples.

        Args:
            shopify_client: Cliente de Shopify GraphQL
            primary_location_id: ID de la ubicación principal
            product_repository: Repositorio de productos RMS (requerido para limpieza)
            enable_cleanup: Habilitar limpieza de variantes con stock 0 (default: True)
        """
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id
        self.product_repository = product_repository

        # Inicializar módulos especializados
        self.data_preparator = DataPreparator()
        self.variant_manager = VariantManager(shopify_client, primary_location_id)
        self.inventory_manager = InventoryManager(shopify_client, primary_location_id)
        self.metafields_manager = MetafieldsManager(shopify_client)

        # Inicializar servicio de limpieza de variantes con stock 0
        # Solo si enable_cleanup Y product_repository están disponibles
        self.cleanup_service = None
        if enable_cleanup and product_repository:
            self.cleanup_service = ZeroStockVariantCleanupService(
                shopify_client=shopify_client,
            )
        elif enable_cleanup and not product_repository:
            logger.warning("⚠️  Cleanup service disabled: product_repository not provided")

    async def create_product_with_variants(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        FLUJO COMPLETO: Crea un producto en Shopify siguiendo el flujo especificado:
        B. Crear Producto → C. Crear Variantes → D. Actualizar Inventario →
        E. Crear Metafields → F. Verificar Precio de Oferta → G. ¿Tiene Sale Price? →
        H. Crear Descuento Automático → J. Producto Completo

        Args:
            shopify_input: Input del producto con todas las variantes

        Returns:
            Dict: Producto creado con todas las variantes siguiendo flujo completo

        Raises:
            Exception: Si falla la creación del producto o variantes
        """
        try:
            # Validar datos antes de procesar
            validation_result = self.data_preparator.validate_product_data(shopify_input)
            if not validation_result["is_valid"]:
                logger.error(f"❌ Product data validation failed: {validation_result['results']['invalid']}")
                raise Exception(f"Invalid product data: {validation_result['results']['invalid']}")

            # B. CREAR PRODUCTO básico
            logger.info(f"🔄 STEP B: Creating base product - {shopify_input.title}")
            product_data = self.data_preparator.prepare_base_product_data(shopify_input)
            created_product = await self.shopify_client.create_product(product_data)

            if not created_product or not created_product.get("id"):
                raise Exception("Product creation failed - no product ID returned")

            product_id = created_product["id"]
            logger.info(f"✅ STEP B: Created base product: {product_id} - {created_product.get('title')}")

            # C. CREAR VARIANTES usando productVariantsBulkCreate
            logger.info(f"🔄 STEP C: Creating {len(shopify_input.variants)} variants")
            if shopify_input.variants:
                # Primero obtener las variantes existentes para evitar conflictos
                existing_variants = await self.variant_manager.get_existing_variants(product_id)
                # Usar sync_product_variants que funciona correctamente tanto para una como múltiples variantes
                await self.variant_manager.sync_product_variants(product_id, shopify_input.variants, existing_variants)
            logger.info("✅ STEP C: Created variants successfully")

            # D. ACTUALIZAR INVENTARIO para todas las variantes (ANTES de metafields)
            logger.info("🔄 STEP D: Activating inventory tracking")
            # Para creación, forzar actualización de inventario aunque las variantes sean nuevas
            await self.inventory_manager.force_inventory_update_for_new_product(product_id, shopify_input.variants)
            logger.info("✅ STEP D: Inventory tracking activated")

            # E. CREAR METAFIELDS
            logger.info("🔄 STEP E: Creating metafields")
            if shopify_input.metafields:
                await self.metafields_manager.create_metafields(product_id, shopify_input.metafields)
            logger.info("✅ STEP E: Metafields created")

            # F→G→H. PRECIO DE OFERTA SE APLICA POR CÓDIGO PYTHON (descuentos removidos)
            logger.info("✅ STEPS F-H: Sale prices applied directly in Python code")

            # J. PRODUCTO COMPLETO
            logger.info(f"🎉 STEP J: Product creation complete with {len(shopify_input.variants)} variants")
            return created_product

        except Exception as e:
            logger.error(f"❌ Error in product creation flow: {e}")
            raise

    async def update_product_with_variants(
        self, product_id: str, shopify_input: ShopifyProductInput, existing_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza un producto existente en Shopify con múltiples variantes.

        Realiza las siguientes operaciones:
        1. Actualizar información básica del producto
        2. Sincronizar variantes (crear nuevas, actualizar existentes)
        3. Actualizar inventario para todas las variantes
        4. Actualizar metafields

        Args:
            product_id: ID del producto existente en Shopify
            shopify_input: Nuevos datos del producto con variantes
            existing_product: Producto existente obtenido de Shopify

        Returns:
            Dict: Producto actualizado

        Raises:
            Exception: Si falla la actualización del producto
        """
        try:
            logger.info(
                f"🔄⚠️ FLUJO COMPLETO: Starting update of product {product_id} "
                f"with {len(shopify_input.variants)} variants and existing product data: {existing_product}"
            )

            # Validar datos antes de procesar
            validation_result = self.data_preparator.validate_product_data(shopify_input)
            if not validation_result["is_valid"]:
                logger.error(f"❌ Product data validation failed: {validation_result['results']['invalid']}")
                raise Exception(f"Invalid product data: {validation_result['results']['invalid']}")

            # B. ACTUALIZAR PRODUCTO básico (solo campos seguros de RMS)
            logger.info(f"🔄 STEP B: Updating base product - {shopify_input.title}")

            # Obtener tags existentes del producto para limpieza de RMS-Sync antiguos
            existing_tags = existing_product.get("tags", [])
            logger.debug(f"🏷️ Tags existentes en Shopify: {existing_tags}")

            product_update_data = self.data_preparator.prepare_product_update_data(
                shopify_input,
                existing_tags=existing_tags,  # Pasar tags existentes para limpieza
                preserve_media=True,  # Preservar imágenes y contenido
                preserve_publishing=True,  # Preservar configuración de publishing
            )
            updated_product = await self.shopify_client.update_product(product_id, product_update_data)
            logger.info(f"✅ STEP B: Updated basic product info: {updated_product.get('title')}")

            # C. SINCRONIZAR VARIANTES (crear nuevas, actualizar existentes)
            logger.info(f"🔄 STEP C: Syncing {len(shopify_input.variants)} variants")
            existing_variants = await self.variant_manager.get_existing_variants(product_id)
            if shopify_input.variants:
                await self.variant_manager.sync_product_variants(product_id, shopify_input.variants, existing_variants)
            logger.info("✅ STEP C: Variants synchronized successfully")

            # E. ACTUALIZAR METAFIELDS
            logger.info("🔄 STEP E: Updating metafields")
            if shopify_input.metafields:
                await self.metafields_manager.update_metafields(product_id, shopify_input.metafields)
            logger.info("✅ STEP E: Metafields updated")

            # D. ACTUALIZAR INVENTARIO para todas las variantes
            logger.info("🔄 STEP D: Updating inventory tracking")
            # Para actualizaciones, usar el método original que funcionaba
            await self.inventory_manager.activate_inventory_for_all_variants(product_id, shopify_input.variants)
            logger.info("✅ STEP D: Inventory tracking updated")

            # D.1 LIMPIEZA DE VARIANTES CON STOCK 0 EN RMS
            if self.cleanup_service and self.product_repository:
                logger.info("🔄 STEP D.1: Cleaning up zero-stock variants from Shopify")

                # Extraer CCOD para consulta SQL
                ccod = "unknown"
                if shopify_input.metafields:
                    for metafield in shopify_input.metafields:
                        if metafield.get("key") == "ccod" and metafield.get("namespace") == "rms":
                            ccod = metafield.get("value", "unknown")
                            break

                # Validar CCOD extraído
                if ccod == "unknown":
                    available_keys = [m.get("key") for m in (shopify_input.metafields or [])]
                    logger.warning(
                        f"⚠️ STEP D.1: Cannot cleanup - CCOD metafield not found in product. "
                        f"Available metafield keys: {available_keys}"
                    )
                    logger.info("⏭️  STEP D.1: Skipping zero-stock cleanup (no valid CCOD)")
                else:
                    logger.info(f"📋 STEP D.1: Extracted CCOD={ccod} from metafields")
                    logger.info(f"🔍 STEP D.1: Querying RMS for zero-stock variants (CCOD={ccod})")

                    # 1. Consultar RMS por variantes con stock 0
                    zero_stock_variants = await self.product_repository.get_zero_stock_variants_by_ccod(ccod)
                    zero_stock_skus = {v.c_articulo for v in zero_stock_variants if v.c_articulo}

                    logger.info(
                        f"📊 STEP D.1: RMS Query Results - "
                        f"Found {len(zero_stock_variants)} variants with Quantity=0 for CCOD={ccod}"
                    )

                    # 2. Si hay variantes con stock 0, eliminarlas de Shopify
                    if zero_stock_skus:
                        logger.info(
                            f"🗑️  STEP D.1: Will attempt to delete {len(zero_stock_skus)} zero-stock variants: "
                            f"{list(zero_stock_skus)[:5]}{'...' if len(zero_stock_skus) > 5 else ''}"
                        )

                        cleanup_stats = await self.cleanup_service.cleanup_zero_stock_variants(
                            shopify_product_id=product_id,
                            zero_stock_skus=zero_stock_skus,
                            ccod=ccod,
                        )
                        logger.info(
                            f"✅ STEP D.1: Cleanup completed - "
                            f"Checked: {cleanup_stats['variants_checked']}, "
                            f"Deleted: {cleanup_stats['variants_deleted']}, "
                            f"Errors: {cleanup_stats['errors']}"
                        )
                    else:
                        logger.info(f"✅ STEP D.1: No zero-stock variants found in RMS for CCOD={ccod}")
            else:
                logger.debug("⏭️  STEP D.1: Zero-stock cleanup skipped (service/repository not available)")

            # F→G→H. PRECIO DE OFERTA SE APLICA POR CÓDIGO PYTHON (descuentos removidos)
            logger.info("✅ STEPS F-H: Sale prices applied directly in Python code")

            # J. PRODUCTO COMPLETO
            logger.info(f"🎉 STEP J: Product update complete with {len(shopify_input.variants)} variants")
            return updated_product

        except Exception as e:
            logger.error(f"❌ Error updating product {product_id} with multiple variants: {e}")
            raise

    # Métodos de conveniencia para acceso directo a funcionalidades específicas

    def validate_product_data(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Valida los datos del producto antes de crear/actualizar.

        Args:
            shopify_input: Datos del producto a validar

        Returns:
            Dict: Resultado de la validación
        """
        return self.data_preparator.validate_product_data(shopify_input)

    def validate_inventory_data(self, variants: List[Any]) -> Dict[str, Any]:
        """
        Valida los datos de inventario antes de aplicar.

        Args:
            variants: Lista de variantes con datos de inventario

        Returns:
            Dict: Resultado de la validación
        """
        return self.inventory_manager.validate_inventory_data(variants)

    # Métodos para operaciones en lote

    async def bulk_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Actualiza inventario para múltiples variantes en lote.

        Args:
            inventory_updates: Lista de actualizaciones de inventario

        Returns:
            Dict: Resultado con éxitos y fallos
        """
        return await self.inventory_manager.bulk_update_inventory(inventory_updates)

    async def bulk_create_metafields(self, metafields_by_product: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """
        Crea metafields para múltiples productos en lote.

        Args:
            metafields_by_product: Diccionario con product_id como key y lista de metafields como value

        Returns:
            Dict: Resultado con éxitos y fallos
        """
        return await self.metafields_manager.bulk_create_metafields(metafields_by_product)
