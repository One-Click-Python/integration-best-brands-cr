"""
Value objects for the domain layer.

Value objects are immutable objects that represent concepts
with no conceptual identity, only defined by their attributes.
"""

from .money import Money

__all__ = ["Money"]
