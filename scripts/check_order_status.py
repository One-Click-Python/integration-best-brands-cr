#!/usr/bin/env python3
"""Check order status with full details including updatedAt."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.shopify_clients.base_client import BaseShopifyGraphQLClient


async def main():
    print("\n" + "=" * 80)
    print("🔍 ORDER #1013 FULL QUERY (with updatedAt)")
    print("=" * 80)
    
    client = BaseShopifyGraphQLClient()
    await client.initialize()
    
    try:
        query = """
        query GetOrder($id: ID!) {
          order(id: $id) {
            id
            legacyResourceId
            name
            createdAt
            updatedAt
            email
            displayFinancialStatus
            displayFulfillmentStatus
            test
            confirmed
            closed
          }
        }
        """
        
        order_id = "gid://shopify/Order/6157526401084"
        print(f"\nQuerying order: {order_id}")
        
        result = await client._execute_query(query, {"id": order_id})
        order = result.get("order")
        
        if order:
            print("\n✅ Order found!")
            print(f"\nOrder Details:")
            print(f"  Name: {order.get('name')}")
            print(f"  Legacy ID: {order.get('legacyResourceId')}")
            print(f"  Created: {order.get('createdAt')}")
            print(f"  Updated: {order.get('updatedAt')}")  # This is key!
            print(f"  Email: {order.get('email')}")
            print(f"  Financial Status: {order.get('displayFinancialStatus')}")
            print(f"  Fulfillment Status: {order.get('displayFulfillmentStatus')}")
            print(f"  Test: {order.get('test')}")
            print(f"  Confirmed: {order.get('confirmed')}")
            print(f"  Closed: {order.get('closed')}")
            
            # Check time difference
            from datetime import UTC, datetime
            
            updated_at = order.get('updatedAt')
            if updated_at:
                updated_time = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                now = datetime.now(UTC)
                time_diff = now - updated_time
                minutes_ago = int(time_diff.total_seconds() / 60)
                
                print(f"\n⏰ Time Analysis:")
                print(f"  Updated: {updated_time.isoformat()}")
                print(f"  Now: {now.isoformat()}")
                print(f"  Minutes ago: {minutes_ago}")
                print(f"  Time difference: {time_diff}")
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
