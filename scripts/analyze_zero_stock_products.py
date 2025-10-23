#!/usr/bin/env python3
"""
Analizar productos sin stock para determinar cuáles necesitan sincronización
"""

import asyncio
import logging
from typing import Set

from sqlalchemy import text

from app.db.rms.query_executor import QueryExecutor
from app.db.shopify_graphql_client import ShopifyGraphQLClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_shopify_products() -> Set[str]:
    """Obtener todos los handles de productos existentes en Shopify"""
    shopify_client = ShopifyGraphQLClient()
    await shopify_client.initialize()

    try:
        all_products = []
        has_next_page = True
        cursor = None

        while has_next_page:
            query = """
            query($cursor: String) {
                products(first: 250, after: $cursor) {
                    edges {
                        node {
                            handle
                            tags
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
            """

            variables = {"cursor": cursor}
            response = await shopify_client._execute_query(query, variables)

            if response and "products" in response:
                for edge in response["products"]["edges"]:
                    product = edge["node"]
                    # Extraer CCOD del handle o tags
                    handle = product["handle"]
                    tags = product.get("tags", [])

                    # El CCOD puede estar en el handle o en un tag como "ccod_XXXX"
                    ccod = None
                    for tag in tags:
                        if tag.startswith("ccod_"):
                            ccod = tag.replace("ccod_", "").upper()
                            break

                    if not ccod and handle:
                        # El handle podría contener el CCOD
                        ccod = handle.split("-")[0].upper()

                    if ccod:
                        all_products.append(ccod)

                has_next_page = response["products"]["pageInfo"]["hasNextPage"]
                cursor = response["products"]["pageInfo"]["endCursor"]
            else:
                break

        logger.info(f"Found {len(all_products)} products in Shopify")
        return set(all_products)

    finally:
        await shopify_client.close()


async def analyze_zero_stock_products():
    """Analizar productos sin stock y determinar estrategia de sincronización"""

    query_executor = QueryExecutor()
    await query_executor.initialize()

    try:
        async with query_executor.get_session() as session:

            print("=" * 80)
            print("ANÁLISIS DE PRODUCTOS SIN STOCK")
            print("=" * 80)

            # Categorías de productos sin stock
            query_categories = """
            SELECT Categoria, COUNT(DISTINCT CCOD) as product_count
            FROM View_Items
            WHERE CCOD IS NOT NULL
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            AND Quantity = 0
            GROUP BY Categoria
            ORDER BY COUNT(DISTINCT CCOD) DESC
            """

            result = await session.execute(text(query_categories))
            categories = result.fetchall()

            print("\nTOP 20 CATEGORÍAS CON PRODUCTOS SIN STOCK:")
            print("-" * 80)
            total_zero_stock = 0
            for i, row in enumerate(categories[:20], 1):
                print(f"{i:2}. {row.Categoria:30s} | {row.product_count:6,} productos")
                total_zero_stock += row.product_count

            # 3. Productos sin stock pero con precio de oferta activo (podrían ser importantes)
            query_sale = """
            SELECT COUNT(DISTINCT CCOD) as total
            FROM View_Items
            WHERE CCOD IS NOT NULL
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            AND Quantity = 0
            AND SalePrice IS NOT NULL
            AND SalePrice > 0
            """

            result = await session.execute(text(query_sale))
            products_on_sale = result.fetchone().total

            print(f"\n📊 Productos sin stock pero EN OFERTA: {products_on_sale:,}")
            print("   (Estos podrían reabastecerse pronto)")

            # 4. Productos con stock negativo (oversold)
            query_negative = """
            SELECT COUNT(DISTINCT CCOD) as total
            FROM View_Items
            WHERE CCOD IS NOT NULL
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            AND Quantity < 0
            """

            result = await session.execute(text(query_negative))
            negative_stock = result.fetchone().total

            print(f"\n⚠️  Productos con stock NEGATIVO: {negative_stock:,}")
            print("   (Estos DEBEN sincronizarse para reflejar overselling)")

            # 5. Obtener muestra de productos sin stock
            query_sample = """
            SELECT TOP 10 CCOD, MIN(Description) as Description, 
                   SUM(Quantity) as TotalQuantity, COUNT(*) as Variants
            FROM View_Items
            WHERE CCOD IS NOT NULL
            AND CCOD != ''
            AND C_ARTICULO IS NOT NULL
            AND Description IS NOT NULL
            AND Price > 0
            AND Quantity <= 0
            GROUP BY CCOD
            ORDER BY COUNT(*) DESC
            """

            result = await session.execute(text(query_sample))
            samples = result.fetchall()

            print("\n" + "=" * 80)
            print("MUESTRA DE PRODUCTOS SIN STOCK:")
            print("-" * 80)
            for row in samples:
                print(f"CCOD: {row.CCOD:15s} | {row.Description[:40]:40s} | Variantes: {row.Variants:3d}")

    finally:
        await query_executor.close()

    # Verificar cuáles existen en Shopify
    print("\n" + "=" * 80)
    print("VERIFICANDO PRODUCTOS EN SHOPIFY...")
    print("-" * 80)

    shopify_products = await get_shopify_products()
    print(f"✅ Productos encontrados en Shopify: {len(shopify_products):,}")

    # Estrategias recomendadas
    print("\n" + "=" * 80)
    print("📋 ESTRATEGIAS RECOMENDADAS:")
    print("=" * 80)

    print(
        """
1. SINCRONIZACIÓN INMEDIATA (Alta prioridad):
   - Productos con stock negativo: Actualizar para mostrar overselling
   - Productos en oferta sin stock: Actualizar para quitar de disponibles
   - Total estimado: < 1,000 productos

2. SINCRONIZACIÓN SELECTIVA (Media prioridad):
   - Solo productos que YA existen en Shopify
   - Actualizar stock a 0 para productos agotados
   - Usar: sync_only_existing=True

3. SINCRONIZACIÓN POR CATEGORÍAS (Baja prioridad):
   - Seleccionar 5-10 categorías principales
   - Sincronizar todos los productos de esas categorías
   - Ignorar categorías obsoletas o de temporadas pasadas

4. SINCRONIZACIÓN DIFERENCIAL (Óptima):
   - Implementar campo LastUpdated en RMS
   - Solo sincronizar productos modificados en últimos 30 días
   - Reduce carga de ~98,000 a probablemente < 5,000 productos
"""
    )


if __name__ == "__main__":
    asyncio.run(analyze_zero_stock_products())
