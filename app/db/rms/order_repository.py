"""
OrderRepository: Order and order-entry operations for RMS.

Encapsulates creation, updates, retrieval, and Shopify-related lookups for orders
and order entries. Extracted from the legacy RMSHandler to comply with SRP.
"""

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import text

from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry
from app.core.config import get_settings
from app.db.rms.base import BaseRepository, log_operation, with_retry
from app.utils.error_handler import RMSConnectionException

logger = logging.getLogger(__name__)
settings = get_settings()


class OrderRepository(BaseRepository):
    """Repository for order and order-entry operations in RMS."""

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
            raise RMSConnectionException(
                message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST
            )
        try:
            async with self.get_session() as session:
                query = """
                INSERT INTO [Order] (
                    StoreID, Time, Type, CustomerID, Deposit, Tax, Total,
                    SalesRepID, ShippingServiceID, ShippingTrackingNumber,
                    Comment, ShippingNotes,
                    ReferenceNumber, ChannelType, Closed, ShippingChargeOnOrder
                )
                OUTPUT INSERTED.ID
                VALUES (
                    :store_id, :time, :type, :customer_id, :deposit, :tax, :total,
                    :sales_rep_id, :shipping_service_id, :shipping_tracking_number,
                    :comment, :shipping_notes,
                    :reference_number, :channel_type, :closed, :shipping_charge_on_order
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
                }

                result = await session.execute(text(query), params)
                order_id = result.scalar()
                if not order_id:
                    raise RMSConnectionException(
                        message="Order creation did not return an ID",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="order_creation",
                    )

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
    async def create_order_entry(self, entry: RMSOrderEntry) -> int:
        """Create a new order entry (line item) in RMS and return its ID."""
        if not self.is_initialized():
            raise RMSConnectionException(
                message="OrderRepository not initialized", db_host=settings.RMS_DB_HOST
            )
        try:
            async with self.get_session() as session:
                query = """
                INSERT INTO OrderEntry (
                    OrderID, ItemID, Price, FullPrice, Cost,
                    QuantityOnOrder, QuantityRTD, SalesRepID,
                    DiscountReasonCodeID, ReturnReasonCodeID,
                    Description, Taxable, IsAddMoney, VoucherID
                )
                OUTPUT INSERTED.ID
                VALUES (
                    :order_id, :item_id, :price, :full_price, :cost,
                    :quantity_on_order, :quantity_rtd, :sales_rep_id,
                    :discount_reason_code_id, :return_reason_code_id,
                    :description, :taxable, :is_add_money, :voucher_id
                )
                """

                params = {
                    "order_id": entry.order_id,
                    "item_id": entry.item_id,
                    "price": float(entry.price),
                    "full_price": float(entry.full_price),
                    "cost": float(entry.cost) if entry.cost is not None else 0.0,
                    "quantity_on_order": entry.quantity_on_order,
                    "quantity_rtd": entry.quantity_rtd,
                    "sales_rep_id": entry.sales_rep_id,
                    "discount_reason_code_id": entry.discount_reason_code_id,
                    "return_reason_code_id": entry.return_reason_code_id,
                    "description": entry.description,
                    "taxable": entry.taxable,
                    "is_add_money": entry.is_add_money,
                    "voucher_id": entry.voucher_id,
                }

                result = await session.execute(text(query), params)
                entry_id = result.scalar()
                if not entry_id:
                    raise RMSConnectionException(
                        message="Order entry creation did not return an ID",
                        db_host=settings.RMS_DB_HOST,
                        connection_type="order_entry_creation",
                    )

                await session.commit()
                logger.info(f"Created order entry in RMS with ID: {entry_id}")
                return int(entry_id)
        except Exception as e:
            logger.error(f"Error creating order entry in RMS: {e}")
            raise RMSConnectionException(
                message=f"Failed to create order entry: {str(e)}",
                db_host=settings.RMS_DB_HOST,
                connection_type="order_entry_creation",
            ) from e

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
                result = await session.execute(
                    text(query), {"reference_number": reference_number}
                )
                row = result.fetchone()
                return row._asdict() if row else None
        except Exception as e:
            logger.error(
                f"Error finding order by Shopify ID {shopify_order_id}: {e}"
            )
            return None

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_order(self, order_id: int, order_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing order with provided fields and return updated view."""
        try:
            async with self.get_session() as session:
                set_clauses: List[str] = []
                params: Dict[str, Any] = {"order_id": order_id}

                for key, value in order_data.items():
                    if key != "id":
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                if not set_clauses:
                    logger.warning("No fields to update in order")
                    return {"id": order_id}

                query = f"""
                UPDATE [Order] 
                SET {', '.join(set_clauses)}
                WHERE ID = :order_id
                """

                await session.execute(text(query), params)
                await session.commit()
                logger.info(f"Updated order {order_id}")
                return {"id": order_id, **order_data}
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {e}")
            raise

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def get_order_entries(self, order_id: int) -> List[Dict[str, Any]]:
        """Retrieve all entries for an order."""
        try:
            async with self.get_session() as session:
                query = """
                SELECT * FROM OrderEntry 
                WHERE OrderID = :order_id
                """
                result = await session.execute(text(query), {"order_id": order_id})
                rows = result.fetchall()
                return [row._asdict() for row in rows]
        except Exception as e:
            logger.error(f"Error getting order entries for order {order_id}: {e}")
            return []

    @with_retry(max_attempts=3, delay=1.0)
    @log_operation()
    async def update_order_entry(self, entry_id: int, entry_data: Dict[str, Any]) -> None:
        """Update fields for a specific order entry."""
        try:
            async with self.get_session() as session:
                set_clauses: List[str] = []
                params: Dict[str, Any] = {"entry_id": entry_id}

                for key, value in entry_data.items():
                    if key != "id":
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                if set_clauses:
                    query = f"""
                    UPDATE OrderEntry 
                    SET {', '.join(set_clauses)}
                    WHERE ID = :entry_id
                    """
                    await session.execute(text(query), params)
                    await session.commit()
                    logger.info(f"Updated order entry {entry_id}")
        except Exception as e:
            logger.error(f"Error updating order entry {entry_id}: {e}")
            raise
