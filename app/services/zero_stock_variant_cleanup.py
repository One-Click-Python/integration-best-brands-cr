"""
Servicio de limpieza de variantes con stock 0 en Shopify.

Este módulo consulta RMS por variantes con stock 0 y las elimina de Shopify si existen.

Flujo:
1. Consultar RMS: "SELECT * FROM View_Items WHERE CCOD = :ccod AND Quantity = 0"
2. Obtener SKUs de variantes con stock 0
3. Buscar esas variantes en Shopify
4. Eliminar las que existan

IMPORTANTE: Las variantes con stock 0 NO vienen en el sync normal porque el query las filtra.
Por eso necesitamos una consulta SQL adicional específica para stock 0.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from app.core.config import get_settings
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.utils.error_handler import AppException

settings = get_settings()
logger = logging.getLogger(__name__)


class ZeroStockVariantCleanupService:
    """
    Servicio para eliminar variantes de Shopify que tienen stock 0 en RMS.

    Workflow:
    1. Recibe SKUs de variantes con stock 0 (obtenidos de RMS)
    2. Obtiene todas las variantes del producto en Shopify
    3. Elimina las variantes de Shopify cuyos SKUs están en la lista de stock 0
    """

    def __init__(
        self,
        shopify_client: Optional[ShopifyGraphQLClient] = None,
    ):
        """
        Inicializa el servicio de limpieza.

        Args:
            shopify_client: Cliente GraphQL de Shopify
        """
        self.shopify_client = shopify_client or ShopifyGraphQLClient()
        self.stats = {
            "variants_checked": 0,
            "variants_deleted": 0,
            "errors": 0,
        }

    async def cleanup_zero_stock_variants(
        self, shopify_product_id: str, zero_stock_skus: Set[str], ccod: str
    ) -> Dict[str, Any]:
        """
        Elimina variantes de Shopify que tienen stock 0 en RMS.

        Args:
            shopify_product_id: ID del producto en Shopify (gid://...)
            zero_stock_skus: Set de SKUs con stock 0 en RMS (de consulta SQL adicional)
            ccod: Código del producto en RMS (para logging)

        Returns:
            Dict con estadísticas de la limpieza:
            - variants_checked: Total de variantes verificadas en Shopify
            - variants_deleted: Variantes eliminadas exitosamente
            - errors: Errores durante el proceso
        """
        if not zero_stock_skus:
            logger.debug(f"No hay variantes con stock 0 para producto {ccod}")
            return self.stats

        logger.info(
            f"🧹 Iniciando limpieza de variantes con stock 0 para producto {ccod} "
            f"(variantes con stock 0: {len(zero_stock_skus)})"
        )

        try:
            # 1. Obtener todas las variantes del producto en Shopify
            shopify_variants = await self._get_shopify_variants(shopify_product_id)

            if not shopify_variants:
                logger.debug(f"No se encontraron variantes en Shopify para producto {ccod}")
                return self.stats

            logger.debug(f"Encontradas {len(shopify_variants)} variantes en Shopify para {ccod}")

            # 2. Eliminar variantes que tienen stock 0 en RMS
            for variant in shopify_variants:
                self.stats["variants_checked"] += 1
                sku = variant.get("sku")
                variant_id = variant.get("id")

                if not sku or not variant_id:
                    logger.warning(f"Variante sin SKU o ID: {variant}")
                    continue

                # Si el SKU ESTÁ en la lista de stock 0, eliminar de Shopify
                if sku in zero_stock_skus:
                    logger.warning(
                        f"🗑️  Variante con stock 0 detectada en Shopify: " f"SKU={sku}, ID={variant_id}, CCOD={ccod}"
                    )

                    deleted = await self._delete_variant(variant_id, sku, ccod, shopify_product_id)
                    if deleted:
                        self.stats["variants_deleted"] += 1
                else:
                    logger.debug(f"✅ Variante {sku} tiene stock > 0 en RMS, manteniendo")

            logger.info(
                f"✅ Limpieza completada para {ccod}: "
                f"{self.stats['variants_checked']} verificadas, "
                f"{self.stats['variants_deleted']} eliminadas, "
                f"{self.stats['errors']} errores"
            )

            return self.stats

        except Exception as e:
            logger.error(f"Error durante limpieza de variantes para {ccod}: {e}")
            self.stats["errors"] += 1
            return self.stats

    async def _get_shopify_variants(self, product_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene todas las variantes de un producto en Shopify.

        Args:
            product_id: ID del producto en Shopify

        Returns:
            Lista de variantes con id, sku
        """
        query = """
        query getProductVariants($id: ID!) {
            product(id: $id) {
                variants(first: 100) {
                    edges {
                        node {
                            id
                            sku
                        }
                    }
                }
            }
        }
        """

        try:
            response = await self.shopify_client._execute_query(query, {"id": product_id})

            # Note: _execute_query already extracts "data" field, so response = {'product': {...}}
            if not response or "product" not in response:
                logger.warning(f"Respuesta inválida al obtener variantes: {response}")
                return []

            variants_data = response.get("product", {}).get("variants", {}).get("edges", [])

            variants = []
            for edge in variants_data:
                node = edge.get("node", {})
                variants.append(
                    {
                        "id": node.get("id"),
                        "sku": node.get("sku"),
                    }
                )

            return variants

        except Exception as e:
            logger.error(f"Error obteniendo variantes de Shopify: {e}")
            raise AppException(
                message=f"Failed to get Shopify variants: {str(e)}",
                status_code=500,
            ) from e

    async def _delete_variant(self, variant_id: str, sku: str, ccod: str, product_id: str) -> bool:
        """
        Elimina una variante en Shopify.

        Args:
            variant_id: ID de la variante en Shopify (gid://shopify/ProductVariant/...)
            sku: SKU de la variante
            ccod: Código del producto en RMS
            product_id: ID del producto en Shopify (gid://shopify/Product/...)

        Returns:
            True si se eliminó exitosamente, False en caso contrario
        """
        delete_mutation = """
        mutation bulkDeleteProductVariants($productId: ID!, $variantsIds: [ID!]!) {
            productVariantsBulkDelete(productId: $productId, variantsIds: $variantsIds) {
                product {
                    id
                    title
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """

        try:
            response = await self.shopify_client._execute_query(
                delete_mutation, {"productId": product_id, "variantsIds": [variant_id]}
            )

            # Note: _execute_query already extracts "data" field
            if not response or "productVariantsBulkDelete" not in response:
                logger.error(f"Respuesta inválida al eliminar variante {sku}: {response}")
                return False

            user_errors = response.get("productVariantsBulkDelete", {}).get("userErrors", [])

            if user_errors:
                logger.error(f"Errores al eliminar variante {sku}: {user_errors}")
                self.stats["errors"] += 1
                return False

            product = response.get("productVariantsBulkDelete", {}).get("product")

            if product:
                logger.info(f"🗑️  Variante ELIMINADA (stock 0 en RMS): SKU={sku}, ID={variant_id}, CCOD={ccod}")
                return True
            else:
                logger.warning(f"No se pudo confirmar eliminación de variante {sku}")
                return False

        except Exception as e:
            logger.error(f"Error eliminando variante {sku}: {e}")
            self.stats["errors"] += 1
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene las estadísticas actuales del servicio.

        Returns:
            Dict con estadísticas de limpieza
        """
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Reinicia las estadísticas del servicio."""
        self.stats = {
            "variants_checked": 0,
            "variants_deleted": 0,
            "errors": 0,
        }
