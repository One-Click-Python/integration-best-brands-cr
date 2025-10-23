"""
OrderFactory - Factory pattern for creating domain objects (OCP).

This factory encapsulates object creation logic, making it easier
to modify without changing client code.
"""

from decimal import Decimal

from app.domain.models import CustomerDomain, OrderDomain, OrderEntryDomain
from app.domain.value_objects import Money


class OrderFactory:
    """Factory for creating domain objects with proper defaults."""

    @staticmethod
    def create_order_from_shopify(
        shopify_id: str,
        total: Decimal,
        tax: Decimal,
        comment: str,
        **kwargs,
    ) -> OrderDomain:
        """
        Create an OrderDomain from Shopify data.

        Args:
            shopify_id: Shopify order ID (numeric part)
            total: Order total amount
            tax: Tax amount
            comment: Order comment
            **kwargs: Additional order fields

        Returns:
            OrderDomain: Created order domain model
        """
        return OrderDomain(
            total=Money(amount=total),
            tax=Money(amount=tax),
            reference_number=f"SHOPIFY-{shopify_id}",
            comment=comment,
            **kwargs,
        )

    @staticmethod
    def create_customer(email: str, first_name: str = "", last_name: str = "", **kwargs) -> CustomerDomain:
        """Create a CustomerDomain."""
        return CustomerDomain(
            email=email,
            first_name=first_name,
            last_name=last_name,
            **kwargs,
        )

    @staticmethod
    def create_guest_customer(email: str = "") -> CustomerDomain:
        """Create a guest CustomerDomain."""
        return CustomerDomain.create_guest(email=email)

    @staticmethod
    def create_order_entry(
        item_id: int,
        price: Decimal,
        full_price: Decimal,
        cost: Decimal,
        quantity: float,
        **kwargs,
    ) -> OrderEntryDomain:
        """Create an OrderEntryDomain."""
        return OrderEntryDomain(
            item_id=item_id,
            price=Money(amount=price),
            full_price=Money(amount=full_price),
            cost=Money(amount=cost),
            quantity_on_order=quantity,
            **kwargs,
        )
