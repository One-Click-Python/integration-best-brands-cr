"""
Shopify GraphQL clients organized by responsibility.

This module contains specialized GraphQL clients for different Shopify resources,
following the single responsibility principle.
"""

from .base_client import BaseShopifyGraphQLClient
from .product_client import ShopifyProductClient
from .collection_client import ShopifyCollectionClient
from .inventory_client import ShopifyInventoryClient
from .unified_client import ShopifyGraphQLClient

__all__ = [
    "BaseShopifyGraphQLClient",
    "ShopifyProductClient", 
    "ShopifyCollectionClient",
    "ShopifyInventoryClient",
    "ShopifyGraphQLClient"
]