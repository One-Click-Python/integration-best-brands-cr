"""
Shopify GraphQL client for inventory operations.

This module handles all inventory-related operations including inventory tracking,
quantity updates, and location management.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, Tuple

import aiohttp

from app.db.queries import (
    INVENTORY_ACTIVATE_MUTATION,
    INVENTORY_ADJUST_QUANTITIES_MUTATION,
    INVENTORY_ITEM_UPDATE_MUTATION,
    INVENTORY_SET_QUANTITIES_MUTATION,
)
from app.utils.error_handler import ShopifyAPIException

from .base_client import BaseShopifyGraphQLClient

logger = logging.getLogger(__name__)


class ShopifyInventoryClient(BaseShopifyGraphQLClient):
    """
    Specialized client for Shopify inventory operations.

    Handles inventory tracking, quantity management, and location-based inventory.
    """

    async def set_variant_inventory_quantity(
        self,
        variant_or_inventory_item_id,
        location_id: str,
        quantity: int,
        disconnect_if_necessary: bool = False,  # Parameter is used in the mutation logic
    ) -> Dict[str, Any]:
        """
        Set the inventory quantity for a variant at a specific location.

        Args:
            variant_or_inventory_item_id: Variant object with inventoryItem or inventory item ID string
            location_id: Location ID
            quantity: New quantity
            disconnect_if_necessary: Whether to disconnect if necessary

        Returns:
            Result dictionary with success status
        """
        try:
            # Handle both variant object and inventory item ID string
            if isinstance(variant_or_inventory_item_id, dict):
                # It's a variant object
                variant = variant_or_inventory_item_id
                inventory_item = variant.get("inventoryItem", {})
                if not inventory_item or not inventory_item.get("id"):
                    logger.warning(f"Variant {variant.get('id')} has no inventory item")
                    return {"success": False, "error": "No inventory item"}

                inventory_item_id = inventory_item["id"]
            else:
                # It's an inventory item ID string
                inventory_item_id = variant_or_inventory_item_id

            # Use INVENTORY_SET_QUANTITIES_MUTATION for exact quantity setting
            variables = {
                "input": {
                    "name": "available",
                    "reason": "correction",
                    "referenceDocumentUri": f"variant-creation-{inventory_item_id}",
                    "ignoreCompareQuantity": True,
                    "quantities": [
                        {"inventoryItemId": inventory_item_id, "locationId": location_id, "quantity": quantity}
                    ],
                }
            }

            result = await self._execute_query(INVENTORY_SET_QUANTITIES_MUTATION, variables)

            set_data = result.get("inventorySetQuantities", {})
            if set_errors := set_data.get("userErrors", []):
                logger.error(f"Failed to set inventory quantity: {set_errors}")
                return {"success": False, "errors": set_errors}

            adjustment_group = set_data.get("inventoryAdjustmentGroup", {})
            changes = adjustment_group.get("changes", [])

            if changes:
                available_change = next((c for c in changes if c.get("name") == "available"), changes[0])
                delta = available_change.get("delta", 0)
                logger.info(f"✅ Inventory set for item {inventory_item_id}: Δ{delta:+d} → {quantity}")
            else:
                logger.info(f"✅ Inventory quantity set to {quantity} for item {inventory_item_id}")

            return {
                "success": True,
                "inventory_item_id": inventory_item_id,
                "quantity": quantity,
            }

        except Exception as e:
            logger.error(f"Failed to set variant inventory quantity: {e}")
            return {"success": False, "error": str(e)}

    async def activate_inventory_tracking_well(
        self, inventory_item_id: str, location_id: str, available_quantity: int = None
    ) -> Dict[str, Any]:
        """
        Activate inventory tracking with quantity setting (backward compatible method).

        Args:
            inventory_item_id: Inventory item ID
            location_id: Location ID
            available_quantity: Quantity to set

        Returns:
            Result with success and inventory level data
        """
        try:
            # First activate inventory tracking
            tracking_result = await self.activate_inventory_tracking(
                inventory_item_id=inventory_item_id,
                location_id=location_id,
                track_quantity=True,
                continue_selling_when_out_of_stock=False,
            )

            # Set quantity if provided
            if available_quantity is not None and available_quantity > 0:
                # Use the INVENTORY_SET_QUANTITIES_MUTATION for setting exact quantities
                variables = {
                    "input": {
                        "name": "available",
                        "reason": "correction",
                        "referenceDocumentUri": f"inventory-setup-{inventory_item_id}",
                        "ignoreCompareQuantity": True,
                        "quantities": [
                            {
                                "inventoryItemId": inventory_item_id,
                                "locationId": location_id,
                                "quantity": available_quantity,
                            }
                        ],
                    }
                }

                set_result = await self._execute_query(INVENTORY_SET_QUANTITIES_MUTATION, variables)
                set_data = set_result.get("inventorySetQuantities", {})
                self._handle_graphql_errors(set_data, "Inventory quantity set")

                logger.info(f"✅ Set inventory quantity: {available_quantity} for item {inventory_item_id}")

            return {
                "success": True,
                "inventoryLevel": tracking_result,
                "tracked": True,
                "finalQuantity": available_quantity or 0,
            }

        except Exception as e:
            logger.error(f"Error in activate_inventory_tracking_well: {e}")
            return {"success": False, "error": str(e)}

    async def activate_inventory_tracking(
        self,
        inventory_item_id: str,
        location_id: str,
        track_quantity: bool = True,
        continue_selling_when_out_of_stock: bool = False,
    ) -> Dict[str, Any]:
        """
        Activate inventory tracking for a variant at a location.

        Args:
            inventory_item_id: Inventory item ID
            location_id: Location ID
            track_quantity: Whether to track quantity
            continue_selling_when_out_of_stock: Allow sales when out of stock

        Returns:
            Inventory level data
        """
        try:
            variables = {
                "inventoryItemId": inventory_item_id,
                "locationId": location_id,
                "tracked": track_quantity,
                "availableWhenSoldOut": continue_selling_when_out_of_stock,
            }

            result = await self._execute_query(INVENTORY_ACTIVATE_MUTATION, variables)

            activate_result = result.get("inventoryActivate", {})
            self._handle_graphql_errors(activate_result, "Inventory activation")

            inventory_level = activate_result.get("inventoryLevel")
            if inventory_level:
                logger.info(
                    f"✅ Activated inventory tracking for item {inventory_item_id} " f"at location {location_id}"
                )
                return inventory_level

            raise ShopifyAPIException("Inventory activation failed: No inventory level returned")

        except Exception as e:
            logger.error(f"Error activating inventory tracking: {e}")
            raise ShopifyAPIException(f"Failed to activate inventory tracking: {str(e)}") from e

    async def update_inventory(self, inventory_item_id: str, location_id: str, available_quantity: int) -> bool:
        """
        Update inventory quantity for a specific item at a location.

        Args:
            inventory_item_id: Inventory item ID
            location_id: Location ID
            available_quantity: New available quantity

        Returns:
            True if update was successful
        """
        try:
            # First activate inventory tracking if needed
            try:
                await self.activate_inventory_tracking(inventory_item_id, location_id)
            except Exception as e:
                # If activation fails, it might already be activated
                logger.debug(f"Inventory activation warning (may already be active): {e}")

            # Set the inventory quantity
            inventory_level = await self.set_variant_inventory_quantity(
                variant_or_inventory_item_id=inventory_item_id, location_id=location_id, quantity=available_quantity
            )

            if inventory_level:
                logger.info(f"✅ Updated inventory: {available_quantity} for item {inventory_item_id}")
                return True

            return False

        except Exception as e:
            logger.error(f"Error updating inventory: {e}")
            raise ShopifyAPIException(f"Failed to update inventory: {str(e)}") from e

    async def batch_update_inventory(self, inventory_updates: List[Dict[str, Any]]) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Update inventory in batch with error handling and rate limiting.

        Args:
            inventory_updates: List of inventory updates with structure:
                [{"inventory_item_id": "...", "location_id": "...", "available": 123}, ...]

        Returns:
            Tuple with (success_count, list_of_errors)
        """
        success_count = 0
        errors = []

        # Process in chunks to avoid overwhelming the API
        chunk_size = 10
        for i in range(0, len(inventory_updates), chunk_size):
            chunk = inventory_updates[i : i + chunk_size]

            # Process chunk concurrently
            tasks = []
            for update in chunk:
                task = self.update_inventory(update["inventory_item_id"], update["location_id"], update["available"])
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            for j, result in enumerate(results):
                if isinstance(result, Exception):
                    errors.append({"update": chunk[j], "error": str(result)})
                elif result:
                    success_count += 1
                else:
                    errors.append({"update": chunk[j], "error": "Update failed"})

            # Rate limit pause between chunks
            if i + chunk_size < len(inventory_updates):
                await asyncio.sleep(1)

        logger.info(f"✅ Inventory batch update: {success_count} success, {len(errors)} errors")
        return success_count, errors

    async def adjust_inventory_quantities(self, adjustments: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Adjust inventory quantities using bulk operation.

        Args:
            adjustments: List of inventory adjustments with structure:
                [{
                    "inventoryItemId": "gid://shopify/InventoryItem/123",
                    "locationId": "gid://shopify/Location/456",
                    "quantityDelta": 5
                }, ...]

        Returns:
            Adjustment result
        """
        try:
            variables = {"input": {"name": "available", "changes": adjustments}}

            result = await self._execute_query(INVENTORY_ADJUST_QUANTITIES_MUTATION, variables)

            adjust_result = result.get("inventoryAdjustQuantities", {})
            self._handle_graphql_errors(adjust_result, "Inventory quantity adjustment")

            adjustment_group = adjust_result.get("inventoryAdjustmentGroup")
            if adjustment_group:
                changes_count = len(adjustment_group.get("changes", []))
                logger.info(f"✅ Adjusted inventory quantities: {changes_count} changes applied")
                return adjustment_group

            raise ShopifyAPIException("Inventory adjustment failed: No adjustment group returned")

        except Exception as e:
            logger.error(f"Error adjusting inventory quantities: {e}")
            raise ShopifyAPIException(f"Failed to adjust inventory quantities: {str(e)}") from e

    async def update_inventory_item(
        self,
        inventory_item_id: str,
        cost: Optional[str] = None,
        country_code_of_origin: Optional[str] = None,
        harmonized_system_code: Optional[str] = None,
        province_code_of_origin: Optional[str] = None,
        sku: Optional[str] = None,
        tracked: Optional[bool] = None,
        country_harmonized_system_codes: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Update inventory item properties.

        Args:
            inventory_item_id: Inventory item ID to update
            cost: Cost per unit
            country_code_of_origin: Country code of origin
            harmonized_system_code: Harmonized system code
            province_code_of_origin: Province code of origin
            sku: SKU
            tracked: Whether inventory is tracked
            country_harmonized_system_codes: Country-specific HS codes

        Returns:
            Updated inventory item
        """
        try:
            input_data = {"id": inventory_item_id}

            if cost is not None:
                input_data["cost"] = cost
            if country_code_of_origin is not None:
                input_data["countryCodeOfOrigin"] = country_code_of_origin
            if harmonized_system_code is not None:
                input_data["harmonizedSystemCode"] = harmonized_system_code
            if province_code_of_origin is not None:
                input_data["provinceCodeOfOrigin"] = province_code_of_origin
            if sku is not None:
                input_data["sku"] = sku
            if tracked is not None:
                input_data["tracked"] = tracked
            if country_harmonized_system_codes is not None:
                input_data["countryHarmonizedSystemCodes"] = country_harmonized_system_codes

            variables = {"input": input_data}

            result = await self._execute_query(INVENTORY_ITEM_UPDATE_MUTATION, variables)

            update_result = result.get("inventoryItemUpdate", {})
            self._handle_graphql_errors(update_result, "Inventory item update")

            inventory_item = update_result.get("inventoryItem")
            if inventory_item:
                logger.info(f"✅ Updated inventory item: {inventory_item_id}")
                return inventory_item

            raise ShopifyAPIException("Inventory item update failed: No inventory item returned")

        except Exception as e:
            logger.error(f"Error updating inventory item {inventory_item_id}: {e}")
            raise ShopifyAPIException(f"Failed to update inventory item: {str(e)}") from e

    async def update_variant_rest(self, variant_id: str, variant_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a variant using REST API (useful for fields like SKU that might not be available in GraphQL).

        Args:
            variant_id: Variant ID (without gid prefix)
            variant_data: Data to update

        Returns:
            Updated variant data
        """
        try:
            # Extract numeric ID from GraphQL ID
            if variant_id.startswith("gid://shopify/ProductVariant/"):
                numeric_id = variant_id.split("/")[-1]
            else:
                numeric_id = variant_id

            # Build REST API URL
            shop_name = self.shop_url.replace("https://", "").replace("http://", "")
            if not shop_name.endswith(".myshopify.com"):
                shop_name = f"{shop_name}.myshopify.com"

            rest_url = f"https://{shop_name}/admin/api/{self.api_version}/variants/{numeric_id}.json"

            # Prepare payload
            payload = {"variant": variant_data}

            # Make REST API call
            headers = {
                "Content-Type": "application/json",
                "X-Shopify-Access-Token": self.access_token,
            }

            async with aiohttp.ClientSession() as session:
                async with session.put(rest_url, json=payload, headers=headers) as response:
                    response_data = await response.json()

                    if response.status != 200:
                        error_msg = response_data.get("error", response_data.get("errors", "Unknown error"))
                        raise ShopifyAPIException(f"REST API error {response.status}: {error_msg}")

                    variant = response_data.get("variant", {})
                    logger.info(f"✅ Updated variant via REST API: {variant.get('sku', 'Unknown SKU')}")
                    return variant

        except Exception as e:
            logger.error(f"Error updating variant via REST API: {e}")
            raise ShopifyAPIException(f"Failed to update variant via REST API: {str(e)}") from e

    async def get_inventory_item(self, inventory_item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get inventory item with inventory levels.

        Args:
            inventory_item_id: Inventory item ID (gid://shopify/InventoryItem/...)

        Returns:
            Inventory item dict with levels, or None if not found
        """
        try:
            from app.db.queries.reverse_sync import INVENTORY_ITEM_QUERY

            variables = {"id": inventory_item_id}
            result = await self._execute_query(INVENTORY_ITEM_QUERY, variables)

            inventory_item = result.get("inventoryItem")
            if inventory_item:
                logger.info(
                    f"Found inventory item: {inventory_item.get('sku', 'Unknown')} "
                    f"(tracked: {inventory_item.get('tracked', False)})"
                )
                return inventory_item

            logger.info(f"No inventory item found with ID: {inventory_item_id}")
            return None

        except Exception as e:
            logger.error(f"Error fetching inventory item {inventory_item_id}: {e}")
            raise ShopifyAPIException(f"Failed to fetch inventory item: {str(e)}") from e
