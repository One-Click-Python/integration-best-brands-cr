"""OrderCreator service - SRP compliance."""

import logging

from app.api.v1.schemas.rms_schemas import RMSOrder, RMSOrderEntry
from app.db.rms.order_repository import OrderRepository
from app.domain.models import OrderDomain
from app.utils.error_handler import SyncException

logger = logging.getLogger(__name__)


class OrderCreator:
    """Creates orders in RMS (SRP: Order creation only)."""

    def __init__(self, order_repo: OrderRepository):
        """
        Initialize with SOLID dependencies (DIP).

        Args:
            order_repo: Repository for order operations
        """
        self.order_repo = order_repo

    async def create(self, order: OrderDomain) -> int:
        """
        Create order in RMS and return order ID.

        Args:
            order: Domain model with all order data

        Returns:
            int: Created order ID

        Raises:
            SyncException: If creation fails
        """
        try:
            # Convert domain model to RMS schema
            order_data = order.to_dict()

            # 🔍 Logging de depuración - valores ANTES de RMSOrder
            logger.info(
                f"🔍 Order data BEFORE RMSOrder conversion: "
                f"total={order_data['total']} ({type(order_data['total']).__name__}), "
                f"tax={order_data['tax']} ({type(order_data['tax']).__name__})"
            )

            order_model = RMSOrder(**order_data)

            # 🔍 Logging de depuración - valores DESPUÉS de RMSOrder
            logger.info(
                f"🔍 Order model AFTER RMSOrder conversion: "
                f"total={order_model.total} ({type(order_model.total).__name__}), "
                f"tax={order_model.tax} ({type(order_model.tax).__name__})"
            )

            # Create order header
            order_id = await self.order_repo.create_order(order_model)
            logger.info(f"Created RMS order {order_id} for {order.reference_number}")

            # Create order entries
            created_entries = []
            for entry in order.entries:
                entry_data = entry.to_dict()
                entry_data["order_id"] = order_id
                entry_model = RMSOrderEntry(**entry_data)
                entry_id = await self.order_repo.create_order_entry(entry_model)
                created_entries.append({"id": entry_id, **entry_data})
                logger.debug(f"Created order entry {entry_id} for item {entry.item_id}")

            logger.info(f"Successfully created order {order_id} with {len(created_entries)} entries")
            return order_id

        except Exception as e:
            logger.error(f"Error creating RMS order: {e}")
            raise SyncException(
                message=f"Failed to create RMS order: {str(e)}",
                service="order_creator",
                operation="create",
            ) from e

    async def update(self, existing_order_id: int, order: OrderDomain) -> int:
        """
        Update existing order in RMS with atomic transaction.

        All operations (update header, update/create/delete entries) are wrapped
        in a single database transaction for atomicity.

        Args:
            existing_order_id: ID of existing RMS order
            order: Domain model with updated data

        Returns:
            int: Updated order ID

        Raises:
            SyncException: If update fails
        """
        try:
            # 🔒 ATOMIC TRANSACTION: All operations in one session
            async with self.order_repo.get_session() as session:
                # 1. Update order header
                order_data = order.to_dict()

                # 🔍 Logging de depuración - valores del OrderDomain
                logger.info(
                    f"🔍 OrderDomain values BEFORE to_dict: "
                    f"total={order.total.amount} ({type(order.total.amount).__name__}), "
                    f"tax={order.tax.amount} ({type(order.tax.amount).__name__})"
                )

                # 🔍 Logging de depuración - valores después de to_dict
                logger.info(
                    f"🔍 order_data AFTER to_dict: "
                    f"total={order_data['total']} ({type(order_data['total']).__name__}), "
                    f"tax={order_data['tax']} ({type(order_data['tax']).__name__})"
                )

                # Remove id from update data, we use existing_order_id
                order_data.pop("id", None)

                await self.order_repo.update_order(existing_order_id, order_data, session=session)
                logger.info(f"Updated RMS order {existing_order_id} for {order.reference_number}")

                # 2. Get existing entries to compare
                existing_entries = await self.order_repo.get_order_entries(existing_order_id, session=session)
                existing_entries_by_item = {entry["ItemID"]: entry for entry in existing_entries}

                # 3. Sync order entries (create/update)
                updated_count = 0
                created_count = 0

                for entry in order.entries:
                    entry_data = entry.to_dict()
                    entry_data["order_id"] = existing_order_id
                    item_id = entry.item_id

                    if item_id in existing_entries_by_item:
                        # Update existing entry
                        existing_entry = existing_entries_by_item[item_id]
                        entry_id = existing_entry["ID"]
                        await self.order_repo.update_order_entry(entry_id, entry_data, session=session)
                        updated_count += 1
                        logger.debug(f"Updated order entry {entry_id} for item {item_id}")
                    else:
                        # Create new entry
                        entry_model = RMSOrderEntry(**entry_data)
                        await self.order_repo.create_order_entry(entry_model, session=session)
                        created_count += 1
                        logger.debug(f"Created new order entry for item {item_id}")

                # ✅ DEFENSIVE CHECK: Verify shipping entry exists if order has shipping charge
                from app.core.config import settings

                if order.shipping_charge_on_order.amount > 0:
                    shipping_item_id = settings.SHIPPING_ITEM_ID
                    order_item_ids = {entry.item_id for entry in order.entries}

                    if shipping_item_id not in order_item_ids:
                        logger.warning(
                            f"⚠️ DEFENSIVE CHECK: Order {existing_order_id} has shipping charge "
                            f"₡{order.shipping_charge_on_order.amount:.2f} but no shipping entry "
                            f"(ItemID={shipping_item_id}) found in order.entries. "
                            f"This should not happen if OrderConverter worked correctly. "
                            f"The shipping entry should have been added by OrderConverter._create_shipping_entry()."
                        )
                    else:
                        logger.debug(
                            f"✅ Shipping entry verified: ItemID={shipping_item_id} present in order entries "
                            f"(shipping charge=₡{order.shipping_charge_on_order.amount:.2f})"
                        )

                # 4. Delete orphaned entries (products removed from Shopify order)
                # SPECIAL CASE: Shipping entry should be updated to 0, not deleted
                deleted_count = 0
                shopify_item_ids = {entry.item_id for entry in order.entries}

                for existing_entry in existing_entries:
                    item_id = existing_entry["ItemID"]
                    if item_id not in shopify_item_ids:
                        # SPECIAL: Shipping entry handling (update to 0, don't delete)
                        if item_id == settings.SHIPPING_ITEM_ID:
                            # Shipping entry exists but no shipping in Shopify → update to 0
                            entry_id = existing_entry["ID"]

                            # Create update data with zeros
                            zero_entry_data = {
                                "order_id": existing_order_id,
                                "item_id": item_id,
                                "store_id": existing_entry["StoreID"],
                                "price": 0.0,
                                "full_price": 0.0,
                                "cost": existing_entry["Cost"],  # Keep original cost
                                "quantity_on_order": 0.0,  # Both quantities to 0
                                "quantity_rtd": 0.0,
                                "description": existing_entry["Description"],  # Keep description
                                "taxable": existing_entry["Taxable"],
                                "sales_rep_id": existing_entry["SalesRepID"],
                                "discount_reason_code_id": existing_entry.get("DiscountReasonCodeID", 0),
                                "return_reason_code_id": existing_entry.get("ReturnReasonCodeID", 0),
                                "is_add_money": existing_entry.get("IsAddMoney", False),
                                "voucher_id": existing_entry.get("VoucherID", 0),
                                "comment": existing_entry.get("Comment", "Shipping Item"),
                                "price_source": existing_entry.get("PriceSource", 10),
                            }

                            await self.order_repo.update_order_entry(entry_id, zero_entry_data, session=session)
                            logger.info(
                                f"📦 Updated shipping entry {entry_id} to ₡0 (shipping removed from Shopify order, "
                                f"ItemID={item_id}, QuantityOnOrder=0, QuantityRTD=0)"
                            )
                        else:
                            # NORMAL: Other items → delete as orphaned
                            entry_id = existing_entry["ID"]
                            await self.order_repo.delete_order_entry(entry_id, session=session)
                            deleted_count += 1
                            logger.info(
                                f"🗑️ Deleted orphaned order entry {entry_id} for item {item_id} "
                                f"(product removed from Shopify order)"
                            )

                # 5. Commit transaction (all or nothing)
                await session.commit()
                logger.info(
                    f"✅ Successfully updated order {existing_order_id} (ATOMIC): "
                    f"{updated_count} entries updated, {created_count} entries created, "
                    f"{deleted_count} entries deleted"
                )

            return existing_order_id

        except Exception as e:
            logger.error(f"❌ Error updating RMS order {existing_order_id}: {e}")
            # Transaction automatically rolled back on exception
            raise SyncException(
                message=f"Failed to update RMS order: {str(e)}",
                service="order_creator",
                operation="update",
            ) from e
