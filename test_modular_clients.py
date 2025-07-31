#!/usr/bin/env python3
"""
Script de prueba para la nueva estructura modular de clientes Shopify.

Este script verifica que todos los clientes especializados funcionen correctamente
y que la compatibilidad hacia atrás se mantenga.
"""

import asyncio
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_backward_compatibility():
    """Test que el código existente sigue funcionando."""
    logger.info("🔄 Testing backward compatibility...")
    
    try:
        # Import tradicional debe seguir funcionando
        from app.db.shopify_graphql_client import ShopifyGraphQLClient
        
        client = ShopifyGraphQLClient()
        logger.info(f"✅ Traditional import works: {client}")
        
        await client.initialize()
        logger.info("✅ Client initialization successful")
        
        # Test conexión
        connection_ok = await client.test_connection()
        logger.info(f"✅ Connection test: {'SUCCESS' if connection_ok else 'FAILED'}")
        
        await client.close()
        logger.info("✅ Client cleanup successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Backward compatibility test failed: {e}")
        return False


async def test_specialized_clients():
    """Test que los clientes especializados funcionen."""
    logger.info("🔄 Testing specialized clients...")
    
    results = {}
    
    # Test BaseClient
    try:
        from app.db.shopify_clients import BaseShopifyGraphQLClient
        
        base_client = BaseShopifyGraphQLClient()
        await base_client.initialize()
        
        # Test básico
        locations = await base_client.get_locations()
        logger.info(f"✅ BaseClient: Found {len(locations)} locations")
        
        await base_client.close()
        results['base'] = True
        
    except Exception as e:
        logger.error(f"❌ BaseClient test failed: {e}")
        results['base'] = False
    
    # Test ProductClient
    try:
        from app.db.shopify_clients import ShopifyProductClient
        
        product_client = ShopifyProductClient()
        await product_client.initialize()
        
        # Test básico - obtener productos
        products_result = await product_client.get_products(limit=5)
        product_count = len(products_result.get('edges', []))
        logger.info(f"✅ ProductClient: Retrieved {product_count} products")
        
        await product_client.close()
        results['products'] = True
        
    except Exception as e:
        logger.error(f"❌ ProductClient test failed: {e}")
        results['products'] = False
    
    # Test CollectionClient
    try:
        from app.db.shopify_clients import ShopifyCollectionClient
        
        collection_client = ShopifyCollectionClient()
        await collection_client.initialize()
        
        # Test básico - obtener colecciones
        collections_result = await collection_client.get_collections(limit=5)
        collection_count = len(collections_result.get('edges', []))
        logger.info(f"✅ CollectionClient: Retrieved {collection_count} collections")
        
        await collection_client.close()
        results['collections'] = True
        
    except Exception as e:
        logger.error(f"❌ CollectionClient test failed: {e}")
        results['collections'] = False
    
    # Test InventoryClient
    try:
        from app.db.shopify_clients import ShopifyInventoryClient
        
        inventory_client = ShopifyInventoryClient()
        await inventory_client.initialize()
        
        # Test básico - obtener ubicaciones
        locations = await inventory_client.get_locations()
        logger.info(f"✅ InventoryClient: Found {len(locations)} locations for inventory")
        
        await inventory_client.close()
        results['inventory'] = True
        
    except Exception as e:
        logger.error(f"❌ InventoryClient test failed: {e}")
        results['inventory'] = False
    
    return results


