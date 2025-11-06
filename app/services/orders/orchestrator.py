"""
ShopifyToRMSOrderOrchestrator - Main coordinator (SOLID compliant).

This orchestrator follows:
- SRP: Only coordinates order sync flow
- OCP: Open for extension via new services
- LSP: Works with any implementations of service interfaces
- ISP: Uses specific service interfaces
- DIP: Depends on abstractions (interfaces), not concrete implementations
"""

import logging
from typing import Any

from app.core.config import get_settings
from app.services.orders.converters import OrderConverter
from app.services.orders.managers import InventoryManager, OrderCreator
from app.services.orders.resolvers import CustomerResolver
from app.services.orders.validators import OrderValidator
from app.utils.error_handler import SyncException

settings = get_settings()
logger = logging.getLogger(__name__)


class ShopifyToRMSOrderOrchestrator:
    """
    Orchestrates the order sync process from Shopify to RMS.

    This class coordinates all services following the SOLID principles.
    Each service has a single responsibility and is injected via constructor.
    """

    def __init__(
        self,
        validator: OrderValidator,
        converter: OrderConverter,
        customer_resolver: CustomerResolver,
        order_creator: OrderCreator,
        inventory_manager: InventoryManager,
    ):
        """
        Initialize orchestrator with service dependencies (DIP).

        Args:
            validator: Service for order validation
            converter: Service for Shopify → Domain conversion
            customer_resolver: Service for customer resolution
            order_creator: Service for order creation in RMS
            inventory_manager: Service for inventory management
        """
        self.validator = validator
        self.converter = converter
        self.customer_resolver = customer_resolver
        self.order_creator = order_creator
        self.inventory_manager = inventory_manager

    async def sync_order(self, shopify_order: dict[str, Any], skip_validation: bool = False) -> dict[str, Any]:
        """
        Synchronize a single order from Shopify to RMS.

        This method orchestrates the complete flow:
        1. Validate order (if not skipped)
        2. Convert to domain model
        3. Resolve customer
        4. Create order in RMS
        5. Update inventory

        Args:
            shopify_order: Shopify order data
            skip_validation: Whether to skip validation

        Returns:
            dict: Sync result with order_id and status

        Raises:
            SyncException: If sync fails
        """
        order_id = shopify_order.get("id", "unknown")

        try:
            logger.info(f"Starting order sync for Shopify order {order_id}")

            # Step 1: Validate
            if not skip_validation:
                validated_order = self.validator.validate(shopify_order)
            else:
                validated_order = shopify_order
                logger.debug(f"Validation skipped for order {order_id}")

            # Step 2: Convert to domain model
            logger.debug(f"Converting order {order_id} to domain model")
            order_domain = await self.converter.convert_to_domain(validated_order)

            # Step 3: Resolve customer
            logger.debug(f"Resolving customer for order {order_id}")
            customer_data = validated_order.get("customer")
            billing_address = validated_order.get("billingAddress")
            customer_id = await self.customer_resolver.resolve(customer_data, billing_address)
            order_domain.customer_id = customer_id

            # Regenerate comment with payment status
            customer_info = self.converter.customer_fetcher.fetch_customer_info(validated_order)
            payment_status = validated_order.get("displayFinancialStatus", "PENDING")
            order_domain.comment = self.converter.customer_fetcher.format_comment_for_rms(
                customer_info, order_name=validated_order.get("name"), payment_status=payment_status
            )

            # Step 4: Create order in RMS
            logger.debug(f"Creating order {order_id} in RMS")
            rms_order_id = await self.order_creator.create(order_domain)

            # Step 5: Update inventory
            logger.debug(f"Updating inventory for order {order_id}")
            entry_dicts = [entry.to_dict() for entry in order_domain.entries]
            await self.inventory_manager.validate_and_update(entry_dicts)

            logger.info(f"Successfully synced order {order_id} → RMS order {rms_order_id}")

            return {
                "shopify_order_id": order_id,
                "rms_order_id": rms_order_id,
                "action": "created",
                "status": "success",
                "items_count": len(order_domain.entries),
                "total": float(order_domain.total.amount),
            }

        except Exception as e:
            logger.error(f"Failed to sync order {order_id}: {e}")
            raise SyncException(
                message=f"Failed to sync order {order_id}: {str(e)}",
                service="orchestrator",
                operation="sync_order",
            ) from e

    async def update_order(
        self, existing_order_id: int, shopify_order: dict[str, Any], skip_validation: bool = False
    ) -> dict[str, Any]:
        """
        Update existing order from Shopify to RMS.

        This method orchestrates the complete update flow:
        1. Validate order (if not skipped)
        2. Convert to domain model
        3. Resolve customer (may have changed)
        4. Get existing entries for inventory adjustment
        5. Update order in RMS
        6. Adjust inventory based on differences

        Args:
            existing_order_id: ID of existing RMS order
            shopify_order: Shopify order data
            skip_validation: Whether to skip validation

        Returns:
            dict: Update result with order_id and status

        Raises:
            SyncException: If update fails
        """
        order_id = shopify_order.get("id", "unknown")

        try:
            logger.info(f"Starting order update for Shopify order {order_id} → RMS order {existing_order_id}")

            # Step 1: Validate
            if not skip_validation:
                validated_order = self.validator.validate(shopify_order)
            else:
                validated_order = shopify_order
                logger.debug(f"Validation skipped for order {order_id}")

            # Step 2: Convert to domain model
            logger.debug(f"Converting order {order_id} to domain model")
            order_domain = await self.converter.convert_to_domain(validated_order)

            # Step 3: Resolve customer (may have changed)
            logger.debug(f"Resolving customer for order {order_id}")
            customer_data = validated_order.get("customer")
            billing_address = validated_order.get("billingAddress")
            customer_id = await self.customer_resolver.resolve(customer_data, billing_address)
            order_domain.customer_id = customer_id

            # Regenerate comment with payment status
            customer_info = self.converter.customer_fetcher.fetch_customer_info(validated_order)
            payment_status = validated_order.get("displayFinancialStatus", "PENDING")
            order_domain.comment = self.converter.customer_fetcher.format_comment_for_rms(
                customer_info, order_name=validated_order.get("name"), payment_status=payment_status
            )

            # Step 4: Get existing entries for inventory adjustment
            logger.debug("Getting existing entries for inventory adjustment")
            existing_entries_raw = await self.order_creator.order_repo.get_order_entries(existing_order_id)
            # Convert to dict format expected by inventory manager
            old_entries = [
                {"item_id": entry["ItemID"], "quantity_on_order": entry["QuantityOnOrder"]}
                for entry in existing_entries_raw
            ]

            # Step 5: Update order in RMS
            logger.debug(f"Updating order {existing_order_id} in RMS")
            rms_order_id = await self.order_creator.update(existing_order_id, order_domain)

            # Step 6: Adjust inventory based on differences
            logger.debug("Adjusting inventory for order update")
            new_entries = [entry.to_dict() for entry in order_domain.entries]
            await self.inventory_manager.adjust_for_update(old_entries, new_entries)

            logger.info(f"Successfully updated order {order_id} → RMS order {rms_order_id}")

            return {
                "shopify_order_id": order_id,
                "rms_order_id": rms_order_id,
                "action": "updated",
                "status": "success",
                "items_count": len(order_domain.entries),
                "total": float(order_domain.total.amount),
            }

        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {e}")
            raise SyncException(
                message=f"Failed to update order {order_id}: {str(e)}",
                service="orchestrator",
                operation="update_order",
            ) from e


