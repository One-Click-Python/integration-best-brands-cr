"""
Order Entry (Line Item) domain model.

Represents a line item in an order with business logic and validation.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.value_objects.money import Money


@dataclass
class OrderEntryDomain:
    """
    Domain model representing an order line item.

    This model contains order entry business logic and validation rules.
    It is independent of persistence and infrastructure concerns.

    Attributes:
        item_id: RMS item ID
        store_id: Store ID (default 40 for virtual store)
        price: Unit price with discounts applied
        full_price: Original unit price without discounts
        cost: Item cost from RMS
        quantity_on_order: Quantity ordered
        quantity_rtd: Quantity ready to deliver
        description: Item description
        taxable: Whether item is taxable
        sales_rep_id: Sales representative ID
        discount_reason_code_id: Discount reason code
        return_reason_code_id: Return reason code
        is_add_money: Whether this is an additional charge
        voucher_id: Voucher/coupon ID if applicable
        id: Order entry ID (None for new entries)
        order_id: Parent order ID (None until order is created)
    """

    item_id: int
    price: Money
    full_price: Money
    cost: Money
    quantity_on_order: float
    store_id: int = 40
    quantity_rtd: float = 0.0
    description: str = ""
    taxable: bool = True
    sales_rep_id: int = 0
    discount_reason_code_id: int = 0
    return_reason_code_id: int = 0
    is_add_money: bool = False
    voucher_id: int = 0
    id: int | None = None
    order_id: int | None = None

    def __post_init__(self) -> None:
        """Validate order entry data after initialization."""
        if self.quantity_on_order <= 0:
            raise ValueError(f"Quantity must be positive: {self.quantity_on_order}")

        if self.quantity_rtd < 0:
            raise ValueError(f"Quantity RTD cannot be negative: {self.quantity_rtd}")

        if self.quantity_rtd > self.quantity_on_order:
            raise ValueError(
                f"Quantity RTD ({self.quantity_rtd}) cannot exceed quantity ordered ({self.quantity_on_order})"
            )

        # Validate that all Money objects have the same currency
        if not (self.price.currency == self.full_price.currency == self.cost.currency):
            raise ValueError("All monetary values must have the same currency")

    @property
    def line_total(self) -> Money:
        """Calculate line total (price * quantity)."""
        return self.price * Decimal(str(self.quantity_on_order))

    @property
    def discount_amount(self) -> Money:
        """Calculate discount amount per unit."""
        return Money(
            amount=self.full_price.amount - self.price.amount,
            currency=self.price.currency,
        )

    @property
    def total_discount(self) -> Money:
        """Calculate total discount for the line."""
        return self.discount_amount * Decimal(str(self.quantity_on_order))

    @property
    def has_discount(self) -> bool:
        """Check if line item has a discount."""
        return self.price.amount < self.full_price.amount

    @property
    def is_fully_delivered(self) -> bool:
        """Check if all ordered quantity has been delivered."""
        return self.quantity_rtd >= self.quantity_on_order

    def to_dict(self) -> dict[str, Any]:
        """Convert order entry to dictionary for persistence."""
        return {
            "id": self.id,
            "order_id": self.order_id,
            "item_id": self.item_id,
            "store_id": self.store_id,
            "price": float(self.price.amount),
            "full_price": float(self.full_price.amount),
            "cost": float(self.cost.amount),
            "quantity_on_order": self.quantity_on_order,
            "quantity_rtd": self.quantity_rtd,
            "description": self.description,
            "taxable": 1 if self.taxable else 0,
            "sales_rep_id": self.sales_rep_id,
            "discount_reason_code_id": self.discount_reason_code_id,
            "return_reason_code_id": self.return_reason_code_id,
            "is_add_money": self.is_add_money,
            "voucher_id": self.voucher_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], currency: str = "USD") -> "OrderEntryDomain":
        """Create order entry from dictionary."""
        return cls(
            id=data.get("id"),
            order_id=data.get("order_id"),
            item_id=data["item_id"],
            store_id=data.get("store_id", 40),
            price=Money(amount=Decimal(str(data["price"])), currency=currency),
            full_price=Money(amount=Decimal(str(data["full_price"])), currency=currency),
            cost=Money(amount=Decimal(str(data["cost"])), currency=currency),
            quantity_on_order=float(data["quantity_on_order"]),
            quantity_rtd=float(data.get("quantity_rtd", 0.0)),
            description=data.get("description", ""),
            taxable=bool(data.get("taxable", True)),
            sales_rep_id=data.get("sales_rep_id", 0),
            discount_reason_code_id=data.get("discount_reason_code_id", 0),
            return_reason_code_id=data.get("return_reason_code_id", 0),
            is_add_money=data.get("is_add_money", False),
            voucher_id=data.get("voucher_id", 0),
        )
