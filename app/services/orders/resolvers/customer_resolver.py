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
                return self._handle_guest_order()

            email = customer_data.get("email")

            # Customer without email
            if not email:
                return self._handle_customer_without_email()

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
                return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS or None
            raise

    def _handle_guest_order(self) -> int | None:
        """Handle guest orders based on configuration."""
        if not settings.ALLOW_ORDERS_WITHOUT_CUSTOMER:
            raise ValidationException(
                message="Orders without customer are not allowed",
                field="customer",
                invalid_value=None,
            )

        if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
            logger.info(f"Using default customer ID {settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS} for guest")
            return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS

        logger.warning("No customer data, creating order with customer_id=NULL")
        return None

    def _handle_customer_without_email(self) -> int | None:
        """Handle customers without email based on configuration."""
        if settings.REQUIRE_CUSTOMER_EMAIL:
            raise ValidationException(
                message="Customer email is required",
                field="customer.email",
                invalid_value=None,
            )

        if settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS:
            logger.info("Using default customer ID for customer without email")
            return settings.DEFAULT_CUSTOMER_ID_FOR_GUEST_ORDERS

        logger.warning("Customer has no email, using customer_id=NULL")
        return None

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
