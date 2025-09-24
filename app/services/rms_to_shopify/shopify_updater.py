import asyncio
import logging
from typing import Any, Dict, List, Optional

from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.multiple_variants_creator import MultipleVariantsCreator
from app.utils.error_handler import SyncException

logger = logging.getLogger(__name__)


class ShopifyUpdater:
    """Updates data in Shopify."""

    def __init__(self, shopify_client: ShopifyGraphQLClient, primary_location_id: str):
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id
        self.batch_handle_cache: Dict[str, Optional[Dict[str, Any]]] = {}

    async def check_products_exist_batch(self, handles: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Checks if products exist in Shopify by their handles using an optimized batch search.

        Args:
            handles: A list of product handles to check.

        Returns:
            A dictionary mapping handles to existing products (or None if they don't exist).
        """
        if not handles:
            return {}

        MAX_HANDLES_PER_QUERY = 50

        cached_results = {}
        uncached_handles = []

        for handle in handles:
            if handle in self.batch_handle_cache:
                cached_results[handle] = self.batch_handle_cache[handle]
            else:
                uncached_handles.append(handle)

        results = cached_results.copy()

        if uncached_handles:
            try:
                for i in range(0, len(uncached_handles), MAX_HANDLES_PER_QUERY):
                    chunk_handles = uncached_handles[i:i + MAX_HANDLES_PER_QUERY]

                    logger.debug(
                        f"🔍 Checking {len(chunk_handles)} products in Shopify "
                        f"(chunk {i//MAX_HANDLES_PER_QUERY + 1})"
                    )

                    batch_results = await self.shopify_client.get_products_by_handles_batch(chunk_handles)

                    for handle, product in batch_results.items():
                        self.batch_handle_cache[handle] = product
                        results[handle] = product

                    if i + MAX_HANDLES_PER_QUERY < len(uncached_handles):
                        await asyncio.sleep(0.5)

                found_count = sum(1 for p in results.values() if p is not None)
                cache_hits = len(cached_results)
                logger.debug(
                    f"🔍 Batch check completed: {found_count}/{len(handles)} products found "
                    f"({cache_hits} from cache, {len(uncached_handles)} queried)"
                )

            except Exception as e:
                logger.error(f"Error in batch product check: {e}")
                for handle in uncached_handles:
                    results[handle] = None

        return results

    async def create_shopify_product(self, shopify_input: ShopifyProductInput) -> Dict[str, Any]:
        """
        Creates a product in Shopify.

        Args:
            shopify_input: The validated product input with variants.

        Returns:
            The created product with all variants.
        """
        try:
            variants_creator = MultipleVariantsCreator(self.shopify_client, self.primary_location_id)
            created_product = await variants_creator.create_product_with_variants(shopify_input)

            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"

            logger.info(f"🎉 Successfully created product with multiple variants: {sku}")
            return created_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to create product in Shopify: {str(e)}",
                service="shopify",
                operation="create_product",
                failed_records=[shopify_input.model_dump()],
            ) from e

    async def update_shopify_product(
        self, shopify_input: ShopifyProductInput, shopify_product: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Updates a product in Shopify.

        Args:
            shopify_input: The updated product data.
            shopify_product: The existing product.

        Returns:
            The updated product.
        """
        try:
            variants_creator = MultipleVariantsCreator(self.shopify_client, self.primary_location_id)

            product_id = shopify_product.get("id")
            if not product_id:
                raise ValueError("Product ID not found in existing product")

            updated_product = await variants_creator.update_product_with_variants(
                product_id, shopify_input, shopify_product
            )

            sku = shopify_input.variants[0].sku if shopify_input.variants else "unknown"
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"✅ Updated product with multiple variants in Shopify: {sku}")
            return updated_product

        except Exception as e:
            raise SyncException(
                message=f"Failed to update product in Shopify: {str(e)}",
                service="shopify",
                operation="update_product",
                failed_records=[shopify_input.model_dump()],
            ) from e