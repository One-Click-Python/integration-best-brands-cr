"""
RMS Database Repository Package.

This package contains repository classes following the Single Responsibility Principle
for interacting with the RMS (Retail Management System) database.

Repository Structure:
- BaseRepository: Abstract base with connection management
- ProductRepository: Product and inventory operations
- OrderRepository: Order creation and management
- CustomerRepository: Customer CRUD operations
- QueryExecutor: Generic query execution utilities
- MetadataRepository: Lookup data and metadata

Each repository has a single, well-defined responsibility.
"""

from .base import BaseRepository
from .customer_repository import CustomerRepository
from .metadata_repository import MetadataRepository
from .order_repository import OrderRepository
from .product_repository import ProductRepository
from .query_executor import QueryExecutor

__all__ = [
    "BaseRepository",
    "ProductRepository",
    "OrderRepository",
    "CustomerRepository",
    "QueryExecutor",
    "MetadataRepository",
]

# Version information
__version__ = "2.0.0"
__author__ = "Enzo Leonardo Illanez"
__email__ = "enzo@oneclick.cr"
