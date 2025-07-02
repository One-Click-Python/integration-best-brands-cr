#!/usr/bin/env python3
"""
Script para impactar REALMENTE la base de datos RMS con datos de Shopify.
"""

import asyncio
import aiohttp
import json
from datetime import datetime

BASE_URL = "http://localhost:8000/api/v1"

async def get_current_order_count():
    """Obtiene el conteo actual de órdenes en RMS."""
    print("\n📊 Verificando estado actual de la base de datos...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/admin/database-health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Conexión RMS activa: {data['health_check']['test_passed']}")
                print(f"   ⏱️ Tiempo de respuesta: {data['health_check']['response_time_ms']}ms")
                return True
            else:
                print(f"   ❌ Error verificando base de datos: {response.status}")
                return False

async def perform_real_sync(order_id):
    """Ejecuta una sincronización REAL que impactará la base de datos."""
    print(f"\n🚀 EJECUTANDO SINCRONIZACIÓN REAL CON ORDEN: {order_id}")
    print("⚠️  ESTO CREARÁ DATOS REALES EN LA BASE DE DATOS RMS!")
    
    payload = {
        "order_ids": [order_id],
        "skip_validation": False
    }
    
    async with aiohttp.ClientSession() as session:
        # Ejecutar en modo síncrono para ver resultados inmediatos
        async with session.post(
            f"{BASE_URL}/sync/shopify-to-rms?run_async=false",
            json=payload,
            headers={"Content-Type": "application/json"}
        ) as response:
            print(f"\n📡 Respuesta del servidor (Status: {response.status}):")
            
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
                
                # Mostrar detalles de errores si los hay
                if 'errors' in data and data['errors']:
                    errors_data = data['errors']
                    
                    if isinstance(errors_data, dict):
                        if errors_data.get('warnings'):
                            print(f"\n⚠️ WARNINGS ({len(errors_data['warnings'])}):")
                            for i, warning in enumerate(errors_data['warnings'][:3], 1):
                                print(f"   {i}. {warning.get('message', 'N/A')}")
                        
                        if errors_data.get('errors'):
                            print(f"\n❌ ERRORS ({len(errors_data['errors'])}):")
                            for i, error in enumerate(errors_data['errors'][:3], 1):
                                print(f"   {i}. {error.get('message', 'N/A')}")
                
                return data
            else:
                error_text = await response.text()
                print(f"❌ ERROR {response.status}: {error_text}")
                return None

async def verify_database_impact():
    """Verifica el impacto en la base de datos después de la sincronización."""
    print("\n🔍 Verificando impacto en la base de datos...")
    
    # Esperar un momento para que se complete la transacción
    await asyncio.sleep(2)
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/admin/database-health") as response:
            if response.status == 200:
                data = await response.json()
                print(f"   ✅ Base de datos sigue conectada")
                print(f"   ⏱️ Tiempo de respuesta: {data['health_check']['response_time_ms']}ms")
                return True
            else:
                print(f"   ❌ Error verificando base de datos: {response.status}")
                return False

async def check_sync_history():
    """Verifica el historial reciente de sincronizaciones."""
    print("\n📜 Verificando historial de sincronizaciones...")
    
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{BASE_URL}/sync/history?limit=3") as response:
            if response.status == 200:
                data = await response.json()
                
                if data.get('syncs'):
                    print(f"   📋 Últimas sincronizaciones:")
                    for sync in data['syncs']:
                        print(f"      • {sync.get('sync_id', 'N/A')} - {sync.get('status', 'N/A')}")
                        print(f"        {sync.get('timestamp', 'N/A')}")
                else:
                    print("   📭 No hay historial disponible")
            else:
                print(f"   ⚠️ No se pudo obtener historial: {response.status}")

async def main():
    """Función principal para ejecutar la sincronización real."""
    print("🔧 PRUEBA DE IMPACTO REAL EN BASE DE DATOS RMS")
    print("=" * 80)
    print(f"📍 API URL: {BASE_URL}")
    print(f"⏰ Hora: {datetime.now()}")
    
    # 1. Verificar estado inicial
    if not await get_current_order_count():
        print("❌ No se puede conectar a la base de datos")
        return
    
    # 2. ID de orden real para probar
    # AQUÍ DEBES PONER UN ID DE ORDEN REAL DE TU SHOPIFY
    real_order_id = "gid://shopify/Order/5679885926663"  # Reemplazar con ID real
    
    print(f"\n📋 Orden a sincronizar: {real_order_id}")
    
    # 3. Confirmación de seguridad
    print("\n" + "="*80)
    print("⚠️  ADVERTENCIA IMPORTANTE:")
    print("   Esta operación insertará datos REALES en las tablas ORDER y ORDERENTRY")
    print("   de la base de datos RMS. Los datos NO se pueden deshacer fácilmente.")
    print("="*80)
    
    # Para automatización, descomentamos la siguiente línea para confirmación manual:
    # respuesta = input("\n¿Confirma que desea proceder? (escriba 'SI' para continuar): ")
    
    # Por seguridad, usamos confirmación automática = NO
    respuesta = "NO"  # Cambiar a "SI" cuando esté listo para el impacto real
    
    if respuesta != "SI":
        print("\n❌ Operación cancelada por seguridad")
        print("\n💡 Para ejecutar la sincronización real:")
        print("   1. Cambie 'respuesta = \"NO\"' por 'respuesta = \"SI\"' en el código")
        print("   2. O use el comando curl directamente:")
        print(f"   curl -X POST {BASE_URL}/sync/shopify-to-rms \\")
        print("        -H 'Content-Type: application/json' \\")
        print(f"        -d '{{\"order_ids\": [\"{real_order_id}\"]}}'")
        return
    
    # 4. Ejecutar sincronización REAL
    print("\n🚀 INICIANDO SINCRONIZACIÓN CON IMPACTO REAL...")
    result = await perform_real_sync(real_order_id)
    
    if result:
        # 5. Verificar el impacto
        await verify_database_impact()
        
        # 6. Verificar historial
        await check_sync_history()
        
        # 7. Resumen final
        if result.get('success') and result.get('statistics', {}).get('created', 0) > 0:
            print("\n🎉 ¡SINCRONIZACIÓN EXITOSA!")
            print(f"   ✅ Se crearon {result['statistics']['created']} nuevas órdenes en RMS")
            print("   📝 Verifique las tablas [Order] y [OrderEntry] en SQL Server")
        else:
            print("\n⚠️ Sincronización completada pero sin nuevas inserciones")
            print("   🔍 Revise los warnings/errores mostrados arriba")
    else:
        print("\n❌ Sincronización falló")
    
    print(f"\n✅ Prueba de impacto real completada a las {datetime.now()}")

if __name__ == "__main__":
    asyncio.run(main())