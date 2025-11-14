"""
Script to list ALL recent orders from Shopify to find order #1013.
"""

import asyncio
from datetime import UTC, datetime

from app.db.shopify_clients.base_client import BaseShopifyGraphQLClient


async def list_all_orders():
    """List all recent orders."""
    client = None
    try:
        print("🔍 Listing ALL recent orders from Shopify...")
        print("=" * 80)

        client = BaseShopifyGraphQLClient()
        await client.initialize()

        # Query for ALL orders (no time filter)
        query = """
        query listOrders($first: Int!, $after: String) {
          orders(first: $first, after: $after, reverse: true) {
            edges {
              node {
                id
                legacyResourceId
                name
                createdAt
                updatedAt
                displayFinancialStatus
                test
                totalPriceSet {
                  shopMoney {
                    amount
                    currencyCode
                  }
                }
              }
              cursor
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

        all_orders = []
        cursor = None
        page = 0

        # Fetch first 50 orders
        while page < 5:  # Limit to 5 pages (250 orders)
            page += 1
            variables = {"first": 50}
            if cursor:
                variables["after"] = cursor

            print(f"\n📄 Fetching page {page}...")
            response = await client._execute_single_query(query, variables)

            # Debug: print response
            if "errors" in response:
                print(f"   ❌ GraphQL Errors: {response['errors']}")
                break

            # BaseShopifyGraphQLClient already extracts 'data', so response IS the data
            if response and response.get("orders"):
                print(f"   ✅ Orders received")

                edges = response["orders"]["edges"]
                all_orders.extend(edges)

                print(f"   Found {len(edges)} orders on this page")

                page_info = response["orders"]["pageInfo"]
                if page_info["hasNextPage"]:
                    cursor = page_info["endCursor"]
                else:
                    print("   No more pages")
                    break
            else:
                print(f"   ⚠️  No orders found. Response keys: {response.keys() if response else 'None'}")
                break

        print(f"\n📊 Total orders fetched: {len(all_orders)}")
        print("=" * 80)

        # Display all orders
        for i, edge in enumerate(all_orders[:50], 1):  # Show first 50
            order = edge["node"]
            print(f"\n{i}. Order {order['name']}")
            print(f"   Legacy ID: {order.get('legacyResourceId', 'N/A')}")
            print(f"   GID: {order['id']}")
            print(f"   Updated: {order['updatedAt']}")
            print(f"   Status: {order['displayFinancialStatus']}")
            print(f"   Total: {order['totalPriceSet']['shopMoney']['amount']} {order['totalPriceSet']['shopMoney']['currencyCode']}")

        # Search for order #1013
        print("\n" + "=" * 80)
        print("🔍 Searching for order #1013...")
        found = False
        for edge in all_orders:
            order = edge["node"]
            if order["name"] == "#1013" or order.get("legacyResourceId") == "6157526401084":
                print(f"✅ FOUND IT!")
                print(f"   Name: {order['name']}")
                print(f"   Legacy ID: {order.get('legacyResourceId')}")
                print(f"   GID: {order['id']}")
                print(f"   Updated: {order['updatedAt']}")
                found = True
                break

        if not found:
            print("❌ Order #1013 or ID 6157526401084 NOT FOUND in fetched orders")
            print(f"   Checked {len(all_orders)} orders")

        print("=" * 80)

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if client:
            await client.close()


if __name__ == "__main__":
    asyncio.run(list_all_orders())
