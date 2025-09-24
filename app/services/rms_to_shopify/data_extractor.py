import logging
from decimal import Decimal
from typing import Any, List, Optional

from app.api.v1.schemas.rms_schemas import RMSViewItem
from app.api.v1.schemas.shopify_schemas import ShopifyProductInput
from app.db.rms_handler import RMSHandler
from app.services.variant_mapper import create_products_with_variants
from app.utils.error_handler import SyncException

logger = logging.getLogger(__name__)


class RMSExtractor:
    """Extracts data from RMS."""

    def __init__(self, rms_handler: RMSHandler, shopify_client: Any, primary_location_id: str):
        self.rms_handler = rms_handler
        self.shopify_client = shopify_client
        self.primary_location_id = primary_location_id

    async def count_rms_products(
        self,
        filter_categories: Optional[List[str]] = None,
        ccod: Optional[str] = None,
        include_zero_stock: bool = False,
    ) -> int:
        """
        Counts the number of products in RMS that meet the filter criteria.

        Args:
            filter_categories: Categories to filter by.
            ccod: Specific CCOD to filter by.
            include_zero_stock: Whether to include products with zero stock.

        Returns:
            The total number of products.
        """
        base_query = """
        FROM View_Items
        WHERE CCOD IS NOT NULL
        AND CCOD != ''
        AND C_ARTICULO IS NOT NULL
        AND Description IS NOT NULL
        AND Price > 0
        """

        # Add stock filter if not including zero stock products
        if not include_zero_stock:
            base_query += " AND Quantity > 0"

        if ccod:
            base_query += f" AND CCOD = '{ccod}'"

        if filter_categories:
            categories_str = "', '".join(filter_categories)
            base_query += f" AND Categoria IN ('{categories_str}')"

        count_query = f"SELECT COUNT(DISTINCT CCOD) as total {base_query}"

        try:
            async with self.rms_handler.conn_db.get_session() as session:
                from sqlalchemy import text

                result = await session.execute(text(count_query))
                row = result.fetchone()
                return row.total if row else 0
        except Exception as e:
            logger.error(f"Error counting RMS products: {e}")
            return 0

    async def extract_rms_products_paginated(
        self,
        offset: int,
        limit: int,
        filter_categories: Optional[List[str]] = None,
        ccod: Optional[str] = None,
        include_zero_stock: bool = False,
    ) -> List[ShopifyProductInput]:
        """
        Extracts a paginated list of products from RMS.

        Args:
            offset: The number of products (CCODs) to skip.
            limit: The number of products (CCODs) to extract.
            filter_categories: Categories to filter by.
            ccod: Specific CCOD to filter by.
            include_zero_stock: Whether to include products with zero stock.

        Returns:
            A list of Shopify products with multiple variants for this page.
        """
        try:
            logger.info(f"📄 Extracting RMS products page - Offset: {offset}, Limit: {limit} (products/CCODs)")

            # First, get the CCODs for this page using pagination at the CCOD level
            ccod_query = """
            WITH DistinctCCODs AS (
                SELECT DISTINCT CCOD
                FROM View_Items
                WHERE CCOD IS NOT NULL
                AND CCOD != ''
                AND C_ARTICULO IS NOT NULL
                AND Description IS NOT NULL
                AND Price > 0
            """
            
            # Add stock filter if not including zero stock products
            if not include_zero_stock:
                ccod_query += " AND Quantity > 0"
            
            if ccod:
                ccod_query += f" AND CCOD = '{ccod}'"
            
            if filter_categories:
                categories_str = "', '".join(filter_categories)
                ccod_query += f" AND Categoria IN ('{categories_str}')"
            
            ccod_query += f"""
            )
            SELECT CCOD FROM DistinctCCODs
            ORDER BY CCOD
            OFFSET {offset} ROWS FETCH NEXT {limit} ROWS ONLY
            """
            
            # Get the CCODs for this page
            async with self.rms_handler.conn_db.get_session() as session:
                from sqlalchemy import text
                result = await session.execute(text(ccod_query))
                page_ccods = [row.CCOD for row in result.fetchall()]
            
            if not page_ccods:
                logger.info(f"📊 No CCODs found for page (offset: {offset}, limit: {limit})")
                return []
            
            logger.info(f"📊 Found {len(page_ccods)} CCODs for this page")
            
            # Now get all items for these CCODs
            ccods_str = "', '".join(page_ccods)
            items_query = f"""
            SELECT
                Familia, Genero, Categoria, CCOD, C_ARTICULO,
                ItemID, Description, color, talla, Quantity,
                ROUND(Price * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2) AS Price,
                CASE
                    WHEN SalePrice IS NOT NULL AND SalePrice > 0
                    THEN ROUND(SalePrice * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2)
                    ELSE NULL
                END AS SalePrice,
                ExtendedCategory, Tax,
                SaleStartDate, SaleEndDate
            FROM View_Items
            WHERE CCOD IN ('{ccods_str}')
            ORDER BY CCOD, talla
            """
            
            items_data = await self.rms_handler.execute_custom_query(items_query)
            logger.info(f"📊 Extracted {len(items_data)} items for {len(page_ccods)} products (CCODs) from RMS")

            if not items_data:
                return []

            rms_items = []
            for item_data in items_data:
                try:
                    raw_quantity = item_data.get("Quantity", 0)
                    normalized_quantity = max(0, int(raw_quantity))

                    rms_item = RMSViewItem(
                        familia=item_data.get("Familia", ""),
                        genero=item_data.get("Genero", ""),
                        categoria=item_data.get("Categoria", ""),
                        ccod=item_data.get("CCOD", ""),
                        c_articulo=item_data.get("C_ARTICULO", ""),
                        item_id=item_data.get("ItemID", 0),
                        description=item_data.get("Description", ""),
                        color=item_data.get("color", ""),
                        talla=item_data.get("talla", ""),
                        quantity=normalized_quantity,
                        price=Decimal(str(item_data.get("Price", 0))),
                        sale_price=Decimal(str(item_data.get("SalePrice", 0))) if item_data.get("SalePrice") else None,
                        extended_category=item_data.get("ExtendedCategory", ""),
                        tax=int(item_data.get("Tax", 13)),
                        sale_start_date=item_data.get("SaleStartDate"),
                        sale_end_date=item_data.get("SaleEndDate"),
                    )
                    rms_items.append(rms_item)
                except Exception as e:
                    logger.warning(f"Error processing RMS item: {e}")
                    continue

            shopify_products = await create_products_with_variants(
                rms_items, self.shopify_client, self.primary_location_id
            )

            logger.info(f"🎯 Generated {len(shopify_products)} products from {len(rms_items)} items (page)")
            return shopify_products

        except Exception as e:
            logger.error(f"Error extracting paginated RMS products: {e}")
            raise SyncException(f"Failed to extract paginated RMS products: {e}") from e

    async def extract_rms_products_with_variants(
        self,
        filter_categories: Optional[List[str]] = None,
        ccod: Optional[str] = None,
        include_zero_stock: bool = False,
    ) -> List[ShopifyProductInput]:
        """
        Extracts products from RMS using the new multi-variant system by CCOD.

        Args:
            filter_categories: Categories to filter by.
            ccod: Specific CCOD to sync.
            include_zero_stock: Whether to include products with zero stock.

        Returns:
            A list of Shopify products with multiple variants.
        """
        try:
            logger.info("🔄 Extracting products with multi-variant system by CCOD")

            query = """
            SELECT 
                Familia, Genero, Categoria, CCOD, C_ARTICULO,
                ItemID, Description, color, talla, Quantity,
                ROUND(Price * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2) AS Price,
                CASE 
                    WHEN SalePrice IS NOT NULL AND SalePrice > 0 
                    THEN ROUND(SalePrice * IIF(Tax > 0, 1 + (Tax / 100.0), 1), 2)
                    ELSE NULL
                END AS SalePrice,
                ExtendedCategory, Tax,
                SaleStartDate, SaleEndDate
            FROM View_Items
            WHERE CCOD IS NOT NULL
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            """

            # Add stock filter if not including zero stock products
            if not include_zero_stock:
                query += " AND Quantity > 0"

            if ccod:
                query += f" AND CCOD = '{ccod}'"

            if filter_categories:
                categories_str = "', '".join(filter_categories)
                query += f" AND Categoria IN ('{categories_str}')"

            query += " ORDER BY CCOD, talla"

            logger.info("📋 Executing query to extract items from RMS...")
            items_data = await self.rms_handler.execute_custom_query(query)
            logger.info(f"📊 Extracted {len(items_data)} items from RMS")

            ccods_extracted = set(item.get("CCOD") for item in items_data if item.get("CCOD"))
            logger.info(f"📋 Unique CCODs extracted: {len(ccods_extracted)}")

            rms_items = []
            negative_quantity_count = 0
            for item_data in items_data:
                try:
                    raw_quantity = item_data.get("Quantity", 0)
                    normalized_quantity = max(0, int(raw_quantity))

                    if raw_quantity < 0:
                        negative_quantity_count += 1
                        c_articulo = item_data.get("C_ARTICULO", "unknown")
                        logger.debug(
                            f"📊 Negative quantity normalized: {raw_quantity} → {normalized_quantity}\
                                para item {c_articulo}"
                        )

                    rms_item = RMSViewItem(
                        familia=item_data.get("Familia", ""),
                        genero=item_data.get("Genero", ""),
                        categoria=item_data.get("Categoria", ""),
                        ccod=item_data.get("CCOD", ""),
                        c_articulo=item_data.get("C_ARTICULO", ""),
                        item_id=item_data.get("ItemID", 0),
                        description=item_data.get("Description", ""),
                        color=item_data.get("color", ""),
                        talla=item_data.get("talla", ""),
                        quantity=normalized_quantity,
                        price=Decimal(str(item_data.get("Price", 0))),
                        sale_price=Decimal(str(item_data.get("SalePrice", 0))) if item_data.get("SalePrice") else None,
                        extended_category=item_data.get("ExtendedCategory", ""),
                        tax=int(item_data.get("Tax", 13)),
                        sale_start_date=item_data.get("SaleStartDate"),
                        sale_end_date=item_data.get("SaleEndDate"),
                    )
                    rms_items.append(rms_item)
                except Exception as e:
                    logger.warning(f"❌ --> (RMSViewItem) Error processing RMS item: {e}")
                    continue

            logger.info(f"✅ Processed {len(rms_items)} valid items from RMS")
            if negative_quantity_count > 0:
                logger.info(f"📊 Normalized {negative_quantity_count} negative quantities to 0")

            logger.info("🔄 Grouping items by CCOD and creating products with variants...")
            shopify_products = await create_products_with_variants(
                rms_items, self.shopify_client, self.primary_location_id
            )

            logger.info(f"🎯 Generated {len(shopify_products)} products with multiple variants")
            logger.info(f"📈 Reduction: {len(rms_items)} items → {len(shopify_products)} products")

            return shopify_products

        except Exception as e:
            logger.error(f"❌ Error extracting RMS products with variants: {e}")
            raise SyncException(f"Failed to extract RMS products: {e}") from e
