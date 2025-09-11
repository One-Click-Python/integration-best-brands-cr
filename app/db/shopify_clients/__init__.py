"""
Shopify GraphQL clients organized by responsibility.

This module contains specialized GraphQL clients for different Shopify resources,
following the single responsibility principle.
"""

from .base_client import BaseShopifyGraphQLClient
from .collection_client import ShopifyCollectionClient
from .inventory_client import ShopifyInventoryClient
from .product_client import ShopifyProductClient
from .unified_client import ShopifyGraphQLClient

__all__ = [
    "BaseShopifyGraphQLClient",
    "ShopifyProductClient",
    "ShopifyCollectionClient",
    "ShopifyInventoryClient",
    "ShopifyGraphQLClient",
]

