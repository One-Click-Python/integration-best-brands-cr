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
from app.db.queries import (
    CREATE_PRODUCT_MUTATION,
    CREATE_VARIANT_MUTATION,
    CREATE_VARIANTS_BULK_MUTATION,
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
        self.api_version = settings.SHOPIFY_API_VERSION or "2025-04"
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

    async def get_primary_location_id(self, preferred_location_name: Optional[str] = None) -> Optional[str]:
        """
        Obtiene el ID de la ubicación principal usando lógica mejorada.

        Args:
            preferred_location_name: Nombre de ubicación preferida (opcional)

        Returns:
            ID de la ubicación principal o None si no hay ubicaciones
        """
        try:
            locations = await self.get_locations()
            if not locations:
                logger.warning("No active locations found")
                return None

            logger.info(f"Found {len(locations)} active locations:")
            for i, loc in enumerate(locations):
                logger.info(f"  {i + 1}. {loc['name']} (ID: {loc['id']})")
                if loc.get("address"):
                    addr = loc["address"]
                    logger.info(
                        f"     Address: {addr.get('address1', '')}, {addr.get('city', '')}, {addr.get('country', '')}"
                    )

            # Si se especifica una ubicación preferida, buscarla
            if preferred_location_name:
                for location in locations:
                    if location["name"].lower() == preferred_location_name.lower():
                        logger.info(f"Using configured primary location: {location['name']} ({location['id']})")
                        return location["id"]
                logger.warning(f"Preferred location '{preferred_location_name}' not found")

            # Buscar ubicaciones con nombres que sugieran ser principales
            primary_keywords = [
                "main",
                "primary",
                "principal",
                "headquarters",
                "default",
                "warehouse",
                "almacen",
                "central",
            ]

            for location in locations:
                location_name = location["name"].lower()
                for keyword in primary_keywords:
                    if keyword in location_name:
                        logger.info(
                            f"Found primary location by name pattern '{keyword}': {location['name']} ({location['id']})"
                        )
                        return location["id"]

            # Si solo hay una ubicación, usarla
            if len(locations) == 1:
                primary_location = locations[0]
                logger.info(
                    f"Using single active location as primary: {primary_location['name']} ({primary_location['id']})"
                )
                return primary_location["id"]

            # Usar la primera como fallback pero advertir
            primary_location = locations[0]
            logger.warning(
                f"No clear primary location found, using first active location: "
                f"{primary_location['name']} ({primary_location['id']})"
            )
            logger.warning("Consider configuring a preferred location name to avoid ambiguity")
            return primary_location["id"]

        except Exception as e:
            logger.error(f"Error getting primary location: {e}")
            return None

    async def search_taxonomy_categories(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Busca categorías en la taxonomía de Shopify.

        Args:
            search_term: Término de búsqueda para encontrar categorías

        Returns:
            Lista de categorías con id, name, fullName y attributes
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

    async def get_taxonomy_category_details(self, category_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene detalles completos de una categoría de taxonomía.

        Args:
            category_id: ID de la categoría de taxonomía

        Returns:
            Dict con detalles de la categoría o None si no se encuentra
        """
        try:
            from .shopify_graphql_queries import TAXONOMY_CATEGORY_DETAILS_QUERY

            variables = {"categoryId": category_id}
            result = await self._execute_query(TAXONOMY_CATEGORY_DETAILS_QUERY, variables)

            category_data = result.get("taxonomy", {}).get("category")
            if category_data:
                logger.info(f"Retrieved details for taxonomy category: {category_data.get('fullName')}")
                return category_data
            else:
                logger.warning(f"Taxonomy category not found: {category_id}")
                return None

        except Exception as e:
            logger.error(f"Error getting taxonomy category details: {e}")
            return None

    async def find_best_taxonomy_match(self, search_terms: List[str]) -> Optional[Dict[str, Any]]:
        """
        Encuentra la mejor coincidencia de taxonomía para una lista de términos de búsqueda.

        Args:
            search_terms: Lista de términos de búsqueda ordenados por prioridad

        Returns:
            Mejor categoría encontrada o None
        """
        try:
            best_match = None
            best_score = 0

            for i, term in enumerate(search_terms):
                categories = await self.search_taxonomy_categories(term)

                for category in categories:
                    # Calcular puntuación basada en prioridad del término y exactitud del nombre
                    term_priority_score = (len(search_terms) - i) * 10  # Términos anteriores tienen mayor prioridad
                    name_match_score = 0

                    # Bonificación por coincidencia exacta en nombre
                    if term.lower() == category["name"].lower():
                        name_match_score = 50
                    elif term.lower() in category["name"].lower():
                        name_match_score = 25
                    elif term.lower() in category["fullName"].lower():
                        name_match_score = 15

                    total_score = term_priority_score + name_match_score

                    if total_score > best_score:
                        best_score = total_score
                        best_match = category
                        logger.debug(f"New best match: {category['fullName']} (score: {total_score})")

            if best_match:
                logger.info(f"Best taxonomy match: {best_match['fullName']} (score: {best_score})")
            else:
                logger.warning(f"No taxonomy match found for search terms: {search_terms}")

            return best_match

        except Exception as e:
            logger.error(f"Error finding best taxonomy match: {e}")
            return None

    async def create_metafields_bulk(self, metafields_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Crea múltiples metafields en una sola operación (hasta 25).

        Args:
            metafields_data: Lista de datos de metafields a crear

        Returns:
            Lista de metafields creados
        """
        try:
            from .shopify_graphql_queries import METAFIELDS_SET_MUTATION

            if len(metafields_data) > 25:
                logger.warning(f"Attempted to create {len(metafields_data)} metafields, but max is 25. Truncating.")
                metafields_data = metafields_data[:25]

            variables = {"metafields": metafields_data}
            result = await self._execute_query(METAFIELDS_SET_MUTATION, variables)

            metafields_set_result = result.get("metafieldsSet", {})
            created_metafields = metafields_set_result.get("metafields", [])
            user_errors = metafields_set_result.get("userErrors", [])

            if user_errors:
                logger.error(f"Errors creating metafields: {user_errors}")
            else:
                logger.info(f"Successfully created {len(created_metafields)} metafields")

            return created_metafields

        except Exception as e:
            logger.error(f"Error creating metafields bulk: {e}")
            raise

    async def create_metafield_definition(self, definition_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea una definición de metafield.

        Args:
            definition_data: Datos de la definición del metafield

        Returns:
            Definición creada o None si falla
        """
        try:
            from .shopify_graphql_queries import CREATE_METAFIELD_DEFINITION_MUTATION

            variables = {"definition": definition_data}
            result = await self._execute_query(CREATE_METAFIELD_DEFINITION_MUTATION, variables)

            metafield_definition_result = result.get("metafieldDefinitionCreate", {})
            created_definition = metafield_definition_result.get("createdDefinition")
            user_errors = metafield_definition_result.get("userErrors", [])

            if user_errors:
                logger.error(f"Errors creating metafield definition: {user_errors}")
                return None
            elif created_definition:
                logger.info(
                    f"Successfully created metafield definition: "
                    f"{created_definition['namespace']}.{created_definition['key']}"
                )
                return created_definition
            else:
                logger.error("Unknown error creating metafield definition")
                return None

        except Exception as e:
            logger.error(f"Error creating metafield definition: {e}")
            return None

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

    async def get_product_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Busca un producto por handle.

        Args:
            handle: Handle del producto

        Returns:
            Producto si existe, None si no se encuentra
        """
        try:
            from .shopify_graphql_queries import PRODUCT_BY_HANDLE_QUERY

            variables = {"handle": f"handle:{handle}"}
            result = await self._execute_query(PRODUCT_BY_HANDLE_QUERY, variables)

            edges = result.get("products", {}).get("edges", [])
            if edges:
                product = edges[0].get("node")
                # Verify handle match
                if product.get("handle") == handle:
                    return product

            return None

        except Exception as e:
            logger.error(f"Error finding product by handle {handle}: {e}")
            return None

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo producto en Shopify o actualiza uno existente si el handle ya existe.

        Args:
            product_data: Datos del producto siguiendo el schema de Shopify

        Returns:
            Producto creado o actualizado con su ID

        Raises:
            ShopifyAPIException: Si hay errores en la creación
        """
        try:
            variables = {"input": product_data}
            result = await self._execute_query(CREATE_PRODUCT_MUTATION, variables)

            product_result = result.get("productCreate", {})
            user_errors = product_result.get("userErrors", [])

            if user_errors:
                # Check if the error is about handle already in use
                for error in user_errors:
                    if "handle" in error.get("field", []) and "already in use" in error.get("message", ""):
                        handle = product_data.get("handle")
                        logger.warning(f"Handle '{handle}' already in use, checking existing product")

                        # Try to find the existing product
                        existing_product = await self.get_product_by_handle(handle)
                        if existing_product:
                            logger.info(f"Found existing product with handle '{handle}', updating instead of creating")
                            # Update the existing product
                            update_data = product_data.copy()
                            update_data["id"] = existing_product["id"]
                            return await self.update_product(existing_product["id"], update_data)
                        else:
                            # Generate a unique handle and try again
                            product_data["handle"] = handle
                            return await self.create_product(product_data)

                # If it's not a handle error, raise the original exception
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

    async def create_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Crea múltiples variantes de producto en lote usando productVariantsBulkCreate.

        Args:
            product_id: ID del producto
            variants_data: Lista de datos de variantes a crear

        Returns:
            Resultado de la creación masiva de variantes
        """
        try:
            variables = {"productId": product_id, "variants": variants_data}
            result = await self._execute_query(CREATE_VARIANTS_BULK_MUTATION, variables)

            bulk_result = result.get("productVariantsBulkCreate", {})
            user_errors = bulk_result.get("userErrors", [])

            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                raise ShopifyAPIException(f"Bulk variant creation failed: {', '.join(error_messages)}")

            variants = bulk_result.get("productVariants", [])
            product = bulk_result.get("product", {})

            if variants:
                logger.info(f"✅ Created {len(variants)} variants for product {product_id}")
                for variant in variants:
                    options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                    logger.info(f"   ✅ Variant: {variant['sku']} - {options_str} - ${variant['price']}")
                return bulk_result

            raise ShopifyAPIException("Bulk variant creation failed: No variants returned")

        except Exception as e:
            logger.error(f"Error creating variants for product {product_id}: {e}")
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

    async def activate_inventory_tracking(
        self, inventory_item_id: str, location_id: str, available_quantity: int = None
    ) -> Dict[str, Any]:
        """
         Activa el tracking de inventario y establece la cantidad disponible inicial.

        Flujo de 3 pasos:
        1. Habilitar tracking en el inventory item
        2. Activar inventory en la ubicación
        3. Establecer cantidad disponible

        Args:
            inventory_item_id: ID del item de inventario
            location_id: ID de la ubicación
            available_quantity: Cantidad disponible inicial

        Returns:
            Resultado completo con el inventory level final
        """
        try:
            from .shopify_graphql_queries import (
                INVENTORY_ACTIVATE_MUTATION,
                INVENTORY_ITEM_UPDATE_MUTATION,
                INVENTORY_SET_QUANTITIES_MUTATION
            )

            # 📝 PASO 1: Habilitar tracking en el inventory item
            logger.info(f"🔄 Step 1: Enabling tracking for item {inventory_item_id}")

            update_variables = {"id": inventory_item_id, "input": {"tracked": True}}

            update_result = await self._execute_query(INVENTORY_ITEM_UPDATE_MUTATION, update_variables)

            update_data = update_result.get("inventoryItemUpdate", {})
            if update_errors := update_data.get("userErrors", []):
                logger.error(f"❌ Step 1 failed: {update_errors}")
                return {"success": False, "step": 1, "errors": update_errors}

            logger.info("✅ Step 1: Tracking enabled successfully")

            # 📍 PASO 2: Activar inventory en la ubicación
            activation_variables = {"inventoryItemId": inventory_item_id, "locationId": location_id}

            activation_result = await self._execute_query(INVENTORY_ACTIVATE_MUTATION, activation_variables)

            activation_data = activation_result.get("inventoryActivate", {})
            if activation_errors := activation_data.get("userErrors", []):
                logger.error(f"❌ Step 2 failed: {activation_errors}")
                return {"success": False, "step": 2, "errors": activation_errors}

            inventory_level = activation_data.get("inventoryLevel", {})
            logger.info("✅ Step 2: Inventory activated at location")

            # 📊 PASO 3: Establecer cantidad disponible (si se especifica)
            if available_quantity is not None and available_quantity > 0:
                logger.info(f"🔄 Step 3: Setting available quantity to {available_quantity}")

                # Obtener la cantidad actual del inventory level
                current_quantity = inventory_level.get("available", 0)
                logger.info(f"   Current quantity: {current_quantity}")

                # Para establecer la cantidad, usamos inventorySetQuantities
                # Ignoramos compareQuantity para simplificar
                set_quantity_variables = {
                    "input": {
                        "name": "available",
                        "reason": "correction",  
                        "referenceDocumentUri": f"inventory-setup-{inventory_item_id}",
                        "ignoreCompareQuantity": True,  # Ignorar la verificación de cantidad actual
                        "quantities": [
                            {
                                "inventoryItemId": inventory_item_id,
                                "locationId": location_id,
                                "quantity": available_quantity
                            }
                        ]
                    }
                }

                set_result = await self._execute_query(
                    INVENTORY_SET_QUANTITIES_MUTATION,
                    set_quantity_variables
                )

                set_data = set_result.get("inventorySetQuantities", {})
                if set_errors := set_data.get("userErrors", []):
                    logger.error(f"❌ Step 3 failed: {set_errors}")
                    return {"success": False, "step": 3, "errors": set_errors}

                adjustment_group = set_data.get("inventoryAdjustmentGroup", {})
                changes = adjustment_group.get("changes", [])
                
                if changes:
                    available_change = next(
                        (c for c in changes if c.get("name") == "available"),
                        changes[0]
                    )
                    delta = available_change.get("delta", 0)
                    final_quantity = current_quantity + delta
                    logger.info(f"✅ Step 3: Quantity set (Δ{delta:+d}) → Final: {final_quantity}")
                else:
                    final_quantity = available_quantity
                    logger.info("✅ Step 3: Quantity operation completed")
            else:
                logger.info("ℹ️ Step 3: No quantity specified, skipping adjustment")
                final_quantity = 0

            return {
                "success": True,
                "inventoryLevel": inventory_level,
                "tracked": True,
                "finalQuantity": final_quantity
            }

        except Exception as e:
            logger.error(f"❌ Failed to activate inventory tracking: {e}")
            return {"success": False, "error": str(e)}

    async def update_inventory(
        self, inventory_item_id: str, location_id: str, available_quantity: int
    ) -> Dict[str, Any]:
        """
        Actualiza el inventario de un producto en una ubicación específica con mejor tracking.

        Args:
            inventory_item_id: ID del item de inventario
            location_id: ID de la ubicación
            available_quantity: Nueva cantidad disponible

        Returns:
            Dict: Resultado detallado de la actualización
        """
        import time

        start_time = time.time()

        try:
            # Usar inventorySetOnHandQuantities mutation optimizada
            variables = {
                "input": {
                    "reason": "RMS Sync",
                    "referenceDocumentUri": f"rms://sync/{inventory_item_id}",
                    "setQuantities": [
                        {
                            "inventoryItemId": inventory_item_id,
                            "locationId": location_id,
                            "quantity": available_quantity,
                        }
                    ],
                }
            }

            result = await self._execute_query(INVENTORY_SET_MUTATION, variables)
            inventory_result = result.get("inventorySetOnHandQuantities", {})

            # Manejo mejorado de errores
            user_errors = inventory_result.get("userErrors", [])
            if user_errors:
                error_messages = [f"{e['field']}: {e['message']}" for e in user_errors]
                logger.error(f"Inventory update failed: {', '.join(error_messages)}")
                return {"success": False, "errors": user_errors}

            # Extraer información de cambios
            adjustment_group = inventory_result.get("inventoryAdjustmentGroup", {})
            changes = adjustment_group.get("changes", [])
            available_change = next((c for c in changes if c["name"] == "available"), None)

            duration = time.time() - start_time

            result_data = {
                "success": True,
                "inventory_item_id": inventory_item_id,
                "location_id": location_id,
                "new_quantity": available_quantity,
                "delta": available_change["delta"] if available_change else 0,
                "adjustment_id": adjustment_group.get("id"),
                "duration_ms": round(duration * 1000, 2),
            }

            logger.info(
                f"✅ Inventory updated successfully: {inventory_item_id} → {available_quantity} units "
                f"(delta: {result_data['delta']}) in {result_data['duration_ms']}ms"
            )

            return result_data

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"❌ Inventory update failed: {e} (duration: {round(duration * 1000, 2)}ms)")
            return {
                "success": False,
                "error": str(e),
                "inventory_item_id": inventory_item_id,
                "location_id": location_id,
                "duration_ms": round(duration * 1000, 2),
            }

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
            page_count = 0

            while True:
                page_count += 1
                logger.info(f"Fetching page {page_count} of products (cursor: {cursor[:50] if cursor else 'None'}...)")

                result = await self.get_products(limit=250, cursor=cursor)
                products = result.get("products", [])

                logger.info(f"Page {page_count}: Retrieved {len(products)} products")

                if products:
                    # Log some product details for debugging
                    for i, product in enumerate(products[:3]):
                        logger.info(
                            f"  Product {i + 1}: {product.get('title', 'No title')} (ID: {product.get('id', 'No ID')})"
                        )

                all_products.extend(products)

                has_next_page = result.get("hasNextPage", False)
                logger.info(f"Page {page_count}: hasNextPage = {has_next_page}")

                if not has_next_page:
                    logger.info(f"No more pages. Completed pagination after {page_count} pages.")
                    break

                cursor = result.get("endCursor")
                if not cursor:
                    logger.warning("hasNextPage=True but no endCursor provided. Breaking pagination.")
                    break

                # Small delay to be respectful of rate limits
                await asyncio.sleep(5)

            logger.info(f"Retrieved {len(all_products)} total products across {page_count} pages")
            return all_products

        except Exception as e:
            logger.error(f"Error getting all products with pagination 😒: {e}")
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
