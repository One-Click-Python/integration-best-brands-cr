"""
Script para verificar órdenes en RMS con costo de envío y sus OrderEntries.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.db.connection import ConnDB
from app.core.config import get_settings

settings = get_settings()


async def check_rms_orders():
    """Check recent RMS orders for shipping charges and entries."""
    print("🔍 Checking recent RMS orders for shipping...\n")

    conn_db = ConnDB()

    try:
        await conn_db.initialize()

        # Query recent orders with shipping charges
        query_orders = """
        SELECT TOP 10
            o.ID,
            o.ReferenceNumber as ShopifyID,
            o.Time as OrderTime,
            o.Total,
            o.Tax,
            o.ShippingChargeOnOrder,
            o.Comment
        FROM [Order] o
        WHERE o.ReferenceNumber IS NOT NULL
            AND o.Time >= DATEADD(DAY, -7, GETDATE())
        ORDER BY o.Time DESC
        """

        async with conn_db.get_session() as session:
            result = await session.execute(query_orders)
            orders = result.fetchall()

            if not orders:
                print("❌ No orders found in last 7 days")
                return

            print(f"📦 Found {len(orders)} recent orders:\n")

            for order in orders:
                order_id = order.ID
                shopify_id = order.ShopifyID
                shipping = float(order.ShippingChargeOnOrder or 0)
                total = float(order.Total or 0)
                tax = float(order.Tax or 0)

                print(f"Order {order_id} (Shopify: {shopify_id}):")
                print(f"  Time: {order.OrderTime}")
                print(f"  Total: ₡{total:,.2f}")
                print(f"  Tax: ₡{tax:,.2f}")
                print(f"  Shipping: ₡{shipping:,.2f}")

                if shipping > 0:
                    print(f"  ✅ HAS shipping charge")

                    # Check for shipping OrderEntry
                    query_entries = """
                    SELECT
                        oe.ID,
                        oe.ItemID,
                        oe.Description,
                        oe.Price,
                        oe.QuantityOnOrder,
                        oe.QuantityRTD,
                        oe.Comment,
                        oe.PriceSource
                    FROM OrderEntry oe
                    WHERE oe.OrderID = :order_id
                        AND oe.ItemID = :shipping_item_id
                    """

                    result_entries = await session.execute(
                        query_entries,
                        {"order_id": order_id, "shipping_item_id": settings.SHIPPING_ITEM_ID}
                    )
                    shipping_entries = result_entries.fetchall()

                    if shipping_entries:
                        print(f"  ✅ Shipping OrderEntry EXISTS:")
                        for entry in shipping_entries:
                            print(f"     EntryID: {entry.ID}")
                            print(f"     ItemID: {entry.ItemID}")
                            print(f"     Description: {entry.Description}")
                            print(f"     Price: ₡{float(entry.Price):,.2f}")
                            print(f"     QuantityOnOrder: {entry.QuantityOnOrder}")
                            print(f"     QuantityRTD: {entry.QuantityRTD}")
                            print(f"     Comment: {entry.Comment}")
                            print(f"     PriceSource: {entry.PriceSource}")
                    else:
                        print(f"  ❌ Shipping OrderEntry MISSING (ItemID={settings.SHIPPING_ITEM_ID})")

                    # Show all entries for this order
                    query_all_entries = """
                    SELECT
                        oe.ID,
                        oe.ItemID,
                        oe.Description,
                        oe.Price,
                        oe.QuantityOnOrder,
                        oe.Comment
                    FROM OrderEntry oe
                    WHERE oe.OrderID = :order_id
                    """

                    result_all = await session.execute(query_all_entries, {"order_id": order_id})
                    all_entries = result_all.fetchall()

                    print(f"  Total OrderEntries: {len(all_entries)}")
                    for entry in all_entries:
                        print(f"     - ItemID: {entry.ItemID}, Desc: {entry.Description}, Price: ₡{float(entry.Price):,.2f}, Qty: {entry.QuantityOnOrder}")

                else:
                    print(f"  ⏭️ No shipping charge")

                print()

    finally:
        await conn_db.close()


if __name__ == "__main__":
    asyncio.run(check_rms_orders())
