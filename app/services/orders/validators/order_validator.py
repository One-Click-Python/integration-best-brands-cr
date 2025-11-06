"""
OrderValidator service for validating Shopify orders before conversion to RMS.

This service follows SRP (Single Responsibility Principle) by focusing only on
validation logic for Shopify orders.
"""

import logging
from typing import Any

from app.utils.error_handler import ValidationException

logger = logging.getLogger(__name__)


class OrderValidator:
    """
    Validates Shopify orders before they are converted to RMS format.

    Responsibilities:
    - Validate required fields
    - Validate line items
    - Validate financial status
    - Validate order totals
    - Business rule validation
    """

    def __init__(self, allowed_financial_statuses: list[str] | None = None):
        """
        Initialize validator with configurable financial statuses.

        Args:
            allowed_financial_statuses: List of allowed financial statuses for sync.
                                       Defaults to PAID, PARTIALLY_PAID, AUTHORIZED, PENDING
        """
        self.allowed_financial_statuses = allowed_financial_statuses or [
            "PAID", "PARTIALLY_PAID", "AUTHORIZED", "PENDING"
        ]

    def validate(self, order: dict[str, Any]) -> dict[str, Any]:
        """
        Validates a Shopify order and returns the validated order.

        Args:
            order: Shopify order data dictionary

        Returns:
            dict: Validated order (same as input if valid)

        Raises:
            ValidationException: If validation fails
        """
        try:
            self._validate_required_fields(order)
            self._validate_line_items(order)
            self._validate_total(order)
            self._validate_financial_status(order)

            logger.info(f"Order {order['id']} validation passed successfully")
            return order

        except ValidationException:
            raise
        except Exception as e:
            raise ValidationException(
                message=f"Unexpected validation error: {str(e)}",
                field="order",
                invalid_value=order.get("id"),
            ) from e

    def _validate_required_fields(self, order: dict[str, Any]) -> None:
        """
        Validates that all required fields are present in the order.

        Args:
            order: Shopify order data

        Raises:
            ValidationException: If any required field is missing
        """
        required_fields = ["id", "name", "createdAt", "totalPriceSet", "lineItems"]

        for field in required_fields:
            if not order.get(field):
                raise ValidationException(
                    message=f"Missing required field: {field}",
                    field=field,
                    invalid_value=order.get(field),
                )

        logger.debug(f"Required fields validation passed for order {order['id']}")

    def _validate_line_items(self, order: dict[str, Any]) -> None:
        """
        Validates that the order has valid line items.

        Args:
            order: Shopify order data

        Raises:
            ValidationException: If line items are invalid
        """
        # Extract line items from GraphQL format
        line_items_raw = order.get("lineItems", {})

        if isinstance(line_items_raw, dict) and "edges" in line_items_raw:
            # GraphQL format: lineItems.edges[].node
            line_items = [edge["node"] for edge in line_items_raw["edges"]]
        else:
            # Simple list format
            line_items = line_items_raw if isinstance(line_items_raw, list) else []

        # Validate that there's at least one line item
        if not line_items or len(line_items) == 0:
            raise ValidationException(
                message="Order must have at least one line item",
                field="lineItems",
                invalid_value=line_items_raw,
            )

        # Validate that each line item has either a SKU or variant ID
        for i, item in enumerate(line_items):
            variant_sku = (item.get("variant") or {}).get("sku")
            item_level_sku = item.get("sku")
            item_sku = variant_sku or item_level_sku

            # Check if we have SKU or at least a variant ID
            if not item_sku or item_sku.strip() == "":
                variant_id = (item.get("variant") or {}).get("id")
                if not variant_id:
                    logger.warning(
                        f"Line item {i + 1} in order {order['id']} has no SKU or variant ID - "
                        f"will be skipped: {item.get('title', 'Unknown item')}"
                    )

        logger.debug(f"Line items validation passed for order {order['id']}: {len(line_items)} items")

    def _validate_total(self, order: dict[str, Any]) -> None:
        """
        Validates that the order total is greater than zero.

        Args:
            order: Shopify order data

        Raises:
            ValidationException: If total is invalid
        """
        total_price = order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount")

        if not total_price or float(total_price) <= 0:
            raise ValidationException(
                message="Order total must be greater than zero",
                field="totalPriceSet.shopMoney.amount",
                invalid_value=total_price,
            )

        logger.debug(f"Total validation passed for order {order['id']}: {total_price}")

    def _validate_financial_status(self, order: dict[str, Any]) -> None:
        """
        Validates that the order has a valid financial status for syncing.

        Args:
            order: Shopify order data

        Raises:
            ValidationException: If financial status is not valid for sync
        """
        financial_status = order.get("displayFinancialStatus", "").upper()

        if financial_status not in self.allowed_financial_statuses:
            raise ValidationException(
                message=(
                    f"Order financial status '{financial_status}' not valid for sync. "
                    f"Must be one of: {self.allowed_financial_statuses}"
                ),
                field="displayFinancialStatus",
                invalid_value=financial_status,
            )

        logger.debug(f"Financial status validation passed for order {order['id']}: {financial_status}")

    def validate_line_item_for_sync(self, item: dict[str, Any], order_id: str) -> tuple[bool, str | None]:
        """
        Validates if a line item can be synced to RMS.

        Args:
            item: Line item data
            order_id: Order ID for logging

        Returns:
            tuple: (is_valid, skip_reason)
                - is_valid: True if item can be synced
                - skip_reason: Reason for skipping if not valid, None otherwise
        """
        # Check for SKU
        variant_sku = (item.get("variant") or {}).get("sku")
        item_level_sku = item.get("sku")
        item_sku = variant_sku or item_level_sku

        if not item_sku or item_sku.strip() == "":
            # Check for variant ID as fallback
            variant_id = (item.get("variant") or {}).get("id")
            if not variant_id:
                return (
                    False,
                    f"No SKU or variant ID for item: {item.get('title', 'Unknown')}",
                )

        # Check quantity
        quantity = item.get("quantity", 0)
        if quantity <= 0:
            return False, f"Invalid quantity ({quantity}) for item: {item.get('title', 'Unknown')}"

        return True, None
