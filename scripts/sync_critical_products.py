#!/usr/bin/env python3
"""
Sincronización selectiva de productos críticos con Shopify
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import List

from sqlalchemy import text

from app.db.rms.query_executor import QueryExecutor
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.rms_to_shopify.product_processor import ProductProcessor

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class CriticalProductSync:
    """Sincronización de productos críticos"""

    def __init__(self):
        self.query_executor = None
        self.shopify_client = None
        self.product_processor = None
        self.stats = {"total_products": 0, "synced": 0, "errors": 0, "skipped": 0}

    async def initialize(self):
        """Inicializar conexiones"""
        self.query_executor = QueryExecutor()
        await self.query_executor.initialize()

        self.shopify_client = ShopifyGraphQLClient()
        await self.shopify_client.initialize()

        self.product_processor = ProductProcessor(shopify_client=self.shopify_client, batch_size=5)
        logger.info("✅ Sistema inicializado")

    async def close(self):
        """Cerrar conexiones"""
        if self.query_executor:
            await self.query_executor.close()
        if self.shopify_client:
            await self.shopify_client.close()

    async def get_negative_stock_products(self) -> List[str]:
        """Obtener productos con stock negativo"""
        async with self.query_executor.get_session() as session:
            query = """
            SELECT DISTINCT CCOD
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
            result = await session.execute(text(query))
            return [row.CCOD for row in result.fetchall()]

    async def get_sale_zero_stock_products(self, limit: int = 100) -> List[str]:
        """Obtener productos en oferta sin stock"""
        async with self.query_executor.get_session() as session:
            query = f"""
            SELECT TOP {limit} CCOD
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
            result = await session.execute(text(query))
            return [row.CCOD for row in result.fetchall()]

    async def get_products_from_file(self, filename: str) -> List[str]:
        """Leer lista de productos desde archivo"""
        products = []
        try:
            with open(filename, "r") as f:
                for line in f:
                    ccod = line.strip()
                    if ccod:
                        products.append(ccod)
            logger.info(f"📄 Leídos {len(products)} productos desde {filename}")
        except FileNotFoundError:
            logger.error(f"❌ Archivo no encontrado: {filename}")
        return products

    async def check_product_exists_in_shopify(self, ccod: str) -> bool:
        """Verificar si un producto existe en Shopify"""
        try:
            # Buscar por handle o tag
            query = """
            query($query: String!) {
                products(first: 1, query: $query) {
                    edges {
                        node {
                            id
                            handle
                            tags
                        }
                    }
                }
            }
            """

            # Buscar por tag ccod_ o en el handle
            search_query = f"tag:ccod_{ccod.lower()} OR handle:*{ccod.lower()}*"
            variables = {"query": search_query}

            response = await self.shopify_client._execute_query(query, variables)

            if response and "products" in response:
                return len(response["products"]["edges"]) > 0

            return False

        except Exception as e:
            logger.error(f"Error verificando producto {ccod}: {e}")
            return False

    async def sync_single_product(self, ccod: str, force_update: bool = False):
        """Sincronizar un producto individual"""
        try:
            logger.info(f"🔄 Sincronizando producto {ccod}...")

            # Verificar si existe en Shopify si no forzamos actualización
            if not force_update:
                exists = await self.check_product_exists_in_shopify(ccod)
                if not exists:
                    logger.info(f"⏭️  Producto {ccod} no existe en Shopify, saltando...")
                    self.stats["skipped"] += 1
                    return

            # Obtener datos del producto desde RMS
            async with self.query_executor.get_session() as session:
                query = """
                SELECT CCOD, C_ARTICULO, Description, Price, SalePrice, 
                       Quantity, Categoria, Talla, Color, Brand
                FROM View_Items
                WHERE CCOD = :ccod
                AND C_ARTICULO IS NOT NULL
                AND Description IS NOT NULL
                ORDER BY C_ARTICULO
                """

                result = await session.execute(text(query), {"ccod": ccod})
                items = result.fetchall()

                if not items:
                    logger.warning(f"⚠️  No se encontraron items para CCOD {ccod}")
                    self.stats["skipped"] += 1
                    return

                # Preparar estructura del producto para ProductProcessor
                product_data = {"ccod": ccod, "items": []}

                for item in items:
                    product_data["items"].append(
                        {
                            "CCOD": item.CCOD,
                            "C_ARTICULO": item.C_ARTICULO,
                            "Description": item.Description,
                            "Price": float(item.Price),
                            "SalePrice": float(item.SalePrice) if item.SalePrice else None,
                            "Quantity": int(item.Quantity),
                            "Categoria": item.Categoria,
                            "Talla": item.Talla,
                            "Color": item.Color,
                            "Brand": item.Brand,
                        }
                    )

                # TODO: Sincronizar con Shopify usando ProductProcessor
                # El método process_single_product no existe en ProductProcessor
                # Se necesita refactorizar para usar process_products_in_batches_optimized
                logger.warning(
                    f"⚠️  Sincronización no implementada para producto {ccod} - "
                    "Se requiere usar process_products_in_batches_optimized"
                )
                self.stats["skipped"] += 1

        except Exception as e:
            logger.error(f"❌ Error procesando producto {ccod}: {e}")
            self.stats["errors"] += 1

    async def sync_products_batch(self, ccods: List[str], batch_size: int = 5, force_update: bool = False):
        """Sincronizar productos en lotes"""
        total = len(ccods)
        self.stats["total_products"] = total

        logger.info(f"📦 Iniciando sincronización de {total} productos en lotes de {batch_size}")

        for i in range(0, total, batch_size):
            batch = ccods[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (total + batch_size - 1) // batch_size

            logger.info(f"🔄 Procesando lote {batch_num}/{total_batches}")

            # Procesar lote en paralelo
            tasks = [self.sync_single_product(ccod, force_update) for ccod in batch]
            await asyncio.gather(*tasks)

            # Mostrar progreso
            processed = min(i + batch_size, total)
            progress = (processed / total) * 100
            logger.info(f"📊 Progreso: {processed}/{total} ({progress:.1f}%)")

            # Pequeña pausa entre lotes
            if i + batch_size < total:
                await asyncio.sleep(1)

        # Mostrar resumen
        logger.info("=" * 60)
        logger.info("📊 RESUMEN DE SINCRONIZACIÓN")
        logger.info("=" * 60)
        logger.info(f"Total productos: {self.stats['total_products']}")
        logger.info(f"✅ Sincronizados: {self.stats['synced']}")
        logger.info(f"⏭️  Saltados: {self.stats['skipped']}")
        logger.info(f"❌ Errores: {self.stats['errors']}")

        success_rate = (self.stats["synced"] / total * 100) if total > 0 else 0
        logger.info(f"🎯 Tasa de éxito: {success_rate:.1f}%")


async def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description="Sincronización selectiva de productos críticos")
    parser.add_argument(
        "--mode",
        choices=["negative", "sale", "file"],
        required=True,
        help="Modo de sincronización: negative (stock negativo), sale (ofertas sin stock), file (desde archivo)",
    )
    parser.add_argument("--file", help="Archivo con lista de CCODs (para modo file)")
    parser.add_argument("--limit", type=int, default=100, help="Límite de productos (para modo sale)")
    parser.add_argument("--batch-size", type=int, default=5, help="Tamaño del lote")
    parser.add_argument("--force", action="store_true", help="Forzar actualización aunque no exista en Shopify")

    args = parser.parse_args()

    sync = CriticalProductSync()

    try:
        await sync.initialize()

        # Obtener lista de productos según el modo
        ccods: List[str] = []
        if args.mode == "negative":
            logger.info("🚨 Modo: Productos con stock NEGATIVO")
            ccods = await sync.get_negative_stock_products()

        elif args.mode == "sale":
            logger.info(f"💰 Modo: Productos en OFERTA sin stock (límite: {args.limit})")
            ccods = await sync.get_sale_zero_stock_products(args.limit)

        elif args.mode == "file":
            if not args.file:
                logger.error("❌ Debe especificar un archivo con --file")
                return
            logger.info(f"📄 Modo: Productos desde archivo {args.file}")
            ccods = await sync.get_products_from_file(args.file)

        if not ccods:
            logger.warning("⚠️  No se encontraron productos para sincronizar")
            return

        # Sincronizar productos
        start_time = datetime.now()
        await sync.sync_products_batch(ccods, args.batch_size, args.force)
        end_time = datetime.now()

        duration = (end_time - start_time).total_seconds()
        logger.info(f"⏱️  Tiempo total: {duration:.1f} segundos")

    except KeyboardInterrupt:
        logger.info("\n⚠️  Sincronización interrumpida por el usuario")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}", exc_info=True)
    finally:
        await sync.close()


if __name__ == "__main__":
    asyncio.run(main())
