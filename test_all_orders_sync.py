#!/usr/bin/env python3
"""
Test script para sincronizar TODAS las órdenes de Shopify a RMS.

Este script recupera todas las órdenes (regulares y draft orders) de Shopify
y las sincroniza con la base de datos RMS através del endpoint de la API,
como fue solicitado por el usuario.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import aiohttp
from aiohttp import ClientTimeout

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuración del servidor local
API_BASE_URL = "http://localhost:8000"
SYNC_ENDPOINT = f"{API_BASE_URL}/api/v1/sync/orders"

class AllOrdersSyncTester:
    """Tester para sincronizar todas las órdenes de Shopify."""
    
    def __init__(self):
        """Inicializa el tester."""
        self.session: Optional[aiohttp.ClientSession] = None
        self.synced_orders = []
        self.failed_orders = []
        self.total_orders = 0
        
    async def initialize(self):
        """Inicializa el cliente HTTP."""
        timeout = ClientTimeout(total=60, connect=10)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("Cliente HTTP inicializado")
        
    async def close(self):
        """Cierra el cliente HTTP."""
        if self.session:
            await self.session.close()
            logger.info("Cliente HTTP cerrado")
    
    async def get_all_orders(self) -> List[Dict[str, Any]]:
        """
        Obtiene todas las órdenes de Shopify usando el endpoint de la API.
        
        Returns:
            List[Dict]: Lista de todas las órdenes obtenidas
        """
        try:
            logger.info("Obteniendo todas las órdenes de Shopify...")
            
            # Llamar al endpoint para obtener órdenes
            async with self.session.get(f"{API_BASE_URL}/api/v1/sync/orders") as response:
                if response.status == 200:
                    orders_data = await response.json()
                    
                    # Extraer órdenes de la respuesta
                    if isinstance(orders_data, dict):
                        orders = orders_data.get('orders', [])
                        draft_orders = orders_data.get('draft_orders', [])
                        all_orders = orders + draft_orders
                    else:
                        all_orders = orders_data if isinstance(orders_data, list) else []
                    
                    self.total_orders = len(all_orders)
                    logger.info(f"Se obtuvieron {self.total_orders} órdenes en total")
                    return all_orders
                    
                else:
                    logger.error(f"Error al obtener órdenes: {response.status}")
                    error_text = await response.text()
                    logger.error(f"Respuesta del error: {error_text}")
                    return []
                    
        except Exception as e:
            logger.error(f"Excepción al obtener órdenes: {e}")
            return []
    
    async def sync_order(self, order: Dict[str, Any]) -> bool:
        """
        Sincroniza una orden específica usando el endpoint de sync.
        
        Args:
            order: Datos de la orden a sincronizar
            
        Returns:
            bool: True si la sincronización fue exitosa
        """
        try:
            order_id = order.get('id', 'unknown')
            logger.info(f"Sincronizando orden {order_id}...")
            
            # Preparar datos para el endpoint (convertir booleans a strings)
            sync_data = {
                "order_id": order_id,
                "force_sync": "true",
                "validate_before_insert": "true",
                "run_async": "false"  # Ejecutar sincrónicamente para obtener resultados inmediatos
            }
            
            # Llamar al endpoint de sincronización (usar POST /api/v1/sync/orders)
            async with self.session.post(
                f"{API_BASE_URL}/api/v1/sync/orders",
                params=sync_data,  # Usar params en lugar de json ya que son query parameters
                headers={'Content-Type': 'application/json'}
            ) as response:
                
                if response.status in [200, 201]:
                    result = await response.json()
                    logger.info(f"✅ Orden {order_id} sincronizada exitosamente")
                    self.synced_orders.append({
                        'order_id': order_id,
                        'status': 'success',
                        'result': result,
                        'timestamp': datetime.now().isoformat()
                    })
                    return True
                    
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Error sincronizando orden {order_id}: {response.status}")
                    logger.error(f"Detalle del error: {error_text}")
                    
                    self.failed_orders.append({
                        'order_id': order_id,
                        'status': 'failed',
                        'error': error_text,
                        'http_status': response.status,
                        'timestamp': datetime.now().isoformat()
                    })
                    return False
                    
        except Exception as e:
            logger.error(f"❌ Excepción sincronizando orden {order_id}: {e}")
            self.failed_orders.append({
                'order_id': order_id,
                'status': 'exception',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            return False
    
    async def sync_all_orders(self, max_concurrent: int = 3) -> Dict[str, Any]:
        """
        Sincroniza todas las órdenes de forma controlada.
        
        Args:
            max_concurrent: Máximo número de sincronizaciones concurrentes
            
        Returns:
            Dict: Resumen de la sincronización
        """
        start_time = time.time()
        logger.info("🚀 Iniciando sincronización de TODAS las órdenes...")
        
        # Obtener todas las órdenes
        all_orders = await self.get_all_orders()
        
        if not all_orders:
            logger.warning("No se encontraron órdenes para sincronizar")
            return {
                'total_orders': 0,
                'synced': 0,
                'failed': 0,
                'duration_seconds': time.time() - start_time
            }
        
        logger.info(f"Sincronizando {len(all_orders)} órdenes con máximo {max_concurrent} concurrentes...")
        
        # Crear semáforo para controlar concurrencia
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def sync_with_semaphore(order):
            async with semaphore:
                return await self.sync_order(order)
        
        # Ejecutar sincronizaciones
        tasks = [sync_with_semaphore(order) for order in all_orders]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Calcular estadísticas
        successful_syncs = sum(1 for result in results if result is True)
        failed_syncs = len(results) - successful_syncs
        duration = time.time() - start_time
        
        # Generar resumen
        summary = {
            'total_orders': len(all_orders),
            'synced': successful_syncs,
            'failed': failed_syncs,
            'success_rate': (successful_syncs / len(all_orders)) * 100 if all_orders else 0,
            'duration_seconds': duration,
            'orders_per_second': len(all_orders) / duration if duration > 0 else 0,
            'synced_orders': self.synced_orders,
            'failed_orders': self.failed_orders
        }
        
        logger.info("📊 Resumen de sincronización:")
        logger.info(f"   Total de órdenes: {summary['total_orders']}")
        logger.info(f"   Sincronizadas: {summary['synced']}")
        logger.info(f"   Fallidas: {summary['failed']}")
        logger.info(f"   Tasa de éxito: {summary['success_rate']:.1f}%")
        logger.info(f"   Duración: {summary['duration_seconds']:.1f} segundos")
        logger.info(f"   Velocidad: {summary['orders_per_second']:.1f} órdenes/segundo")
        
        return summary
    
    async def save_results(self, summary: Dict[str, Any]):
        """Guarda los resultados en un archivo JSON."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"all_orders_sync_results_{timestamp}.json"
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
            logger.info(f"📄 Resultados guardados en: {filename}")
        except Exception as e:
            logger.error(f"Error guardando resultados: {e}")
    
    async def check_api_health(self) -> bool:
        """Verifica que la API esté disponible."""
        try:
            async with self.session.get(f"{API_BASE_URL}/health") as response:
                if response.status == 200:
                    health_data = await response.json()
                    logger.info(f"✅ API está disponible: {health_data}")
                    return True
                else:
                    logger.error(f"❌ API no disponible: {response.status}")
                    return False
        except Exception as e:
            logger.error(f"❌ Error verificando API: {e}")
            return False


