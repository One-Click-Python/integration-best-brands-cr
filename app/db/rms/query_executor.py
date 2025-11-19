"""
QueryExecutor: Generic SQL query operations for RMS.

Encapsulates custom query execution, pagination, counting, and other
generic SQL operations. Provides safety measures against SQL injection
and performance monitoring. Extracted from legacy RMSHandler following
Single Responsibility Principle.
"""

import logging
import time
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class QueryExecutor(BaseRepository):
    """Repository for generic SQL query operations in RMS."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Track query performance metrics
        self._query_metrics: Dict[str, List[float]] = {}
        self._slow_query_threshold = 5.0  # seconds
        # Cache for shipping item data (populated on first query)
        self._shipping_item_cache: Optional[Dict[str, Any]] = None

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation("verify_table_access_query_executor")
    async def _verify_table_access(self) -> None:
        """
        Verify basic database access. QueryExecutor works with any table,
        so we just verify we can execute a simple query.
        """
        try:
            async with self.conn_db.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                _ = result.scalar()
                logger.info("QueryExecutor: Database access verified")
        except Exception as e:
            logger.error(f"QueryExecutor database access verification failed: {e}")
            raise RMSConnectionException(
                message=f"Cannot access database: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="database_access",
            ) from e

    # ------------------------- Performance tracking -------------------------
    def _track_query_performance(self, query_type: str, duration: float) -> None:
        """Track query execution time for performance monitoring."""
        if query_type not in self._query_metrics:
            self._query_metrics[query_type] = []

        self._query_metrics[query_type].append(duration)

        # Keep only last 100 measurements per query type
        if len(self._query_metrics[query_type]) > 100:
            self._query_metrics[query_type] = self._query_metrics[query_type][-100:]

        # Log slow queries
        if duration > self._slow_query_threshold:
            logger.warning(f"Slow query detected - Type: {query_type}, Duration: {duration:.2f}s")

    def get_query_metrics(self) -> Dict[str, Dict[str, float]]:
        """Get performance metrics for all query types."""
        metrics = {}
        for query_type, durations in self._query_metrics.items():
            if durations:
                metrics[query_type] = {
                    "count": len(durations),
                    "avg_duration": sum(durations) / len(durations),
                    "min_duration": min(durations),
                    "max_duration": max(durations),
                }
        return metrics

    # ------------------------- Core query operations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def execute_custom_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Execute a custom SQL query with parameters.

        WARNING: Use parameterized queries to prevent SQL injection.
        Never concatenate user input directly into query strings.

        Args:
            query: SQL query with named parameters (e.g., :param_name)
            params: Dictionary of parameter values

        Returns:
            List of result rows as dictionaries
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="QueryExecutor not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        start_time = time.time()
        try:
            # Basic SQL injection prevention: warn if query looks suspicious
            if params is None and any(char in query.lower() for char in [";", "--", "/*", "*/", "exec", "xp_"]):
                logger.warning("Potentially unsafe query detected. Consider using parameterized queries.")

            async with self.get_session() as session:
                result = await session.execute(text(query), params or {})
                rows = result.fetchall()

                # Convert rows to dictionaries
                results = [row._asdict() for row in rows]

                duration = time.time() - start_time
                self._track_query_performance("custom_query", duration)

                logger.debug(f"Executed custom query: {len(results)} rows returned in {duration:.2f}s")
                return results

        except Exception as e:
            logger.error(f"Error executing custom query: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute custom query: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="custom_query",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def execute_paginated_query(
        self,
        query: str,
        offset: int,
        limit: int,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute a query with pagination using OFFSET/FETCH.

        Args:
            query: Base SQL query (must include ORDER BY, no OFFSET/FETCH)
            offset: Number of rows to skip
            limit: Maximum number of rows to return
            params: Optional query parameters

        Returns:
            List of paginated results as dictionaries
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="QueryExecutor not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        # Validate that query has ORDER BY (required for OFFSET/FETCH)
        if "order by" not in query.lower():
            raise ValueError("Query must contain ORDER BY clause for pagination in SQL Server")

        # Ensure query doesn't already have OFFSET/FETCH
        if "offset" in query.lower() or "fetch" in query.lower():
            raise ValueError("Query should not contain OFFSET/FETCH clauses - they will be added automatically")

        start_time = time.time()
        try:
            # Add pagination to query
            paginated_query = f"{query} OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

            async with self.get_session() as session:
                result = await session.execute(text(paginated_query), params or {})
                rows = result.fetchall()
                results = [row._asdict() for row in rows]

                duration = time.time() - start_time
                self._track_query_performance("paginated_query", duration)

                logger.debug(
                    f"Paginated query: {len(results)} rows (offset={offset}, limit={limit}) in {duration:.2f}s"
                )
                return results

        except Exception as e:
            logger.error(f"Error executing paginated query: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute paginated query: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="paginated_query",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def count_query_results(
        self,
        base_query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Count total results for a query by converting it to COUNT(*).

        Args:
            base_query: Original SELECT query to count results for
            params: Optional query parameters

        Returns:
            Total count of results
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="QueryExecutor not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        start_time = time.time()
        try:
            # Extract the FROM clause and everything after it
            query_upper = base_query.upper()
            from_index = query_upper.find("FROM")

            if from_index == -1:
                raise ValueError("Query must contain FROM clause")

            # Get everything from FROM onwards
            from_part = base_query[from_index:]

            # Remove ORDER BY if present (not needed for COUNT)
            order_by_index = from_part.upper().find("ORDER BY")
            if order_by_index != -1:
                from_part = from_part[:order_by_index]

            # Remove OFFSET/FETCH if present
            offset_index = from_part.upper().find("OFFSET")
            if offset_index != -1:
                from_part = from_part[:offset_index]

            # Build COUNT query
            count_query = f"SELECT COUNT(*) as total {from_part}"

            async with self.get_session() as session:
                result = await session.execute(text(count_query), params or {})
                row = result.fetchone()
                count = row.total if row else 0

                duration = time.time() - start_time
                self._track_query_performance("count_query", duration)

                logger.debug(f"Count query result: {count} rows in {duration:.2f}s")
                return count

        except Exception as e:
            logger.error(f"Error counting query results: {e}")
            raise RMSConnectionException(
                message=f"Failed to count query results: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="count_query",
            ) from e

    # ------------------------- Utility operations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def find_item_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """
        Find an item in View_Items by SKU (C_ARTICULO field).

        This is a utility method that was in the original RMSHandler
        but didn't fit cleanly into ProductRepository.
        """
        try:
            logger.info(f"Searching for item with SKU: '{sku}' (length: {len(sku)})")

            query = """
            SELECT
                vi.ItemID as item_id,
                vi.Description,
                vi.C_ARTICULO as sku,
                vi.CCOD as ccod,
                vi.Quantity,
                vi.Price as price,
                vi.Tax as tax_percentage,
                i.Cost as cost,
                i.SalePrice as sale_price,
                i.SaleStartDate as sale_start,
                i.SaleEndDate as sale_end,
                i.Taxable as taxable
            FROM View_Items vi
            INNER JOIN Item i ON vi.ItemID = i.ID
            WHERE vi.C_ARTICULO = :sku
            """
            results = await self.execute_custom_query(query, {"sku": sku})

            if results:
                result_item = results[0]
                logger.info(
                    f"Found item for SKU '{sku}': ItemID={result_item.get('item_id')}, "
                    f"Cost={result_item.get('cost')} (type: {type(result_item.get('cost')).__name__})"
                )
                logger.debug(f"Full item data: {result_item}")
                return result_item
            else:
                logger.warning(f"No item found for SKU '{sku}' in View_Items table")

                # Debug: intentar búsqueda parcial para ver si hay items similares
                debug_query = """
                SELECT TOP 5
                    ItemID as item_id,
                    C_ARTICULO as sku,
                    Description
                FROM View_Items
                WHERE C_ARTICULO LIKE :sku_pattern
                """
                debug_results = await self.execute_custom_query(debug_query, {"sku_pattern": f"%{sku}%"})
                if debug_results:
                    logger.info(f"Similar SKUs found: {[r['sku'] for r in debug_results]}")
                else:
                    logger.warning("No similar SKUs found either")

                return None
        except Exception as e:
            logger.error(f"Error finding item by SKU {sku}: {e}", exc_info=True)
            return None

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_shipping_item(self, shipping_item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get shipping item data from VIEW_Items.

        This method queries the shipping item (typically ItemID=481461) to retrieve
        its details including price, tax percentage, cost, and taxable status.
        Used for creating automatic shipping cost OrderEntry records.

        Args:
            shipping_item_id: ItemID for shipping (from config SHIPPING_ITEM_ID)

        Returns:
            Dict with shipping item data:
                - item_id: ItemID
                - Description: Item description ("ENVÍO")
                - price: Base price (WITHOUT tax)
                - tax_percentage: Tax percentage (e.g., 13 for 13%)
                - cost: Item cost
                - taxable: Whether item is taxable (0 or 1)
            Returns None if item not found

        Example:
            {
                'item_id': 481461,
                'Description': 'ENVÍO',
                'price': Decimal('5000.00'),
                'tax_percentage': Decimal('13'),
                'cost': Decimal('0.00'),
                'taxable': 1
            }
        """
        try:
            logger.info(f"Querying shipping item with ItemID: {shipping_item_id}")

            query = """
            SELECT
                vi.ItemID as item_id,
                vi.Description,
                vi.Price as price,
                vi.Tax as tax_percentage,
                i.Cost as cost,
                i.Taxable as taxable
            FROM View_Items vi
            INNER JOIN Item i ON vi.ItemID = i.ID
            WHERE vi.ItemID = :item_id
            """

            results = await self.execute_custom_query(query, {"item_id": shipping_item_id})

            if results:
                shipping_item = results[0]
                logger.info(
                    f"✅ Found shipping item: ItemID={shipping_item['item_id']}, "
                    f"Description='{shipping_item['Description']}', "
                    f"Price={shipping_item['price']}, "
                    f"Tax={shipping_item['tax_percentage']}%"
                )
                return shipping_item
            else:
                logger.warning(
                    f"⚠️ Shipping item with ItemID={shipping_item_id} not found in VIEW_Items. "
                    f"Shipping OrderEntry creation will be skipped for orders."
                )
                return None

        except Exception as e:
            logger.error(f"❌ Error querying shipping item {shipping_item_id}: {e}", exc_info=True)
            return None

    async def get_shipping_item_cached(self, shipping_item_id: int) -> Optional[Dict[str, Any]]:
        """
        Get shipping item data with caching to avoid repeated database queries.

        The shipping item data (e.g., ItemID=481461) is queried once and cached
        for the lifetime of the QueryExecutor instance. This improves performance
        since shipping item data rarely changes.

        Args:
            shipping_item_id: ItemID for shipping (from config SHIPPING_ITEM_ID)

        Returns:
            Cached shipping item dict or None if not found

        Notes:
            - Cache is populated on first call
            - Cache persists for QueryExecutor instance lifetime
            - Returns None if item not found (also cached to avoid repeated failures)
        """
        # Return cached data if available
        if self._shipping_item_cache is not None:
            logger.debug(f"Using cached shipping item data for ItemID={shipping_item_id}")
            return self._shipping_item_cache

        # Query and cache the result
        logger.info(f"Caching shipping item data for ItemID={shipping_item_id}")
        self._shipping_item_cache = await self.get_shipping_item(shipping_item_id)

        if self._shipping_item_cache:
            logger.info("✅ Shipping item data cached successfully")
        else:
            logger.warning(
                "⚠️ Shipping item not found - None cached. "
                "Subsequent order syncs will skip shipping OrderEntry creation."
            )

        return self._shipping_item_cache

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def execute_bulk_insert(
        self,
        table: str,
        rows: List[Dict[str, Any]],
        batch_size: int = 100,
    ) -> int:
        """
        Execute bulk insert operation with batching.

        Args:
            table: Target table name
            rows: List of row dictionaries to insert
            batch_size: Number of rows per batch

        Returns:
            Total number of rows inserted
        """
        if not rows:
            return 0

        if not self.is_initialized():
            raise RMSConnectionException(
                message="QueryExecutor not initialized",
                db_host=settings.RMS_DB_HOST,
            )

        total_inserted = 0
        start_time = time.time()

        try:
            # Process in batches
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]

                # Get column names from first row
                columns = list(batch[0].keys())
                column_list = ", ".join(columns)
                value_placeholders = ", ".join([f":{col}" for col in columns])

                # Build INSERT query
                query = f"""
                INSERT INTO {table} ({column_list})
                VALUES ({value_placeholders})
                """

                async with self.get_session() as session:
                    # Execute batch insert
                    for row in batch:
                        await session.execute(text(query), row)

                    await session.commit()
                    total_inserted += len(batch)

                logger.debug(f"Inserted batch of {len(batch)} rows into {table}")

            duration = time.time() - start_time
            self._track_query_performance("bulk_insert", duration)

            logger.info(f"Bulk insert completed: {total_inserted} rows into {table} in {duration:.2f}s")
            return total_inserted

        except Exception as e:
            logger.error(f"Error executing bulk insert: {e}")
            raise RMSConnectionException(
                message=f"Failed to execute bulk insert: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="bulk_insert",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.

        Args:
            table_name: Name of the table to check

        Returns:
            True if table exists, False otherwise
        """
        try:
            query = """
            SELECT COUNT(*) as count
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_NAME = :table_name
            """
            results = await self.execute_custom_query(query, {"table_name": table_name})
            return results[0]["count"] > 0 if results else False
        except Exception as e:
            logger.error(f"Error checking if table {table_name} exists: {e}")
            return False
