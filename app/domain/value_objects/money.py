"""
Money value object for handling monetary amounts with currency.

This value object ensures type safety and provides clear semantics
for monetary operations in the domain.
"""

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True)
class Money:
    """
    Immutable value object representing a monetary amount with currency.

    Attributes:
        amount: The monetary amount as Decimal for precision
        currency: Currency code (e.g., "USD", "CRC")

    Example:
        >>> price = Money(amount=Decimal("99.99"), currency="USD")
        >>> tax = Money(amount=Decimal("13.00"), currency="USD")
        >>> total = price + tax
        >>> print(total.amount)
        112.99
    """

    amount: Decimal
    currency: str = "USD"

    def __post_init__(self) -> None:
        """Validate money object after initialization."""
        if not isinstance(self.amount, Decimal):
            # Convert to Decimal if needed
            object.__setattr__(self, "amount", Decimal(str(self.amount)))

        # Normalizar a 0 decimales para valores monetarios (CRC colones)
        # CRC no usa decimales - todos los montos deben ser enteros
        normalized_amount = self.amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        object.__setattr__(self, "amount", normalized_amount)

        if self.amount < 0:
            raise ValueError(f"Money amount cannot be negative: {self.amount}")

        if not self.currency or len(self.currency) != 3:
            raise ValueError(f"Invalid currency code: {self.currency}")

    def __add__(self, other: "Money") -> "Money":
        """Add two Money objects with the same currency."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot add Money with {type(other)}")

        if self.currency != other.currency:
            raise ValueError(f"Cannot add different currencies: {self.currency} and {other.currency}")

        return Money(amount=self.amount + other.amount, currency=self.currency)

    def __sub__(self, other: "Money") -> "Money":
        """Subtract two Money objects with the same currency."""
        if not isinstance(other, Money):
            raise TypeError(f"Cannot subtract Money with {type(other)}")

        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract different currencies: {self.currency} and {other.currency}")

        return Money(amount=self.amount - other.amount, currency=self.currency)

    def __mul__(self, multiplier: int | float | Decimal) -> "Money":
        """Multiply money by a scalar value."""
        if not isinstance(multiplier, (int, float, Decimal)):
            raise TypeError(f"Cannot multiply Money by {type(multiplier)}")

        return Money(amount=self.amount * Decimal(str(multiplier)), currency=self.currency)

    def __str__(self) -> str:
        """String representation of Money."""
        return f"{self.currency} {self.amount:.0f}"

    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return f"Money(amount=Decimal('{self.amount}'), currency='{self.currency}')"

    @property
    def is_zero(self) -> bool:
        """Check if amount is zero."""
        return self.amount == Decimal("0")

    @property
    def is_positive(self) -> bool:
        """Check if amount is positive."""
        return self.amount > Decimal("0")

    @classmethod
    def zero(cls, currency: str = "USD") -> "Money":
        """Create a zero Money object."""
        return cls(amount=Decimal("0"), currency=currency)

    @classmethod
    def from_float(cls, amount: float, currency: str = "USD") -> "Money":
        """Create Money from float value (use with caution due to float precision)."""
        return cls(amount=Decimal(str(amount)), currency=currency)

    @classmethod
    def from_string(cls, amount: str, currency: str = "USD") -> "Money":
        """Create Money from string representation."""
        return cls(amount=Decimal(amount), currency=currency)
