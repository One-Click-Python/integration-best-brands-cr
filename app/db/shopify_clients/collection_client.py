"""
Shopify GraphQL client for collection operations.

This module handles all collection-related operations including CRUD operations,
product assignment to collections, and collection management.
"""

import logging
from typing import Any, Dict, List, Optional

from app.db.queries import (
    COLLECTION_ADD_PRODUCTS_MUTATION,
    COLLECTION_BY_HANDLE_QUERY,
    COLLECTION_BY_ID_QUERY,
    COLLECTION_REMOVE_PRODUCTS_MUTATION,
    COLLECTIONS_QUERY,
    CREATE_COLLECTION_MUTATION,
    DELETE_COLLECTION_MUTATION,
    UPDATE_COLLECTION_MUTATION,
)
from app.utils.error_handler import ShopifyAPIException

from .base_client import BaseShopifyGraphQLClient

logger = logging.getLogger(__name__)


class ShopifyCollectionClient(BaseShopifyGraphQLClient):
    """
    Specialized client for Shopify collection operations.

    Handles collections, collection management, and product-collection relationships.
    """

    async def get_collections(self, limit: int = 250, cursor: Optional[str] = None) -> Dict[str, Any]:
        """
        Fetch collections with pagination support.

        Args:
            limit: Number of collections to fetch (max 250)
            cursor: Pagination cursor

        Returns:
            Dict containing collections and pagination info
        """
        try:
            variables = {"first": min(limit, 250)}
            if cursor:
                variables["after"] = cursor

            result = await self._execute_query(COLLECTIONS_QUERY, variables)
            return result.get("collections", {})

        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            raise ShopifyAPIException(f"Failed to fetch collections: {str(e)}") from e

    async def get_collection_by_id(self, collection_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a collection by its ID.

        Args:
            collection_id: Collection ID to fetch

        Returns:
            Collection dict or None if not found
        """
        try:
            variables = {"id": collection_id}
            result = await self._execute_query(COLLECTION_BY_ID_QUERY, variables)

            collection = result.get("collection")
            if collection:
                logger.info(f"Found collection by ID '{collection_id}': {collection.get('title', 'Unknown')}")
                return collection

            logger.info(f"No collection found with ID: {collection_id}")
            return None

        except Exception as e:
            logger.error(f"Error fetching collection by ID '{collection_id}': {e}")
            raise ShopifyAPIException(f"Failed to fetch collection by ID: {str(e)}") from e

    async def get_collection_by_handle(self, handle: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a collection by its handle.

        Args:
            handle: Collection handle to fetch

        Returns:
            Collection dict or None if not found
        """
        try:
            variables = {"handle": handle}
            result = await self._execute_query(COLLECTION_BY_HANDLE_QUERY, variables)

            collection = result.get("collectionByHandle")
            if collection:
                logger.info(f"Found collection by handle '{handle}': {collection.get('title', 'Unknown')}")
                return collection

            logger.info(f"No collection found with handle: {handle}")
            return None

        except Exception as e:
            logger.error(f"Error fetching collection by handle '{handle}': {e}")
            raise ShopifyAPIException(f"Failed to fetch collection by handle: {str(e)}") from e

    async def get_all_collections(self) -> List[Dict[str, Any]]:
        """
        Fetch all collections using pagination.

        Returns:
            List of all collections
        """
        try:
            all_collections = []
            cursor = None
            page_count = 0

            while True:
                page_count += 1
                logger.info(
                    f"Fetching page {page_count} of collections (cursor: {cursor[:50] if cursor else 'None'}...)"
                )

                result = await self.get_collections(limit=250, cursor=cursor)
                collections = result.get("collections", [])

                logger.info(f"Page {page_count}: Retrieved {len(collections)} collections")

                if collections:
                    # Log some collection details for debugging
                    for i, collection in enumerate(collections[:3]):
                        products_count = (
                            collection.get("productsCount", {}).get("count", 0)
                            if isinstance(collection.get("productsCount"), dict)
                            else collection.get("productsCount", 0)
                        )
                        logger.info(
                            f"  Collection {i + 1}: {collection.get('title', 'No title')} "
                            f"(ID: {collection.get('id', 'No ID')}, "
                            f"Products: {products_count})"
                        )

                all_collections.extend(collections)

                # Check if there are more pages
                page_info = result.get("pageInfo", {})
                if not page_info.get("hasNextPage", False):
                    break

                cursor = page_info.get("endCursor")
                if not cursor:
                    break

            logger.info(f"✅ Fetched all collections: {len(all_collections)} total")
            return all_collections

        except Exception as e:
            logger.error(f"Error fetching all collections: {e}")
            raise ShopifyAPIException(f"Failed to fetch all collections: {str(e)}") from e

    async def create_collection(self, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new collection in Shopify.

        Args:
            collection_data: Collection data dictionary

        Returns:
            Created collection data
        """
        try:
            variables = {"input": collection_data}
            result = await self._execute_query(CREATE_COLLECTION_MUTATION, variables)

            collection_result = result.get("collectionCreate", {})
            self._handle_graphql_errors(collection_result, "Collection creation")

            collection = collection_result.get("collection")
            if collection:
                logger.info(
                    f"✅ Collection created: {collection.get('title', 'Unknown')} "
                    f"(ID: {collection.get('id')}, handle: {collection.get('handle')})"
                )
                return collection

            raise ShopifyAPIException("Collection creation failed: No collection returned")

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise ShopifyAPIException(f"Failed to create collection: {str(e)}") from e

    async def update_collection(self, collection_id: str, collection_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing collection.

        Args:
            collection_id: Collection ID to update
            collection_data: Updated collection data

        Returns:
            Updated collection data
        """
        try:
            # Add collection ID to the input data
            input_data = {"id": collection_id, **collection_data}
            variables = {"input": input_data}

            result = await self._execute_query(UPDATE_COLLECTION_MUTATION, variables)

            collection_result = result.get("collectionUpdate", {})
            self._handle_graphql_errors(collection_result, "Collection update")

            collection = collection_result.get("collection")
            if collection:
                logger.info(f"✅ Collection updated: {collection.get('title', 'Unknown')} (ID: {collection_id})")
                return collection

            raise ShopifyAPIException("Collection update failed: No collection returned")

        except Exception as e:
            logger.error(f"Error updating collection {collection_id}: {e}")
            raise ShopifyAPIException(f"Failed to update collection: {str(e)}") from e

    async def delete_collection(self, collection_id: str) -> bool:
        """
        Delete a collection.

        Args:
            collection_id: Collection ID to delete

        Returns:
            True if deletion was successful
        """
        try:
            variables = {"input": {"id": collection_id}}
            result = await self._execute_query(DELETE_COLLECTION_MUTATION, variables)

            delete_result = result.get("collectionDelete", {})
            self._handle_graphql_errors(delete_result, "Collection deletion")

            deleted_id = delete_result.get("deletedCollectionId")
            if deleted_id:
                logger.info(f"✅ Collection deleted: {deleted_id}")
                return True

            raise ShopifyAPIException("Collection deletion failed: No deletion confirmation")

        except Exception as e:
            logger.error(f"Error deleting collection {collection_id}: {e}")
            raise ShopifyAPIException(f"Failed to delete collection: {str(e)}") from e

    async def add_products_to_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """
        Add products to a collection.

        Args:
            collection_id: Collection ID
            product_ids: List of product IDs to add

        Returns:
            Updated collection data
        """
        try:
            variables = {"id": collection_id, "productIds": product_ids}
            result = await self._execute_query(COLLECTION_ADD_PRODUCTS_MUTATION, variables)

            add_result = result.get("collectionAddProducts", {})
            self._handle_graphql_errors(add_result, "Add products to collection")

            collection = add_result.get("collection")
            if collection:
                logger.info(
                    f"✅ Added {len(product_ids)} products to collection "
                    f"'{collection.get('title')}' (ID: {collection_id})"
                )
                return collection

            raise ShopifyAPIException("Failed to add products: No collection returned")

        except Exception as e:
            logger.error(f"Error adding products to collection {collection_id}: {e}")
            raise ShopifyAPIException(f"Failed to add products to collection: {str(e)}") from e

    async def remove_products_from_collection(self, collection_id: str, product_ids: List[str]) -> Dict[str, Any]:
        """
        Remove products from a collection.

        Args:
            collection_id: Collection ID
            product_ids: List of product IDs to remove

        Returns:
            Updated collection data
        """
        try:
            variables = {"id": collection_id, "productIds": product_ids}
            result = await self._execute_query(COLLECTION_REMOVE_PRODUCTS_MUTATION, variables)

            remove_result = result.get("collectionRemoveProducts", {})
            self._handle_graphql_errors(remove_result, "Remove products from collection")

            collection = remove_result.get("collection")
            if collection:
                logger.info(
                    f"✅ Removed {len(product_ids)} products from collection "
                    f"'{collection.get('title')}' (ID: {collection_id})"
                )
                return collection

            raise ShopifyAPIException("Failed to remove products: No collection returned")

        except Exception as e:
            logger.error(f"Error removing products from collection {collection_id}: {e}")
            raise ShopifyAPIException(f"Failed to remove products from collection: {str(e)}") from e

    async def sync_collection_products(
        self, collection_id: str, target_product_ids: List[str], current_product_ids: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """
        Synchronize products in a collection by adding missing and removing excess products.

        Args:
            collection_id: Collection ID to sync
            target_product_ids: List of product IDs that should be in the collection
            current_product_ids: Current product IDs in collection (if known)

        Returns:
            Dict with added and removed product IDs
        """
        try:
            # If current products not provided, fetch collection to get them
            if current_product_ids is None:
                collection = await self.get_collection_by_id(collection_id)
                if not collection:
                    raise ShopifyAPIException(f"Collection {collection_id} not found")

                # Extract current product IDs from collection
                current_product_ids = []
                products = collection.get("products", {}).get("edges", [])
                for edge in products:
                    product_id = edge.get("node", {}).get("id")
                    if product_id:
                        current_product_ids.append(product_id)

            # Calculate differences
            current_set = set(current_product_ids)
            target_set = set(target_product_ids)

            to_add = list(target_set - current_set)
            to_remove = list(current_set - target_set)

            result = {"added": [], "removed": []}

            # Add missing products
            if to_add:
                try:
                    await self.add_products_to_collection(collection_id, to_add)
                    result["added"] = to_add
                except Exception as e:
                    logger.warning(f"Failed to add products to collection: {e}")

            # Remove excess products
            if to_remove:
                try:
                    await self.remove_products_from_collection(collection_id, to_remove)
                    result["removed"] = to_remove
                except Exception as e:
                    logger.warning(f"Failed to remove products from collection: {e}")

            if to_add or to_remove:
                logger.info(f"✅ Collection {collection_id} synced: +{len(to_add)} -{len(to_remove)} products")
            else:
                logger.info(f"Collection {collection_id} already in sync")

            return result

        except Exception as e:
            logger.error(f"Error syncing collection products: {e}")
            raise ShopifyAPIException(f"Failed to sync collection products: {str(e)}") from e

