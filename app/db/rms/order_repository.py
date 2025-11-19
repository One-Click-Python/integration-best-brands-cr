"""
OrderRepository: Order and order-entry operations for RMS.

Encapsulates creation, updates, retrieval, and Shopify-related lookups for orders
and order entries. Extracted from the legacy RMSHandler to comply with SRP.
"""

import logging
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry
from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class OrderRepository(BaseRepository):
    """Repository for order and order-entry operations in RMS."""

    # Mapping from Python snake_case to RMS PascalCase column names
    ORDER_COLUMN_MAP = {
        "store_id": "StoreID",
        "time": "Time",
        "type": "Type",
        "customer_id": "CustomerID",
        "deposit": "Deposit",
        "tax": "Tax",
        "total": "Total",
        "sales_rep_id": "SalesRepID",
        "shipping_service_id": "ShippingServiceID",
        "shipping_tracking_number": "ShippingTrackingNumber",
        "comment": "Comment",
        "shipping_notes": "ShippingNotes",
        "reference_number": "ReferenceNumber",
        "channel_type": "ChannelType",
        "closed": "Closed",
        "shipping_charge_on_order": "ShippingChargeOnOrder",
        "last_updated": "LastUpdated",  # Auto-update timestamp on modifications
    }

    # Mapping for OrderEntry columns
    ORDER_ENTRY_COLUMN_MAP = {
        "order_id": "OrderID",
        "item_id": "ItemID",
        "store_id": "StoreID",
        "price": "Price",
        "full_price": "FullPrice",
        "cost": "Cost",
        "quantity_on_order": "QuantityOnOrder",
        "quantity_rtd": "QuantityRTD",
        "sales_rep_id": "SalesRepID",
        "discount_reason_code_id": "DiscountReasonCodeID",
        "return_reason_code_id": "ReturnReasonCodeID",
        "description": "Description",
        "taxable": "Taxable",
        "is_add_money": "IsAddMoney",
        "voucher_id": "VoucherID",
        "comment": "Comment",  # "Shipping Item" para envíos
        "price_source": "PriceSource",  # 10 para envíos, 1 para productos
        "last_updated": "LastUpdated",  # Auto-update timestamp on modifications
    }

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation("verify_table_access_orders")
    async def _verify_table_access(self) -> None:
        """Verify access to order-related tables ([Order], OrderEntry)."""
        try:
            async with self.conn_db.get_session() as session:
                # Verify [Order]
                result = await session.execute(text("SELECT COUNT(*) FROM [Order]"))
                _ = result.scalar()
                # Verify OrderEntry
                result = await session.execute(text("SELECT COUNT(*) FROM OrderEntry"))
                _ = result.scalar()
        except Exception as e:
            logger.error(f"OrderRepository table access verification failed: {e}")
            raise RMSConnectionException(
                message=f"Cannot access order tables: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="table_access_orders",
            ) from e

    # ------------------------- Order creation -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def create_order(self, order: RMSOrder) -> int:
        """Create a new order in RMS and return its ID."""
        if not self.is_initialized():
            raise RMSConnectionException(message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST)
        try:
            async with self.get_session() as session:
                # ✨ Set LastUpdated for new order creation
                last_updated = datetime.now(UTC)

                query = """
                INSERT INTO [Order] (
                    StoreID, Time, Type, CustomerID, Deposit, Tax, Total,
                    SalesRepID, ShippingServiceID, ShippingTrackingNumber,
                    Comment, ShippingNotes,
                    ReferenceNumber, ChannelType, Closed, ShippingChargeOnOrder,
                    LastUpdated
                )
                OUTPUT INSERTED.ID
                VALUES (
                    :store_id, :time, :type, :customer_id, :deposit, :tax, :total,
                    :sales_rep_id, :shipping_service_id, :shipping_tracking_number,
                    :comment, :shipping_notes,
                    :reference_number, :channel_type, :closed, :shipping_charge_on_order,
                    :last_updated
                )
                """

                params = {
                    "store_id": order.store_id,
                    "time": order.time,
                    "type": order.type,
                    "customer_id": order.customer_id,
                    "deposit": float(order.deposit),
                    "tax": float(order.tax),
                    "total": float(order.total),
                    "sales_rep_id": order.sales_rep_id,
                    "shipping_service_id": order.shipping_service_id,
                    "shipping_tracking_number": order.shipping_tracking_number,
                    "comment": order.comment,
                    "shipping_notes": order.shipping_notes,
                    "reference_number": order.reference_number,
                    "channel_type": order.channel_type,
                    "closed": order.closed,
                    "shipping_charge_on_order": (
                        float(order.shipping_charge_on_order) if order.shipping_charge_on_order else 0.0
                    ),
                    "last_updated": last_updated,
                }

                # 🔍 Logging de depuración - valores antes del INSERT
                logger.info(
                    f"🔍 SQL params for INSERT: "
                    f"total={params['total']}, tax={params['tax']}, "
                    f"deposit={params['deposit']}, shipping={params['shipping_charge_on_order']}"
                )

                result = await session.execute(text(query), params)
                order_id = result.scalar()
                if not order_id:
                    raise RMSConnectionException(
                        message="Order creation did not return an ID",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="order_creation",
                    )

                # 🔍 Verificar valores inmediatamente después del INSERT
                verify_query = "SELECT Total, Tax, Deposit FROM [Order] WHERE ID = :order_id"
                verify_result = await session.execute(text(verify_query), {"order_id": order_id})
                verify_data = verify_result.fetchone()

                if verify_data:
                    logger.info(
                        f"✅ Order {order_id} verification - "
                        f"Expected: Total={params['total']}, Tax={params['tax']} | "
                        f"Actual DB: Total={verify_data.Total}, Tax={verify_data.Tax}"
                    )

                    # Alertar si hay discrepancia
                    if abs(float(verify_data.Total) - params["total"]) > 0.01:
                        logger.error(f"❌ Order.Total mismatch! Expected {params['total']}, got {verify_data.Total}")
                    if abs(float(verify_data.Tax) - params["tax"]) > 0.01:
                        logger.error(f"❌ Order.Tax mismatch! Expected {params['tax']}, got {verify_data.Tax}")

                await session.commit()
                logger.info(f"Created order in RMS with ID: {order_id}")
                return int(order_id)
        except Exception as e:
            logger.error(f"Error creating order in RMS: {e}")
            raise RMSConnectionException(
                message=f"Failed to create order: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_creation",
            ) from e

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def create_order_entry(self, entry: RMSOrderEntry, session: Optional[AsyncSession] = None) -> int:
        """
        Create a new order entry (line item) in RMS and return its ID.

        Args:
            entry: Order entry data
            session: Optional shared session for atomic transactions
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST)
        try:
            if session:
                return await self._create_order_entry_impl(session, entry)
            else:
                async with self.get_session() as new_session:
                    entry_id = await self._create_order_entry_impl(new_session, entry)
                    await new_session.commit()
                    return entry_id
        except Exception as e:
            logger.error(f"Error creating order entry in RMS: {e}")
            raise RMSConnectionException(
                message=f"Failed to create order entry: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_entry_creation",
            ) from e

    async def _create_order_entry_impl(self, session: AsyncSession, entry: RMSOrderEntry) -> int:
        """Internal implementation of create_order_entry."""
        # ✨ Set LastUpdated for new entry creation
        last_updated = datetime.now(UTC)

        query = """
        INSERT INTO OrderEntry (
            OrderID, ItemID, StoreId, Price, FullPrice, Cost,
            QuantityOnOrder, QuantityRTD, SalesRepID,
            DiscountReasonCodeID, ReturnReasonCodeID,
            Description, Taxable, IsAddMoney, VoucherID,
            Comment, PriceSource, LastUpdated
        )
        OUTPUT INSERTED.ID
        VALUES (
            :order_id, :item_id, :store_id, :price, :full_price, :cost,
            :quantity_on_order, :quantity_rtd, :sales_rep_id,
            :discount_reason_code_id, :return_reason_code_id,
            :description, :taxable, :is_add_money, :voucher_id,
            :comment, :price_source, :last_updated
        )
        """

        params = {
            "order_id": entry.order_id,
            "item_id": entry.item_id,
            "store_id": entry.store_id,
            "price": float(entry.price),
            "full_price": float(entry.full_price),
            "cost": float(entry.cost),
            "quantity_on_order": entry.quantity_on_order,
            "quantity_rtd": entry.quantity_rtd,
            "sales_rep_id": entry.sales_rep_id,
            "discount_reason_code_id": entry.discount_reason_code_id,
            "return_reason_code_id": entry.return_reason_code_id,
            "description": entry.description,
            "taxable": entry.taxable,
            "is_add_money": entry.is_add_money,
            "voucher_id": entry.voucher_id,
            "comment": entry.comment,  # "Shipping Item" for shipping entries
            "price_source": entry.price_source,  # 10 for shipping, 1 for products
            "last_updated": last_updated,
        }

        result = await session.execute(text(query), params)
        entry_id = result.scalar()
        if not entry_id:
            raise RMSConnectionException(
                message="Order entry creation did not return an ID",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_entry_creation",
            )

        logger.info(f"Created order entry in RMS with ID: {entry_id}")
        return int(entry_id)

    # ------------------------- Retrieval and updates -------------------------
    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def find_order_by_shopify_id(self, shopify_order_id: str) -> Optional[Dict[str, Any]]:
        """Find an RMS order by Shopify order ID via ReferenceNumber and ChannelType."""
        try:
            async with self.get_session() as session:
                reference_number = f"SHOPIFY-{shopify_order_id}"
                query = """
                SELECT * FROM [Order]
                WHERE ReferenceNumber = :reference_number
                  AND ChannelType = 2
                """
                result = await session.execute(text(query), {"reference_number": reference_number})
                row = result.fetchone()
                return row._asdict() if row else None
        except Exception as e:
            logger.error(f"Error finding order by Shopify ID {shopify_order_id}: {e}")
            return None

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def order_exists_by_shopify_id(self, shopify_order_id: str) -> bool:
        """
        Check if an order already exists in RMS by Shopify order ID.

        This method is optimized for deduplication checks in the polling system.
        It only checks existence without retrieving the full order data.

        Args:
            shopify_order_id: Shopify order ID (e.g., "5678901234")

        Returns:
            bool: True if order exists, False otherwise
        """
        try:
            async with self.get_session() as session:
                reference_number = f"SHOPIFY-{shopify_order_id}"
                query = """
                SELECT COUNT(*) as order_count
                FROM [Order]
                WHERE ReferenceNumber = :reference_number
                  AND ChannelType = 2
                """
                result = await session.execute(text(query), {"reference_number": reference_number})
                count = result.scalar()
                exists = (count or 0) > 0

                if exists:
                    logger.debug(f"Order with Shopify ID {shopify_order_id} already exists in RMS")

                return exists
        except Exception as e:
            logger.error(f"Error checking order existence for Shopify ID {shopify_order_id}: {e}")
            # Return False to allow retry instead of blocking the order
            return False

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def check_orders_exist_batch(self, shopify_order_ids: list[str]) -> dict[str, bool]:
        """
        Check existence of multiple orders in batch for efficient deduplication.

        Args:
            shopify_order_ids: List of Shopify order IDs to check

        Returns:
            Dict mapping Shopify order ID to existence boolean
        """
        try:
            if not shopify_order_ids:
                return {}

            async with self.get_session() as session:
                # Build reference numbers
                reference_numbers = [f"SHOPIFY-{order_id}" for order_id in shopify_order_ids]

                # Use IN clause for batch query
                placeholders = ", ".join([f":ref{i}" for i in range(len(reference_numbers))])
                query = f"""
                SELECT ReferenceNumber
                FROM [Order]
                WHERE ReferenceNumber IN ({placeholders})
                  AND ChannelType = 2
                """

                # Build params dict
                params = {f"ref{i}": ref for i, ref in enumerate(reference_numbers)}

                result = await session.execute(text(query), params)
                existing_refs = {row.ReferenceNumber for row in result.fetchall()}

                # Map back to original Shopify IDs
                existence_map = {}
                for order_id in shopify_order_ids:
                    ref_number = f"SHOPIFY-{order_id}"
                    existence_map[order_id] = ref_number in existing_refs

                existing_count = sum(existence_map.values())
                logger.info(
                    f"Batch existence check: {existing_count}/{len(shopify_order_ids)} " f"orders already exist in RMS"
                )

                return existence_map

        except Exception as e:
            logger.error(f"Error in batch order existence check: {e}")
            # Return empty dict to allow fallback to individual checks
            return {}

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_order(
        self, order_id: int, order_data: Dict[str, Any], session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        Update an existing order with provided fields and return updated view.

        Args:
            order_id: RMS order ID
            order_data: Fields to update
            session: Optional shared session for atomic transactions
        """
        try:
            # Use provided session or create a new one
            if session:
                return await self._update_order_impl(session, order_id, order_data)
            else:
                async with self.get_session() as new_session:
                    result = await self._update_order_impl(new_session, order_id, order_data)
                    await new_session.commit()
                    return result
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {e}")
            raise

    async def _update_order_impl(
        self, session: AsyncSession, order_id: int, order_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Internal implementation of update_order."""
        set_clauses: List[str] = []
        params: Dict[str, Any] = {"order_id": order_id}

        for key, value in order_data.items():
            if key != "id":
                # Map snake_case to PascalCase for RMS
                db_column = self.ORDER_COLUMN_MAP.get(key, key)
                set_clauses.append(f"{db_column} = :{key}")
                params[key] = value

        # ✨ ALWAYS update LastUpdated timestamp on any order modification
        set_clauses.append("LastUpdated = :last_updated")
        params["last_updated"] = datetime.now(UTC)

        if not set_clauses:
            logger.warning("No fields to update in order")
            return {"id": order_id}

        query = f"""
        UPDATE [Order]
        SET {', '.join(set_clauses)}
        WHERE ID = :order_id
        """

        await session.execute(text(query), params)
        logger.info(f"Updated order {order_id} (LastUpdated={params['last_updated'].isoformat()})")
        return {"id": order_id, **order_data}

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_order_entries(self, order_id: int, session: Optional[AsyncSession] = None) -> List[Dict[str, Any]]:
        """
        Retrieve all entries for an order.

        Args:
            order_id: RMS order ID
            session: Optional shared session for atomic transactions
        """
        try:
            if session:
                return await self._get_order_entries_impl(session, order_id)
            else:
                async with self.get_session() as new_session:
                    return await self._get_order_entries_impl(new_session, order_id)
        except Exception as e:
            logger.error(f"Error getting order entries for order {order_id}: {e}")
            return []

    async def _get_order_entries_impl(self, session: AsyncSession, order_id: int) -> List[Dict[str, Any]]:
        """Internal implementation of get_order_entries."""
        query = """
        SELECT * FROM OrderEntry
        WHERE OrderID = :order_id
        """
        result = await session.execute(text(query), {"order_id": order_id})
        rows = result.fetchall()
        return [row._asdict() for row in rows]

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_order_entry(
        self, entry_id: int, entry_data: Dict[str, Any], session: Optional[AsyncSession] = None
    ) -> None:
        """
        Update fields for a specific order entry.

        Args:
            entry_id: RMS OrderEntry ID
            entry_data: Fields to update
            session: Optional shared session for atomic transactions
        """
        try:
            if session:
                await self._update_order_entry_impl(session, entry_id, entry_data)
            else:
                async with self.get_session() as new_session:
                    await self._update_order_entry_impl(new_session, entry_id, entry_data)
                    await new_session.commit()
        except Exception as e:
            logger.error(f"Error updating order entry {entry_id}: {e}")
            raise

    async def _update_order_entry_impl(self, session: AsyncSession, entry_id: int, entry_data: Dict[str, Any]) -> None:
        """Internal implementation of update_order_entry."""
        set_clauses: List[str] = []
        params: Dict[str, Any] = {"entry_id": entry_id}

        for key, value in entry_data.items():
            if key != "id":
                # Map snake_case to PascalCase for RMS
                db_column = self.ORDER_ENTRY_COLUMN_MAP.get(key, key)
                set_clauses.append(f"{db_column} = :{key}")
                params[key] = value

        # ✨ ALWAYS update LastUpdated timestamp on any entry modification
        set_clauses.append("LastUpdated = :last_updated")
        params["last_updated"] = datetime.now(UTC)

        if set_clauses:
            query = f"""
            UPDATE OrderEntry
            SET {', '.join(set_clauses)}
            WHERE ID = :entry_id
            """
            await session.execute(text(query), params)
            logger.info(f"Updated order entry {entry_id} (LastUpdated={params['last_updated'].isoformat()})")

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def delete_order_entry(self, entry_id: int, session: Optional[AsyncSession] = None) -> None:
        """
        Delete a specific order entry (line item) from RMS.

        This method is used when a product is removed from a Shopify order
        during order edits, ensuring RMS stays in sync with Shopify.

        Args:
            entry_id: RMS OrderEntry ID to delete
            session: Optional shared session for atomic transactions

        Raises:
            RMSConnectionException: If deletion fails
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST)

        try:
            if session:
                await self._delete_order_entry_impl(session, entry_id)
            else:
                async with self.get_session() as new_session:
                    await self._delete_order_entry_impl(new_session, entry_id)
                    await new_session.commit()
        except Exception as e:
            logger.error(f"❌ Error deleting order entry {entry_id}: {e}")
            raise RMSConnectionException(
                message=f"Failed to delete order entry: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_entry_deletion",
            ) from e

    async def _delete_order_entry_impl(self, session: AsyncSession, entry_id: int) -> None:
        """Internal implementation of delete_order_entry."""
        query = """
        DELETE FROM OrderEntry
        WHERE ID = :entry_id
        """

        result = await session.execute(text(query), {"entry_id": entry_id})

        # Note: rowcount may not be available for all dialects, log optimistically
        logger.info(f"✅ Deleted order entry {entry_id} from RMS")

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def mark_order_cancelled(self, order_id: int, cancel_reason: str | None = None) -> None:
        """
        Mark an order as cancelled in RMS (SOLID best practice).

        This method encapsulates the business logic for marking an order as cancelled,
        following Single Responsibility Principle.

        Args:
            order_id: RMS order ID
            cancel_reason: Optional cancellation reason from Shopify

        Raises:
            RMSConnectionException: If update fails
        """
        if not self.is_initialized():
            raise RMSConnectionException(message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST)

        try:
            async with self.get_session() as session:
                # Build comment with cancellation reason
                comment = "CANCELADA EN SHOPIFY"
                if cancel_reason:
                    comment += f": {cancel_reason}"

                # ✨ Update LastUpdated when marking as cancelled
                last_updated = datetime.now(UTC)

                query = """
                UPDATE [Order]
                SET Closed = 1, Comment = :comment, LastUpdated = :last_updated
                WHERE ID = :order_id
                """

                await session.execute(
                    text(query), {"order_id": order_id, "comment": comment, "last_updated": last_updated}
                )
                await session.commit()
                logger.info(f"✅ Marked order {order_id} as cancelled in RMS (LastUpdated={last_updated.isoformat()})")

        except Exception as e:
            logger.error(f"❌ Error marking order {order_id} as cancelled: {e}")
            raise RMSConnectionException(
                message=f"Failed to mark order as cancelled: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_cancellation",
            ) from e
