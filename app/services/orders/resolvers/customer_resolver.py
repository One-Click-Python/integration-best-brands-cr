"""CustomerResolver service - SRP compliance."""

import logging
from typing import Any

from app.core.config import get_settings
from app.db.rms.customer_repository import CustomerRepository
from app.utils.error_handler import ValidationException

logger = logging.getLogger(__name__)
settings = get_settings()


class CustomerResolver:
    """Resolves or creates customers in RMS (SRP: Customer management only)."""

    def __init__(self, customer_repo: CustomerRepository):
        """
        Initialize with SOLID dependencies (DIP).

        Args:
            customer_repo: Repository for customer operations
        """
        self.customer_repo = customer_repo

    async def resolve(self, customer_data: dict[str, Any] | None, billing_address: dict[str, Any] | None) -> int | None:
        """
        Resolve or create customer, return customer ID.

        Returns:
            int | None: Customer ID or None if allowed
        """
        try:
            # Guest order without customer
            if not customer_data:
                return await self._handle_guest_order()

            email = customer_data.get("email")

            # Customer without email
            if not email:
                return await self._handle_customer_without_email()

            # Find existing customer by email
            existing = await self.customer_repo.find_customer_by_email(email)
            if existing:
                logger.debug(f"Found existing customer: {existing['id']} for {email}")
                return existing["id"]

            # Create new customer
            return await self._create_customer(customer_data, billing_address)

        except Exception as e:
            logger.error(f"Error resolving customer: {e}")
            if settings.ALLOW_ORDERS_WITHOUT_CUSTOMER:
                # Try to use configured ID or auto-create guest customer
                if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
                    return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS
                try:
                    return await self.customer_repo.find_or_create_guest_customer()
                except Exception as fallback_error:
                    logger.error(f"Failed to create guest customer fallback: {fallback_error}")
                    return None
            raise

    async def _handle_guest_order(self) -> int:
        """
        Handle guest orders based on configuration.

        Returns:
            int: Customer ID for guest order (never None)

        Raises:
            ValidationException: If orders without customer are not allowed
        """
        if not settings.ALLOW_ORDERS_WITHOUT_CUSTOMER:
            raise ValidationException(
                message="Orders without customer are not allowed",
                field="customer",
                invalid_value=None,
            )

        # Priority 1: Use manually configured customer ID if set
        if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
            logger.info(
                f"Using configured default customer ID "
                f"{settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS} for guest order"
            )
            return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS

        # Priority 2: Auto-create or find guest customer in RMS
        logger.info("Auto-creating/finding guest customer in RMS")
        guest_customer_id = await self.customer_repo.find_or_create_guest_customer()
        logger.info(f"Using guest customer ID {guest_customer_id} for order")
        return guest_customer_id

    async def _handle_customer_without_email(self) -> int:
        """
        Handle customers without email based on configuration.

        Returns:
            int: Customer ID for customer without email (never None)

        Raises:
            ValidationException: If customer email is required
        """
        if settings.REQUIRE_CUSTOMER_EMAIL:
            raise ValidationException(
                message="Customer email is required",
                field="customer.email",
                invalid_value=None,
            )

        # Priority 1: Use manually configured customer ID if set
        if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
            logger.info("Using default customer ID for customer without email")
            return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS

        # Priority 2: Auto-create or find guest customer
        logger.info("Customer has no email - using guest customer")
        guest_customer_id = await self.customer_repo.find_or_create_guest_customer()
        logger.info(f"Using guest customer ID {guest_customer_id} for customer without email")
        return guest_customer_id

    async def _create_customer(self, customer_data: dict[str, Any], billing_address: dict[str, Any] | None) -> int:
        """Create new customer in RMS."""
        customer_info = {
            "email": customer_data.get("email"),
            "first_name": customer_data.get("firstName", ""),
            "last_name": customer_data.get("lastName", ""),
            "phone": customer_data.get("phone", ""),
            "shopify_customer_id": customer_data.get("id"),
        }

        if billing_address:
            customer_info.update(
                {
                    "address1": billing_address.get("address1", ""),
                    "address2": billing_address.get("address2", ""),
                    "city": billing_address.get("city", ""),
                    "province": billing_address.get("province", ""),
                    "country": billing_address.get("country", ""),
                    "zip": billing_address.get("zip", ""),
                }
            )

        customer_id = await self.customer_repo.create_customer(customer_info)
        logger.info(f"Created new customer: {customer_id} for {customer_info['email']}")
        return customer_id
