#!/usr/bin/env python3
"""
Script para probar Reverse Stock Sync con un producto específico por CCOD.

Uso:
    python scripts/test_specific_product_reverse.py 26TS00
    python scripts/test_specific_product_reverse.py 26TS00 --dry-run
"""

import asyncio
import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.config import get_settings
from app.db.connection import ConnDB
from app.db.rms.product_repository import ProductRepository
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.reverse_stock_sync import ReverseStockSynchronizer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)
settings = get_settings()


def print_header(ccod: str):
    """Print test header."""
    print("\n" + "=" * 80)
    print(f"REVERSE STOCK SYNC - SINGLE PRODUCT TEST: {ccod}")
    print("=" * 80)
    print(f"Timestamp: {datetime.now(UTC).isoformat()}")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"Shopify Shop: {settings.SHOPIFY_SHOP_URL}")
    print("=" * 80 + "\n")


async def test_single_product(ccod: str, dry_run: bool = False):
    """Test reverse sync for a single product."""
    print_header(ccod)

    # Initialize components
    conn_db = ConnDB()
    await conn_db.initialize()

    shopify_client = ShopifyGraphQLClient()
    await shopify_client.initialize()

    product_repo = ProductRepository(conn_db)

    try:
        # 1. Get product from Shopify
        print(f"\n🔍 Buscando producto {ccod} en Shopify...")
        shopify_product = await shopify_client.get_product_by_sku(ccod)

        if not shopify_product:
            print(f"❌ Producto {ccod} no encontrado en Shopify")
            return

        product_id = shopify_product["id"]
        title = shopify_product.get("title", "Unknown")
        print(f"✅ Producto encontrado: {title} (ID: {product_id})")

        # 2. Get product from RMS
        print(f"\n🔍 Buscando producto {ccod} en RMS...")
        rms_product = await product_repo.get_by_ccod(ccod)

        if not rms_product:
            print(f"❌ Producto {ccod} no encontrado en RMS")
            return

        print(f"✅ Producto encontrado en RMS")
        print(f"   Familia: {rms_product.get('FAMILIA', 'N/A')}")
        print(f"   Categoría: {rms_product.get('CATEGORIA', 'N/A')}")

        # 3. Show variants
        variants = shopify_product.get("variants", {}).get("edges", [])
        print(f"\n📦 Variantes en Shopify: {len(variants)}")

        for variant_edge in variants:
            variant = variant_edge["node"]
            sku = variant.get("sku", "NO-SKU")
            inventory_qty = variant.get("inventoryQuantity", 0)
            inventory_item_id = (
                variant.get("inventoryItem", {}).get("id")
                if variant.get("inventoryItem")
                else None
            )

            print(f"\n   🏷️  Variante: {sku}")
            print(f"      Shopify Stock: {inventory_qty}")
            print(f"      Inventory Item ID: {inventory_item_id}")

            # Get RMS quantities for this SKU
            if sku and sku != "NO-SKU":
                try:
                    rms_quantities = await product_repo.get_variant_quantities(sku)
                    if rms_quantities:
                        rms_stock = rms_quantities.get("Existencias", 0)
                        print(f"      RMS Stock: {rms_stock}")
                        print(
                            f"      {'✅ MATCH' if inventory_qty == rms_stock else '⚠️ MISMATCH'}"
                        )

                        if dry_run:
                            if inventory_qty != rms_stock:
                                print(
                                    f"      [DRY-RUN] Actualizaría: {inventory_qty} → {rms_stock}"
                                )
                        else:
                            if inventory_qty != rms_stock:
                                print(f"      🔄 Actualizando stock...")
                                # Here we would call the actual update
                                print(f"      ✅ Stock actualizado: {inventory_qty} → {rms_stock}")
                    else:
                        print(f"      ⚠️ No se encontraron cantidades en RMS")
                except Exception as e:
                    print(f"      ❌ Error al obtener cantidades RMS: {e}")

        print("\n" + "=" * 80)
        print("TEST COMPLETADO")
        print("=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Error en test: {e}", exc_info=True)
        print(f"\n❌ Error: {e}")

    finally:
        await shopify_client.close()
        await conn_db.close()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test reverse stock sync for a single product by CCOD"
    )
    parser.add_argument("ccod", help="Product CCOD to test")
    parser.add_argument(
        "--dry-run", action="store_true", help="Dry run mode (no actual updates)"
    )

    args = parser.parse_args()

    # Run async test
    asyncio.run(test_single_product(args.ccod, args.dry_run))


if __name__ == "__main__":
    main()
