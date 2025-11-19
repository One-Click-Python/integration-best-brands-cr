"""
Script para verificar si una orden de Shopify tiene costo de envío.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.db.shopify_clients.order_polling_client import OrderPollingClient

settings = get_settings()


async def check_order_shipping():
    """Check if recent order has shipping cost."""
    print("🔍 Checking recent orders for shipping costs...")

    client = OrderPollingClient()

    try:
        await client.initialize()

        # Fetch recent orders (last 24 hours)
        result = await client.fetch_recent_orders(
            lookback_minutes=1440,  # 24 hours
            batch_size=10,
            max_pages=1,
            include_test_orders=False
        )

        orders = result["orders"]

        if not orders:
            print("❌ No orders found in last 24 hours")
            return

        print(f"\n📦 Found {len(orders)} orders:\n")

        for order in orders:
            order_id = order.get("legacyResourceId") or order.get("id", "").split("/")[-1]
            order_name = order.get("name", "Unknown")

            # Get shipping info
            shipping_line = order.get("shippingLine")

            if shipping_line:
                shipping_price = shipping_line.get("currentDiscountedPriceSet", {}).get("shopMoney", {}).get("amount", "0")
                shipping_title = shipping_line.get("title", "Unknown")

                print(f"Order {order_name} (ID: {order_id}):")
                print(f"  Shipping Method: {shipping_title}")
                print(f"  Shipping Cost: ₡{shipping_price}")

                if float(shipping_price) > 0:
                    print(f"  ✅ HAS shipping cost - OrderEntry SHOULD be created")
                else:
                    print(f"  ❌ NO shipping cost - OrderEntry will NOT be created")
            else:
                print(f"Order {order_name} (ID: {order_id}):")
                print(f"  ❌ NO shipping line found")

            # Get total
            total = order.get("totalPriceSet", {}).get("shopMoney", {}).get("amount", "0")
            print(f"  Total: ₡{total}\n")

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(check_order_shipping())
