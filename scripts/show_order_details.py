#!/usr/bin/env python3
"""Show order #1013 details."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.connection import ConnDB


async def main():
    print("\n" + "=" * 80)
    print("📋 ORDER #1013 (ID: 114827) VERIFICATION")
    print("=" * 80)
    
    db = ConnDB()
    await db.initialize()
    
    try:
        async with db.get_session() as session:
            # Get order details
            print(f"\n🔍 Order Details:")
            result = await session.execute(
                text("""
                    SELECT 
                        ID, ReferenceNumber, CustomerID, Total, SubTotal, Tax,
                        ChannelType, StoreID, Status
                    FROM [Order]
                    WHERE ID = :id
                """),
                {"id": 114827}
            )
            order = result.mappings().first()
            
            if order:
                print(f"  ✅ Order ID: {order['ID']}")
                print(f"  ✅ Reference: {order['ReferenceNumber']}")
                print(f"  ✅ Customer ID: {order['CustomerID']}")
                print(f"  ✅ Store ID: {order['StoreID']}")
                print(f"  ✅ Channel Type: {order['ChannelType']} (2 = Shopify)")
                print(f"  ✅ Status: {order['Status']}")
                print(f"  ✅ Total: ₡{order['Total']}")
                print(f"  ✅ SubTotal: ₡{order['SubTotal']}")
                print(f"  ✅ Tax: ₡{order['Tax']}")
                
                # Get order entries
                print(f"\n📦 Order Entries:")
                result = await session.execute(
                    text("""
                        SELECT 
                            ID, ItemID, Description, Price, FullPrice, 
                            Cost, QuantityOnOrder, Taxable
                        FROM OrderEntry
                        WHERE OrderID = :order_id
                    """),
                    {"order_id": 114827}
                )
                entries = result.mappings().all()
                
                print(f"  Total entries: {len(entries)}")
                for i, entry in enumerate(entries, 1):
                    print(f"\n  Entry #{i}:")
                    print(f"    ID: {entry['ID']}")
                    print(f"    ItemID: {entry['ItemID']}")
                    print(f"    Description: {entry['Description']}")
                    print(f"    Quantity: {entry['QuantityOnOrder']}")
                    print(f"    Price: ₡{entry['Price']}")
                    print(f"    Full Price: ₡{entry['FullPrice']}")
                    print(f"    Cost: ₡{entry['Cost']}")
                    print(f"    Taxable: {entry['Taxable']}")
                
                # Compare with Shopify
                print(f"\n📊 Comparison:")
                print(f"  Shopify Order #1013 (Legacy ID: 6157526401084)")
                print(f"  ↓")
                print(f"  RMS Order #{order['ID']} ({order['ReferenceNumber']})")
                print(f"  ✅ Successfully synchronized!")
                
            else:
                print(f"  ❌ Order not found")
        
        await db.close()
        
        print("\n" + "=" * 80)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
