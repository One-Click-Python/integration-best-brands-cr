"""
ProductRepository: Product and inventory operations for RMS.

This repository encapsulates all read/write operations related to products and
inventory in RMS, extracted from the legacy RMSHandler to comply with SRP.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class ProductRepository(BaseRepository):
    """Repository for product and inventory operations in RMS."""

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation("verify_table_access_products")
    async def _verify_table_access(self) -> None:
        """Verify access to product-related tables (View_Items, Item)."""
        try:
            async with self.conn_db.get_session() as session:
                # Verify View_Items
                result = await session.execute(text("SELECT COUNT(*) FROM View_Items"))
                _ = result.scalar()
                # Verify Item
                result = await session.execute(text("SELECT COUNT(*) FROM Item"))
                _ = result.scalar()
        except Exception as e:
            logger.error(f"ProductRepository table access verification failed: {e}")
            raise RMSConnectionException(
                message=f"Cannot access product tables: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="table_access_products",
            ) from e

    # ------------------------- Query helpers -------------------------
    def _apply_filters(
        self,
        query: str,
        params: Dict[str, Any],
        category_filter: Optional[List[str]],
        family_filter: Optional[List[str]],
        gender_filter: Optional[List[str]],
        incremental_hours: Optional[int],
        time_field: str = "LastModified",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Apply dynamic filters to a SQL query for View_Items-like datasets.

        Args:
            query: Base SQL query fragment (already has WHERE 1=1 or equivalent)
            params: Current parameters dict to be extended
            category_filter: List of categories to include
            family_filter: List of families to include
            gender_filter: List of genders to include
            incremental_hours: If provided, filter by items modified within last N hours
            time_field: Column to use for incremental time filtering

        Returns:
            Tuple of (modified_query, updated_params)
        """
        # Categories
        if category_filter:
            placeholders = ", ".join([f":cat_{i}" for i in range(len(category_filter))])
            query += f" AND Categoria IN ({placeholders})"
            for i, cat in enumerate(category_filter):
                params[f"cat_{i}"] = cat

        # Families
        if family_filter:
            placeholders = ", ".join([f":fam_{i}" for i in range(len(family_filter))])
            query += f" AND Familia IN ({placeholders})"
            for i, fam in enumerate(family_filter):
                params[f"fam_{i}"] = fam

        # Genders
        if gender_filter:
            placeholders = ", ".join([f":gen_{i}" for i in range(len(gender_filter))])
            query += f" AND Genero IN ({placeholders})"
            for i, gen in enumerate(gender_filter):
                params[f"gen_{i}"] = gen

        # Incremental time filter
        if incremental_hours:
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=incremental_hours)
            query += f" AND {time_field} >= :cutoff_time"
            params["cutoff_time"] = cutoff_time

        return query, params

    # ------------------------- Read operations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
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
        """
        Get products modified since a specific timestamp using Item.LastUpdated.
        """
        if not self.is_initialized():
            raise RMSConnectionException(
                message="ProductRepository not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    v.Familia as familia,
                    v.Genero as genero, 
                    v.Categoria as categoria,
                    v.CCOD as ccod,
                    v.C_ARTICULO as c_articulo,
                    v.ItemID as item_id,
                    v.Description as description,
                    v.color,
                    v.talla,
                    v.Quantity as quantity,
                    v.Price as price,
                    v.SaleStartDate as sale_start_date,
                    v.SaleEndDate as sale_end_date, 
                    v.SalePrice as sale_price,
                    v.ExtendedCategory as extended_category,
                    v.Tax as tax,
                    v.Exis00 as exis00,
                    v.Exis57 as exis57
                FROM View_Items v
                """
                params: Dict[str, Any] = {}

                if since_timestamp:
                    query += """
                    INNER JOIN Item i ON v.ItemID = i.ID
                    WHERE i.LastUpdated > :since_timestamp
                    """
                    params["since_timestamp"] = since_timestamp
                else:
                    query += " WHERE 1=1"

                query, params = self._apply_filters(
                    query,
                    params,
                    category_filter,
                    family_filter,
                    gender_filter,
                    None,
                )

                query += " AND v.C_ARTICULO IS NOT NULL AND v.Description IS NOT NULL"
                query += " AND v.Price > 0"
                if not include_zero_stock:
                    query += " AND v.Quantity > 0"

                query += " ORDER BY v.ItemID"
                if limit:
                    query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

                if since_timestamp:
                    logger.info(f"Executing View_Items query for items modified since {since_timestamp}")
                else:
                    logger.debug(f"Executing View_Items query (no since) with {len(params)} parameters")

                result = await session.execute(text(query), params)
                rows = result.fetchall()

                products: List[RMSViewItem] = []
                for row in rows:
                    try:
                        row_dict = row._asdict()
                        products.append(RMSViewItem(**row_dict))
                    except Exception as e:
                        logger.warning(
                            f"Error converting row to RMSViewItem: {e} - SKU: {getattr(row, 'c_articulo', 'UNKNOWN')}"
                        )
                        continue

                logger.info(
                    f"Retrieved {len(products)} products from View_Items"
                    + (f" modified since {since_timestamp}" if since_timestamp else "")
                )
                return products
        except Exception as e:
            logger.error(f"Error retrieving products from View_Items: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve products: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
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
        """Retrieve products from View_Items with optional filters and pagination."""
        if not self.is_initialized():
            raise RMSConnectionException(
                message="ProductRepository not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE 1=1
                """
                params: Dict[str, Any] = {}

                query, params = self._apply_filters(
                    query,
                    params,
                    category_filter,
                    family_filter,
                    gender_filter,
                    incremental_hours,
                )

                query += " AND C_ARTICULO IS NOT NULL AND Description IS NOT NULL"
                query += " AND Price > 0"
                if not include_zero_stock:
                    query += " AND Quantity > 0"

                query += " ORDER BY ItemID"
                if limit:
                    query += f" OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY"

                logger.debug(
                    f"Executing View_Items query with {len(params)} parameters (incremental_hours={incremental_hours})"
                )

                result = await session.execute(text(query), params)
                rows = result.fetchall()

                products: List[RMSViewItem] = []
                for row in rows:
                    try:
                        products.append(RMSViewItem(**row._asdict()))
                    except Exception as e:
                        logger.warning(
                            f"Error converting row to RMSViewItem: {e} - SKU: {getattr(row, 'c_articulo', 'UNKNOWN')}"
                        )
                        continue

                logger.info(f"Retrieved {len(products)} products from View_Items")
                return products
        except Exception as e:
            logger.error(f"Error retrieving products from View_Items: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve products: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="query_execution",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_product_by_sku(self, sku: str) -> Optional[RMSViewItem]:
        """Get a specific product by SKU (C_ARTICULO)."""
        if not self.is_initialized():
            raise RMSConnectionException(
                message="ProductRepository not initialized",
                db_host=settings.RMS_DB_HOST,
            )
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE C_ARTICULO = :sku
                """
                result = await session.execute(text(query), {"sku": sku})
                row = result.fetchone()
                if row:
                    return RMSViewItem(**row._asdict())
                return None
        except Exception as e:
            logger.error(f"Error retrieving product by SKU {sku}: {e}")
            raise RMSConnectionException(
                message=f"Failed to retrieve product by SKU: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="single_product_query",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_products_by_ccod(self, ccod: str) -> List[RMSViewItem]:
        """Get all product variants by CCOD."""
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    Familia as familia,
                    Genero as genero, 
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date, 
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items 
                WHERE CCOD = :ccod
                ORDER BY C_ARTICULO
                """
                result = await session.execute(text(query), {"ccod": ccod})
                rows = result.fetchall()
                products: List[RMSViewItem] = []
                for row in rows:
                    try:
                        products.append(RMSViewItem(**row._asdict()))
                    except Exception as e:
                        logger.warning(f"Error converting row to RMSViewItem: {e}")
                        continue
                return products
        except Exception as e:
            logger.error(f"Error retrieving products by CCOD {ccod}: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_zero_stock_variants_by_ccod(self, ccod: str) -> List[RMSViewItem]:
        """
        Get all product variants with zero stock for a specific CCOD.

        This is used to identify variants that should be removed from Shopify
        since they have no stock in RMS.

        Args:
            ccod: Product code (CCOD) to search for

        Returns:
            List of RMSViewItem objects with Quantity = 0
        """
        try:
            async with self.get_session() as session:
                query = """
                SELECT
                    Familia as familia,
                    Genero as genero,
                    Categoria as categoria,
                    CCOD as ccod,
                    C_ARTICULO as c_articulo,
                    ItemID as item_id,
                    Description as description,
                    color,
                    talla,
                    Quantity as quantity,
                    Price as price,
                    SaleStartDate as sale_start_date,
                    SaleEndDate as sale_end_date,
                    SalePrice as sale_price,
                    ExtendedCategory as extended_category,
                    Tax as tax,
                    Exis00 as exis00,
                    Exis57 as exis57
                FROM View_Items
                WHERE CCOD = :ccod AND Quantity = 0
                ORDER BY C_ARTICULO
                """
                result = await session.execute(text(query), {"ccod": ccod})
                rows = result.fetchall()
                products: List[RMSViewItem] = []
                for row in rows:
                    try:
                        products.append(RMSViewItem(**row._asdict()))
                    except Exception as e:
                        logger.warning(f"Error converting row to RMSViewItem: {e}")
                        continue

                if products:
                    logger.info(
                        f"Found {len(products)} zero-stock variants for CCOD {ccod}: "
                        f"{[p.c_articulo for p in products]}"
                    )

                return products
        except Exception as e:
            logger.error(f"Error retrieving zero-stock variants for CCOD {ccod}: {e}")
            return []

    # ------------------------- Counting/Aggregations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def count_view_items_since(
        self,
        since_timestamp: Optional[datetime] = None,
        category_filter: Optional[List[str]] = None,
        include_zero_stock: bool = False,
    ) -> int:
        """Count products modified since a specific timestamp."""
        if not self.is_initialized():
            raise RMSConnectionException(
                message="ProductRepository not initialized",
                db_host=settings.RMS_DB_HOST,
                connection_type="handler_not_initialized",
            )
        try:
            async with self.get_session() as session:
                query = "SELECT COUNT(DISTINCT v.CCOD) as total FROM View_Items v"
                params: Dict[str, Any] = {}

                if since_timestamp:
                    query += " INNER JOIN Item i ON v.ItemID = i.ID WHERE i.LastUpdated > :since_timestamp"
                    params["since_timestamp"] = since_timestamp
                else:
                    query += " WHERE 1=1"

                query += " AND v.C_ARTICULO IS NOT NULL AND v.Description IS NOT NULL AND v.Price > 0"
                if not include_zero_stock:
                    query += " AND v.Quantity > 0"

                if category_filter:
                    placeholders = ", ".join([f":cat_{i}" for i in range(len(category_filter))])
                    query += f" AND v.Categoria IN ({placeholders})"
                    for i, cat in enumerate(category_filter):
                        params[f"cat_{i}"] = cat

                result = await session.execute(text(query), params)
                row = result.fetchone()
                count = row.total if row else 0
                logger.info(
                    f"Found {count} products" + (f" modified since {since_timestamp}" if since_timestamp else "")
                )
                return count
        except Exception as e:
            logger.error(f"Error counting products: {e}")
            return 0

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_inventory_summary(self) -> Dict[str, Any]:
        """Get inventory summary across View_Items."""
        try:
            async with self.get_session() as session:
                query = """
                SELECT 
                    COUNT(*) as total_products,
                    SUM(CASE WHEN Quantity > 0 THEN 1 ELSE 0 END) as products_with_stock,
                    SUM(Quantity) as total_quantity,
                    COUNT(DISTINCT Categoria) as unique_categories,
                    COUNT(DISTINCT Familia) as unique_families,
                    COUNT(DISTINCT CCOD) as unique_models
                FROM View_Items
                WHERE C_ARTICULO IS NOT NULL
                """
                result = await session.execute(text(query))
                row = result.fetchone()
                if row:
                    return row._asdict()
                return {}
        except Exception as e:
            logger.error(f"Error getting inventory summary: {e}")
            return {}

    # ------------------------- Stock operations -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_item_stock(self, item_id: int) -> int:
        """Get current stock for an item by ID."""
        try:
            async with self.get_session() as session:
                query = """
                SELECT Quantity FROM Item 
                WHERE ID = :item_id
                """
                result = await session.execute(text(query), {"item_id": item_id})
                row = result.fetchone()
                return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error getting stock for item {item_id}: {e}")
            return 0

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_item_stock(self, item_id: int, quantity_change: int) -> None:
        """Update stock quantity for an item by delta (can be negative)."""
        try:
            async with self.get_session() as session:
                query = """
                UPDATE Item 
                SET Quantity = Quantity + :quantity_change
                WHERE ID = :item_id
                """
                await session.execute(
                    text(query),
                    {"item_id": item_id, "quantity_change": quantity_change},
                )
                await session.commit()
                logger.info(f"Updated stock for item {item_id}: {quantity_change:+d}")
        except Exception as e:
            logger.error(f"Error updating stock for item {item_id}: {e}")
            raise
