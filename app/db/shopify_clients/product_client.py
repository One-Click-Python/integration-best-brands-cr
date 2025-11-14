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

    async def get_products_by_handles_batch(self, handles: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Find multiple products by their handles in a single query.

        Args:
            handles: List of product handles to search for

        Returns:
            Dict mapping handle to product data (or None if not found)
        """
        if not handles:
            return {}

        try:
            # Build search query with multiple handles
            # Shopify search syntax: handle:handle1 OR handle:handle2 OR ...
            handle_queries = [f"handle:{handle}" for handle in handles]
            search_query = " OR ".join(handle_queries)

            # Import the new query
            from app.db.queries.products import PRODUCTS_BY_HANDLES_BATCH_QUERY

            variables = {"handles": search_query}
            result = await self._execute_query(PRODUCTS_BY_HANDLES_BATCH_QUERY, variables)

            # Build result dictionary with correct typing
            products_by_handle: Dict[str, Optional[Dict[str, Any]]] = {handle: None for handle in handles}

            edges = result.get("products", {}).get("edges", [])
            for edge in edges:
                product = edge["node"]
                product_handle = product.get("handle")
                if product_handle in products_by_handle:
                    products_by_handle[product_handle] = product

            # Log results
            found_count = sum(1 for p in products_by_handle.values() if p is not None)
            logger.info(f"Batch search: Found {found_count}/{len(handles)} products by handle")

            return products_by_handle

        except Exception as e:
            logger.error(f"Error in batch product search: {e}")
            raise ShopifyAPIException(f"Failed to search products in batch: {str(e)}") from e

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
            # Log what we're trying to create for debugging
            logger.info(f"📦 Attempting to create {len(variants_data)} variants for product {product_id}")
            for i, variant_data in enumerate(variants_data[:3]):  # Log first 3 for debugging
                logger.debug(f"   Variant {i + 1}: {variant_data}")
            if len(variants_data) > 3:
                logger.debug(f"   ... and {len(variants_data) - 3} more variants")

            variables = {"productId": product_id, "variants": variants_data}
            result = await self._execute_query(CREATE_VARIANTS_BULK_MUTATION, variables)

            bulk_result = result.get("productVariantsBulkCreate", {})

            # Check for user errors before calling generic error handler
            user_errors = bulk_result.get("userErrors", [])
            if user_errors:
                # Handle duplicate variant errors specifically
                duplicate_errors = []
                other_errors = []

                for error in user_errors:
                    error_msg = error.get("message", "")
                    if "already exists" in error_msg.lower():
                        duplicate_errors.append(error_msg)
                        logger.warning(f"⚠️ Duplicate variant detected: {error_msg}")
                    else:
                        other_errors.append(f"{error.get('field', 'unknown')}: {error_msg}")

                # If ALL errors are duplicate errors, log as warning but don't fail
                if duplicate_errors and not other_errors:
                    logger.warning(f"⚠️ All {len(duplicate_errors)} variants already exist, skipping creation")
                    # Return a result indicating no new variants were created
                    return {
                        "productVariants": [],
                        "userErrors": user_errors,
                        "duplicatesSkipped": len(duplicate_errors),
                    }

                # If there are other errors besides duplicates, raise exception
                if other_errors:
                    raise ShopifyAPIException(f"Bulk variant creation failed: {', '.join(other_errors)}")

            # If no errors, handle normally
            self._handle_graphql_errors(bulk_result, "Bulk variant creation")

            variants = bulk_result.get("productVariants")
            if variants:
                logger.info(f"✅ Created {len(variants)} variants for product {product_id}")
                for variant in variants:
                    options_str = " / ".join([opt["value"] for opt in variant.get("selectedOptions", [])])
                    logger.info(f"   ✅ Variant: {variant['sku']} - {options_str} - ${variant['price']}")
            else:
                logger.info("ℹ️ No new variants created (they may already exist)")

            return bulk_result

        except ShopifyAPIException:
            # Re-raise ShopifyAPIException as-is
            raise
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

    async def get_draft_products(
        self, limit: int = 250, cursor: Optional[str] = None, ccod_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch DRAFT products with optional CCOD filtering.

        Args:
            limit: Number of products to fetch (max 250)
            cursor: Pagination cursor
            ccod_filter: Optional CCOD to filter by (e.g., "24RX04")

        Returns:
            Dict containing products and pagination info
        """
        try:
            from app.db.queries.products import DRAFT_PRODUCTS_QUERY

            # Build query string
            query_parts = ["status:DRAFT"]
            if ccod_filter:
                # Search by tag or handle containing CCOD
                query_parts.append(f"(tag:ccod_{ccod_filter} OR handle:*{ccod_filter}*)")

            query_string = " AND ".join(query_parts)

            variables = {"first": min(limit, 250), "query": query_string}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(DRAFT_PRODUCTS_QUERY, variables)
            products_data = result.get("products", {})

            products_count = len(products_data.get("edges", []))
            logger.info(f"Fetched {products_count} DRAFT products (CCOD filter: {ccod_filter or 'None'})")

            return products_data

        except Exception as e:
            logger.error(f"Error fetching DRAFT products: {e}")
            raise ShopifyAPIException(f"Failed to fetch DRAFT products: {str(e)}") from e

    async def update_product_tags(self, product_id: str, tags: List[str]) -> Dict[str, Any]:
        """
        Update product tags (replaces all existing tags).

        Args:
            product_id: Product ID to update
            tags: New list of tags (replaces existing)

        Returns:
            Updated product data
        """
        try:
            from app.db.queries.products import UPDATE_PRODUCT_TAGS_MUTATION

            variables = {"id": product_id, "tags": tags}

            result = await self._execute_query(UPDATE_PRODUCT_TAGS_MUTATION, variables)

            product_result = result.get("productUpdate", {})
            self._handle_graphql_errors(product_result, "Product tag update")

            product = product_result.get("product")
            if product:
                logger.info(
                    f"✅ Tags updated for product: {product.get('title', 'Unknown')} "
                    f"(ID: {product_id}) - New tags: {tags}"
                )
                return product

            raise ShopifyAPIException("Product tag update failed: No product returned")

        except Exception as e:
            logger.error(f"Error updating tags for product {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to update product tags: {str(e)}") from e

    async def get_all_draft_products(self, ccod_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all DRAFT products using pagination.

        Args:
            ccod_filter: Optional CCOD to filter by

        Returns:
            List of all DRAFT products
        """
        try:
            all_products = []
            cursor = None
            page_count = 0

            while True:
                page_count += 1
                logger.info(
                    f"Fetching page {page_count} of DRAFT products "
                    f"(CCOD: {ccod_filter or 'All'}, cursor: {cursor[:50] if cursor else 'None'}...)"
                )

                result = await self.get_draft_products(limit=250, cursor=cursor, ccod_filter=ccod_filter)
                edges = result.get("edges", [])
                products = [edge["node"] for edge in edges]

                logger.info(f"Page {page_count}: Retrieved {len(products)} DRAFT products")

                if products:
                    all_products.extend(products)

                # Check if there are more pages
                page_info = result.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

            logger.info(f"✅ Fetched all DRAFT products: {len(all_products)} total")
            return all_products

        except Exception as e:
            logger.error(f"Error fetching all DRAFT products: {e}")
            raise ShopifyAPIException(f"Failed to fetch all DRAFT products: {str(e)}") from e

    async def get_active_products(
        self, limit: int = 250, cursor: Optional[str] = None, ccod_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fetch ACTIVE products with optional CCOD filtering.

        Args:
            limit: Number of products to fetch (max 250)
            cursor: Pagination cursor
            ccod_filter: Optional CCOD to filter by (e.g., "24RX04")

        Returns:
            Dict containing products and pagination info
        """
        try:
            from app.db.queries.products import DRAFT_PRODUCTS_QUERY  # Reuse same query structure

            # Build query string
            query_parts = ["status:ACTIVE"]
            if ccod_filter:
                # Search by tag or handle containing CCOD
                query_parts.append(f"(tag:ccod_{ccod_filter} OR handle:*{ccod_filter}*)")

            query_string = " AND ".join(query_parts)

            variables = {"first": min(limit, 250), "query": query_string}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(DRAFT_PRODUCTS_QUERY, variables)
            products_data = result.get("products", {})

            products_count = len(products_data.get("edges", []))
            logger.info(f"Fetched {products_count} ACTIVE products (CCOD filter: {ccod_filter or 'None'})")

            return products_data

        except Exception as e:
            logger.error(f"Error fetching ACTIVE products: {e}")
            raise ShopifyAPIException(f"Failed to fetch ACTIVE products: {str(e)}") from e

    async def get_all_active_products(self, ccod_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Fetch all ACTIVE products using pagination.

        Args:
            ccod_filter: Optional CCOD to filter by

        Returns:
            List of all ACTIVE products
        """
        try:
            all_products = []
            cursor = None
            page_count = 0

            while True:
                page_count += 1
                logger.info(
                    f"Fetching page {page_count} of ACTIVE products "
                    f"(CCOD: {ccod_filter or 'All'}, cursor: {cursor[:50] if cursor else 'None'}...)"
                )

                result = await self.get_active_products(limit=250, cursor=cursor, ccod_filter=ccod_filter)
                edges = result.get("edges", [])
                products = [edge["node"] for edge in edges]

                logger.info(f"Page {page_count}: Retrieved {len(products)} ACTIVE products")

                if products:
                    all_products.extend(products)

                # Check if there are more pages
                page_info = result.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

            logger.info(f"✅ Fetched all ACTIVE products: {len(all_products)} total")
            return all_products

        except Exception as e:
            logger.error(f"Error fetching all ACTIVE products: {e}")
            raise ShopifyAPIException(f"Failed to fetch all ACTIVE products: {str(e)}") from e

    async def delete_variant(self, product_id: str, variant_id: str) -> Dict[str, Any]:
        """
        Delete a product variant using bulk delete mutation (API 2025-04 compatible).

        Args:
            product_id: Product ID (gid://shopify/Product/...)
            variant_id: Variant ID to delete (gid://shopify/ProductVariant/...)

        Returns:
            Deletion result with product info after deletion
        """
        try:
            from app.db.queries.reverse_sync import DELETE_VARIANTS_BULK_MUTATION

            variables = {"productId": product_id, "variantsIds": [variant_id]}

            result = await self._execute_query(DELETE_VARIANTS_BULK_MUTATION, variables)

            delete_result = result.get("productVariantsBulkDelete", {})
            self._handle_graphql_errors(delete_result, "Variant deletion")

            product = delete_result.get("product")
            if product:
                logger.info(f"✅ Variant deleted from product: {product.get('id')}")
                return {
                    "success": True,
                    "product": product,
                }

            raise ShopifyAPIException("Variant deletion failed: No product returned")

        except Exception as e:
            logger.error(f"Error deleting variant {variant_id}: {e}")
            raise ShopifyAPIException(f"Failed to delete variant: {str(e)}") from e

    async def get_products_without_tag(
        self, tag: str, limit: int = 250, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get products that DON'T have a specific tag.

        Args:
            tag: Tag to exclude (e.g., "RMS-SYNC-25-01-23")
            limit: Number of products to fetch (max 250)
            cursor: Pagination cursor

        Returns:
            Dict containing products and pagination info
        """
        try:
            from app.db.queries.reverse_sync import PRODUCTS_WITHOUT_TAG_QUERY

            query_string = f"status:ACTIVE AND NOT tag:{tag}"
            variables = {"query": query_string, "first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(PRODUCTS_WITHOUT_TAG_QUERY, variables)
            products_data = result.get("products", {})

            products_count = len(products_data.get("edges", []))
            logger.info(f"Fetched {products_count} products without tag '{tag}'")

            return products_data

        except Exception as e:
            logger.error(f"Error fetching products without tag '{tag}': {e}")
            raise ShopifyAPIException(f"Failed to fetch products without tag: {str(e)}") from e

    async def get_product_with_inventory(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get product with full inventory information.

        Args:
            product_id: Product ID (gid://shopify/Product/...)

        Returns:
            Product dict with variants and inventory data, or None if not found
        """
        try:
            from app.db.queries.reverse_sync import PRODUCT_WITH_INVENTORY_QUERY

            variables = {"id": product_id}
            result = await self._execute_query(PRODUCT_WITH_INVENTORY_QUERY, variables)

            product = result.get("product")
            if product:
                logger.info(f"Found product with inventory: {product.get('title', 'Unknown')}")
                return product

            logger.info(f"No product found with ID: {product_id}")
            return None

        except Exception as e:
            logger.error(f"Error fetching product with inventory {product_id}: {e}")
            raise ShopifyAPIException(f"Failed to fetch product with inventory: {str(e)}") from e
