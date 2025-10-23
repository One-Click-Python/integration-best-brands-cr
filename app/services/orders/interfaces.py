"""
Interfaces/Protocols for order services (Dependency Inversion Principle).

These protocols define contracts that services must implement,
allowing for loose coupling and easy testing.
"""

from typing import Any, Protocol

from app.domain.models import OrderDomain


class IOrderValidator(Protocol):
    """Protocol for order validation services."""

    def validate(self, order: dict[str, Any]) -> dict[str, Any]:
        """Validate a Shopify order."""
        ...


class IOrderConverter(Protocol):
    """Protocol for order conversion services."""

    async def convert_to_domain(self, shopify_order: dict[str, Any]) -> OrderDomain:
        """Convert Shopify order to domain model."""
        ...


class ICustomerResolver(Protocol):
    """Protocol for customer resolution services."""

    async def resolve(self, customer_data: dict[str, Any] | None, billing_address: dict[str, Any] | None) -> int | None:
        """Resolve or create customer, return customer ID."""
        ...


class IInventoryManager(Protocol):
    """Protocol for inventory management services."""

    async def validate_and_update(self, order_entries: list[dict[str, Any]]) -> None:
        """Validate stock and update inventory."""
        ...


class IOrderCreator(Protocol):
    """Protocol for order creation services."""

    async def create(self, order: OrderDomain) -> int:
        """Create order in RMS, return order ID."""
        ...
