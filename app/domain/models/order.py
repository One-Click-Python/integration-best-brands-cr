"""
Order domain model (Aggregate Root).

Represents an order entity with business logic, validation, and order entries.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.domain.value_objects.money import Money

from .order_entry import OrderEntryDomain


@dataclass
class OrderDomain:
    """
    Domain model representing an order (Aggregate Root).

    This model contains order business logic and validation rules.
    It maintains consistency of the order and its entries.

    Attributes:
        store_id: Store ID (40 for virtual store)
        time: Order creation time
        type: Order type (2 for Shopify orders)
        total: Order total amount
        tax: Tax amount
        deposit: Deposit amount (0 for Shopify)
        reference_number: External reference (SHOPIFY-xxxxx)
        channel_type: Channel type (2 for Shopify)
        comment: Order comment with customer info
        sales_rep_id: Sales representative ID (1000 for Shopify)
        customer_id: Customer ID (optional)
        closed: Whether order is closed
        shipping_charge_on_order: Shipping charge
        shipping_service_id: Shipping service ID
        shipping_tracking_number: Tracking number
        shipping_notes: Shipping notes
        entries: List of order entries (line items)
        id: Order ID (None for new orders)
    """

    total: Money
    tax: Money
    reference_number: str
    comment: str
    store_id: int = 40
    time: datetime = field(default_factory=lambda: datetime.now(UTC))
    type: int = 2  # Tipo 2 para órdenes de Shopify
    deposit: Money = field(default_factory=lambda: Money.zero())
    channel_type: int = 2
    sales_rep_id: int = 1000
    customer_id: int | None = None
    closed: int = 0
    shipping_charge_on_order: Money = field(default_factory=lambda: Money.zero())
    shipping_service_id: int = 0
    shipping_tracking_number: str = ""
    shipping_notes: str = ""
    entries: list[OrderEntryDomain] = field(default_factory=list)
    id: int | None = None

    def __post_init__(self) -> None:
        """Validate order data after initialization."""
        if not self.reference_number:
            raise ValueError("Reference number is required")

        if not self.reference_number.startswith("SHOPIFY-"):
            raise ValueError(f"Invalid reference number format: {self.reference_number}")

        # Validate monetary consistency
        if not (
            self.total.currency == self.tax.currency == self.deposit.currency == self.shipping_charge_on_order.currency
        ):
            raise ValueError("All monetary values must have the same currency")

        # Validate that total is positive
        if self.total.amount <= 0:
            raise ValueError(f"Order total must be positive: {self.total.amount}")

    @property
    def subtotal(self) -> Money:
        """Calculate subtotal (total - tax - shipping)."""
        return Money(
            amount=self.total.amount - self.tax.amount - self.shipping_charge_on_order.amount,
            currency=self.total.currency,
        )

    @property
    def items_count(self) -> int:
        """Get total number of line items."""
        return len(self.entries)

    @property
    def total_quantity(self) -> float:
        """Get total quantity of all items."""
        return sum(entry.quantity_on_order for entry in self.entries)

    @property
    def is_closed(self) -> bool:
        """Check if order is closed."""
        return self.closed == 1

    @property
    def is_from_shopify(self) -> bool:
        """Check if order is from Shopify."""
        return self.channel_type == 2 and self.reference_number.startswith("SHOPIFY-")

    @property
    def shopify_order_id(self) -> str | None:
        """Extract Shopify order ID from reference number."""
        if self.is_from_shopify:
            return self.reference_number.replace("SHOPIFY-", "")
        return None

    def add_entry(self, entry: OrderEntryDomain) -> None:
        """
        Add an entry to the order.

        Args:
            entry: Order entry to add

        Raises:
            ValueError: If entry currency doesn't match order currency
        """
        if entry.price.currency != self.total.currency:
            raise ValueError(
                f"Entry currency ({entry.price.currency}) " f"doesn't match order currency ({self.total.currency})"
            )

        self.entries.append(entry)

    def close_order(self) -> None:
        """Close the order."""
        if self.is_closed:
            raise ValueError("Order is already closed")
        self.closed = 1

    def reopen_order(self) -> None:
        """Reopen a closed order."""
        if not self.is_closed:
            raise ValueError("Order is not closed")
        self.closed = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert order to dictionary for persistence."""
        return {
            "id": self.id,
            "store_id": self.store_id,
            "time": self.time,
            "type": self.type,
            "customer_id": self.customer_id,
            "deposit": self.deposit.amount,
            "tax": self.tax.amount,
            "total": self.total.amount,
            "sales_rep_id": self.sales_rep_id,
            "shipping_service_id": self.shipping_service_id,
            "shipping_tracking_number": self.shipping_tracking_number,
            "comment": self.comment,
            "shipping_notes": self.shipping_notes,
            "reference_number": self.reference_number,
            "channel_type": self.channel_type,
            "closed": self.closed,
            "shipping_charge_on_order": self.shipping_charge_on_order.amount,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], currency: str = "USD") -> "OrderDomain":
        """Create order from dictionary."""
        return cls(
            id=data.get("id"),
            store_id=data.get("store_id", 40),
            time=data.get("time", datetime.now(UTC)),
            type=data.get("type", 2),
            customer_id=data.get("customer_id"),
            deposit=Money(amount=Decimal(str(data.get("deposit", "0.00"))), currency=currency),
            tax=Money(amount=Decimal(str(data["tax"])), currency=currency),
            total=Money(amount=Decimal(str(data["total"])), currency=currency),
            sales_rep_id=data.get("sales_rep_id", 1000),
            shipping_service_id=data.get("shipping_service_id", 0),
            shipping_tracking_number=data.get("shipping_tracking_number", ""),
            comment=data["comment"],
            shipping_notes=data.get("shipping_notes", ""),
            reference_number=data["reference_number"],
            channel_type=data.get("channel_type", 2),
            closed=data.get("closed", 0),
            shipping_charge_on_order=Money(
                amount=Decimal(str(data.get("shipping_charge_on_order", "0.00"))), currency=currency
            ),
            entries=[],  # Entries loaded separately
        )
