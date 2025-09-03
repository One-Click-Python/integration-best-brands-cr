"""
Shopify GraphQL client for product operations.

This module handles all product-related operations including CRUD operations,
product searching, variant management, and taxonomy integration.
"""

import logging
from typing import Any, Dict, List, Optional

from app.db.queries import (
    CREATE_PRODUCT_MUTATION,
    CREATE_VARIANT_MUTATION,
    CREATE_VARIANTS_BULK_MUTATION,
    PRODUCT_BY_HANDLE_QUERY,
    PRODUCT_BY_SKU_QUERY,
    PRODUCTS_QUERY,
    TAXONOMY_CATEGORIES_QUERY,
    UPDATE_PRODUCT_MUTATION,
    UPDATE_VARIANTS_BULK_MUTATION,
)
from app.utils.error_handler import ShopifyAPIException

from .base_client import BaseShopifyGraphQLClient

logger = logging.getLogger(__name__)


class ShopifyProductClient(BaseShopifyGraphQLClient):
    """
    Specialized client for Shopify product operations.

    Handles products, variants, and product-related functionality.
    """

    async def get_products(self, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch products with pagination support.

        Args:
            limit: Number of products to fetch (max 250)
            cursor: Pagination cursor

        Returns:
            Dict containing products and pagination info
        """
        try:
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(PRODUCTS_QUERY, variables)
            return result.get("products", {})

        except Exception as e:
            logger.error(f"Error fetching products: {e}")
            raise ShopifyAPIException(f"Failed to fetch products: {str(e)}") from e

    async def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Find a product by SKU.

        Args:
            sku: Product SKU to search for

        Returns:
            Product dict or None if not found
        """
        try:
            variables = {"sku": f"sku:{sku}"}
            result = await self._execute_query(PRODUCT_BY_SKU_QUERY, variables)

            products = result.get("products", {}).get("edges", [])
            if products:
                product = products[0]["node"]
                logger.info(f"Found product by SKU '{sku}': {product.get('title', 'Unknown')}")
                return product

            logger.info(f"No product found with SKU: {sku}")
            return None

        except Exception as e:
            logger.error(f"Error searching product by SKU '{sku}': {e}")
            raise ShopifyAPIException(f"Failed to search product by SKU: {str(e)}") from e

    async def get_product_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Find a product by handle.

        Args:
            handle: Product handle to search for

        Returns:
            Product dict or None if not found
        """
        try:
            variables = {"handle": f"handle:{handle}"}
            result = await self._execute_query(PRODUCT_BY_HANDLE_QUERY, variables)

            products = result.get("products", {}).get("edges", [])
            if products:
                product = products[0]["node"]
                logger.info(f"Found product by handle '{handle}': {product.get('title', 'Unknown')}")
                return product

            logger.info(f"No product found with handle: {handle}")
            return None

        except Exception as e:
            logger.error(f"Error searching product by handle '{handle}': {e}")
            raise ShopifyAPIException(f"Failed to search product by handle: {str(e)}") from e

    async def create_product(self, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new product in Shopify.

        Args:
            product_data: Product data dictionary

        Returns:
            Created product data
        """
        try:
            variables = {"input": product_data}
            result = await self._execute_query(CREATE_PRODUCT_MUTATION, variables)

            product_result = result.get("productCreate", {})
            self._handle_graphql_errors(product_result, "Product creation")

            product = product_result.get("product")
            if product:
                logger.info(f"✅ Product created: {product.get('title', 'Unknown')} (ID: {product.get('id')})")
                return product

            raise ShopifyAPIException("Product creation failed: No product returned")

        except Exception as e:
            logger.error(f"Error creating product: {e}")
            raise ShopifyAPIException(f"Failed to create product: {str(e)}") from e

    async def update_product(self, product_id: str, product_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing product.

        Args:
            product_id: Product ID to update
            product_data: Updated product data

        Returns:
            Updated product data
        """
        try:
            # Add product ID to the input data
            input_data = {"id": product_id, **product_data}
            variables = {"input": input_data}

            # Use the same mutation as create (GraphQL handles update based on ID presence)
            result = await self._execute_query(UPDATE_PRODUCT_MUTATION, variables)

            product_result = result.get("productUpdate", {})
            self._handle_graphql_errors(product_result, "Product update")

            product = product_result.get("product")
            if product:
                logger.info(f"✅ Product updated: {product.get('title', 'Unknown')} (ID: {product_id})")
                return product

            raise ShopifyAPIException("Product update failed: No product returned")

        except Exception as e:
            logger.error(f"Error updating product {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to update product: {str(e)}") from e

    async def create_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create multiple variants for a product in bulk.

        Args:
            product_id: Product ID to add variants to
            variants_data: List of variant data dictionaries

        Returns:
            Bulk operation result
        """
        try:
            variables = {"productId": product_id, "variants": variants_data}
            result = await self._execute_query(CREATE_VARIANTS_BULK_MUTATION, variables)

            bulk_result = result.get("productVariantsBulkCreate", {})
            self._handle_graphql_errors(bulk_result, "Bulk variant creation")

            variants = bulk_result.get("productVariants")
            if variants:
                logger.info(f"✅ Created {len(variants)} variants for product {product_id}")
                for variant in variants:
                    options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                    logger.info(f"   ✅ Variant: {variant['sku']} - {options_str} - ${variant['price']}")

            return bulk_result

        except Exception as e:
            logger.error(f"Error creating variants in bulk for product {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to create variants in bulk: {str(e)}") from e

    async def update_variants_bulk(self, product_id: str, variants_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Update multiple variants for a product in bulk.

        Args:
            product_id: Product ID
            variants_data: List of variant data with IDs for updates

        Returns:
            Bulk operation result
        """
        try:
            variables = {"productId": product_id, "variants": variants_data}

            result = await self._execute_query(UPDATE_VARIANTS_BULK_MUTATION, variables)

            variants_result = result.get("productVariantsBulkUpdate", {})
            self._handle_graphql_errors(variants_result, "Bulk variant update")

            product = variants_result.get("product")
            if product:
                variant_count = len(variants_data)
                logger.info(
                    f"✅ Updated {variant_count} variants for product "
                    f"{product.get('title', 'Unknown')} (ID: {product_id})"
                )
                return variants_result

            raise ShopifyAPIException("Bulk variant update failed: No product returned")

        except Exception as e:
            logger.error(f"Error updating variants in bulk for product {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to update variants in bulk: {str(e)}") from e

    async def create_variant(self, product_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a single variant for a product.

        Args:
            product_id: Product ID to add variant to
            variant_data: Variant data dictionary

        Returns:
            Created variant data
        """
        try:
            variables = {"input": {"productId": product_id, **variant_data}}

            result = await self._execute_query(CREATE_VARIANT_MUTATION, variables)

            variant_result = result.get("productVariantCreate", {})
            self._handle_graphql_errors(variant_result, "Variant creation")

            variant = variant_result.get("productVariant")
            if variant:
                logger.info(
                    f"✅ Variant created: {variant.get('title', 'Unknown')} "
                    f"(SKU: {variant.get('sku', 'N/A')}, ID: {variant.get('id')})"
                )
                return variant

            raise ShopifyAPIException("Variant creation failed: No variant returned")

        except Exception as e:
            logger.error(f"Error creating variant for product {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to create variant: {str(e)}") from e

    async def get_all_products(self) -> List[Dict[str, Any]]:
        """
        Fetch all products using pagination.

        Returns:
            List of all products
        """
        try:
            all_products = []
            cursor = None
            page_count = 0

            while True:
                page_count += 1
                logger.info(f"Fetching page {page_count} of products (cursor: {cursor[:50] if cursor else 'None'}...)")

                result = await self.get_products(limit=250, cursor=cursor)
                edges = result.get("edges", [])
                products = [edge["node"] for edge in edges]

                logger.info(f"Page {page_count}: Retrieved {len(products)} products")

                if products:
                    # Log some product details for debugging
                    for i, product in enumerate(products[:3]):
                        logger.info(
                            f"  Product {i + 1}: {product.get('title', 'No title')} "
                            f"(ID: {product.get('id', 'No ID')}, "
                            f"Handle: {product.get('handle', 'No handle')})"
                        )

                all_products.extend(products)

                # Check if there are more pages
                page_info = result.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

            logger.info(f"✅ Fetched all products: {len(all_products)} total")
            return all_products

        except Exception as e:
            logger.error(f"Error fetching all products: {e}")
            raise ShopifyAPIException(f"Failed to fetch all products: {str(e)}") from e

    async def search_taxonomy_categories(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Search for taxonomy categories by term.

        Args:
            search_term: Term to search for in category names

        Returns:
            List of matching categories
        """
        try:
            variables = {"search": search_term}
            result = await self._execute_query(TAXONOMY_CATEGORIES_QUERY, variables)

            categories = result.get("taxonomy", {}).get("categories", {}).get("edges", [])
            category_list = [edge["node"] for edge in categories]

            logger.info(f"Found {len(category_list)} taxonomy categories for '{search_term}'")
            return category_list

        except Exception as e:
            logger.error(f"Error searching taxonomy categories: {e}")
            raise ShopifyAPIException(f"Failed to search taxonomy categories: {str(e)}") from e

    async def find_best_taxonomy_match(self, search_terms: List[str]) -> Optional[Dict[str, Any]]:
        """
        Find the best taxonomy category match from a list of search terms.

        Args:
            search_terms: List of terms to search for, in order of preference

        Returns:
            Best matching category or None if no match found
        """
        try:
            for search_term in search_terms:
                logger.info(f"Searching taxonomy for: '{search_term}'")

                categories = await self.search_taxonomy_categories(search_term)

                if categories:
                    # Return the first (presumably best) match
                    best_match = categories[0]
                    logger.info(
                        f"✅ Found taxonomy match for '{search_term}': "
                        f"{best_match.get('name', 'Unknown')} (ID: {best_match.get('id')})"
                    )
                    return best_match
                else:
                    logger.info(f"No taxonomy match found for: '{search_term}'")

            logger.warning(f"No taxonomy match found for any of: {search_terms}")
            return None

        except Exception as e:
            logger.error(f"Error finding best taxonomy match: {e}")
            raise ShopifyAPIException(f"Failed to find taxonomy match: {str(e)}") from e
