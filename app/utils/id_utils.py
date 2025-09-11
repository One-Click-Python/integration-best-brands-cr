"""
ID format conversion utilities for Shopify GraphQL and REST API compatibility.

This module handles conversion between different ID formats used by Shopify:
- REST API IDs: numeric strings like "298548887612" 
- GraphQL IDs: global IDs like "gid://shopify/Collection/298548887612"
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def rest_to_graphql_id(rest_id: str, resource_type: str) -> str:
    """
    Convert a REST API ID to a GraphQL global ID.
    
    Args:
        rest_id: Numeric REST ID (e.g., "298548887612")
        resource_type: Resource type (e.g., "Collection", "Product", "ProductVariant")
    
    Returns:
        GraphQL global ID (e.g., "gid://shopify/Collection/298548887612")
    """
    if not rest_id or not resource_type:
        return ""
    
    # Remove any existing gid prefix if present
    clean_id = graphql_to_rest_id(rest_id)
    
    graphql_id = f"gid://shopify/{resource_type}/{clean_id}"
    logger.debug(f"Converted REST ID '{rest_id}' to GraphQL ID: {graphql_id}")
    return graphql_id


def graphql_to_rest_id(graphql_id: str) -> str:
    """
    Extract the numeric ID from a GraphQL global ID.
    
    Args:
        graphql_id: GraphQL global ID (e.g., "gid://shopify/Collection/298548887612")
    
    Returns:
        Numeric REST ID (e.g., "298548887612")
    """
    if not graphql_id:
        return ""
    
    # If it's already a numeric ID, return as-is
    if graphql_id.isdigit():
        return graphql_id
    
    # Extract numeric ID from GraphQL format
    match = re.match(r"gid://shopify/\w+/(\d+)", graphql_id)
    if match:
        rest_id = match.group(1)
        logger.debug(f"Extracted REST ID '{rest_id}' from GraphQL ID: {graphql_id}")
        return rest_id
    
    # If no match, assume it's already a REST ID or invalid
    logger.warning(f"Could not extract REST ID from: {graphql_id}")
    return graphql_id


def normalize_collection_id(collection_id: str) -> str:
    """
    Normalize a collection ID to GraphQL format.
    
    Args:
        collection_id: Collection ID in any format
    
    Returns:
        Collection ID in GraphQL format
    """
    if not collection_id:
        return ""
    
    # If already in GraphQL format, return as-is
    if collection_id.startswith("gid://shopify/Collection/"):
        return collection_id
    
    # Convert numeric ID to GraphQL format
    return rest_to_graphql_id(collection_id, "Collection")


def normalize_product_id(product_id: str) -> str:
    """
    Normalize a product ID to GraphQL format.
    
    Args:
        product_id: Product ID in any format
    
    Returns:
        Product ID in GraphQL format
    """
    if not product_id:
        return ""
    
    # If already in GraphQL format, return as-is
    if product_id.startswith("gid://shopify/Product/"):
        return product_id
    
    # Convert numeric ID to GraphQL format
    return rest_to_graphql_id(product_id, "Product")


def get_resource_type_from_gid(graphql_id: str) -> Optional[str]:
    """
    Extract the resource type from a GraphQL global ID.
    
    Args:
        graphql_id: GraphQL global ID (e.g., "gid://shopify/Collection/298548887612")
    
    Returns:
        Resource type (e.g., "Collection") or None if invalid
    """
    if not graphql_id or not graphql_id.startswith("gid://shopify/"):
        return None
    
    match = re.match(r"gid://shopify/(\w+)/\d+", graphql_id)
    return match.group(1) if match else None


def is_valid_graphql_id(graphql_id: str, expected_type: Optional[str] = None) -> bool:
    """
    Validate a GraphQL global ID format and optionally check resource type.
    
    Args:
        graphql_id: GraphQL global ID to validate
        expected_type: Expected resource type (optional)
    
    Returns:
        True if valid GraphQL ID (and matches expected type if provided)
    """
    if not graphql_id or not isinstance(graphql_id, str):
        return False
    
    # Check basic format
    if not re.match(r"gid://shopify/\w+/\d+", graphql_id):
        return False
    
    # Check specific resource type if provided
    if expected_type:
        actual_type = get_resource_type_from_gid(graphql_id)
        return actual_type == expected_type
    
    return True


def format_admin_url(resource_type: str, resource_id: str, shop_domain: str) -> str:
    """
    Generate a Shopify admin URL for a given resource.
    
    Args:
        resource_type: Resource type (e.g., "collections", "products")
        resource_id: Resource ID (GraphQL or REST format)
        shop_domain: Shop domain (e.g., "best-brands-cr")
    
    Returns:
        Admin URL (e.g., "https://admin.shopify.com/store/best-brands-cr/collections/298548887612")
    """
    # Extract numeric ID for admin URL
    rest_id = graphql_to_rest_id(resource_id)
    return f"https://admin.shopify.com/store/{shop_domain}/{resource_type}/{rest_id}"


# Convenience functions for common operations
def collection_gid(rest_id: str) -> str:
    """Convert collection REST ID to GraphQL ID."""
    return normalize_collection_id(rest_id)


def product_gid(rest_id: str) -> str:
    """Convert product REST ID to GraphQL ID."""
    return normalize_product_id(rest_id)


def collection_rest_id(graphql_id: str) -> str:
    """Extract collection REST ID from GraphQL ID."""
    return graphql_to_rest_id(graphql_id)


def product_rest_id(graphql_id: str) -> str:
    """Extract product REST ID from GraphQL ID."""
    return graphql_to_rest_id(graphql_id)