# Factory function to create orchestrator with all dependencies
def create_orchestrator(
    query_executor,
    customer_repo,
    order_repo,
    product_repo,
    shopify_client=None,
) -> ShopifyToRMSOrderOrchestrator:
    """
    Factory function to create fully initialized orchestrator with SOLID repositories.

    This function encapsulates dependency creation and injection following DIP.

    Args:
        query_executor: QueryExecutor for custom SQL queries
        customer_repo: CustomerRepository for customer operations
        order_repo: OrderRepository for order operations
        product_repo: ProductRepository for product/inventory operations
        shopify_client: Shopify client (optional, for future extensions)

    Returns:
        ShopifyToRMSOrderOrchestrator: Fully configured orchestrator
    """
    # Create service instances with SOLID repositories
    validator = OrderValidator(allowed_financial_statuses=settings.ALLOWED_ORDER_FINANCIAL_STATUSES)
    converter = OrderConverter(query_executor=query_executor)
    customer_resolver = CustomerResolver(customer_repo=customer_repo)
    order_creator = OrderCreator(order_repo=order_repo)
    inventory_manager = InventoryManager(product_repo=product_repo)

    # Create and return orchestrator with injected dependencies
    return ShopifyToRMSOrderOrchestrator(
        validator=validator,
        converter=converter,
        customer_resolver=customer_resolver,
        order_creator=order_creator,
        inventory_manager=inventory_manager,
    )
