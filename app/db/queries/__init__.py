"""
Enhanced modular GraphQL queries for Shopify API.

This module provides a more granular organization of GraphQL queries by domain and operation type,
improving maintainability, discoverability, and code organization.

Structure:
- core/: Common queries used across domains
- products/: Product-related operations split by function
- collections/: Collection-related operations
- inventory/: Inventory management operations
- orders/: Order processing operations
- customers/: Customer management operations
- metafields/: Metafield operations
- taxonomy/: Product taxonomy operations
- webhooks/: Webhook management
- bulk/: Bulk operations
"""

# Import all organized queries
from .bulk import *
from .collections import *
from .core import *
from .customers import *
from .inventory import *
from .metafields import *
from .orders import *
from .products import *
from .taxonomy import *
from .webhooks import *

# Organized exports by domain
__all__ = [
    # Core queries
    "SHOP_INFO_QUERY",
    "LOCATIONS_QUERY",
    "LOCATIONS_SIMPLE_QUERY",
    "APP_INSTALLATION_QUERY",
    "API_VERSION_QUERY",
    # Product queries
    "PRODUCT_QUERY",
    "PRODUCTS_QUERY",
    "PRODUCT_BY_SKU_QUERY",
    "PRODUCT_BY_HANDLE_QUERY",
    "PRODUCT_SEARCH_QUERY",
    # Product mutations
    "CREATE_PRODUCT_MUTATION",
    "UPDATE_PRODUCT_MUTATION",
    "DELETE_PRODUCT_MUTATION",
    "PUBLISH_PRODUCT_MUTATION",
    "UNPUBLISH_PRODUCT_MUTATION",
    "CREATE_PRODUCT_WITH_CATEGORY_MUTATION",
    "UPDATE_PRODUCT_WITH_CATEGORY_MUTATION",
    # Variant operations
    "CREATE_VARIANT_MUTATION",
    "UPDATE_VARIANT_MUTATION",
    "CREATE_VARIANTS_BULK_MUTATION",
    "UPDATE_VARIANTS_BULK_MUTATION",
    "DELETE_VARIANT_MUTATION",
    # Collection queries
    "COLLECTIONS_QUERY",
    "COLLECTIONS_SIMPLE_QUERY",
    "COLLECTION_BY_ID_QUERY",
    "COLLECTION_BY_HANDLE_QUERY",
    "SMART_COLLECTIONS_QUERY",
    "COLLECTION_WITH_ANALYTICS_QUERY",
    "COLLECTIONS_WITH_INVENTORY_QUERY",
    # Collection mutations
    "CREATE_COLLECTION_MUTATION",
    "UPDATE_COLLECTION_MUTATION",
    "DELETE_COLLECTION_MUTATION",
    "COLLECTION_ADD_PRODUCTS_MUTATION",
    "COLLECTION_REMOVE_PRODUCTS_MUTATION",
    "COLLECTION_REORDER_PRODUCTS_MUTATION",
    "CREATE_SMART_COLLECTION_MUTATION",
    "UPDATE_SMART_COLLECTION_MUTATION",
    # Inventory operations
    "INVENTORY_LEVELS_QUERY",
    "INVENTORY_LEVELS_SIMPLE_QUERY",
    "INVENTORY_LEVEL_BY_ITEM_QUERY",
    "INVENTORY_ITEMS_QUERY",
    "INVENTORY_ITEM_QUERY",
    "INVENTORY_SET_MUTATION",
    "INVENTORY_ADJUST_MUTATION",
    "INVENTORY_ACTIVATE_MUTATION",
    "INVENTORY_DEACTIVATE_MUTATION",
    "INVENTORY_ADJUST_QUANTITIES_MUTATION",
    "INVENTORY_ITEM_UPDATE_MUTATION",
    "INVENTORY_BULK_SET_MUTATION",
    "INVENTORY_BULK_ADJUST_MUTATION",
    "LOW_STOCK_INVENTORY_QUERY",
    "OUT_OF_STOCK_INVENTORY_QUERY",
    "INVENTORY_SUMMARY_BY_LOCATION_QUERY",
    "INVENTORY_VALUE_QUERY",
    # Order operations
    "ORDERS_QUERY",
    "ORDER_BY_ID_QUERY",
    "DRAFT_ORDERS_QUERY",
    "DRAFT_ORDER_QUERY",
    "ORDERS_BY_CUSTOMER_QUERY",
    "CREATE_ORDER_MUTATION",
    "UPDATE_ORDER_MUTATION",
    "CANCEL_ORDER_MUTATION",
    "CREATE_FULFILLMENT_MUTATION",
    "UPDATE_FULFILLMENT_MUTATION",
    "CANCEL_FULFILLMENT_MUTATION",
    "CREATE_DRAFT_ORDER_MUTATION",
    "UPDATE_DRAFT_ORDER_MUTATION",
    "COMPLETE_DRAFT_ORDER_MUTATION",
    "DELETE_DRAFT_ORDER_MUTATION",
    # Customer operations
    "CUSTOMERS_QUERY",
    "CUSTOMER_BY_ID_QUERY",
    "CREATE_CUSTOMER_MUTATION",
    "UPDATE_CUSTOMER_MUTATION",
    # Metafield operations
    "METAFIELDS_QUERY",
    "METAFIELD_DEFINITIONS_QUERY",
    "CREATE_METAFIELD_MUTATION",
    "UPDATE_METAFIELD_MUTATION",
    "METAFIELDS_SET_MUTATION",
    "CREATE_METAFIELD_DEFINITION_MUTATION",
    # Taxonomy operations
    "TAXONOMY_CATEGORIES_QUERY",
    "TAXONOMY_CATEGORY_DETAILS_QUERY",
    "TAXONOMY_BROWSE_QUERY",
    # Webhook operations
    "WEBHOOK_SUBSCRIPTIONS_QUERY",
    "CREATE_WEBHOOK_SUBSCRIPTION",
    "UPDATE_WEBHOOK_SUBSCRIPTION",
    "DELETE_WEBHOOK_SUBSCRIPTION",
    "GET_WEBHOOK_SUBSCRIPTION",
    "GET_WEBHOOK_SUBSCRIPTIONS",
    # Bulk operations
    "BULK_OPERATION_STATUS_QUERY",
    "CURRENT_BULK_OPERATION_QUERY",
    "BULK_OPERATION_PRODUCTS_QUERY",
    "CREATE_BULK_OPERATION_MUTATION",
    "CANCEL_BULK_OPERATION_MUTATION",
]

