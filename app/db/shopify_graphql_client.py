"""
Cliente GraphQL para Shopify API.

Este módulo implementa un cliente completo para interactuar con la API GraphQL de Shopify,
siguiendo las mejores prácticas y especificaciones de la versión 2024-10.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from aiohttp import ClientTimeout

from app.core.config import get_settings
from app.db.shopify_graphql_queries import (
    CREATE_PRODUCT_MUTATION,
    CREATE_VARIANT_MUTATION,
    INVENTORY_SET_MUTATION,
    LOCATIONS_QUERY,
    ORDERS_QUERY,
    PRODUCT_BY_SKU_QUERY,
    PRODUCTS_QUERY,
    TAXONOMY_CATEGORIES_QUERY,
    UPDATE_PRODUCT_MUTATION,
    UPDATE_VARIANTS_BULK_MUTATION,
)
from app.utils.error_handler import RateLimitException, ShopifyAPIException
from app.utils.retry_handler import get_handler

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyGraphQLClient:
    """
    Cliente GraphQL para operaciones con la API de Shopify.

    Implementa:
    - Autenticación con token de acceso
    - Manejo de rate limits con estrategia de backoff
    - Operaciones CRUD para productos
    - Gestión de inventario multi-ubicación
    - Procesamiento de pedidos
    - Manejo de errores y reintentos
    """

    def __init__(self):
        """Inicializa el cliente GraphQL de Shopify."""
        self.shop_url = settings.SHOPIFY_SHOP_URL
        self.access_token = settings.SHOPIFY_ACCESS_TOKEN
        self.api_version = settings.SHOPIFY_API_VERSION or "2024-10"
        self.session: Optional[aiohttp.ClientSession] = None

        # Rate limiting configuration
        self.rate_limit_points = 1000  # Standard plan bucket size
        self.rate_limit_restore = 50  # Points per second
        self.current_points = self.rate_limit_points
        self.last_request_time = time.time()

        # GraphQL endpoint
        # Remove https:// if already present in shop_url
        clean_shop_url = self.shop_url.replace("https://", "").replace("http://", "")
        self.graphql_url = f"https://{clean_shop_url}/admin/api/{self.api_version}/graphql.json"

        # Initialize retry handler
        self.retry_handler = get_handler("shopify")

        logger.info(f"Shopify GraphQL Client initialized for {self.shop_url}")

    async def initialize(self):
        """Inicializa el cliente HTTP con configuración optimizada."""
        try:
            timeout = ClientTimeout(total=30, connect=10, sock_read=20)
            connector = aiohttp.TCPConnector(limit=100, ttl_dns_cache=300)

            self.session = aiohttp.ClientSession(headers=self._get_headers(), timeout=timeout, connector=connector)
            logger.info("Shopify HTTP client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Shopify client: {e}")
            raise

    async def close(self):
        """Cierra el cliente HTTP de forma segura."""
        try:
            if self.session:
                if not self.session.closed:
                    await self.session.close()
                self.session = None
                logger.info("Shopify HTTP client closed successfully")
            else:
                logger.debug("Shopify HTTP client was already closed or not initialized")
        except Exception as e:
            logger.error(f"Error closing Shopify client: {e}")
            # No re-raise para evitar que falle el shutdown
            self.session = None

    def _get_headers(self) -> Dict[str, str]:
        """
        Obtiene los headers necesarios para las peticiones GraphQL.

        Returns:
            Dict con headers de autenticación y contenido
        """
        return {
            "X-Shopify-Access-Token": self.access_token,
            "Content-Type": "application/json",
            "User-Agent": f"{settings.APP_NAME}/{settings.APP_VERSION}",
        }

    async def _execute_query(
        self, query: str, variables: Optional[Dict[str, Any]] = None, use_retry: bool = True
    ) -> Dict[str, Any]:
        """
        Ejecuta una query/mutation GraphQL con manejo de errores y reintentos.

        Args:
            query: Query o mutation GraphQL
            variables: Variables para la query
            use_retry: Si usar el sistema de reintentos

        Returns:
            Dict con la respuesta de la API

        Raises:
            ShopifyAPIException: Error en la API
            RateLimitException: Límite de rate alcanzado
        """
        if use_retry:
            return await self.retry_handler.execute(
                self._execute_single_query,
                query,
                variables,
                context={"query_type": "graphql", "endpoint": self.graphql_url},
            )
        else:
            return await self._execute_single_query(query, variables)

    async def _execute_single_query(self, query: str, variables: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Ejecuta una sola query GraphQL sin reintentos.

        Args:
            query: Query o mutation GraphQL
            variables: Variables para la query

        Returns:
            Dict con la respuesta de la API
        """
        if not self.session:
            logger.warning("Session not initialized, creating new session")
            await self.initialize()

        # Check and update rate limit points
        await self._check_rate_limit()

        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with self.session.post(self.graphql_url, json=payload) as response:
            # Update rate limit from headers
            self._update_rate_limit_from_headers(response.headers)

            # Handle different response codes
            if response.status == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitException(
                    message="Shopify rate limit exceeded",
                    limit=self.rate_limit_points,
                    reset_time=int(time.time()) + retry_after,
                    retry_after=retry_after,
                )

            if response.status >= 500:
                raise ShopifyAPIException(
                    message=f"Shopify server error: {response.status}",
                    api_response_code=response.status,
                    endpoint=self.graphql_url,
                )

            if response.status != 200:
                text = await response.text()
                raise ShopifyAPIException(
                    message=f"Shopify API error: {text}", api_response_code=response.status, endpoint=self.graphql_url
                )

            try:
                data = await response.json()
            except Exception as e:
                raise ShopifyAPIException(
                    message=f"Failed to parse Shopify response: {e}",
                    api_response_code=response.status,
                    endpoint=self.graphql_url,
                ) from e

            # Check for GraphQL errors
            if "errors" in data:
                error_messages = [error.get("message", str(error)) for error in data["errors"]]
                raise ShopifyAPIException(
                    message=f"GraphQL errors: {', '.join(error_messages)}",
                    api_response_code=response.status,
                    endpoint=self.graphql_url,
                )

            return data.get("data", {})

    async def _check_rate_limit(self):
        """Verifica y actualiza los puntos de rate limit disponibles."""
        current_time = time.time()
        time_passed = current_time - self.last_request_time

        # Restore points based on time passed
        points_to_restore = min(
            self.rate_limit_points - self.current_points, int(time_passed * self.rate_limit_restore)
        )

        self.current_points = min(self.rate_limit_points, self.current_points + points_to_restore)

        self.last_request_time = current_time

        # If not enough points, wait
        if self.current_points < 100:  # Minimum threshold
            wait_time = (100 - self.current_points) / self.rate_limit_restore
            logger.info(f"Waiting {wait_time:.1f}s for rate limit recovery")
            await asyncio.sleep(wait_time)

    def _update_rate_limit_from_headers(self, headers: Dict[str, str]):
        """Actualiza información de rate limit desde headers de respuesta."""
        if "X-Shopify-Api-Call-Limit" in headers:
            try:
                used, total = headers["X-Shopify-Api-Call-Limit"].split("/")
                self.current_points = self.rate_limit_points - int(used)
            except Exception as e:
                logger.warning(f"Could not parse rate limit header: {e}")

    async def test_connection(self) -> bool:
        """
        Verifica la conectividad con la API GraphQL de Shopify.

        Returns:
            bool: True si la conexión es exitosa
        """
        try:
            query = "{ shop { name currencyCode } }"
            result = await self._execute_query(query)

            if result and "shop" in result:
                logger.info(f"Successfully connected to Shopify: {result['shop']['name']}")
                return True
            return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    async def get_locations(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las ubicaciones de inventario.

        Returns:
            Lista de ubicaciones con sus IDs y detalles
        """
        try:
            result = await self._execute_query(LOCATIONS_QUERY)
            locations = []

            for edge in result.get("locations", {}).get("edges", []):
                location = edge.get("node", {})
                if location.get("isActive"):
                    locations.append(location)

            logger.info(f"Retrieved {len(locations)} active locations")
            return locations

        except Exception as e:
            logger.error(f"Error getting locations: {e}")
            raise

    async def get_primary_location_id(self) -> Optional[str]:
        """
        Obtiene el ID de la ubicación principal (primera activa).

        Returns:
            ID de la ubicación principal o None si no hay ubicaciones
        """
        try:
            locations = await self.get_locations()
            if locations:
                primary_location = locations[0]
                logger.info(f"Using primary location: {primary_location['name']} ({primary_location['id']})")
                return primary_location["id"]
            else:
                logger.warning("No active locations found")
                return None
        except Exception as e:
            logger.error(f"Error getting primary location: {e}")
            return None

    async def search_taxonomy_categories(self, search_term: str) -> List[Dict[str, str]]:
        """
        Busca categorías en la taxonomía de Shopify.

        Args:
            search_term: Término de búsqueda para encontrar categorías

        Returns:
            Lista de categorías con id, name y fullName
        """
        try:
            variables = {"search": search_term}
            result = await self._execute_query(TAXONOMY_CATEGORIES_QUERY, variables)

            categories = []
            for edge in result.get("taxonomy", {}).get("categories", {}).get("edges", []):
                node = edge.get("node", {})
                categories.append({"id": node.get("id"), "name": node.get("name"), "fullName": node.get("fullName")})

            logger.info(f"Found {len(categories)} categories for search term: '{search_term}'")
            return categories

        except Exception as e:
            logger.error(f"Error searching taxonomy categories: {e}")
            return []

    async def get_products(self, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene productos de Shopify con paginación.

        Args:
            limit: Número de productos por página (max 250)
            cursor: Cursor para paginación

        Returns:
            Dict con productos y información de paginación
        """
        try:
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(PRODUCTS_QUERY, variables)

            products = []
            for edge in result.get("products", {}).get("edges", []):
                products.append(edge.get("node"))

            page_info = result.get("products", {}).get("pageInfo", {})

            return {
                "products": products,
                "pageInfo": page_info,
                "hasNextPage": page_info.get("hasNextPage", False),
                "endCursor": page_info.get("endCursor"),
            }

        except Exception as e:
            logger.error(f"Error getting products: {e}")
            raise

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Busca un producto por SKU.

        Args:
            sku: SKU del producto

        Returns:
            Producto si existe, None si no se encuentra
        """
        try:
            variables = {"sku": f"sku:{sku}"}
            result = await self._execute_query(PRODUCT_BY_SKU_QUERY, variables)

            edges = result.get("products", {}).get("edges", [])
            if edges:
                product = edges[0].get("node")
                # Verify SKU match in variants
                for variant_edge in product.get("variants", {}).get("edges", []):
                    variant = variant_edge.get("node", {})
                    if variant.get("sku") == sku:
                        return product

            return None

        except Exception as e:
            logger.error(f"Error finding product by SKU {sku}: {e}")
            return None

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo producto en Shopify.

        Args:
            product_data: Datos del producto siguiendo el schema de Shopify

        Returns:
            Producto creado con su ID

        Raises:
            ShopifyAPIException: Si hay errores en la creación
        """
        try:
            variables = {"input": product_data}
            result = await self._execute_query(CREATE_PRODUCT_MUTATION, variables)

            product_result = result.get("productCreate", {})
            user_errors = product_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Product creation failed: {', '.join(error_messages)}")

            product = product_result.get("product")
            if product:
                logger.info(f"Created product: {product['id']} - {product['title']}")
                return product

            raise ShopifyAPIException("Product creation failed: No product returned")

        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise

    async def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza un producto existente.

        Args:
            product_id: ID del producto en Shopify
            product_data: Datos a actualizar

        Returns:
            Producto actualizado
        """
        try:
            product_data["id"] = product_id
            variables = {"input": product_data}
            result = await self._execute_query(UPDATE_PRODUCT_MUTATION, variables)

            product_result = result.get("productUpdate", {})
            user_errors = product_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Product update failed: {', '.join(error_messages)}")

            product = product_result.get("product")
            if product:
                logger.info(f"Updated product: {product['id']} - {product['title']}")
                return product

            raise ShopifyAPIException("Product update failed: No product returned")

        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            raise

    async def update_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Actualiza variantes de producto en lote usando productVariantsBulkUpdate.

        Args:
            product_id: ID del producto
            variants_data: Lista de datos de variantes a actualizar

        Returns:
            Resultado de la actualización masiva
        """
        try:
            variables = {"productId": product_id, "variants": variants_data}
            result = await self._execute_query(UPDATE_VARIANTS_BULK_MUTATION, variables)

            bulk_result = result.get("productVariantsBulkUpdate", {})
            user_errors = bulk_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Bulk variant update failed: {', '.join(error_messages)}")

            variants = bulk_result.get("productVariants", [])
            if variants:
                logger.info(f"Updated {len(variants)} variants for product {product_id}")
                return bulk_result

            raise ShopifyAPIException("Bulk variant update failed: No variants returned")

        except Exception as e:
            logger.error(f"Error updating variants for product {product_id}: {e}")
            raise

    async def create_variant(self, product_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea una nueva variante para un producto existente.

        Args:
            product_id: ID del producto
            variant_data: Datos de la variante

        Returns:
            Variante creada
        """
        try:
            # Ensure productId is included
            variant_data["productId"] = product_id

            variables = {"input": variant_data}
            result = await self._execute_query(CREATE_VARIANT_MUTATION, variables)

            variant_result = result.get("productVariantCreate", {})
            user_errors = variant_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Variant creation failed: {', '.join(error_messages)}")

            variant = variant_result.get("productVariant")
            if variant:
                logger.info(f"Created variant: {variant['id']} - SKU: {variant.get('sku')}")
                return variant

            raise ShopifyAPIException("Variant creation failed: No variant returned")

        except Exception as e:
            logger.error(f"Error creating variant for product {product_id}: {e}")
            raise

    async def update_variant(self, variant_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza una sola variante usando bulk update con una variante.
        (Wrapper de compatibilidad que usa update_variants_bulk internamente)

        Args:
            variant_id: ID de la variante
            variant_data: Datos a actualizar

        Returns:
            Variante actualizada
        """
        logger.warning("update_variant is deprecated, but cannot determine product_id. Using fallback approach.")

        # Para compatibilidad, necesitamos obtener el product_id de la variante
        # Esto requiere una query adicional, pero es necesario para la nueva API
        raise ShopifyAPIException(
            "update_variant requires product_id. Use update_variants_bulk instead or "
            "create_product_with_variants for new products."
        )

    async def update_inventory(self, inventory_item_id: str, location_id: str, available_quantity: int) -> bool:
        """
        Actualiza el inventario de un producto en una ubicación específica.

        Args:
            inventory_item_id: ID del item de inventario
            location_id: ID de la ubicación
            available_quantity: Nueva cantidad disponible

        Returns:
            bool: True si la actualización fue exitosa
        """
        try:
            # Use inventory set mutation for absolute quantity
            variables = {
                "input": {
                    "reason": "correction",
                    "name": "RMS Sync",
                    "quantities": [
                        {"inventoryItemId": inventory_item_id, "locationId": location_id, "onHand": available_quantity}
                    ],
                }
            }

            result = await self._execute_query(INVENTORY_SET_MUTATION, variables)

            inventory_result = result.get("inventorySetOnHandQuantities", {})
            user_errors = inventory_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                logger.error(f"Inventory update failed: {', '.join(error_messages)}")
                return False

            if inventory_result.get("inventoryAdjustmentGroup"):
                logger.info(f"Updated inventory for {inventory_item_id} at {location_id}: {available_quantity}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating inventory: {e}")
            return False

    async def get_orders(
        self,
        limit: int = 50,
        cursor: Optional[str] = None,
        status: Optional[str] = None,
        created_at_min: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Obtiene pedidos de Shopify con filtros opcionales.

        Args:
            limit: Número de pedidos por página
            cursor: Cursor para paginación
            status: Estado del pedido (e.g., "open", "closed")
            created_at_min: Fecha mínima de creación

        Returns:
            Dict con pedidos y información de paginación
        """
        try:
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            # Build query filter
            query_parts = []
            if status:
                query_parts.append(f"status:{status}")
            if created_at_min:
                query_parts.append(f"created_at:>={created_at_min.isoformat()}")

            if query_parts:
                variables["query"] = " AND ".join(query_parts)

            result = await self._execute_query(ORDERS_QUERY, variables)

            orders = []
            for edge in result.get("orders", {}).get("edges", []):
                orders.append(edge.get("node"))

            page_info = result.get("orders", {}).get("pageInfo", {})

            return {
                "orders": orders,
                "pageInfo": page_info,
                "hasNextPage": page_info.get("hasNextPage", False),
                "endCursor": page_info.get("endCursor"),
            }

        except Exception as e:
            logger.error(f"Error getting orders: {e}")
            raise

    async def get_all_products(self) -> List[Dict[str, Any]]:
        """
        Obtiene todos los productos usando paginación automática.

        Returns:
            Lista completa de productos
        """
        try:
            all_products = []
            cursor = None

            while True:
                result = await self.get_products(limit=250, cursor=cursor)
                products = result.get("products", [])
                all_products.extend(products)

                if not result.get("hasNextPage", False):
                    break

                cursor = result.get("endCursor")
                if not cursor:
                    break

                # Small delay to be respectful of rate limits
                await asyncio.sleep(0.1)

            logger.info(f"Retrieved {len(all_products)} total products")
            return all_products

        except Exception as e:
            logger.error(f"Error getting all products: {e}")
            raise

    async def batch_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Actualiza inventario en lote.

        Args:
            inventory_updates: Lista de actualizaciones con estructura:
                [{"inventory_item_id": "...", "location_id": "...", "available": 123}, ...]

        Returns:
            Tupla con (éxitos, lista de errores)
        """
        success_count = 0
        errors = []

        # Process in chunks to avoid overwhelming the API
        chunk_size = 10
        for i in range(0, len(inventory_updates), chunk_size):
            chunk = inventory_updates[i : i + chunk_size]

            # Process chunk concurrently
            tasks = []
            for update in chunk:
                task = self.update_inventory(update["inventory_item_id"], update["location_id"], update["available"])
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    errors.append({"update": chunk[j], "error": str(result)})
                elif result:
                    success_count += 1
                else:
                    errors.append({"update": chunk[j], "error": "Update failed"})

            # Rate limit pause between chunks
            if i + chunk_size < len(inventory_updates):
                await asyncio.sleep(1)

        logger.info(f"Inventory batch update: {success_count} success, {len(errors)} errors")
        return success_count, errors

    async def update_variant_rest(self, variant_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Actualiza una variante usando REST API (útil para campos como SKU).

        Args:
            variant_id: ID de la variante (sin gid prefix)
            variant_data: Datos a actualizar

        Returns:
            Variante actualizada
        """
        try:
            # Extract numeric ID from GraphQL ID
            if variant_id.startswith("gid://shopify/ProductVariant/"):
                numeric_id = variant_id.split("/")[-1]
            else:
                numeric_id = variant_id

            # Build REST API URL
            shop_name = self.shop_url.replace("https://", "").replace("http://", "")
            if not shop_name.endswith(".myshopify.com"):
                shop_name = f"{shop_name}.myshopify.com"

            rest_url = f"https://{shop_name}/admin/api/{self.api_version}/variants/{numeric_id}.json"

            # Prepare payload
            payload = {"variant": variant_data}

            headers = {"X-Shopify-Access-Token": self.access_token, "Content-Type": "application/json"}

            async with self.session.put(rest_url, json=payload, headers=headers) as response:
                if response.status == 200:
                    result = await response.json()
                    variant = result.get("variant", {})
                    logger.info(f"Updated variant via REST: {variant.get('id')} - SKU: {variant.get('sku')}")
                    return variant
                else:
                    error_text = await response.text()
                    raise ShopifyAPIException(f"REST API error {response.status}: {error_text}")

        except Exception as e:
            logger.error(f"Error updating variant via REST: {e}")
            raise

    def get_retry_metrics(self) -> Dict[str, Any]:
        """
        Obtiene métricas del sistema de reintentos.

        Returns:
            Dict: Métricas de reintentos y circuit breaker
        """
        return self.retry_handler.get_metrics()

    def reset_retry_metrics(self):
        """Reinicia las métricas de reintentos."""
        self.retry_handler.reset_metrics()

