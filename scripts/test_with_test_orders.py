#!/usr/bin/env python3
"""Test polling with test orders included."""

import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.shopify_clients.order_polling_client import OrderPollingClient


async def main():
    print("\n" + "=" * 80)
    print("🧪 TEST POLLING WITH TEST ORDERS INCLUDED")
    print("=" * 80)
    
    client = OrderPollingClient()
    await client.initialize()
    
    try:
        # Test 1: WITHOUT test orders (default)
        print("\n📋 TEST 1: Polling WITHOUT test orders (default)")
        print("-" * 80)
        
        result1 = await client.fetch_recent_orders(
            lookback_minutes=30,
            batch_size=50,
            max_pages=3,
            include_test_orders=False  # Exclude test orders
        )
        
        orders1 = result1.get("orders", [])
        print(f"Orders found: {len(orders1)}")
        
        found_1013 = any(o.get("name") == "#1013" for o in orders1)
        print(f"Order #1013 detected: {'✅ YES' if found_1013 else '❌ NO'}")
        
        if orders1:
            print(f"Orders: {', '.join([o.get('name', '?') for o in orders1[:10]])}")
        
        # Test 2: WITH test orders
        print("\n📋 TEST 2: Polling WITH test orders included")
        print("-" * 80)
        
        result2 = await client.fetch_recent_orders(
            lookback_minutes=30,
            batch_size=50,
            max_pages=3,
            include_test_orders=True  # Include test orders
        )
        
        orders2 = result2.get("orders", [])
        print(f"Orders found: {len(orders2)}")
        
        found_1013 = False
        for order in orders2:
            if order.get("name") == "#1013":
                found_1013 = True
                print(f"\n🎉 SUCCESS! Order #1013 DETECTED with test orders included!")
                print(f"   Legacy ID: {order.get('legacyResourceId')}")
                print(f"   Created: {order.get('createdAt')}")
                print(f"   Updated: {order.get('updatedAt')}")
                print(f"   Status: {order.get('displayFinancialStatus')}")
                print(f"   Test: {order.get('test')}")
                break
        
        if not found_1013:
            print(f"Order #1013 detected: ❌ NO")
        
        if orders2:
            print(f"\nOrders: {', '.join([o.get('name', '?') for o in orders2[:10]])}")
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 SUMMARY")
        print("=" * 80)
        print(f"Without test orders: {len(orders1)} orders")
        print(f"With test orders: {len(orders2)} orders")
        print(f"Difference: {len(orders2) - len(orders1)} test orders")
        print(f"\n✅ CONCLUSION: Order #1013 is a TEST ORDER")
        print("   It's excluded by default (test:false filter)")
        print("   Use include_test_orders=True to detect it")
        print("=" * 80)
        
        await client.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