async def main():
    """Función principal del test."""
    tester = AllOrdersSyncTester()
    
    try:
        await tester.initialize()
        
        # Verificar que la API esté disponible
        if not await tester.check_api_health():
            logger.error("❌ La API no está disponible. Asegúrate de que el servidor esté ejecutándose.")
            return
        
        # Ejecutar sincronización completa
        logger.info("🎯 Ejecutando sincronización de TODAS las órdenes...")
        summary = await tester.sync_all_orders(max_concurrent=2)  # Conservador para evitar rate limits
        
        # Guardar resultados
        await tester.save_results(summary)
        
        # Mostrar resumen final
        print("\n" + "="*60)
        print("📋 RESUMEN FINAL DE SINCRONIZACIÓN")
        print("="*60)
        print(f"Total de órdenes procesadas: {summary['total_orders']}")
        print(f"Sincronizadas exitosamente: {summary['synced']}")
        print(f"Fallidas: {summary['failed']}")
        print(f"Tasa de éxito: {summary['success_rate']:.1f}%")
        print(f"Tiempo total: {summary['duration_seconds']:.1f} segundos")
        print("="*60)
        
        if summary['failed'] > 0:
            print("\n❌ ÓRDENES FALLIDAS:")
            for failed_order in summary['failed_orders'][:5]:  # Mostrar primeras 5
                print(f"   - Orden {failed_order['order_id']}: {failed_order['error'][:100]}...")
        
        if summary['synced'] > 0:
            print(f"\n✅ Se sincronizaron {summary['synced']} órdenes correctamente")
            print("   Las órdenes se insertaron en las tablas ORDER y ORDERENTRY de RMS")
        
    except Exception as e:
        logger.error(f"❌ Error en la ejecución principal: {e}")
        
    finally:
        await tester.close()


if __name__ == "__main__":
    print("🚀 Iniciando test de sincronización de TODAS las órdenes Shopify → RMS")
    print("   Esto probará el impacto real en la base de datos como fue solicitado")
    print("   Todas las pruebas se ejecutan a través de los endpoints de la API")
    print()
    
    asyncio.run(main())