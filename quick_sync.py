#!/usr/bin/env python3
"""
Script rápido para sincronización completa usando el servicio existente.
"""

import asyncio
import logging
from app.services.rms_to_shopify import RMSToShopifySync

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def quick_full_sync():
    """Ejecuta sincronización completa usando el servicio existente."""
    
    print("🚀 SINCRONIZACIÓN RÁPIDA - TODOS LOS PRODUCTOS")
    print("="*50)
    
    sync_service = RMSToShopifySync()
    
    try:
        await sync_service.initialize()
        
        # Configuración para sincronización completa
        config = {
            "force_update": False,      # No forzar actualización de existentes
            "batch_size": 50,          # Procesar 50 productos por lote
            "include_zero_stock": False, # Solo productos con stock
            "filter_categories": None,   # Todas las categorías
        }
        
        logger.info(f"📋 Configuración: {config}")
        
        # Ejecutar sincronización
        result = await sync_service.sync_products(**config)
        
        print("\n" + "="*50)
        print("📊 RESULTADO DE LA SINCRONIZACIÓN")
        print("="*50)
        print(f"✅ Productos sincronizados: {result.get('products_synced', 0)}")
        print(f"❌ Errores: {result.get('errors', 0)}")
        print(f"⏱️  Tiempo: {result.get('elapsed_time', 'N/A')}")
        print(f"📈 Tasa de éxito: {result.get('success_rate', 0):.1f}%")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Error durante sincronización: {e}")
        raise
        
    finally:
        await sync_service.cleanup()

if __name__ == "__main__":
    asyncio.run(quick_full_sync())