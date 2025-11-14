#!/usr/bin/env python3
"""Check order #1013 details directly."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.shopify_clients.order_polling_client import OrderPollingClient


async def main():
    print("\n" + "=" * 80)
    print("🔍 ORDER #1013 DIRECT QUERY")
    print("=" * 80)
    
    client = OrderPollingClient()
    await client.initialize()
    
    try:
        # Query order by legacy ID
        order_id = "gid://shopify/Order/6157526401084"
        
        print(f"\nQuerying order: {order_id}")
        
        order = await client.fetch_order_by_id(order_id)
        
        if order:
            print("\n✅ Order found!")
            print(f"\nOrder Details:")
            print(f"  Name: {order.get('name')}")
            print(f"  Legacy ID: {order.get('legacyResourceId')}")
            print(f"  Created: {order.get('createdAt')}")
            print(f"  Email: {order.get('email')}")
            print(f"  Financial Status: {order.get('displayFinancialStatus')}")
            print(f"  Fulfillment Status: {order.get('displayFulfillmentStatus')}")
        else:
            print("\n❌ Order not found")
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
