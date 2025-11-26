"""
Script para verificar si una orden específica de Shopify tiene costo de envío.

Usage:
    python scripts/check_order_shipping.py [ORDER_ID]

    Si no se proporciona ORDER_ID, consulta pedidos recientes.
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.db.shopify_clients.base_client import BaseShopifyGraphQLClient

settings = get_settings()

QUERY_GET_ORDER = """
query getOrder($id: ID!) {
  order(id: $id) {
    id
    name
    createdAt
    displayFinancialStatus
    totalPriceSet {
      shopMoney {
        amount
        currencyCode
      }
    }
    shippingLine {
      title
      discountedPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
      originalPriceSet {
        shopMoney {
          amount
          currencyCode
        }
      }
    }
    shippingLines(first: 5) {
      edges {
        node {
          id
          title
          discountedPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
          originalPriceSet {
            shopMoney {
              amount
              currencyCode
            }
          }
          taxLines {
            title
            rate
            priceSet {
              shopMoney {
                amount
                currencyCode
              }
            }
          }
        }
      }
    }
    totalShippingPriceSet {
      shopMoney {
        amount
        currencyCode
      }
    }
  }
}
"""


async def check_specific_order(order_id: str):
    """Check shipping info for a specific order."""
    print(f"🔍 Consultando pedido #{order_id}...\n")

    client = BaseShopifyGraphQLClient()

    try:
        await client.initialize()

        # Convert to GID format
        gid = f"gid://shopify/Order/{order_id}"
        variables = {"id": gid}

        # Execute query
        result = await client._execute_query(QUERY_GET_ORDER, variables)
        order = result.get("order")

        if not order:
            print(f"❌ Pedido no encontrado: {order_id}")
            return

        # Print order info
        print("="*80)
        print(f"📦 INFORMACIÓN DEL PEDIDO")
        print("="*80)
        print(f"ID: {order['id']}")
        print(f"Nombre: {order['name']}")
        print(f"Fecha: {order['createdAt']}")
        print(f"Estado: {order['displayFinancialStatus']}")

        total = order['totalPriceSet']['shopMoney']
        print(f"Total: {total['currencyCode']} {total['amount']}")

        # Shipping summary
        print("\n" + "-"*80)
        print("🚚 RESUMEN DE ENVÍO")
        print("-"*80)

        total_shipping = order.get('totalShippingPriceSet', {}).get('shopMoney', {})
        if total_shipping:
            amount = float(total_shipping.get('amount', 0))
            currency = total_shipping.get('currencyCode', 'CRC')
            print(f"💰 Total envío: {currency} {amount}")

            if amount > 0:
                print(f"✅ El pedido TIENE costo de envío - OrderEntry SERÁ creado")
            else:
                print(f"❌ El pedido NO tiene costo de envío - OrderEntry NO será creado")
        else:
            print("⚠️ No se encontró información de envío")

        # Shipping line details
        shipping_line = order.get('shippingLine')
        if shipping_line:
            print(f"\n📋 Detalles:")
            print(f"  Método: {shipping_line['title']}")

            discounted = shipping_line.get('discountedPriceSet', {}).get('shopMoney', {})
            if discounted:
                print(f"  Precio (con descuentos): {discounted['currencyCode']} {discounted['amount']}")

            original = shipping_line.get('originalPriceSet', {}).get('shopMoney', {})
            if original:
                print(f"  Precio original: {original['currencyCode']} {original['amount']}")

        # Detailed shipping lines
        shipping_lines = order.get('shippingLines', {}).get('edges', [])
        if shipping_lines and len(shipping_lines) > 0:
            print(f"\n📦 Líneas de envío ({len(shipping_lines)}):")

            for idx, edge in enumerate(shipping_lines, 1):
                node = edge['node']
                print(f"\n  [{idx}] {node['title']}")

                discounted = node.get('discountedPriceSet', {}).get('shopMoney', {})
                if discounted:
                    print(f"      Precio: {discounted['currencyCode']} {discounted['amount']}")

                # Tax info
                tax_lines = node.get('taxLines', [])
                if tax_lines:
                    print(f"      Impuestos:")
                    for tax in tax_lines:
                        tax_amount = tax['priceSet']['shopMoney']
                        rate = tax['rate'] * 100
                        print(f"        - {tax['title']}: {tax_amount['amount']} ({rate}%)")

        print("\n" + "="*80)

    finally:
        await client.close()


async def main():
    """Main function."""
    # Check if order ID provided as argument
    if len(sys.argv) > 1:
        order_id = sys.argv[1]
    else:
        # Default order ID from URL: https://admin.shopify.com/store/best-brands-cr/orders/6152834482236
        order_id = "6152834482236"
        print(f"ℹ️  No se proporcionó ORDER_ID, usando por defecto: {order_id}")
        print(f"   (Usa: python scripts/check_order_shipping.py <ORDER_ID>)\n")

    await check_specific_order(order_id)


if __name__ == "__main__":
    asyncio.run(main())
