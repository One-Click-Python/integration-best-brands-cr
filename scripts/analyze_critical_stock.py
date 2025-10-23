#!/usr/bin/env python3
"""
Analizar productos críticos sin stock que necesitan sincronización inmediata
"""

import asyncio
import logging
from typing import Dict

from sqlalchemy import text

from app.db.rms.query_executor import QueryExecutor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def get_critical_products_from_rms(query_executor: QueryExecutor) -> Dict:
    """Obtener productos críticos que necesitan sincronización inmediata"""

    async with query_executor.get_session() as session:
        # 1. Productos con stock NEGATIVO (oversold - CRÍTICO)
        query_negative = """
        SELECT CCOD, MIN(Description) as Description, 
               SUM(Quantity) as TotalQuantity, COUNT(*) as Variants,
               MIN(Price) as MinPrice, MAX(Price) as MaxPrice
        FROM View_Items
        WHERE CCOD IS NOT NULL
        AND CCOD != ''
        AND C_ARTICULO IS NOT NULL
        AND Description IS NOT NULL
        AND Price > 0
        AND Quantity < 0
        GROUP BY CCOD
        ORDER BY SUM(Quantity) ASC
        """

        result = await session.execute(text(query_negative))
        negative_stock = result.fetchall()

        # 2. Productos en OFERTA sin stock (TOP 100)
        query_sale_zero = """
        SELECT TOP 100 CCOD, MIN(Description) as Description,
               MIN(Price) as Price, MIN(SalePrice) as SalePrice,
               CAST((MIN(Price) - MIN(SalePrice)) * 100.0 / MIN(Price) as DECIMAL(5,2)) as DiscountPercent,
               COUNT(*) as Variants
        FROM View_Items
        WHERE CCOD IS NOT NULL
        AND CCOD != ''
        AND C_ARTICULO IS NOT NULL
        AND Description IS NOT NULL
        AND Price > 0
        AND Quantity = 0
        AND SalePrice IS NOT NULL
        AND SalePrice > 0
        AND SalePrice < Price
        GROUP BY CCOD
        ORDER BY (MIN(Price) - MIN(SalePrice)) DESC
        """

        result = await session.execute(text(query_sale_zero))
        sale_zero_stock = result.fetchall()

        # 3. Productos recientemente agotados (si tuvieran fecha)
        # Por ahora, tomamos productos con mayor variedad de tallas sin stock
        query_recently_out = """
        SELECT TOP 50 CCOD, MIN(Description) as Description,
               COUNT(DISTINCT Talla) as SizesOutOfStock,
               COUNT(*) as TotalVariants
        FROM View_Items
        WHERE CCOD IS NOT NULL
        AND CCOD != ''
        AND C_ARTICULO IS NOT NULL
        AND Description IS NOT NULL
        AND Price > 0
        AND Quantity = 0
        GROUP BY CCOD
        HAVING COUNT(DISTINCT Talla) >= 5
        ORDER BY COUNT(DISTINCT Talla) DESC
        """

        result = await session.execute(text(query_recently_out))
        recently_out = result.fetchall()

        return {"negative_stock": negative_stock, "sale_zero_stock": sale_zero_stock, "recently_out": recently_out}


