"""
Customer domain model.

Represents a customer entity with business logic and validation.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class CustomerDomain:
    """
    Domain model representing a customer.

    This model contains customer business logic and validation rules.
    It is independent of persistence and infrastructure concerns.

    Attributes:
        id: Customer ID (None for new customers)
        email: Customer email address
        first_name: Customer first name
        last_name: Customer last name
        phone: Customer phone number
        is_guest: Whether this is a guest customer
        shopify_customer_id: Original Shopify customer ID
    """

    email: str
    first_name: str = ""
    last_name: str = ""
    phone: str = ""
    is_guest: bool = False
    shopify_customer_id: str | None = None
    id: int | None = None

    def __post_init__(self) -> None:
        """Validate customer data after initialization."""
        if not self.email and not self.is_guest:
            raise ValueError("Email is required for registered customers")

        if self.email and "@" not in self.email:
            raise ValueError(f"Invalid email format: {self.email}")

    @property
    def full_name(self) -> str:
        """Get customer's full name."""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return "Cliente Invitado" if self.is_guest else "Cliente Shopify"

    @property
    def display_name(self) -> str:
        """Get customer's display name for UI purposes."""
        if self.is_guest:
            return f"Invitado ({self.email})" if self.email else "Invitado"
        return self.full_name

    def to_dict(self) -> dict[str, Any]:
        """Convert customer to dictionary for persistence."""
        return {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "phone": self.phone,
            "is_guest": self.is_guest,
            "shopify_customer_id": self.shopify_customer_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CustomerDomain":
        """Create customer from dictionary."""
        return cls(
            id=data.get("id"),
            email=data.get("email", ""),
            first_name=data.get("first_name", ""),
            last_name=data.get("last_name", ""),
            phone=data.get("phone", ""),
            is_guest=data.get("is_guest", False),
            shopify_customer_id=data.get("shopify_customer_id"),
        )

    @classmethod
    def create_guest(cls, email: str = "") -> "CustomerDomain":
        """Create a guest customer."""
        return cls(
            email=email if email else "invitado@shopify.com",
            first_name="",
            last_name="",
            is_guest=True,
        )
