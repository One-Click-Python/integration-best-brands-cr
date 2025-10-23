"""
RMS Handler Facade - DEPRECATED - Legacy Compatibility Layer.

⚠️ COMPLETE DEPRECATION ⚠️
This facade is COMPLETELY DEPRECATED and is NO LONGER USED anywhere in the project.

🎯 PURPOSE:
This file is maintained only as a reference implementation showing how the
legacy monolithic handler was structured before migration to SOLID repositories.

✅ MIGRATION STATUS: 100% COMPLETE
- RMS → Shopify sync: MIGRATED to SOLID repositories ✅
- Shopify → RMS sync: MIGRATED to SOLID repositories ✅
- Order orchestration: MIGRATED to SOLID orchestrator ✅
- Scripts & utilities: MIGRATED to QueryExecutor ✅
- Tests: Never used RMSHandler ✅

📚 SOLID REPOSITORIES (Use these instead):
- QueryExecutor: Custom SQL queries and generic operations
- ProductRepository: Product and inventory operations
- OrderRepository: Order creation, updates, and management
- CustomerRepository: Customer operations and resolution
- MetadataRepository: Lookup data with intelligent caching

🔧 FOR NEW CODE:
DO NOT import or use RMSHandler. Always use the specialized repositories above.

This facade delegates all operations to the SOLID repositories while maintaining
the exact same interface as the legacy monolithic implementation.

For reference only - not for production use.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from warnings import warn

from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry, RMSViewItem
from app.core.config import get_settings
from app.db.rms import (
    CustomerRepository,
    MetadataRepository,
    OrderRepository,
    ProductRepository,
    QueryExecutor,
)
from app.utils.error_handler import RMSConnectionException

settings = get_settings()
logger = logging.getLogger(__name__)


class RMSHandler:
    """
    Facade for RMS operations - Maintains backward compatibility.

    This class delegates all operations to specialized repositories while
    maintaining the exact same interface as the legacy implementation.

    DEPRECATION WARNING: This facade is provided for backward compatibility.
    New code should use the repositories directly:
    - ProductRepository for product/inventory operations
    - OrderRepository for order operations
    - CustomerRepository for customer operations
    - MetadataRepository for lookup data
    - QueryExecutor for generic SQL operations
    """

    def __init__(self, suppress_warning: bool = False):
        """Initialize the RMS handler facade with lazy-loaded repositories.

        Args:
            suppress_warning: If True, suppresses the deprecation warning.
                            Used internally to avoid warnings in compatibility functions.
        """
        # Lazy-loaded repository instances
        self._product_repo: Optional[ProductRepository] = None
        self._order_repo: Optional[OrderRepository] = None
        self._customer_repo: Optional[CustomerRepository] = None
        self._metadata_repo: Optional[MetadataRepository] = None
        self._query_executor: Optional[QueryExecutor] = None
        self._initialized = False

        # Issue deprecation warning only for external usage
        if not suppress_warning:
            warn(
                "RMSHandler is deprecated. Use individual repositories directly: "
                "ProductRepository, OrderRepository, CustomerRepository, etc.",
                DeprecationWarning,
                stacklevel=2,
            )

        logger.info("RMSHandler facade initialized")

    # ============= Properties for Lazy Loading =============

    @property
    def product_repo(self) -> ProductRepository:
        """Get or create ProductRepository instance."""
        if self._product_repo is None:
            self._product_repo = ProductRepository()
        return self._product_repo

    @property
    def order_repo(self) -> OrderRepository:
        """Get or create OrderRepository instance."""
        if self._order_repo is None:
            self._order_repo = OrderRepository()
        return self._order_repo

    @property
    def customer_repo(self) -> CustomerRepository:
        """Get or create CustomerRepository instance."""
        if self._customer_repo is None:
            self._customer_repo = CustomerRepository()
        return self._customer_repo

    @property
    def metadata_repo(self) -> MetadataRepository:
        """Get or create MetadataRepository instance."""
        if self._metadata_repo is None:
            self._metadata_repo = MetadataRepository()
        return self._metadata_repo

    @property
    def query_executor(self) -> QueryExecutor:
        """Get or create QueryExecutor instance."""
        if self._query_executor is None:
            self._query_executor = QueryExecutor()
        return self._query_executor

    # ============= Lifecycle Methods =============

    async def initialize(self):
        """Initialize all repositories."""
        try:
            # Initialize all repositories
            await self.product_repo.initialize()
            await self.order_repo.initialize()
            await self.customer_repo.initialize()
            await self.metadata_repo.initialize()
            await self.query_executor.initialize()

            self._initialized = True
            logger.info("RMSHandler facade initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RMSHandler facade: {e}")
            raise RMSConnectionException(
                message=f"Failed to initialize RMS handler facade: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_initialization",
            ) from e

    async def close(self):
        """Close all repositories."""
        try:
            if self._product_repo:
                await self._product_repo.close()
            if self._order_repo:
                await self._order_repo.close()
            if self._customer_repo:
                await self._customer_repo.close()
            if self._metadata_repo:
                await self._metadata_repo.close()
            if self._query_executor:
                await self._query_executor.close()

            self._initialized = False
            logger.info("RMSHandler facade closed")
        except Exception as e:
            logger.error(f"Error closing RMSHandler facade: {e}")

    def is_initialized(self) -> bool:
        """Check if the handler is initialized."""
        return self._initialized

    # ============= Product Repository Methods (Delegated) =============

    async def get_view_items_since(
        self,
        since_timestamp: Optional[datetime] = None,
        category_filter: Optional[List[str]] = None,
        family_filter: Optional[List[str]] = None,
        gender_filter: Optional[List[str]] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_zero_stock: bool = False,
    ) -> List[RMSViewItem]:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_view_items_since(
            since_timestamp, category_filter, family_filter, gender_filter, limit, offset, include_zero_stock
        )

    async def get_view_items(
        self,
        category_filter: Optional[List[str]] = None,
        family_filter: Optional[List[str]] = None,
        gender_filter: Optional[List[str]] = None,
        incremental_hours: Optional[int] = None,
        limit: Optional[int] = None,
        offset: int = 0,
        include_zero_stock: bool = False,
    ) -> List[RMSViewItem]:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_view_items(
            category_filter, family_filter, gender_filter, incremental_hours, limit, offset, include_zero_stock
        )

    def _apply_filters(self, *args, **kwargs):
        """Legacy method - delegates to ProductRepository."""
        # This is a private method, included for compatibility
        return self.product_repo._apply_filters(*args, **kwargs)

    async def get_product_by_sku(self, sku: str) -> Optional[RMSViewItem]:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_product_by_sku(sku)

    async def get_products_by_ccod(self, ccod: str) -> List[RMSViewItem]:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_products_by_ccod(ccod)

    async def count_view_items_since(
        self,
        since_timestamp: Optional[datetime] = None,
        category_filter: Optional[List[str]] = None,
        include_zero_stock: bool = False,
    ) -> int:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.count_view_items_since(since_timestamp, category_filter, include_zero_stock)

    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_inventory_summary()

    async def get_item_stock(self, item_id: int) -> int:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.product_repo.get_item_stock(item_id)

    async def update_item_stock(self, item_id: int, quantity_change: int) -> None:
        """Delegate to ProductRepository."""
        if not self._initialized:
            await self.initialize()
        await self.product_repo.update_item_stock(item_id, quantity_change)

    # ============= Order Repository Methods (Delegated) =============

    async def create_order(self, order: RMSOrder) -> int:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.order_repo.create_order(order)

    async def create_order_entry(self, entry: RMSOrderEntry) -> int:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.order_repo.create_order_entry(entry)

    async def find_order_by_shopify_id(self, shopify_order_id: str) -> Optional[Dict[str, Any]]:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.order_repo.find_order_by_shopify_id(shopify_order_id)

    async def update_order(self, order_id: int, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.order_repo.update_order(order_id, order_data)

    async def get_order_entries(self, order_id: int) -> List[Dict[str, Any]]:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.order_repo.get_order_entries(order_id)

    async def update_order_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> None:
        """Delegate to OrderRepository."""
        if not self._initialized:
            await self.initialize()
        await self.order_repo.update_order_entry(entry_id, entry_data)

    # ============= Customer Repository Methods (Delegated) =============

    async def find_customer_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Delegate to CustomerRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.customer_repo.find_customer_by_email(email)

    async def create_customer(self, customer_data: Dict[str, Any]) -> int:
        """Delegate to CustomerRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.customer_repo.create_customer(customer_data)

    # ============= Metadata Repository Methods (Delegated) =============

    async def get_categories(self) -> List[str]:
        """Delegate to MetadataRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.metadata_repo.get_categories()

    async def get_families(self) -> List[str]:
        """Delegate to MetadataRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.metadata_repo.get_families()

    async def get_genders(self) -> List[str]:
        """Delegate to MetadataRepository."""
        if not self._initialized:
            await self.initialize()
        return await self.metadata_repo.get_genders()

    # ============= Query Executor Methods (Delegated) =============

    async def execute_custom_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Delegate to QueryExecutor."""
        if not self._initialized:
            await self.initialize()
        return await self.query_executor.execute_custom_query(query, params)

    async def execute_paginated_query(
        self,
        query: str,
        offset: int,
        limit: int,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Delegate to QueryExecutor."""
        if not self._initialized:
            await self.initialize()
        return await self.query_executor.execute_paginated_query(query, offset, limit, params)

    async def count_query_results(
        self,
        base_query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Delegate to QueryExecutor."""
        if not self._initialized:
            await self.initialize()
        return await self.query_executor.count_query_results(base_query, params)

    async def find_item_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Delegate to QueryExecutor."""
        if not self._initialized:
            await self.initialize()
        return await self.query_executor.find_item_by_sku(sku)


# ============= Module-level compatibility functions =============

# Global handler instance for compatibility
_global_handler: Optional[RMSHandler] = None


async def initialize_rms_handler() -> RMSHandler:
    """
    Initialize and return a global RMSHandler instance.

    This function provides backward compatibility with existing code
    that expects a module-level initialization function.

    Returns:
        RMSHandler: Initialized global handler instance
    """
    global _global_handler

    if _global_handler is None:
        _global_handler = RMSHandler(suppress_warning=True)
        await _global_handler.initialize()

    return _global_handler


async def test_rms_connection() -> bool:
    """
    Test RMS database connection.

    This function provides backward compatibility with existing code
    that expects a module-level test function.

    Returns:
        bool: True if connection is successful, False otherwise
    """
    try:
        handler = RMSHandler(suppress_warning=True)
        await handler.initialize()
        await handler.close()
        return True
    except Exception as e:
        logger.error(f"RMS connection test failed: {e}")
        return False


def get_rms_handler() -> RMSHandler:
    """
    Get the global RMSHandler instance.

    Returns:
        RMSHandler: Global handler instance (may not be initialized)
    """
    global _global_handler

    if _global_handler is None:
        _global_handler = RMSHandler(suppress_warning=True)

    return _global_handler
