"""
GraphQL queries and mutations for Shopify API organized by responsibility.

This module consolidates all GraphQL operations used to interact with the Shopify API,
following the 2024-10 API version specifications and organized by functional areas.

Organized modules:
- taxonomy_queries: Standard Product Taxonomy operations
- product_queries: Product and variant operations  
- inventory_queries: Inventory management and locations
- order_queries: Orders and draft orders
- metafield_queries: Metafields and definitions
- bulk_queries: Bulk operations
- webhook_queries: Webhook subscriptions
"""

# Import all queries from individual modules
from .taxonomy_queries import *
from .product_queries import *  
from .inventory_queries import *
from .order_queries import *
from .metafield_queries import *
from .bulk_queries import *
from .webhook_queries import *

# List all available queries for explicit imports
__all__ = [
    # Taxonomy
    'TAXONOMY_CATEGORIES_QUERY',
    'TAXONOMY_CATEGORY_DETAILS_QUERY', 
    'TAXONOMY_BROWSE_QUERY',
    
    # Products
    'PRODUCT_QUERY',
    'PRODUCTS_QUERY',
    'PRODUCT_BY_SKU_QUERY',
    'PRODUCT_BY_HANDLE_QUERY',
    'CREATE_PRODUCT_MUTATION',
    'UPDATE_PRODUCT_MUTATION',
    'CREATE_VARIANT_MUTATION',
    'UPDATE_VARIANTS_BULK_MUTATION',
    'CREATE_VARIANTS_BULK_MUTATION',
    'CREATE_PRODUCT_WITH_CATEGORY_MUTATION',
    'UPDATE_PRODUCT_WITH_CATEGORY_MUTATION',
    
    # Inventory
    'INVENTORY_ACTIVATE_MUTATION',
    'INVENTORY_ITEM_UPDATE_MUTATION',
    'INVENTORY_ADJUST_MUTATION',
    'INVENTORY_SET_MUTATION',
    'INVENTORY_ADJUST_QUANTITIES_MUTATION',
    'LOCATIONS_QUERY',
    
    # Orders
    'ORDERS_QUERY',
    'DRAFT_ORDERS_QUERY',
    'DRAFT_ORDER_QUERY',
    
    # Metafields
    'CREATE_METAFIELD_MUTATION',
    'UPDATE_METAFIELD_MUTATION',
    'METAFIELDS_SET_MUTATION',
    'CREATE_METAFIELD_DEFINITION_MUTATION',
    'METAFIELD_DEFINITIONS_QUERY',
    
    # Bulk Operations
    'BULK_OPERATION_PRODUCTS_QUERY',
    'BULK_OPERATION_STATUS_QUERY',
    
    # Webhooks
    'CREATE_WEBHOOK_SUBSCRIPTION',
    'GET_WEBHOOK_SUBSCRIPTIONS',
    'GET_WEBHOOK_SUBSCRIPTION',
    'UPDATE_WEBHOOK_SUBSCRIPTION',
    'DELETE_WEBHOOK_SUBSCRIPTION',
]