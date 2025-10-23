"""OrderConverter service - converts Shopify orders to domain models (SRP)."""

import logging
from datetime import datetime
from typing import Any

from app.db.rms.query_executor import QueryExecutor
from app.domain.models import OrderDomain, OrderEntryDomain
from app.domain.value_objects import Money
from app.services.orders.converters.customer_fetcher import CustomerDataFetcher
from app.utils.error_handler import ValidationException

logger = logging.getLogger(__name__)


class OrderConverter:
    """Converts Shopify orders to domain models (SRP: Conversion only)."""

    def __init__(self, query_executor: QueryExecutor, customer_fetcher: CustomerDataFetcher | None = None):
        """
        Initialize with SOLID dependencies (DIP).

        Args:
            query_executor: Repository for custom SQL queries (find_item_by_sku)
            customer_fetcher: Service for extracting customer data
        """
        self.query_executor = query_executor
        self.customer_fetcher = customer_fetcher or CustomerDataFetcher()

    async def convert_to_domain(self, shopify_order: dict[str, Any]) -> OrderDomain:
        """Convert Shopify order to domain model."""
        # Extract basic data
        total_amount = Money.from_string(shopify_order["totalPriceSet"]["shopMoney"]["amount"])
        tax_amount = Money.from_string(shopify_order.get("totalTaxSet", {}).get("shopMoney", {}).get("amount", "0"))
        order_date = datetime.fromisoformat(shopify_order["createdAt"].replace("Z", "+00:00"))
        shopify_id_numeric = shopify_order["id"].split("/")[-1]

        # Get shipping charge
        shipping_charge = self._extract_shipping_charge(shopify_order)

        # Get customer info for comment
        customer_info = self.customer_fetcher.fetch_customer_info(shopify_order)
        order_comment = self.customer_fetcher.format_comment_for_rms(
            customer_info, order_name=shopify_order.get("name")
        )

        # Create order domain model
        order = OrderDomain(
            store_id=40,
            time=order_date,
            type=2,
            total=total_amount,
            tax=tax_amount,
            deposit=Money.zero(),
            reference_number=f"SHOPIFY-{shopify_id_numeric}",
            channel_type=2,
            closed=0,
            shipping_charge_on_order=shipping_charge,
            comment=order_comment,
            shipping_notes="",
            sales_rep_id=1000,
            shipping_service_id=0,
            shipping_tracking_number="",
        )

        # Convert line items
        entries = await self._convert_line_items(shopify_order)
        for entry in entries:
            order.add_entry(entry)

        return order

    def _extract_shipping_charge(self, shopify_order: dict[str, Any]) -> Money:
        """Extract shipping charge from order."""
        shipping_line = shopify_order.get("shippingLine")
        if shipping_line:
            shipping_money = (
                shipping_line.get("currentDiscountedPriceSet", {}).get("shopMoney", {}).get("amount", "0.00")
            )
            return Money.from_string(shipping_money) if shipping_money else Money.zero()
        return Money.zero()

    async def _convert_line_items(self, shopify_order: dict[str, Any]) -> list[OrderEntryDomain]:
        """Convert Shopify line items to order entry domain models."""
        line_items_data = []

        # Extract line items from GraphQL format
        line_items_raw = shopify_order.get("lineItems", {})
        if isinstance(line_items_raw, dict) and "edges" in line_items_raw:
            line_items = [edge["node"] for edge in line_items_raw["edges"]]
        else:
            line_items = line_items_raw if isinstance(line_items_raw, list) else []

        for item in line_items:
            # Get SKU
            variant_sku = (item.get("variant") or {}).get("sku")
            item_level_sku = item.get("sku")
            item_sku = variant_sku or item_level_sku

            # Fallback to variant ID if no SKU
            if not item_sku or item_sku.strip() == "":
                variant_id = (item.get("variant") or {}).get("id", "")
                if variant_id:
                    variant_id_num = variant_id.split("/")[-1] if "/" in variant_id else variant_id
                    item_sku = f"VAR-{variant_id_num}"
                    logger.info(f"Using variant ID as SKU: {item_sku}")
                else:
                    logger.warning(f"Skipping item without SKU: {item.get('title', 'Unknown')}")
                    continue

            # Resolve SKU to ItemID and get cost
            rms_item = await self.query_executor.find_item_by_sku(item_sku)
            if not rms_item:
                logger.error(f"Could not find RMS Item for SKU: {item_sku}")
                continue

            item_id = rms_item["item_id"]
            item_cost = Money.from_string(str(rms_item.get("cost") or 0.0))

            # Get prices
            discounted_price_set = item.get("discountedUnitPriceSet", item.get("originalUnitPriceSet"))
            unit_price = Money.from_string(discounted_price_set["shopMoney"]["amount"])
            original_price = Money.from_string(item["originalUnitPriceSet"]["shopMoney"]["amount"])

            # Create domain entry
            entry = OrderEntryDomain(
                item_id=item_id,
                store_id=40,
                price=unit_price,
                full_price=original_price,
                cost=item_cost,
                quantity_on_order=float(item["quantity"]),
                quantity_rtd=0.0,
                description=item["title"][:255],
                taxable=item.get("taxable", True),
                sales_rep_id=0,
                discount_reason_code_id=0,
                return_reason_code_id=0,
                is_add_money=False,
                voucher_id=0,
            )
            line_items_data.append(entry)

        if not line_items_data:
            raise ValidationException(
                message=f"No valid line items found for order {shopify_order['id']}",
                field="lineItems",
                invalid_value=shopify_order.get("lineItems", []),
            )

        return line_items_data