async def analyze_and_recommend():
    """Analizar productos críticos y dar recomendaciones específicas"""

    query_executor = QueryExecutor()
    await query_executor.initialize()

    try:
        print("=" * 80)
        print("ANÁLISIS DE PRODUCTOS CRÍTICOS SIN STOCK")
        print("=" * 80)

        critical_products = await get_critical_products_from_rms(query_executor)

        # Productos con stock negativo
        print("\n🚨 PRODUCTOS CON STOCK NEGATIVO (OVERSELLING):")
        print("-" * 80)

        if critical_products["negative_stock"]:
            critical_ccods = []
            for i, row in enumerate(critical_products["negative_stock"][:20], 1):
                print(f"{i:2}. CCOD: {row.CCOD:15s} | Stock: {int(row.TotalQuantity):4d} | {row.Description[:40]:40s}")
                critical_ccods.append(row.CCOD)

            total_negative = len(critical_products["negative_stock"])
            print(f"\nTotal productos con stock negativo: {total_negative}")
            print("⚠️  ACCIÓN: Sincronizar INMEDIATAMENTE estos productos")

            # Crear lista para sincronización
            with open("sync_critical_negative.txt", "w") as f:
                for ccod in [r.CCOD for r in critical_products["negative_stock"]]:
                    f.write(f"{ccod}\n")
            print("✅ Lista guardada en: sync_critical_negative.txt")
        else:
            print("✅ No hay productos con stock negativo")

        # Productos en oferta sin stock
        print("\n💰 TOP PRODUCTOS EN OFERTA SIN STOCK:")
        print("-" * 80)

        if critical_products["sale_zero_stock"]:
            sale_ccods = []
            for i, row in enumerate(critical_products["sale_zero_stock"][:10], 1):
                discount = row.DiscountPercent if row.DiscountPercent else 0
                print(f"{i:2}. CCOD: {row.CCOD:15s} | Desc: {discount:5.1f}% | {row.Description[:35]:35s}")
                sale_ccods.append(row.CCOD)

            print(f"\nTotal productos en oferta sin stock: {len(critical_products['sale_zero_stock'])}")
            print("💡 ACCIÓN: Actualizar estos productos para evitar ventas perdidas")

            # Crear lista para sincronización
            with open("sync_sale_zero_stock.txt", "w") as f:
                for ccod in [r.CCOD for r in critical_products["sale_zero_stock"]]:
                    f.write(f"{ccod}\n")
            print("✅ Lista guardada en: sync_sale_zero_stock.txt")

        # Productos con muchas tallas agotadas
        print("\n👟 PRODUCTOS CON MÚLTIPLES TALLAS AGOTADAS:")
        print("-" * 80)

        if critical_products["recently_out"]:
            for i, row in enumerate(critical_products["recently_out"][:10], 1):
                print(
                    f"{i:2}. CCOD: {row.CCOD:15s} | Tallas sin stock: {row.SizesOutOfStock:2d} | {
                        row.Description[:30]:30s}"
                )

            print("\n💡 Estos productos probablemente se vendieron recientemente")

        # Resumen ejecutivo
        print("\n" + "=" * 80)
        print("📊 RESUMEN EJECUTIVO Y PLAN DE ACCIÓN")
        print("=" * 80)

        total_critical = len(critical_products["negative_stock"])
        total_sale = min(100, len(critical_products["sale_zero_stock"]))
        total_urgent = total_critical + total_sale

        print(
            f"""
SINCRONIZACIÓN INMEDIATA (Prioridad CRÍTICA):
----------------------------------------------
1. Productos con stock negativo: {total_critical} productos
   → Archivo: sync_critical_negative.txt
   → Comando: python sync_products.py --file sync_critical_negative.txt --force

2. Productos en oferta sin stock: {total_sale} productos  
   → Archivo: sync_sale_zero_stock.txt
   → Comando: python sync_products.py --file sync_sale_zero_stock.txt

TOTAL URGENTE: {total_urgent} productos
Tiempo estimado: {(total_urgent * 2) // 60} minutos ({total_urgent * 2} segundos a 2 seg/producto)

PRÓXIMOS PASOS:
--------------
1. Sincronizar productos críticos (stock negativo) AHORA
2. Sincronizar productos en oferta sin stock
3. Implementar sincronización incremental basada en cambios
4. Configurar sincronización automática cada 6 horas para productos críticos
"""
        )

    finally:
        await query_executor.close()


async def create_sync_command_for_critical():
    """Crear comando específico para sincronizar solo productos críticos"""

    print("\n" + "=" * 80)
    print("🚀 COMANDO DE SINCRONIZACIÓN PARA PRODUCTOS CRÍTICOS")
    print("=" * 80)

    print(
        """
# Sincronizar productos con stock negativo (overselling)
curl -X POST http://localhost:8000/api/sync/products \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{
    "sync_mode": "critical",
    "filters": {
        "stock_negative": true,
        "limit": 100
    },
    "batch_size": 10,
    "page_size": 50
  }'

# Sincronizar productos en oferta sin stock
curl -X POST http://localhost:8000/api/sync/products \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{
    "sync_mode": "sale_zero_stock", 
    "filters": {
        "on_sale": true,
        "stock_zero": true,
        "limit": 100
    },
    "batch_size": 10,
    "page_size": 50
  }'
"""
    )


if __name__ == "__main__":
    asyncio.run(analyze_and_recommend())
    asyncio.run(create_sync_command_for_critical())
