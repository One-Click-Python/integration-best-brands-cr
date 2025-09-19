#!/usr/bin/env python3
"""
Script de prueba para verificar las optimizaciones de sincronización.

Este script puede ejecutarse para probar las nuevas funcionalidades:
1. Sistema de checkpoints
2. Búsqueda por lotes optimizada
3. Endpoints de progreso

Uso:
    python test_sync_optimization.py
"""

import asyncio
import logging
from datetime import datetime, timezone

from app.services.rms_to_shopify import RMSToShopifySync
from app.services.sync_checkpoint import SyncCheckpointManager

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

logger = logging.getLogger(__name__)


async def test_checkpoint_system():
    """Prueba el sistema de checkpoints."""
    logger.info("🧪 Probando sistema de checkpoints...")

    sync_id = f"test_sync_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    checkpoint_manager = SyncCheckpointManager(sync_id)

    try:
        await checkpoint_manager.initialize()

        # Simular progreso
        test_stats = {
            "total_processed": 0,
            "created": 0,
            "updated": 0,
            "errors": 0,
            "skipped": 0,
            "inventory_updated": 0,
            "inventory_failed": 0,
        }

        total_products = 1000

        for i in range(0, 101, 25):  # Simular progreso del 0% al 100% en pasos del 25%
            test_stats["total_processed"] = i * 10
            test_stats["created"] = i * 7
            test_stats["updated"] = i * 2
            test_stats["skipped"] = i * 1

            success = await checkpoint_manager.save_checkpoint(
                last_processed_ccod=f"TEST{i:03d}",
                processed_count=i * 10,
                total_count=total_products,
                stats=test_stats,
                batch_number=i // 25 + 1,
            )

            if success:
                logger.info(f"✅ Checkpoint guardado: {i * 10}/{total_products} productos")
            else:
                logger.error(f"❌ Error guardando checkpoint en {i}%")

            # Simular pausa
            await asyncio.sleep(1)

        # Probar recuperación
        progress_info = await checkpoint_manager.get_progress_info()
        logger.info(f"📊 Progreso recuperado: {progress_info}")

        # Limpiar
        await checkpoint_manager.delete_checkpoint()
        logger.info("🧹 Checkpoint eliminado")

        return True

    except Exception as e:
        logger.error(f"❌ Error en test de checkpoints: {e}")
        return False
    finally:
        await checkpoint_manager.close()


async def test_optimized_sync():
    """Prueba la sincronización optimizada con un pequeño lote."""
    logger.info("🧪 Probando sincronización optimizada...")

    sync_service = RMSToShopifySync()

    try:
        await sync_service.initialize()

        # Probar con un CCOD específico (cambiar por uno que exista en tu RMS)
        result = await sync_service.sync_products(
            force_update=False,
            batch_size=5,  # Lote pequeño para prueba
            filter_categories=None,
            include_zero_stock=False,
            cod_product="24X104",  # Usar un CCOD específico para prueba
        )

        logger.info(f"📊 Resultado de la sincronización: {result}")

        # Verificar métricas
        success_rate = result.get("success_rate", 0)
        if success_rate > 80:
            logger.info(f"✅ Sincronización exitosa: {success_rate}% de éxito")
            return True
        else:
            logger.warning(f"⚠️ Sincronización con problemas: {success_rate}% de éxito")
            return False

    except Exception as e:
        logger.error(f"❌ Error en test de sincronización: {e}")
        return False
    finally:
        await sync_service.close()


async def test_batch_search():
    """Prueba la búsqueda por lotes de productos."""
    logger.info("🧪 Probando búsqueda por lotes...")

    from app.db.shopify_graphql_client import ShopifyGraphQLClient

    client = ShopifyGraphQLClient()

    try:
        await client.initialize()

        # Probar búsqueda por lotes con handles de prueba
        test_handles = ["test-product-1", "test-product-2", "zapato-test-001", "ropa-test-002"]

        results = await client.products.get_products_by_handles_batch(test_handles)

        logger.info("🔍 Búsqueda por lotes completada:")
        for handle, product in results.items():
            if product:
                logger.info(f"  ✅ {handle}: {product.get('title', 'Sin título')}")
            else:
                logger.info(f"  ❌ {handle}: No encontrado")

        return True

    except Exception as e:
        logger.error(f"❌ Error en test de búsqueda por lotes: {e}")
        return False
    finally:
        await client.close()


async def run_all_tests():
    """Ejecuta todas las pruebas."""
    logger.info("🚀 Iniciando pruebas de optimización de sincronización...")

    tests = [
        ("Sistema de Checkpoints", test_checkpoint_system),
        ("Búsqueda por Lotes", test_batch_search),
        ("Sincronización Optimizada", test_optimized_sync),
    ]

    results = {}

    for test_name, test_func in tests:
        logger.info(f"\n{'=' * 50}")
        logger.info(f"🧪 Ejecutando: {test_name}")
        logger.info(f"{'=' * 50}")

        try:
            result = await test_func()
            results[test_name] = result

            if result:
                logger.info(f"✅ {test_name}: PASÓ")
            else:
                logger.error(f"❌ {test_name}: FALLÓ")

        except Exception as e:
            logger.error(f"💥 {test_name}: ERROR - {e}")
            results[test_name] = False

    # Resumen final
    logger.info(f"\n{'=' * 50}")
    logger.info("📊 RESUMEN DE PRUEBAS")
    logger.info(f"{'=' * 50}")

    passed = sum(1 for result in results.values() if result)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASÓ" if result else "❌ FALLÓ"
        logger.info(f"  {test_name}: {status}")

    logger.info(f"\n📈 Resultado final: {passed}/{total} pruebas pasaron")

    if passed == total:
        logger.info("🎉 ¡Todas las optimizaciones funcionan correctamente!")
    else:
        logger.warning("⚠️ Algunas optimizaciones necesitan revisión")

    return passed == total


if __name__ == "__main__":
    logger.info("🔧 Script de prueba de optimizaciones RMS-Shopify")
    logger.info("=" * 60)

    success = asyncio.run(run_all_tests())

    if success:
        logger.info("\n🚀 Las optimizaciones están listas para producción!")
        exit(0)
    else:
        logger.error("\n🛠️ Se requieren ajustes antes de usar en producción")
        exit(1)

