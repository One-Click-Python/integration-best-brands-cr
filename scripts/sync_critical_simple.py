#!/usr/bin/env python3
"""
Script simplificado para sincronizar productos críticos con stock negativo
"""

import asyncio
import logging
import sys
from typing import List
from datetime import datetime
from app.db.rms_handler import RMSHandler
from app.db.shopify_graphql_client import ShopifyGraphQLClient
from sqlalchemy import text
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def get_critical_products(rms_handler: RMSHandler, limit: int = 10) -> List[dict]:
    """Obtener productos con stock negativo o en situación crítica"""
    
    async with rms_handler.conn_db.get_session() as session:
        query = """
        SELECT CCOD, MIN(Description) as Description, 
               SUM(Quantity) as TotalQuantity, 
               COUNT(*) as Variants,
               MIN(Price) as MinPrice
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
        
        if limit > 0:
            query = query.replace("SELECT", f"SELECT TOP {limit}")
        
        result = await session.execute(text(query))
        products = []
        for row in result.fetchall():
            products.append({
                'ccod': row.CCOD.strip(),
                'description': row.Description,
                'total_quantity': int(row.TotalQuantity),
                'variants': row.Variants,
                'min_price': float(row.MinPrice)
            })
        
        return products


async def update_shopify_inventory(shopify_client: ShopifyGraphQLClient, sku: str, quantity: int) -> bool:
    """Actualizar inventario de una variante en Shopify"""
    try:
        # Primero buscar el producto por SKU
        product = await shopify_client.get_product_by_sku(sku)
        
        if not product:
            logger.warning(f"Producto con SKU {sku} no encontrado en Shopify")
            return False
        
        # Buscar la variante específica con el SKU
        variants = product.get('variants', {}).get('edges', [])
        variant = None
        
        for v_edge in variants:
            v = v_edge.get('node', {})
            if v.get('sku') == sku:
                variant = v
                break
        
        if not variant:
            logger.warning(f"Variante con SKU {sku} no encontrada en el producto")
            return False
        
        variant_id = variant['id']
        current_quantity = variant.get('inventoryQuantity', 0)
        
        logger.info(f"Variante encontrada: SKU={sku}, Stock actual={current_quantity}, Nuevo stock={quantity}")
        
        # Actualizar el inventario
        mutation = """
        mutation($input: InventorySetOnHandQuantitiesInput!) {
            inventorySetOnHandQuantities(input: $input) {
                inventoryAdjustmentGroup {
                    createdAt
                    changes {
                        name
                        delta
                    }
                }
                userErrors {
                    field
                    message
                }
            }
        }
        """
        
        # Necesitamos el inventory_item_id y location_id
        inventory_item_id = variant['inventoryItem']['id'] if variant.get('inventoryItem') else None
        
        if not inventory_item_id:
            logger.error(f"No se pudo obtener inventory_item_id para SKU {sku}")
            return False
        
        # Por simplicidad, asumimos una ubicación por defecto
        # En producción, deberías obtener esto dinámicamente
        location_id = "gid://shopify/Location/YOUR_LOCATION_ID"  # Reemplazar con ID real
        
        update_input = {
            "input": {
                "reason": "correction",
                "setQuantities": [{
                    "inventoryItemId": inventory_item_id,
                    "locationId": location_id,
                    "quantity": quantity
                }]
            }
        }
        
        result = await shopify_client.inventory.execute_query(mutation, update_input)
        
        if result and 'inventorySetOnHandQuantities' in result:
            errors = result['inventorySetOnHandQuantities'].get('userErrors', [])
            if errors:
                logger.error(f"Errores actualizando inventario: {errors}")
                return False
            
            logger.info(f"✅ Inventario actualizado para SKU {sku}: {quantity}")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error actualizando inventario para SKU {sku}: {e}")
        return False


async def sync_critical_product(rms_handler: RMSHandler, shopify_client: ShopifyGraphQLClient, ccod: str) -> dict:
    """Sincronizar un producto crítico específico"""
    
    stats = {'updated': 0, 'errors': 0, 'skipped': 0}
    
    try:
        # Obtener todas las variantes del producto desde RMS
        async with rms_handler.conn_db.get_session() as session:
            query = """
            SELECT C_ARTICULO, Description, Quantity, Price, Talla, Color
            FROM View_Items
            WHERE CCOD = :ccod
            AND C_ARTICULO IS NOT NULL
            ORDER BY C_ARTICULO
            """
            
            result = await session.execute(text(query), {"ccod": ccod})
            items = result.fetchall()
            
            if not items:
                logger.warning(f"No se encontraron items para CCOD {ccod}")
                stats['skipped'] += 1
                return stats
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Procesando producto: {ccod}")
            logger.info(f"Descripción: {items[0].Description}")
            logger.info(f"Variantes encontradas: {len(items)}")
            
            # Actualizar cada variante
            for item in items:
                sku = item.C_ARTICULO
                quantity = int(item.Quantity)
                
                logger.info(f"  - SKU: {sku} | Stock RMS: {quantity}")
                
                # Solo actualizar si el producto existe en Shopify
                success = await update_shopify_inventory(shopify_client, sku, quantity)
                
                if success:
                    stats['updated'] += 1
                else:
                    stats['errors'] += 1
            
            logger.info(f"Resultado: ✅ {stats['updated']} actualizadas, ❌ {stats['errors']} errores")
            
    except Exception as e:
        logger.error(f"Error procesando producto {ccod}: {e}")
        stats['errors'] += 1
    
    return stats


async def main():
    """Función principal"""
    
    # Configuración
    LIMIT = 2  # Procesar solo los primeros 2 productos más críticos para prueba
    
    rms_handler = None
    shopify_client = None
    
    try:
        # Inicializar conexiones
        logger.info("🔄 Inicializando conexiones...")
        
        rms_handler = RMSHandler()
        await rms_handler.initialize()
        
        shopify_client = ShopifyGraphQLClient()
        await shopify_client.initialize()
        
        logger.info("✅ Conexiones establecidas")
        
        # Obtener productos críticos
        logger.info(f"\n📊 Buscando los {LIMIT} productos más críticos con stock negativo...")
        critical_products = await get_critical_products(rms_handler, LIMIT)
        
        if not critical_products:
            logger.warning("No se encontraron productos con stock negativo")
            return
        
        logger.info(f"Encontrados {len(critical_products)} productos críticos:")
        for i, product in enumerate(critical_products, 1):
            logger.info(
                f"  {i}. {product['ccod']:15s} | "
                f"Stock: {product['total_quantity']:4d} | "
                f"{product['description'][:40]:40s}"
            )
        
        # Sincronizar productos
        logger.info("\n" + "="*60)
        logger.info("🚀 INICIANDO SINCRONIZACIÓN DE INVENTARIO")
        logger.info("="*60)
        
        total_stats = {'updated': 0, 'errors': 0, 'skipped': 0}
        
        for product in critical_products:
            product_stats = await sync_critical_product(
                rms_handler, 
                shopify_client, 
                product['ccod']
            )
            
            for key in total_stats:
                total_stats[key] += product_stats[key]
            
            # Pausa breve entre productos
            await asyncio.sleep(1)
        
        # Resumen final
        logger.info("\n" + "="*60)
        logger.info("📊 RESUMEN FINAL")
        logger.info("="*60)
        logger.info(f"Total productos procesados: {len(critical_products)}")
        logger.info(f"✅ Variantes actualizadas: {total_stats['updated']}")
        logger.info(f"⏭️  Variantes saltadas: {total_stats['skipped']}")  
        logger.info(f"❌ Errores: {total_stats['errors']}")
        
        success_rate = (total_stats['updated'] / (total_stats['updated'] + total_stats['errors']) * 100) if (total_stats['updated'] + total_stats['errors']) > 0 else 0
        logger.info(f"🎯 Tasa de éxito: {success_rate:.1f}%")
        
    except Exception as e:
        logger.error(f"Error fatal: {e}", exc_info=True)
    finally:
        if rms_handler:
            await rms_handler.close()
        if shopify_client:
            await shopify_client.close()
        logger.info("\n✅ Conexiones cerradas")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("SINCRONIZACIÓN DE PRODUCTOS CRÍTICOS CON STOCK NEGATIVO")
    print("="*60)
    print("Este script actualizará el inventario de productos con stock")
    print("negativo (overselling) en Shopify.")
    print("="*60 + "\n")
    
    asyncio.run(main())