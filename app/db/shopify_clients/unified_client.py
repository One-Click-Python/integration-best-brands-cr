"""
Unified Shopify GraphQL client that combines all specialized clients.

This module provides a single interface that delegates to specialized clients
while maintaining backward compatibility with the existing codebase.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .base_client import BaseShopifyGraphQLClient
from .product_client import ShopifyProductClient
from .collection_client import ShopifyCollectionClient
from .inventory_client import ShopifyInventoryClient
from app.db.queries import ORDERS_QUERY
from app.utils.error_handler import ShopifyAPIException

logger = logging.getLogger(__name__)


class ShopifyGraphQLClient(BaseShopifyGraphQLClient):
    """
    Unified Shopify GraphQL client that combines all specialized functionality.
    
    This client maintains backward compatibility while providing access to
    specialized clients for more focused operations.
    """

    def __init__(self):
        """Initialize the unified client with all specialized clients."""
        super().__init__()
        
        # Initialize specialized clients
        self.products = ShopifyProductClient()
        self.collections = ShopifyCollectionClient()
        self.inventory = ShopifyInventoryClient()

    async def initialize(self):
        """
        Initialize the unified client and all specialized clients.
        """
        # Initialize base client
        await super().initialize()
        
        # Initialize specialized clients with shared session
        await self._initialize_specialized_clients()
        
        logger.info("✅ Unified Shopify GraphQL client initialized with all specialized clients")

    async def _initialize_specialized_clients(self):
        """Initialize all specialized clients with shared configuration."""
        clients = [self.products, self.collections, self.inventory]
        
        for client in clients:
            # Share configuration
            client.settings = self.settings
            client.shop_url = self.shop_url
            client.access_token = self.access_token
            client.api_version = self.api_version
            client.graphql_url = self.graphql_url
            
            # Share session and rate limiting
            client.session = self.session
            client._last_request_time = self._last_request_time
            client._min_request_interval = self._min_request_interval

    async def close(self):
        """Close the unified client and all specialized clients."""
        # The specialized clients share the same session, so we only need to close once
        await super().close()
        
        # Clear specialized client sessions to avoid double-close
        for client in [self.products, self.collections, self.inventory]:
            client.session = None

    # =============================================================================
    # PRODUCT OPERATIONS - Delegate to ProductClient
    # =============================================================================

    async def get_products(self, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.get_products(limit, cursor)

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Delegate to product client."""
        return await self.products.get_product_by_sku(sku)

    async def get_product_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """Delegate to product client."""
        return await self.products.get_product_by_handle(handle)

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.create_product(product_data)

    async def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.update_product(product_id, product_data)

    async def create_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.create_variants_bulk(product_id, variants_data)

    async def update_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.update_variants_bulk(product_id, variants_data)

    async def create_variant(self, product_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to product client."""
        return await self.products.create_variant(product_id, variant_data)

    async def get_all_products(self) -> List[Dict[str, Any]]:
        """Delegate to product client."""
        return await self.products.get_all_products()

    async def search_taxonomy_categories(self, search_term: str) -> List[Dict[str, Any]]:
        """Delegate to product client."""
        return await self.products.search_taxonomy_categories(search_term)

    async def find_best_taxonomy_match(self, search_terms: List[str]) -> Optional[Dict[str, Any]]:
        """Delegate to product client."""
        return await self.products.find_best_taxonomy_match(search_terms)

    # =============================================================================
    # COLLECTION OPERATIONS - Delegate to CollectionClient
    # =============================================================================

    async def get_collections(self, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        """Delegate to collection client."""
        return await self.collections.get_collections(limit, cursor)

    async def get_collection_by_id(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """Delegate to collection client."""
        return await self.collections.get_collection_by_id(collection_id)

    async def get_collection_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """Delegate to collection client."""
        return await self.collections.get_collection_by_handle(handle)

    async def get_all_collections(self) -> List[Dict[str, Any]]:
        """Delegate to collection client."""
        return await self.collections.get_all_collections()

    async def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to collection client."""
        return await self.collections.create_collection(collection_data)

    async def update_collection(self, collection_id: str, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to collection client."""
        return await self.collections.update_collection(collection_id, collection_data)

    async def delete_collection(self, collection_id: str) -> bool:
        """Delegate to collection client."""
        return await self.collections.delete_collection(collection_id)

    async def add_products_to_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """Delegate to collection client."""
        return await self.collections.add_products_to_collection(collection_id, product_ids)

    async def remove_products_from_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """Delegate to collection client."""
        return await self.collections.remove_products_from_collection(collection_id, product_ids)

    # =============================================================================
    # INVENTORY OPERATIONS - Delegate to InventoryClient
    # =============================================================================

    async def set_variant_inventory_quantity(
        self,
        inventory_item_id: str,
        location_id: str,
        quantity: int,
        disconnect_if_necessary: bool = False
    ) -> Dict[str, Any]:
        """Delegate to inventory client."""
        return await self.inventory.set_variant_inventory_quantity(
            inventory_item_id, location_id, quantity, disconnect_if_necessary
        )

    async def activate_inventory_tracking_well(
        self,
        inventory_item_id: str,
        location_id: str,
        track_quantity: bool = True,
        continue_selling_when_out_of_stock: bool = False
    ) -> Dict[str, Any]:
        """Delegate to inventory client (with backward compatible name)."""
        return await self.inventory.activate_inventory_tracking(
            inventory_item_id, location_id, track_quantity, continue_selling_when_out_of_stock
        )

    async def update_inventory(
        self,
        inventory_item_id: str,
        location_id: str,
        available_quantity: int
    ) -> bool:
        """Delegate to inventory client."""
        return await self.inventory.update_inventory(inventory_item_id, location_id, available_quantity)

    async def batch_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        """Delegate to inventory client."""
        return await self.inventory.batch_update_inventory(inventory_updates)

    async def update_variant_rest(self, variant_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to inventory client."""
        return await self.inventory.update_variant_rest(variant_id, variant_data)

    # =============================================================================
    # ADDITIONAL OPERATIONS (not delegated to specialized clients)
    # =============================================================================

    async def create_metafields_bulk(self, metafields_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Create metafields in bulk.
        
        Args:
            metafields_data: List of metafield data dictionaries
            
        Returns:
            List of created metafields
        """
        # This could be moved to a dedicated MetafieldClient in the future
        from app.db.queries import CREATE_METAFIELD_MUTATION
        
        try:
            created_metafields = []
            
            for metafield_data in metafields_data:
                variables = {"input": metafield_data}
                result = await self._execute_query(CREATE_METAFIELD_MUTATION, variables)
                
                metafield_result = result.get("metafieldSet", {})
                self._handle_graphql_errors(metafield_result, "Metafield creation")
                
                metafield = metafield_result.get("metafield")
                if metafield:
                    created_metafields.append(metafield)
                    
            logger.info(f"✅ Created {len(created_metafields)} metafields")
            return created_metafields
            
        except Exception as e:
            logger.error(f"Error creating metafields in bulk: {e}")
            raise ShopifyAPIException(f"Failed to create metafields in bulk: {str(e)}") from e

    async def get_orders(
        self,
        limit: int = 250,
        cursor: Optional[str] = None,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch orders with pagination support.
        
        Args:
            limit: Number of orders to fetch (max 250)
            cursor: Pagination cursor
            query: Search query for orders
            
        Returns:
            Dict containing orders and pagination info
        """
        try:
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor
            if query:
                variables["query"] = query
                
            result = await self._execute_query(ORDERS_QUERY, variables)
            return result.get("orders", {})
            
        except Exception as e:
            logger.error(f"Error fetching orders: {e}")
            raise ShopifyAPIException(f"Failed to fetch orders: {str(e)}") from e

    # =============================================================================
    # UTILITY METHODS
    # =============================================================================

    def get_specialized_client(self, client_type: str):
        """
        Get a specialized client by type.
        
        Args:
            client_type: Type of client ('products', 'collections', 'inventory')
            
        Returns:
            Specialized client instance
        """
        clients = {
            'products': self.products,
            'collections': self.collections,
            'inventory': self.inventory
        }
        
        client = clients.get(client_type)
        if not client:
            raise ValueError(f"Unknown client type: {client_type}. Available: {list(clients.keys())}")
        
        return client

    def __str__(self):
        """String representation of the unified client."""
        return f"ShopifyGraphQLClient(shop={self.shop_url}, api_version={self.api_version})"

    def __repr__(self):
        """Detailed string representation of the unified client."""
        return (
            f"ShopifyGraphQLClient("
            f"shop_url='{self.shop_url}', "
            f"api_version='{self.api_version}', "
            f"initialized={self.session is not None}, "
            f"specialized_clients=['products', 'collections', 'inventory'])"
        )