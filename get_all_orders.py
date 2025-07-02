#!/usr/bin/env python3
"""
Script para obtener todas las órdenes de Shopify y sincronizarlas con RMS.
"""

import asyncio
import aiohttp
import json
from datetime import datetime
import os
from typing import List, Dict, Any

BASE_URL = "http://localhost:8000/api/v1"

async def fetch_orders_from_shopify() -> List[str]:
    """
    Obtiene todas las órdenes disponibles desde Shopify usando la API interna.
    """
    print("\n📦 Obteniendo órdenes desde Shopify...")
    
    # Usar el cliente GraphQL directamente
    from app.db.shopify_graphql_client import ShopifyGraphQLClient
    from app.db.shopify_order_client import ShopifyOrderClient
    from app.core.config import get_settings
    
    settings = get_settings()
    
    try:
        # Crear clientes
        graphql_client = ShopifyGraphQLClient()
        
        order_client = ShopifyOrderClient(graphql_client)
        
        # Obtener órdenes recientes (límite de 50)
        orders_data = await order_client.get_orders(
            limit=50,
            status="any"  # Todas las órdenes
        )
        
        orders = orders_data.get("orders", [])
        order_ids = [order["id"] for order in orders if order and order.get("id")]
        
        print(f"   ✅ Encontradas {len(order_ids)} órdenes en Shopify")
        
        # Mostrar información de las primeras 5 órdenes
        for i, order in enumerate(orders[:5]):
            if order:
                print(f"      {i+1}. {order.get('name', 'N/A')} - {order.get('displayFinancialStatus', 'N/A')}")
        
        if len(orders) > 5:
            print(f"      ... y {len(orders) - 5} órdenes más")
        
        return order_ids
        
    except Exception as e:
        print(f"   ❌ Error obteniendo órdenes: {e}")
        return []

async def sync_orders_to_rms(order_ids: List[str]) -> Dict[str, Any]:
    """
    Sincroniza las órdenes obtenidas con RMS.
    """
    if not order_ids:
        print("\n❌ No hay órdenes para sincronizar")
        return {"success": False, "message": "No orders found"}
    
    print(f"\n🚀 Sincronizando {len(order_ids)} órdenes con RMS...")
    
    payload = {
        "order_ids": order_ids,
        "skip_validation": False
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{BASE_URL}/sync/shopify-to-rms?run_async=false",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=aiohttp.ClientTimeout(total=300)  # 5 minutos timeout
        ) as response:
            print(f"📡 Respuesta del servidor (Status: {response.status})")
            
            if response.status in [200, 202]:
                data = await response.json()
                
                print(f"✅ Success: {data['success']}")
                print(f"🆔 Sync ID: {data['sync_id']}")
                print(f"💬 Message: {data['message']}")
                
                if 'statistics' in data:
                    stats = data['statistics']
                    print(f"\n📊 RESULTADOS DE LA SINCRONIZACIÓN:")
                    print(f"   📦 Total órdenes procesadas: {stats.get('total_orders', 0)}")
                    print(f"   ✨ Nuevas órdenes creadas en RMS: {stats.get('created', 0)}")
                    print(f"   🔄 Órdenes actualizadas: {stats.get('updated', 0)}")
                    print(f"   ❌ Errores: {stats.get('errors', 0)}")
                    print(f"   ⏭️ Saltadas: {stats.get('skipped', 0)}")
                    
                    if stats.get('duration_seconds'):
                        print(f"   ⏱️ Duración: {stats['duration_seconds']:.2f} segundos")
                
                return data
            else:
                error_text = await response.text()
                print(f"❌ ERROR {response.status}: {error_text}")
                return {"success": False, "error": error_text}

async def main():
    """
    Función principal para obtener y sincronizar todas las órdenes.
    """
    print("🔧 SINCRONIZACIÓN COMPLETA DE ÓRDENES SHOPIFY → RMS")
    print("=" * 80)
    print(f"📍 API URL: {BASE_URL}")
    print(f"⏰ Hora: {datetime.now()}")
    
    try:
        # 1. Obtener todas las órdenes de Shopify
        order_ids = await fetch_orders_from_shopify()
        
        if not order_ids:
            print("\n❌ No se encontraron órdenes para sincronizar")
            return
        
        # 2. Sincronizar con RMS
        result = await sync_orders_to_rms(order_ids)
        
        # 3. Mostrar resultado final
        if result.get('success'):
            stats = result.get('statistics', {})
            created = stats.get('created', 0)
            
            if created > 0:
                print(f"\n🎉 ¡SINCRONIZACIÓN EXITOSA!")
                print(f"   ✅ Se crearon {created} nuevas órdenes en RMS")
                print(f"   📝 Verifique las tablas [Order] y [OrderEntry] en SQL Server")
            else:
                print(f"\n⚠️ Sincronización completada pero sin nuevas inserciones")
                print(f"   🔍 Posiblemente las órdenes ya existían en RMS")
        else:
            print(f"\n❌ Sincronización falló")
            print(f"   Error: {result.get('error', 'Unknown error')}")
    
    except Exception as e:
        print(f"\n❌ Error durante la sincronización: {e}")
    
    print(f"\n✅ Proceso completado a las {datetime.now()}")

if __name__ == "__main__":
    asyncio.run(main())