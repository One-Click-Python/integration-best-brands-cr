#!/usr/bin/env python3
"""
Script para sincronización completa de todos los productos de RMS a Shopify.
Este script utiliza el sistema de múltiples variantes desarrollado.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Any

from app.db.rms_handler import RMSHandler
from app.services.rms_to_shopify import RMSToShopifySync
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from app.services.variant_mapper import create_products_with_variants
from app.api.v1.schemas.rms_schemas import RMSViewItem
from decimal import Decimal

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'sync_complete_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class CompleteSyncManager:
    """Gestor para sincronización completa de productos."""
    
    def __init__(self):
        self.rms_handler = RMSHandler()
        self.sync_service = RMSToShopifySync()
        self.client = ShopifyGraphQLClient()
        self.stats = {
            "total_ccods": 0,
            "total_products_created": 0,
            "total_variants_created": 0,
            "errors": 0,
            "start_time": None,
            "end_time": None
        }
    
    async def initialize(self):
        """Inicializa todos los servicios."""
        logger.info("🚀 Inicializando servicios para sincronización completa...")
        await self.rms_handler.initialize()
        await self.sync_service.initialize()
        await self.client.initialize()
        logger.info("✅ Servicios inicializados correctamente")
    
    async def cleanup(self):
        """Limpia recursos."""
        logger.info("🧹 Limpiando recursos...")
        await self.rms_handler.close()
        await self.sync_service.cleanup()
        await self.client.close()
        logger.info("✅ Recursos liberados")
    
    async def get_all_ccods_with_stock(self, include_zero_stock: bool = False) -> list:
        """
        Obtiene todos los CCODs que tienen productos con stock.
        
        Args:
            include_zero_stock: Si incluir productos sin stock
            
        Returns:
            Lista de CCODs únicos
        """
        logger.info(f"📋 Obteniendo CCODs de la base de datos...")
        
        stock_filter = "" if include_zero_stock else "AND Quantity > 0"
        
        query = f"""
        SELECT DISTINCT CCOD, COUNT(*) as total_variants
        FROM View_Items 
        WHERE CCOD IS NOT NULL 
        AND CCOD != ''
        {stock_filter}
        GROUP BY CCOD
        HAVING COUNT(*) >= 1
        ORDER BY total_variants DESC, CCOD
        """
        
        results = await self.rms_handler.execute_custom_query(query)
        ccods = [result['CCOD'].strip() for result in results if result['CCOD']]
        
        logger.info(f"📊 Encontrados {len(ccods)} CCODs únicos para sincronizar")
        return ccods
    
    async def get_variants_for_ccod(self, ccod: str, include_zero_stock: bool = False) -> list:
        """
        Obtiene todas las variantes para un CCOD específico.
        
        Args:
            ccod: CCOD a procesar
            include_zero_stock: Si incluir productos sin stock
            
        Returns:
            Lista de objetos RMSViewItem
        """
        stock_filter = "" if include_zero_stock else "AND Quantity > 0"
        
        query = f"""
        SELECT 
            Familia, Genero, Categoria, CCOD, C_ARTICULO,
            ItemID, Description, color, talla, Quantity,
            Price, SalePrice, ExtendedCategory, Tax
        FROM View_Items 
        WHERE CCOD = :ccod
        {stock_filter}
        ORDER BY talla
        """
        
        items_data = await self.rms_handler.execute_custom_query(query, {"ccod": ccod})
        
        rms_items = []
        for item_data in items_data:
            try:
                rms_item = RMSViewItem(
                    familia=item_data.get("Familia", ""),
                    genero=item_data.get("Genero", ""),
                    categoria=item_data.get("Categoria", ""),
                    ccod=item_data.get("CCOD", ""),
                    c_articulo=item_data.get("C_ARTICULO", ""),
                    item_id=item_data.get("ItemID", 0),
                    description=item_data.get("Description", ""),
                    color=item_data.get("color", ""),
                    talla=item_data.get("talla", ""),
                    quantity=int(item_data.get("Quantity", 0)),
                    price=Decimal(str(item_data.get("Price", 0))),
                    sale_price=Decimal(str(item_data.get("SalePrice", 0))) if item_data.get("SalePrice") else None,
                    extended_category=item_data.get("ExtendedCategory", ""),
                    tax=int(item_data.get("Tax", 13))
                )
                rms_items.append(rms_item)
            except Exception as e:
                logger.warning(f"❌ Error procesando item para CCOD {ccod}: {e}")
                continue
        
        return rms_items
    
    async def sync_ccod_batch(self, ccods: list, batch_size: int = 10) -> Dict[str, Any]:
        """
        Sincroniza un lote de CCODs.
        
        Args:
            ccods: Lista de CCODs a sincronizar
            batch_size: Tamaño del lote
            
        Returns:
            Estadísticas del proceso
        """
        batch_stats = {"success": 0, "errors": 0, "details": []}
        
        for i, ccod in enumerate(ccods):
            try:
                logger.info(f"🔄 [{i+1}/{len(ccods)}] Procesando CCOD: {ccod}")
                
                # Obtener variantes para este CCOD
                rms_items = await self.get_variants_for_ccod(ccod, include_zero_stock=False)
                
                if not rms_items:
                    logger.warning(f"⚠️  CCOD {ccod}: No tiene variantes con stock")
                    continue
                
                # Mapear a productos con variantes
                products = await create_products_with_variants(
                    rms_items, self.client, self.sync_service.primary_location_id
                )
                
                if len(products) != 1:
                    logger.error(f"❌ CCOD {ccod}: Se esperaba 1 producto, se obtuvieron {len(products)}")
                    batch_stats["errors"] += 1
                    continue
                
                product = products[0]
                logger.info(f"📦 CCOD {ccod}: {product.title} con {len(product.variants)} variantes")
                
                # Crear en Shopify
                created_product = await self.sync_service._create_shopify_product(product)
                
                if created_product and created_product.get("id"):
                    product_id = created_product["id"]
                    numeric_id = product_id.split('/')[-1]
                    shopify_url = f"https://admin.shopify.com/store/best-brands-cr/products/{numeric_id}"
                    
                    batch_stats["success"] += 1
                    self.stats["total_products_created"] += 1
                    self.stats["total_variants_created"] += len(product.variants)
                    
                    batch_stats["details"].append({
                        "ccod": ccod,
                        "title": product.title,
                        "variants": len(product.variants),
                        "url": shopify_url,
                        "status": "success"
                    })
                    
                    logger.info(f"✅ CCOD {ccod}: Producto creado exitosamente - {shopify_url}")
                else:
                    logger.error(f"❌ CCOD {ccod}: Error al crear producto en Shopify")
                    batch_stats["errors"] += 1
                    
            except Exception as e:
                logger.error(f"❌ CCOD {ccod}: Error durante procesamiento - {e}")
                batch_stats["errors"] += 1
                self.stats["errors"] += 1
                
            # Pausa entre productos para evitar rate limiting
            await asyncio.sleep(5)
        
        return batch_stats
    
    async def run_complete_sync(self, 
                              include_zero_stock: bool = False,
                              batch_size: int = 10,
                              max_ccods: int = None) -> Dict[str, Any]:
        """
        Ejecuta la sincronización completa.
        
        Args:
            include_zero_stock: Si incluir productos sin stock
            batch_size: Tamaño del lote de procesamiento
            max_ccods: Máximo número de CCODs a procesar (para testing)
            
        Returns:
            Estadísticas completas del proceso
        """
        self.stats["start_time"] = datetime.now()
        
        logger.info("🎯 INICIANDO SINCRONIZACIÓN COMPLETA RMS → SHOPIFY")
        logger.info("="*70)
        logger.info(f"📋 Configuración:")
        logger.info(f"   - Incluir sin stock: {include_zero_stock}")
        logger.info(f"   - Tamaño de lote: {batch_size}")
        logger.info(f"   - Límite CCODs: {max_ccods or 'Sin límite'}")
        
        try:
            # Obtener todos los CCODs
            all_ccods = await self.get_all_ccods_with_stock(include_zero_stock)
            
            if max_ccods:
                all_ccods = all_ccods[:max_ccods]
                logger.info(f"🔢 Limitando a primeros {max_ccods} CCODs para testing")
            
            self.stats["total_ccods"] = len(all_ccods)
            
            # Procesar en lotes
            for i in range(0, len(all_ccods), batch_size):
                batch = all_ccods[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(all_ccods) + batch_size - 1) // batch_size
                
                logger.info(f"🔄 Procesando lote {batch_num}/{total_batches} ({len(batch)} CCODs)")
                
                batch_stats = await self.sync_ccod_batch(batch, batch_size)
                
                logger.info(f"📊 Lote {batch_num} completado: {batch_stats['success']} éxitos, {batch_stats['errors']} errores")
                
                # Pausa entre lotes
                if i + batch_size < len(all_ccods):
                    logger.info("⏸️  Pausa entre lotes...")
                    await asyncio.sleep(5)
            
            self.stats["end_time"] = datetime.now()
            elapsed = self.stats["end_time"] - self.stats["start_time"]
            
            # Resumen final
            logger.info("\n" + "="*70)
            logger.info("📊 RESUMEN DE SINCRONIZACIÓN COMPLETA")
            logger.info("="*70)
            logger.info(f"⏱️  Tiempo total: {elapsed}")
            logger.info(f"📦 CCODs procesados: {self.stats['total_ccods']}")
            logger.info(f"✅ Productos creados: {self.stats['total_products_created']}")
            logger.info(f"🔢 Variantes creadas: {self.stats['total_variants_created']}")
            logger.info(f"❌ Errores: {self.stats['errors']}")
            
            success_rate = (self.stats['total_products_created'] / self.stats['total_ccods'] * 100) if self.stats['total_ccods'] > 0 else 0
            logger.info(f"📈 Tasa de éxito: {success_rate:.1f}%")
            
            if success_rate >= 95:
                logger.info("🏆 ¡SINCRONIZACIÓN EXCELENTE!")
            elif success_rate >= 80:
                logger.info("🟢 Sincronización exitosa")
            elif success_rate >= 60:
                logger.info("🟡 Sincronización parcial")
            else:
                logger.info("🔴 Sincronización con problemas")
            
            return self.stats
            
        except Exception as e:
            logger.error(f"❌ Error crítico durante sincronización: {e}")
            raise


async def main():
    """Función principal para ejecutar la sincronización completa."""
    
    # Configuración de la sincronización
    CONFIG = {
        "include_zero_stock": False,  # Cambiar a True para incluir productos sin stock
        "batch_size": 3,              # Número de CCODs a procesar por lote (reducido)
        "max_ccods": 15,              # Límite para testing (None para todos)
    }
    
    print("🎯 SINCRONIZACIÓN COMPLETA RMS → SHOPIFY")
    print("="*50)
    print(f"Configuración: {CONFIG}")
    print("="*50)
    
    sync_manager = CompleteSyncManager()
    
    try:
        await sync_manager.initialize()
        result = await sync_manager.run_complete_sync(**CONFIG)
        return result
        
    except Exception as e:
        logger.error(f"❌ Error durante la sincronización: {e}")
        raise
        
    finally:
        await sync_manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())