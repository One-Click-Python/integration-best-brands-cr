#!/usr/bin/env python3
"""Verify order #1013 in RMS database."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.rms.order_repository import OrderRepository


async def main():
    print("\n" + "=" * 80)
    print("🔍 VERIFYING ORDER #1013 IN RMS DATABASE")
    print("=" * 80)
    
    repo = OrderRepository()
    await repo.initialize()
    
    try:
        # Search by Shopify reference number
        reference_number = "SHOPIFY-6157526401084"
        
        print(f"\n📋 Searching for order with reference: {reference_number}")
        
        order = await repo.get_order_by_reference(reference_number)
        
        if order:
            print(f"\n✅ ORDER FOUND IN RMS!")
            print(f"\n📊 Order Details:")
            print(f"  Order ID: {order.get('ID')}")
            print(f"  Reference Number: {order.get('ReferenceNumber')}")
            print(f"  Customer ID: {order.get('CustomerID')}")
            print(f"  Store ID: {order.get('StoreID')}")
            print(f"  Total: {order.get('Total')}")
            print(f"  Subtotal: {order.get('SubTotal')}")
            print(f"  Tax: {order.get('Tax')}")
            print(f"  Channel Type: {order.get('ChannelType')}")
            print(f"  DateTime: {order.get('DateTime')}")
            
            # Get order entries
            print(f"\n📦 Getting order entries...")
            entries = await repo.get_order_entries(order.get('ID'))
            
            if entries:
                print(f"\n✅ Found {len(entries)} order entries:")
                for i, entry in enumerate(entries, 1):
                    print(f"\n  Entry {i}:")
                    print(f"    ID: {entry.get('ID')}")
                    print(f"    Item ID: {entry.get('ItemID')}")
                    print(f"    Description: {entry.get('Description')}")
                    print(f"    Price: {entry.get('Price')}")
                    print(f"    Full Price: {entry.get('FullPrice')}")
                    print(f"    Quantity: {entry.get('QuantityOnOrder')}")
            else:
                print(f"  ⚠️  No order entries found")
        else:
            print(f"\n❌ ORDER NOT FOUND")
            
            # Try searching by order ID
            print(f"\n🔍 Searching by Order ID 114827...")
            
            from sqlalchemy import text
            async with repo.get_session() as session:
                result = await session.execute(
                    text("SELECT * FROM [Order] WHERE ID = :order_id"),
                    {"order_id": 114827}
                )
                order_by_id = result.mappings().first()
                
                if order_by_id:
                    print(f"\n✅ FOUND BY ID!")
                    print(f"  Order ID: {order_by_id.get('ID')}")
                    print(f"  Reference Number: {order_by_id.get('ReferenceNumber')}")
                    print(f"  Customer ID: {order_by_id.get('CustomerID')}")
                    print(f"  Total: {order_by_id.get('Total')}")
                else:
                    print(f"  ❌ Not found by ID either")
                
                # Check recent orders
                print(f"\n🔍 Checking last 5 orders with ChannelType=2...")
                result = await session.execute(
                    text("""
                        SELECT TOP 5 ID, ReferenceNumber, Total, DateTime
                        FROM [Order]
                        WHERE ChannelType = 2
                        ORDER BY ID DESC
                    """)
                )
                recent_orders = result.mappings().all()
                
                if recent_orders:
                    print(f"\n📋 Last 5 Shopify orders:")
                    for order in recent_orders:
                        print(f"  ID={order.get('ID')}, Ref={order.get('ReferenceNumber')}, "
                              f"Total={order.get('Total')}, Date={order.get('DateTime')}")
        
        await repo.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
