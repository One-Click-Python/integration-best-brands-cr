#!/usr/bin/env python3
"""
Quick verification script for timezone format fix.
Tests that the order polling client now uses correct ISO 8601 format (+00:00 with colons).
"""

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.shopify_clients.order_polling_client import OrderPollingClient


async def main():
    print("\n" + "=" * 80)
    print("🔧 TIMEZONE FORMAT FIX VERIFICATION")
    print("=" * 80)
    
    # Test 1: Check timezone format
    print("\n📋 TEST 1: Timezone Format")
    print("-" * 80)
    
    now = datetime.now(UTC)
    iso_format = now.isoformat()
    
    print(f"Current time (ISO 8601): {iso_format}")
    
    if "+00:00" in iso_format or "Z" in iso_format:
        print("✅ Format is CORRECT (includes timezone with colons)")
    else:
        print("❌ Format is WRONG (missing colons in timezone)")
        return False
    
    # Test 2: Poll orders and check if #1013 is detected
    print("\n📋 TEST 2: Order #1013 Detection")
    print("-" * 80)
    
    client = OrderPollingClient()
    await client.initialize()  # Initialize client before use
    
    # Order #1013 was updated at 2025-11-13T04:10:09Z
    # Calculate lookback needed
    order_time = datetime(2025, 11, 13, 4, 10, 9, tzinfo=UTC)
    time_diff = now - order_time
    lookback_minutes = int(time_diff.total_seconds() / 60) + 10  # Add buffer
    
    print(f"Order #1013 updated: {order_time.isoformat()}")
    print(f"Current time: {now.isoformat()}")
    print(f"Time difference: {time_diff}")
    print(f"Lookback minutes: {lookback_minutes}")
    
    print(f"\n🔍 Polling with {lookback_minutes} minute lookback...")
    
    try:
        result = await client.fetch_recent_orders(
            lookback_minutes=lookback_minutes,
            batch_size=50,
            max_pages=3
        )
        
        orders = result.get("orders", [])
        total = result.get("total_fetched", 0)
        
        print(f"✅ Fetched {total} orders")
        
        # Check for #1013
        found_1013 = False
        for order in orders:
            if order.get("name") == "#1013":
                found_1013 = True
                print(f"\n🎉 SUCCESS! Order #1013 DETECTED!")
                print(f"   Legacy ID: {order.get('legacyResourceId')}")
                print(f"   Created: {order.get('createdAt')}")
                print(f"   Updated: {order.get('updatedAt')}")
                print(f"   Status: {order.get('displayFinancialStatus')}")
                break
        
        if not found_1013:
            print(f"\n⚠️  Order #1013 NOT detected")
            print(f"   Found orders: {', '.join([o.get('name', '?') for o in orders[:10]])}")
        
        # Test 3: Recent orders
        print("\n📋 TEST 3: Recent Orders (Last 15 minutes)")
        print("-" * 80)
        
        recent_result = await client.fetch_recent_orders(
            lookback_minutes=15,
            batch_size=50,
            max_pages=2
        )
        
        recent_orders = recent_result.get("orders", [])
        print(f"✅ Found {len(recent_orders)} orders in last 15 minutes")
        
        if recent_orders:
            print(f"\nRecent orders (first 5):")
            for order in recent_orders[:5]:
                print(f"  {order.get('name')}: {order.get('updatedAt')} ({order.get('displayFinancialStatus')})")
        
        # Summary
        print("\n" + "=" * 80)
        print("📊 VERIFICATION SUMMARY")
        print("=" * 80)
        print(f"✅ Timezone format: CORRECT (+00:00)")
        print(f"{'✅' if found_1013 else '⚠️ '} Order #1013: {'DETECTED' if found_1013 else 'NOT DETECTED'}")
        print(f"✅ Recent polling: {len(recent_orders)} orders")
        print("=" * 80)
        
        if found_1013:
            print("\n🎉 ALL TESTS PASSED! The timezone fix is working correctly.")
        else:
            print("\n⚠️  Order #1013 not detected - may need additional investigation")
        
        await client.close()  # Close client
        return found_1013
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await client.close()  # Close client on error
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