async def test_unified_client():
    """Test que el cliente unificado funcione con delegación."""
    logger.info("🔄 Testing unified client with delegation...")
    
    try:
        from app.db.shopify_clients import ShopifyGraphQLClient
        
        unified_client = ShopifyGraphQLClient()
        await unified_client.initialize()
        
        # Test acceso directo a clientes especializados
        logger.info("Testing specialized client access...")
        
        # Test products through specialized client
        products = await unified_client.products.get_products(limit=3)
        product_count = len(products.get('edges', []))
        logger.info(f"✅ Unified->Products: {product_count} products via specialized client")
        
        # Test collections through specialized client
        collections = await unified_client.collections.get_collections(limit=3)
        collection_count = len(collections.get('edges', []))
        logger.info(f"✅ Unified->Collections: {collection_count} collections via specialized client")
        
        # Test delegation (traditional methods)
        logger.info("Testing method delegation...")
        
        delegated_products = await unified_client.get_products(limit=3)
        delegated_count = len(delegated_products.get('edges', []))
        logger.info(f"✅ Unified delegation: {delegated_count} products via delegated method")
        
        # Test specialized client access
        product_client = unified_client.get_specialized_client('products')
        logger.info(f"✅ Specialized client access: {type(product_client).__name__}")
        
        await unified_client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Unified client test failed: {e}")
        return False


async def test_performance_comparison():
    """Test básico de rendimiento entre implementaciones."""
    logger.info("🔄 Testing performance comparison...")
    
    try:
        import time
        
        # Test import times
        start_time = time.time()
        from app.db.shopify_clients import ShopifyProductClient
        product_import_time = time.time() - start_time
        
        start_time = time.time()
        from app.db.shopify_graphql_client import ShopifyGraphQLClient
        unified_import_time = time.time() - start_time
        
        logger.info(f"📊 Import times:")
        logger.info(f"  - Specialized client: {product_import_time*1000:.2f}ms")
        logger.info(f"  - Unified client: {unified_import_time*1000:.2f}ms")
        
        # Test initialization times
        start_time = time.time()
        specialized_client = ShopifyProductClient()
        await specialized_client.initialize()
        specialized_init_time = time.time() - start_time
        await specialized_client.close()
        
        start_time = time.time()
        unified_client = ShopifyGraphQLClient()
        await unified_client.initialize()
        unified_init_time = time.time() - start_time
        await unified_client.close()
        
        logger.info(f"📊 Initialization times:")
        logger.info(f"  - Specialized client: {specialized_init_time*1000:.2f}ms")
        logger.info(f"  - Unified client: {unified_init_time*1000:.2f}ms")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Performance test failed: {e}")
        return False


async def test_services_compatibility():
    """Test que los servicios existentes sigan funcionando."""
    logger.info("🔄 Testing services compatibility...")
    
    try:
        # Test CollectionManager
        from app.services.collection_manager import CollectionManager
        from app.db.shopify_graphql_client import ShopifyGraphQLClient
        
        client = ShopifyGraphQLClient()
        await client.initialize()
        
        collection_manager = CollectionManager(client)
        await collection_manager.initialize()
        
        stats = collection_manager.get_collection_stats()
        logger.info(f"✅ CollectionManager: {stats}")
        
        await client.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Services compatibility test failed: {e}")
        return False


async def main():
    """Run all tests."""
    logger.info("🚀 Starting modular client tests...")
    logger.info("=" * 70)
    
    test_results = {}
    
    # Test 1: Backward compatibility
    test_results['backward_compatibility'] = await test_backward_compatibility()
    
    # Test 2: Specialized clients
    specialized_results = await test_specialized_clients()
    test_results.update(specialized_results)
    
    # Test 3: Unified client
    test_results['unified_client'] = await test_unified_client()
    
    # Test 4: Performance
    test_results['performance'] = await test_performance_comparison()
    
    # Test 5: Services compatibility
    test_results['services'] = await test_services_compatibility()
    
    # Summary
    logger.info("=" * 70)
    logger.info("📊 TEST RESULTS SUMMARY:")
    
    passed = 0
    total = 0
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"  {test_name}: {status}")
        if result:
            passed += 1
        total += 1
    
    success_rate = (passed / total) * 100 if total > 0 else 0
    
    logger.info("=" * 70)
    logger.info(f"🎯 OVERALL RESULTS: {passed}/{total} tests passed ({success_rate:.1f}%)")
    
    if success_rate == 100:
        logger.info("🎉 All tests passed! Modular refactor is successful!")
    elif success_rate >= 80:
        logger.info("⚠️ Most tests passed, but some issues need attention.")
    else:
        logger.info("❌ Many tests failed. Refactor needs review.")
    
    return success_rate == 100


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)