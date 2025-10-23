#!/usr/bin/env python3
"""
Script de prueba para buscar un CCOD específico en RMS
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import text

from app.db.rms.query_executor import QueryExecutor


async def search_ccod(ccod: str):
    """Busca un CCOD específico en RMS con diferentes variaciones."""

    query_executor = QueryExecutor()
    await query_executor.initialize()

    try:
        # Búsqueda directa por CCOD
        print(f"🔍 Buscando CCOD: {ccod}")
        print("=" * 50)

        async with query_executor.get_session() as session:
            # Buscar con diferentes variaciones
            queries = [
                # Búsqueda exacta
                f"SELECT CCOD, C_ARTICULO, Description, color, talla, Quantity, Price FROM View_Items WHERE CCOD = '{
                    ccod
                }' ORDER BY C_ARTICULO",
                # Búsqueda con LIKE
                f"SELECT CCOD, C_ARTICULO, Description, color, talla, Quantity, Price FROM View_Items WHERE\
                    CCOD LIKE '%{ccod}%' ORDER BY C_ARTICULO",
                # Búsqueda sin filtros de precio
                f"SELECT CCOD, C_ARTICULO, Description, color, talla, Quantity, Price FROM View_Items WHERE CCOD = '{
                    ccod
                }' ORDER BY C_ARTICULO",
                # Búsqueda en toda la tabla similar
                f"SELECT TOP 10 CCOD, C_ARTICULO, Description, color, talla, Quantity, Price FROM\
                    View_Items WHERE CCOD LIKE '{ccod[:3]}%' ORDER BY C_ARTICULO",
            ]

            for i, query in enumerate(queries, 1):
                print(f"\n📋 Consulta {i}:")
                print(f"   {query}")

                try:
                    result = await session.execute(text(query))
                    rows = result.fetchall()

                    if rows:
                        print(f"✅ Encontrados {len(rows)} resultados:")
                        for row in rows:
                            ccod_val, sku, desc, color, size, qty, price = row
                            print(
                                f"   CCOD: {ccod_val}, SKU: {sku}, Color: {color}, Talla: {size}, Qty: {qty}, Precio: {
                                    price
                                }"
                            )
                            print(f"   Desc: {desc}")
                    else:
                        print("❌ Sin resultados")

                except Exception as e:
                    print(f"❌ Error en consulta: {e}")

    finally:
        await query_executor.close()


async def main():
    ccod = "24X104"
    if len(sys.argv) > 1:
        ccod = sys.argv[1]

    await search_ccod(ccod)


if __name__ == "__main__":
    asyncio.run(main())
