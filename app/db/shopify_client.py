"""
Cliente API para Shopify.

Este módulo proporciona funciones para interactuar con la API de Shopify,
incluyendo autenticación, consultas y operaciones CRUD para productos,
inventarios y pedidos. Utiliza GraphQL como interfaz principal.
"""

import logging
from typing import Any, Dict, Optional

from app.core.config import get_settings
from app.db.shopify_graphql_client import ShopifyGraphQLClient

settings = get_settings()
logger = logging.getLogger(__name__)

# Global GraphQL client instance
_graphql_client: Optional[ShopifyGraphQLClient] = None


def get_graphql_client() -> ShopifyGraphQLClient:
    """
    Obtiene la instancia global del cliente GraphQL.

    Returns:
        ShopifyGraphQLClient: Cliente GraphQL configurado
    """
    global _graphql_client
    if _graphql_client is None:
        _graphql_client = ShopifyGraphQLClient()
    return _graphql_client


async def test_shopify_connection() -> bool:
    """
    Verifica la conectividad con la API de Shopify.

    Returns:
        bool: True si la conexión es exitosa, False en caso contrario
    """
    try:
        client = get_graphql_client()
        
        # Inicializar el cliente si no está inicializado
        if not hasattr(client, 'session') or client.session is None:
            await client.initialize()
            
        return await client.test_connection()
    except Exception as e:
        logger.error(f"Shopify connection test failed: {e}")
        return False


async def get_shopify_products(
    limit: Optional[int] = None,
    page_info: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Obtiene productos desde Shopify.

    Args:
        limit: Límite de resultados por página
        page_info: Token de paginación

    Returns:
        Dict: Respuesta con productos y metadatos de paginación
    """
    try:
        client = get_graphql_client()
        result = await client.get_products(limit=limit or 50, cursor=page_info)

        return {
            "products": result.get("products", []),
            "page_info": result.get("pageInfo", {}),
            "has_next_page": result.get("hasNextPage", False),
        }
    except Exception as e:
        logger.error(f"Error getting Shopify products: {e}")
        return {
            "products": [],
            "page_info": None,
            "has_next_page": False,
        }


async def get_shopify_orders(
    status: Optional[str] = None,
    limit: Optional[int] = None,
    page_info: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Obtiene pedidos desde Shopify.

    Args:
        status: Filtro por estado del pedido
        limit: Límite de resultados por página
        page_info: Token de paginación

    Returns:
        Dict: Respuesta con pedidos y metadatos de paginación
    """
    try:
        client = get_graphql_client()
        result = await client.get_orders(limit=limit or 50, cursor=page_info, status=status)

        return {
            "orders": result.get("orders", []),
            "page_info": result.get("pageInfo", {}),
            "has_next_page": result.get("hasNextPage", False),
        }
    except Exception as e:
        logger.error(f"Error getting Shopify orders: {e}")
        return {
            "orders": [],
            "page_info": None,
            "has_next_page": False,
        }


async def update_shopify_product(
    product_id: str,
    product_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Actualiza un producto en Shopify.

    Args:
        product_id: ID del producto
        product_data: Datos del producto a actualizar

    Returns:
        Dict: Producto actualizado
    """
    try:
        client = get_graphql_client()
        return await client.update_product(product_id, product_data)
    except Exception as e:
        logger.error(f"Error updating Shopify product {product_id}: {e}")
        raise


async def update_shopify_inventory(
    inventory_item_id: str,
    location_id: str,
    available: int,
) -> bool:
    """
    Actualiza el inventario en Shopify.

    Args:
        inventory_item_id: ID del item de inventario
        location_id: ID de la ubicación
        available: Cantidad disponible

    Returns:
        bool: True si la actualización fue exitosa
    """
    try:
        client = get_graphql_client()
        result = await client.update_inventory(inventory_item_id, location_id, available)
        return isinstance(result, dict) and result.get("success", False)
    except Exception as e:
        logger.error(f"Error updating Shopify inventory: {e}")
        return False


async def create_shopify_product(product_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Crea un producto en Shopify.

    Args:
        product_data: Datos del producto

    Returns:
        Dict: Producto creado
    """
    try:
        client = get_graphql_client()
        return await client.create_product(product_data)
    except Exception as e:
        logger.error(f"Error creating Shopify product: {e}")
        raise


async def initialize_http_client():
    """
    Inicializa el cliente HTTP para Shopify.
    """
    client = get_graphql_client()
    await client.initialize()
    logger.info("Shopify HTTP client initialized")


async def close_http_client():
    """
    Cierra el cliente HTTP para Shopify.
    """
    global _graphql_client
    if _graphql_client is not None:
        await _graphql_client.close()
        _graphql_client = None
        logger.info("Shopify HTTP client closed")
