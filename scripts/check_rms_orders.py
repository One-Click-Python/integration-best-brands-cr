#!/usr/bin/env python3
"""Check RMS orders directly with SQL."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db.connection import ConnDB


async def main():
    print("\n" + "=" * 80)
    print("🔍 CHECKING RMS DATABASE FOR ORDER #1013")
    print("=" * 80)
    
    db = ConnDB()
    await db.initialize()
    
    try:
        async with db.get_session() as session:
            # Check by reference number
            print(f"\n1️⃣  Searching by Reference Number: SHOPIFY-6157526401084")
            result = await session.execute(
                text("""
                    SELECT * FROM [Order]
                    WHERE ReferenceNumber = :ref
                      AND ChannelType = 2
                """),
                {"ref": "SHOPIFY-6157526401084"}
            )
            order = result.mappings().first()
            
            if order:
                print(f"✅ FOUND!")
                print(f"  Order ID: {order['ID']}")
                print(f"  Reference: {order['ReferenceNumber']}")
                print(f"  Customer ID: {order['CustomerID']}")
                print(f"  Total: {order['Total']}")
                print(f"  DateTime: {order['DateTime']}")
            else:
                print(f"❌ NOT FOUND by reference number")
            
            # Check by ID 114827 (from logs)
            print(f"\n2️⃣  Searching by Order ID: 114827")
            result = await session.execute(
                text("SELECT * FROM [Order] WHERE ID = :id"),
                {"id": 114827}
            )
            order_by_id = result.mappings().first()
            
            if order_by_id:
                print(f"✅ FOUND!")
                print(f"  Order ID: {order_by_id['ID']}")
                print(f"  Reference: {order_by_id['ReferenceNumber']}")
                print(f"  Customer ID: {order_by_id['CustomerID']}")
                print(f"  Total: {order_by_id['Total']}")
                print(f"  ChannelType: {order_by_id['ChannelType']}")
                print(f"  DateTime: {order_by_id['DateTime']}")
                
                # Get order entries
                print(f"\n  📦 Order Entries:")
                result = await session.execute(
                    text("""
                        SELECT ID, ItemID, Description, Price, FullPrice, QuantityOnOrder
                        FROM OrderEntry
                        WHERE OrderID = :order_id
                    """),
                    {"order_id": 114827}
                )
                entries = result.mappings().all()
                
                if entries:
                    for entry in entries:
                        print(f"    ✅ Entry {entry['ID']}: {entry['Description']} - "
                              f"₡{entry['Price']} x {entry['QuantityOnOrder']}")
                else:
                    print(f"    ⚠️  No entries found")
            else:
                print(f"❌ NOT FOUND by ID")
            
            # Check last 10 Shopify orders
            print(f"\n3️⃣  Last 10 Shopify Orders (ChannelType=2):")
            result = await session.execute(
                text("""
                    SELECT TOP 10 ID, ReferenceNumber, Total, DateTime
                    FROM [Order]
                    WHERE ChannelType = 2
                    ORDER BY ID DESC
                """)
            )
            recent = result.mappings().all()
            
            if recent:
                for o in recent:
                    marker = "👉" if o['ID'] == 114827 else "  "
                    print(f"{marker} ID={o['ID']}, Ref={o['ReferenceNumber']}, "
                          f"Total={o['Total']}, Date={o['DateTime']}")
            
            # Count total Shopify orders
            print(f"\n4️⃣  Total Shopify Orders:")
            result = await session.execute(
                text("SELECT COUNT(*) as count FROM [Order] WHERE ChannelType = 2")
            )
            count = result.scalar()
            print(f"  Total: {count} orders with ChannelType=2")
        
        await db.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
