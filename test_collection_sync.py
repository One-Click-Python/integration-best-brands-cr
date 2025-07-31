#!/usr/bin/env python3
"""
Script de prueba para sincronización de colecciones basadas en categorías RMS.

Este script demuestra cómo la sincronización RMS->Shopify ahora crea automáticamente
colecciones basadas en las categorías/familias de RMS y asigna productos a ellas.
"""

import asyncio
import logging
from datetime import datetime

from app.services.rms_to_shopify import RMSToShopifySync
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.collection_manager import CollectionManager

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(f'collection_sync_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    ]
)
logger = logging.getLogger(__name__)


async def test_collection_creation():
    """
    Prueba la creación de colecciones y asignación de productos.
    """
    shopify_client = None
    collection_manager = None
    
    try:
        # Inicializar cliente Shopify
        logger.info("🚀 Inicializando cliente Shopify...")
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()
        
        # Inicializar gestor de colecciones
        logger.info("📦 Inicializando gestor de colecciones...")
        collection_manager = CollectionManager(shopify_client)
        await collection_manager.initialize()
        
        # Mostrar estadísticas iniciales
        stats = collection_manager.get_collection_stats()
        logger.info(f"📊 Estadísticas iniciales: {stats}")
        
        # Probar creación de colecciones para diferentes categorías
        test_cases = [
            {
                "categoria": "Tenis",
                "familia": "Zapatos",
                "extended_category": "Calzado > Zapatos > Tenis"
            },
            {
                "categoria": "Botas",
                "familia": "Zapatos",
                "extended_category": "Calzado > Zapatos > Botas"
            },
            {
                "categoria": "Sandalias",
                "familia": "Zapatos",
                "extended_category": "Calzado > Zapatos > Sandalias"
            },
            {
                "categoria": None,
                "familia": "Accesorios",
                "extended_category": "Accesorios"
            }
        ]
        
        logger.info("\n🧪 Probando creación de colecciones...")
        for i, test in enumerate(test_cases, 1):
            logger.info(f"\n--- Test Case {i} ---")
            logger.info(f"Categoría: {test['categoria']}")
            logger.info(f"Familia: {test['familia']}")
            logger.info(f"Extended: {test['extended_category']}")
            
            collection_id = await collection_manager.ensure_collection_exists(
                categoria=test['categoria'],
                familia=test['familia'],
                extended_category=test['extended_category']
            )
            
            if collection_id:
                logger.info(f"✅ Colección creada/encontrada: {collection_id}")
            else:
                logger.warning(f"⚠️ No se pudo crear/encontrar colección")
                
        # Mostrar estadísticas finales
        final_stats = collection_manager.get_collection_stats()
        logger.info(f"\n📊 Estadísticas finales: {final_stats}")
        
        # Mostrar todas las colecciones creadas
        logger.info("\n📋 Listando todas las colecciones...")
        all_collections = await shopify_client.get_all_collections()
        for collection in all_collections:
            logger.info(
                f"  - {collection.get('title')} "
                f"(handle: {collection.get('handle')}, "
                f"productos: {collection.get('productsCount', {}).get('count', 0)})"
            )
            
    except Exception as e:
        logger.error(f"❌ Error en prueba: {e}", exc_info=True)
        
    finally:
        # Limpiar recursos
        if shopify_client:
            await shopify_client.close()
        logger.info("\n✅ Prueba completada")


async def test_full_sync_with_collections():
    """
    Prueba una sincronización completa con creación de colecciones.
    """
    sync_service = None
    
    try:
        logger.info("\n🔄 Iniciando sincronización completa con colecciones...")
        
        # Crear servicio de sincronización
        sync_service = RMSToShopifySync()
        await sync_service.initialize()
        
        # Sincronizar productos de una categoría específica
        # Esto creará automáticamente las colecciones necesarias
        result = await sync_service.sync_products(
            force_update=False,
            batch_size=5,  # Batch pequeño para prueba
            filter_categories=["Tenis", "Botas"],  # Solo estas categorías
            include_zero_stock=False
        )
        
        # Mostrar resultados
        logger.info("\n📊 Resultados de sincronización:")
        logger.info(f"Total procesados: {result['statistics']['total_processed']}")
        logger.info(f"Creados: {result['statistics']['created']}")
        logger.info(f"Actualizados: {result['statistics']['updated']}")
        logger.info(f"Errores: {result['statistics']['errors']}")
        logger.info(f"Omitidos: {result['statistics']['skipped']}")
        
        if result.get('errors', {}).get('error_count', 0) > 0:
            logger.warning(f"\n⚠️ Se encontraron errores:")
            for error in result['errors'].get('errors', []):
                logger.warning(f"  - {error}")
                
    except Exception as e:
        logger.error(f"❌ Error en sincronización: {e}", exc_info=True)
        
    finally:
        if sync_service:
            await sync_service.close()
        logger.info("\n✅ Sincronización completada")


async def main():
    """
    Función principal que ejecuta las pruebas.
    """
    logger.info("🎯 PRUEBA DE SINCRONIZACIÓN DE COLECCIONES BASADAS EN CATEGORÍAS RMS")
    logger.info("=" * 70)
    
    # Menú de opciones
    print("\nSeleccione una opción:")
    print("1. Probar solo creación de colecciones")
    print("2. Probar sincronización completa con colecciones")
    print("3. Ejecutar ambas pruebas")
    
    choice = input("\nOpción (1-3): ").strip()
    
    if choice == "1":
        await test_collection_creation()
    elif choice == "2":
        await test_full_sync_with_collections()
    elif choice == "3":
        await test_collection_creation()
        await test_full_sync_with_collections()
    else:
        logger.error("Opción inválida")
        
    logger.info("\n🏁 Todas las pruebas completadas")


if __name__ == "__main__":
    asyncio.run(main())