"""
Cliente API para Shopify.

Este módulo proporciona funciones para interactuar con la API de Shopify,
incluyendo autenticación, consultas y operaciones CRUD para productos,
inventarios y pedidos. Utiliza GraphQL como interfaz principal.
"""

import logging
from typing import Any, Dict, List, Optional

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
        result = await client.get_products(
            limit=limit or 50,
            cursor=page_info
        )
        
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
        result = await client.get_orders(
            limit=limit or 50,
            cursor=page_info,
            status=status
        )
        
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
        return await client.update_inventory(
            inventory_item_id,
            location_id,
            available
        )
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


class ShopifyClient:
    """
    Cliente principal para operaciones con la API de Shopify.
    Esta clase actúa como wrapper del cliente GraphQL para mantener
    compatibilidad con el código existente.
    """

    def __init__(self):
        """Inicializa el cliente Shopify."""
        self.shop_url = settings.SHOPIFY_SHOP_URL
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = settings.SHOPIFY_API_VERSION
        self._graphql_client = get_graphql_client()
        logger.info("Shopify Client initialized")

    async def test_connection(self) -> bool:
        """
        Prueba la conexión con Shopify.

        Returns:
            bool: True si la conexión es exitosa
        """
        return await self._graphql_client.test_connection()

    async def get_products(self, limit: Optional[int] = None, page_info: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene productos de Shopify.

        Args:
            limit: Límite de resultados
            page_info: Información de página para paginación

        Returns:
            Dict: Respuesta con productos y metadatos
        """
        result = await self._graphql_client.get_products(
            limit=limit or 50,
            cursor=page_info
        )
        
        return {
            "products": result.get("products", []),
            "page_info": result.get("endCursor"),
            "has_next_page": result.get("hasNextPage", False),
        }

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un producto en Shopify.

        Args:
            product_data: Datos del producto

        Returns:
            Dict: Producto creado
        """
        return await self._graphql_client.create_product(product_data)

    async def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza un producto en Shopify.

        Args:
            product_id: ID del producto
            product_data: Datos a actualizar

        Returns:
            Dict: Producto actualizado
        """
        return await self._graphql_client.update_product(product_id, product_data)

    async def get_orders(self, limit: Optional[int] = None, status: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene pedidos de Shopify.

        Args:
            limit: Límite de resultados
            status: Estado de los pedidos

        Returns:
            Dict: Respuesta con pedidos
        """
        result = await self._graphql_client.get_orders(
            limit=limit or 50,
            status=status
        )
        
        return {
            "orders": result.get("orders", []),
            "page_info": result.get("endCursor"),
            "has_next_page": result.get("hasNextPage", False),
        }

    async def update_inventory(self, inventory_item_id: str, location_id: str, available: int) -> bool:
        """
        Actualiza el inventario en Shopify.

        Args:
            inventory_item_id: ID del item de inventario
            location_id: ID de la ubicación
            available: Cantidad disponible

        Returns:
            bool: True si la actualización fue exitosa
        """
        return await self._graphql_client.update_inventory(
            inventory_item_id,
            location_id,
            available
        )

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Busca un producto por SKU.

        Args:
            sku: SKU del producto

        Returns:
            Producto si existe, None si no se encuentra
        """
        return await self._graphql_client.get_product_by_sku(sku)

    async def get_locations(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las ubicaciones de inventario.

        Returns:
            Lista de ubicaciones
        """
        return await self._graphql_client.get_locations()

    async def batch_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> tuple[int, List[Dict[str, Any]]]:
        """
        Actualiza inventario en lote.

        Args:
            inventory_updates: Lista de actualizaciones

        Returns:
            Tupla con (éxitos, errores)
        """
        return await self._graphql_client.batch_update_inventory(inventory_updates)

    async def initialize(self):
        """
        Inicializa el cliente HTTP para Shopify.
        """
        try:
            await self._graphql_client.initialize()
            logger.info("Shopify HTTP client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Shopify client: {e}")
            raise

    async def close(self):
        """
        Cierra el cliente HTTP de Shopify.
        """
        try:
            await self._graphql_client.close()
            logger.info("Shopify HTTP client closed")
        except Exception as e:
            logger.error(f"Error closing Shopify client: {e}")
            raise

    async def get_all_products(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los productos de Shopify con paginación automática.

        Returns:
            List[Dict]: Lista completa de productos
        """
        return await self._graphql_client.get_all_products()

    def get_headers(self) -> Dict[str, str]:
        """
        Obtiene los headers para requests a Shopify.

        Returns:
            Dict: Headers de autenticación
        """
        return self._graphql_client._get_headers()


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