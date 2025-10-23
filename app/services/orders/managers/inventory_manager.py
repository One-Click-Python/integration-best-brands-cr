"""InventoryManager service - SRP compliance."""

import logging
from typing import Any

from app.db.rms.product_repository import ProductRepository

logger = logging.getLogger(__name__)


class InventoryManager:
    """Manages inventory validation and updates (SRP: Inventory only)."""

    def __init__(self, product_repo: ProductRepository):
        """
        Initialize with SOLID dependencies (DIP).

        Args:
            product_repo: Repository for product/inventory operations
        """
        self.product_repo = product_repo

    async def validate_and_update(self, order_entries: list[dict[str, Any]]) -> None:
        """Validate stock and update inventory."""
        try:
            for entry in order_entries:
                item_id = entry["item_id"]
                quantity_ordered = entry["quantity_on_order"]

                # Check stock
                current_stock = await self.product_repo.get_item_stock(item_id)
                if current_stock is None:
                    logger.warning(f"Could not get stock for item {item_id}")
                    continue

                if current_stock < quantity_ordered:
                    logger.warning(
                        f"Insufficient stock for item {item_id}: "
                        f"ordered {quantity_ordered}, available {current_stock}"
                    )
                    # Don't block - allow oversell

                # Update stock
                await self.product_repo.update_item_stock(item_id, -quantity_ordered)
                logger.debug(f"Updated stock for item {item_id}: -{quantity_ordered}")

        except Exception as e:
            logger.error(f"Error in inventory management: {e}")
            # Don't re-raise - inventory can be adjusted manually

    async def adjust_for_update(self, old_entries: list[dict[str, Any]], new_entries: list[dict[str, Any]]) -> None:
        """
        Adjust inventory based on order changes.

        Calculates differences between old and new quantities and adjusts stock accordingly:
        - Item quantity increased: reduce stock further
        - Item quantity decreased: restore stock
        - Item removed: restore full quantity
        - New item added: reduce stock

        Args:
            old_entries: Previous order entries
            new_entries: New order entries

        Note:
            Does not raise exceptions - logs errors but allows order update to complete.
            Inventory can be manually adjusted if needed.
        """
        try:
            # Create lookup dictionaries
            old_by_item = {entry["item_id"]: entry["quantity_on_order"] for entry in old_entries}
            new_by_item = {entry["item_id"]: entry["quantity_on_order"] for entry in new_entries}

            # Get all unique item IDs
            all_items = set(old_by_item.keys()) | set(new_by_item.keys())

            for item_id in all_items:
                old_qty = old_by_item.get(item_id, 0.0)
                new_qty = new_by_item.get(item_id, 0.0)
                difference = new_qty - old_qty

                if difference == 0:
                    # No change in quantity
                    continue

                if difference > 0:
                    # Quantity increased - reduce stock further
                    logger.debug(
                        f"Item {item_id} quantity increased by {difference} "
                        f"(old: {old_qty}, new: {new_qty}) - reducing stock"
                    )
                    await self.product_repo.update_item_stock(item_id, -difference)
                else:
                    # Quantity decreased or item removed - restore stock
                    restore_amount = abs(difference)
                    logger.debug(
                        f"Item {item_id} quantity decreased by {restore_amount} "
                        f"(old: {old_qty}, new: {new_qty}) - restoring stock"
                    )
                    await self.product_repo.update_item_stock(item_id, restore_amount)

            logger.info(f"Successfully adjusted inventory for {len(all_items)} items")

        except Exception as e:
            logger.error(f"Error adjusting inventory for order update: {e}")
            # Don't re-raise - inventory can be adjusted manually
