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
from .bulk import *  # noqa: F403
from .collections import *  # noqa: F403
from .core import *  # noqa: F403
from .customers import *  # noqa: F403
from .inventory import *  # noqa: F403
from .metafields import *  # noqa: F403
from .orders import *  # noqa: F403
from .products import *  # noqa: F403
from .taxonomy import *  # noqa: F403
from .webhooks import *  # noqa: F403

# Organized exports by domain
__all__ = [
    # Core queries
    "SHOP_INFO_QUERY",  # noqa: F405
    "LOCATIONS_QUERY",  # noqa: F405
    "APP_INSTALLATION_QUERY",  # noqa: F405
    "API_VERSION_QUERY",  # noqa: F405
    # Product queries
    "PRODUCT_QUERY",  # noqa: F405
    "PRODUCTS_QUERY",  # noqa: F405
    "PRODUCT_BY_SKU_QUERY",  # noqa: F405
    "PRODUCT_BY_HANDLE_QUERY",  # noqa: F405
    # Product mutations
    "CREATE_PRODUCT_MUTATION",  # noqa: F405
    "UPDATE_PRODUCT_MUTATION",  # noqa: F405
    "CREATE_PRODUCT_WITH_CATEGORY_MUTATION",  # noqa: F405
    "UPDATE_PRODUCT_WITH_CATEGORY_MUTATION",  # noqa: F405
    # Variant operations
    "CREATE_VARIANT_MUTATION",  # noqa: F405
    "CREATE_VARIANTS_BULK_MUTATION",  # noqa: F405
    "UPDATE_VARIANTS_BULK_MUTATION",  # noqa: F405
    "DELETE_VARIANTS_BULK_MUTATION",  # noqa: F405
    # Tag cleanup operations
    "DRAFT_PRODUCTS_QUERY",  # noqa: F405
    "UPDATE_PRODUCT_TAGS_MUTATION",  # noqa: F405
    # Collection queries
    "COLLECTIONS_QUERY",  # noqa: F405
    "COLLECTIONS_SIMPLE_QUERY",  # noqa: F405
    "COLLECTION_BY_ID_QUERY",  # noqa: F405
    "COLLECTION_BY_HANDLE_QUERY",  # noqa: F405
    "SMART_COLLECTIONS_QUERY",  # noqa: F405
    "COLLECTION_WITH_ANALYTICS_QUERY",  # noqa: F405
    "COLLECTIONS_WITH_INVENTORY_QUERY",  # noqa: F405
    # Collection mutations
    "CREATE_COLLECTION_MUTATION",  # noqa: F405
    "UPDATE_COLLECTION_MUTATION",  # noqa: F405
    "DELETE_COLLECTION_MUTATION",  # noqa: F405
    "COLLECTION_ADD_PRODUCTS_MUTATION",  # noqa: F405
    "COLLECTION_REMOVE_PRODUCTS_MUTATION",  # noqa: F405
    "COLLECTION_REORDER_PRODUCTS_MUTATION",  # noqa: F405
    "CREATE_SMART_COLLECTION_MUTATION",  # noqa: F405
    "UPDATE_SMART_COLLECTION_MUTATION",  # noqa: F405
    # Inventory operations
    "INVENTORY_LEVELS_QUERY",  # noqa: F405
    "INVENTORY_LEVELS_SIMPLE_QUERY",  # noqa: F405
    "INVENTORY_LEVEL_BY_ITEM_QUERY",  # noqa: F405
    "INVENTORY_ITEMS_QUERY",  # noqa: F405
    "INVENTORY_ITEM_QUERY",  # noqa: F405
    "INVENTORY_SET_MUTATION",  # noqa: F405
    "INVENTORY_ADJUST_MUTATION",  # noqa: F405
    "INVENTORY_ACTIVATE_MUTATION",  # noqa: F405
    "INVENTORY_DEACTIVATE_MUTATION",  # noqa: F405
    "INVENTORY_ADJUST_QUANTITIES_MUTATION",  # noqa: F405
    "INVENTORY_ITEM_UPDATE_MUTATION",  # noqa: F405
    "INVENTORY_BULK_SET_MUTATION",  # noqa: F405
    "INVENTORY_BULK_ADJUST_MUTATION",  # noqa: F405
    "INVENTORY_SET_QUANTITIES_MUTATION",  # noqa: F405
    "LOW_STOCK_INVENTORY_QUERY",  # noqa: F405
    "OUT_OF_STOCK_INVENTORY_QUERY",  # noqa: F405
    "INVENTORY_SUMMARY_BY_LOCATION_QUERY",  # noqa: F405
    "INVENTORY_VALUE_QUERY",  # noqa: F405
    # Order operations
    "ORDERS_QUERY",  # noqa: F405
    "ORDER_BY_ID_QUERY",  # noqa: F405
    "DRAFT_ORDERS_QUERY",  # noqa: F405
    "DRAFT_ORDER_QUERY",  # noqa: F405
    "ORDERS_BY_CUSTOMER_QUERY",  # noqa: F405
    "CREATE_ORDER_MUTATION",  # noqa: F405
    "UPDATE_ORDER_MUTATION",  # noqa: F405
    "CANCEL_ORDER_MUTATION",  # noqa: F405
    "CREATE_FULFILLMENT_MUTATION",  # noqa: F405
    "UPDATE_FULFILLMENT_MUTATION",  # noqa: F405
    "CANCEL_FULFILLMENT_MUTATION",  # noqa: F405
    "CREATE_DRAFT_ORDER_MUTATION",  # noqa: F405
    "UPDATE_DRAFT_ORDER_MUTATION",  # noqa: F405
    "COMPLETE_DRAFT_ORDER_MUTATION",  # noqa: F405
    "DELETE_DRAFT_ORDER_MUTATION",  # noqa: F405
    # Customer operations
    "CUSTOMERS_QUERY",  # noqa: F405
    "CUSTOMER_BY_ID_QUERY",  # noqa: F405
    "CREATE_CUSTOMER_MUTATION",  # noqa: F405
    "UPDATE_CUSTOMER_MUTATION",  # noqa: F405
    # Metafield operations
    "METAFIELDS_QUERY",  # noqa: F405
    "METAFIELD_DEFINITIONS_QUERY",  # noqa: F405
    "CREATE_METAFIELD_MUTATION",  # noqa: F405
    "UPDATE_METAFIELD_MUTATION",  # noqa: F405
    "METAFIELDS_SET_MUTATION",  # noqa: F405
    "CREATE_METAFIELD_DEFINITION_MUTATION",  # noqa: F405
    # Taxonomy operations
    "TAXONOMY_CATEGORIES_QUERY",  # noqa: F405
    "TAXONOMY_CATEGORY_DETAILS_QUERY",  # noqa: F405
    "TAXONOMY_BROWSE_QUERY",  # noqa: F405
    # Webhook operations
    "WEBHOOK_SUBSCRIPTIONS_QUERY",  # noqa: F405
    "CREATE_WEBHOOK_SUBSCRIPTION",  # noqa: F405
    "UPDATE_WEBHOOK_SUBSCRIPTION",  # noqa: F405
    "DELETE_WEBHOOK_SUBSCRIPTION",  # noqa: F405
    "GET_WEBHOOK_SUBSCRIPTION",  # noqa: F405
    "GET_WEBHOOK_SUBSCRIPTIONS",  # noqa: F405
    # Bulk operations
    "BULK_OPERATION_STATUS_QUERY",  # noqa: F405
    "CURRENT_BULK_OPERATION_QUERY",  # noqa: F405
    "BULK_OPERATION_PRODUCTS_QUERY",  # noqa: F405
    "CREATE_BULK_OPERATION_MUTATION",  # noqa: F405
    "CANCEL_BULK_OPERATION_MUTATION",  # noqa: F405
]
