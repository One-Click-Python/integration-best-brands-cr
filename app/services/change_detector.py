"""
Motor de detección de cambios para sincronización automática RMS → Shopify.

Este módulo detecta cambios en la base de datos RMS usando la tabla Item.LastUpdated
y trigger sincronizaciones automáticas hacia Shopify cuando detecta modificaciones.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.core.config import get_settings
from app.db.rms_handler import RMSHandler
from app.services.rms_to_shopify import RMSToShopifySync
from app.utils.error_handler import ErrorAggregator

settings = get_settings()
logger = logging.getLogger(__name__)


class ChangeDetector:
    """
    Detector de cambios en RMS usando tabla Item.LastUpdated.
    
    Detecta cambios desde la última verificación y sincroniza automáticamente
    los productos modificados hacia Shopify.
    """

    def __init__(self):
        """Inicializa el detector de cambios."""
        self.rms_handler = RMSHandler()
        self.sync_service = None
        self.error_aggregator = ErrorAggregator()
        self.last_check_time = None
        self.running = False
        self.monitoring_task = None
        self.stats = {
            "total_checks": 0,
            "changes_detected": 0,
            "items_synced": 0,
            "last_sync_time": None,
            "errors": 0,
            "last_error": None
        }

    async def initialize(self):
        """Inicializa el detector."""
        try:
            # Inicializar servicio de sincronización
            self.sync_service = RMSToShopifySync()
            await self.sync_service.initialize()
            
            # Establecer tiempo inicial (hace 1 hora para capturar cambios recientes)
            self.last_check_time = datetime.now(timezone.utc) - timedelta(hours=1)
            
            logger.info("🔍 Change Detector inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando Change Detector: {e}")
            raise

    async def close(self):
        """Cierra el detector."""
        try:
            await self.stop_monitoring()
            if self.sync_service:
                await self.sync_service.close()
            logger.info("🔍 Change Detector cerrado")
        except Exception as e:
            logger.error(f"Error cerrando Change Detector: {e}")

    async def start_monitoring(self, check_interval_minutes: int = None):
        """
        Inicia el monitoreo de cambios en background.
        
        Args:
            check_interval_minutes: Intervalo entre verificaciones (default: config)
        """
        if self.running:
            logger.warning("Change Detector ya está ejecutándose")
            return

        interval = check_interval_minutes or settings.SYNC_INTERVAL_MINUTES
        
        try:
            self.running = True
            logger.info(f"🚀 Iniciando monitoreo de cambios cada {interval} minutos")
            
            # Crear tarea de monitoreo
            self.monitoring_task = asyncio.create_task(self._monitoring_loop(interval))
            
        except Exception as e:
            logger.error(f"Error iniciando monitoreo: {e}")
            self.running = False
            raise

    async def stop_monitoring(self):
        """Detiene el monitoreo de cambios."""
        if not self.running:
            return
            
        self.running = False
        logger.info("🛑 Deteniendo monitoreo de cambios")
        
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass

    async def _monitoring_loop(self, interval_minutes: int):
        """Loop principal de monitoreo."""
        try:
            while self.running:
                try:
                    await self.check_for_changes()
                    await asyncio.sleep(interval_minutes * 60)  # Convertir a segundos
                    
                except asyncio.CancelledError:
                    logger.info("Monitoreo de cambios cancelado")
                    break
                except Exception as e:
                    logger.error(f"Error en ciclo de monitoreo: {e}")
                    self.stats["errors"] += 1
                    self.stats["last_error"] = str(e)
                    # Esperar menos tiempo en caso de error
                    await asyncio.sleep(60)
                    
        except Exception as e:
            logger.error(f"Error en loop de monitoreo: {e}")
        finally:
            self.running = False

    async def check_for_changes(self) -> Dict[str, Any]:
        """
        Verifica cambios usando Item.LastUpdated desde la última verificación.
        
        Returns:
            Dict: Resultado de la verificación con cambios detectados
        """
        check_start = datetime.now(timezone.utc)
        self.stats["total_checks"] += 1
        
        try:
            logger.debug(f"🔍 Verificando cambios desde {self.last_check_time}")
            
            # Query para detectar items modificados usando LastUpdated
            changed_items = await self._get_changed_items()
            
            changes_count = len(changed_items)
            
            if changes_count > 0:
                self.stats["changes_detected"] += changes_count
                logger.info(f"🔔 Detectados {changes_count} items modificados en RMS")
                
                # Obtener datos completos de View_Items para los items modificados
                view_items_data = await self._get_view_items_for_changed_items(changed_items)
                
                if view_items_data:
                    # Trigger sincronización automática
                    sync_result = await self._trigger_automatic_sync(view_items_data)
                    
                    if sync_result.get("success"):
                        self.stats["items_synced"] += sync_result.get("items_processed", 0)
                        self.stats["last_sync_time"] = check_start.isoformat()
                        
                else:
                    logger.warning("No se pudieron obtener datos de View_Items para items modificados")
                    
            else:
                logger.debug("✅ No hay cambios detectados")
            
            # Actualizar tiempo de última verificación
            self.last_check_time = check_start
            
            return {
                "timestamp": check_start.isoformat(),
                "changes_detected": changes_count,
                "changed_items": [{"item_id": item["ID"], "last_updated": item["LastUpdated"]} for item in changed_items],
                "sync_triggered": changes_count > 0,
                "stats": self.stats.copy()
            }
            
        except Exception as e:
            logger.error(f"Error verificando cambios: {e}")
            self.error_aggregator.add_error(e, {"operation": "check_for_changes"})
            self.stats["errors"] += 1
            self.stats["last_error"] = str(e)
            raise

    async def _get_changed_items(self) -> List[Dict]:
        """
        Obtiene items que han sido modificados desde la última verificación.
        
        Returns:
            List[Dict]: Lista de items modificados con ID y LastUpdated
        """
        try:
            # Convertir datetime a formato SQL Server
            last_check_sql = self.last_check_time.strftime('%Y-%m-%d %H:%M:%S')
            
            query = """
            SELECT TOP 500
                ID,
                LastUpdated
            FROM Item 
            WHERE LastUpdated > :last_check
                AND LastUpdated IS NOT NULL
            ORDER BY LastUpdated DESC
            """
            
            result = await self.rms_handler.execute_custom_query(query, {"last_check": last_check_sql})
            
            logger.debug(f"Query ejecutado: {len(result)} items modificados encontrados")
            
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo items modificados: {e}")
            return []

    async def _get_view_items_for_changed_items(self, changed_items: List[Dict]) -> List[Dict]:
        """
        Obtiene datos completos de View_Items para los items modificados.
        
        Args:
            changed_items: Lista de items con ID modificados
            
        Returns:
            List[Dict]: Datos completos de View_Items
        """
        try:
            if not changed_items:
                return []
            
            # Extraer IDs de items modificados
            item_ids = [str(item["ID"]) for item in changed_items]
            
            # Crear query IN con parámetros nombrados
            if len(item_ids) == 1:
                # Para un solo ID, usar parámetro simple
                query = """
                SELECT 
                    ItemID,
                    C_ARTICULO,
                    Description,
                    Price,
                    Quantity,
                    Familia,
                    Categoria,
                    color,
                    talla,
                    CCOD,
                    SalePrice,
                    SaleStartDate,
                    SaleEndDate,
                    ExtendedCategory,
                    Tax,
                    Exis00,
                    Exis57
                FROM View_Items 
                WHERE ItemID = :item_id
                    AND C_ARTICULO IS NOT NULL 
                    AND Description IS NOT NULL
                    AND Price > 0
                ORDER BY ItemID
                """
                
                result = await self.rms_handler.execute_custom_query(query, {"item_id": item_ids[0]})
            else:
                # Para múltiples IDs, construir query dinámica
                placeholders = ','.join([f":item_{i}" for i in range(len(item_ids))])
                params = {f"item_{i}": item_id for i, item_id in enumerate(item_ids)}
                
                query = f"""
                SELECT 
                    ItemID,
                    C_ARTICULO,
                    Description,
                    Price,
                    Quantity,
                    Familia,
                    Categoria,
                    color,
                    talla,
                    CCOD,
                    SalePrice,
                    SaleStartDate,
                    SaleEndDate,
                    ExtendedCategory,
                    Tax,
                    Exis00,
                    Exis57
                FROM View_Items 
                WHERE ItemID IN ({placeholders})
                    AND C_ARTICULO IS NOT NULL 
                    AND Description IS NOT NULL
                    AND Price > 0
                ORDER BY ItemID
                """
                
                result = await self.rms_handler.execute_custom_query(query, params)
            
            logger.debug(f"Obtenidos {len(result)} productos válidos de View_Items")
            
            return result
            
        except Exception as e:
            logger.error(f"Error obteniendo datos de View_Items: {e}")
            return []

    async def _trigger_automatic_sync(self, items_data: List[Dict]) -> Dict[str, Any]:
        """
        Trigger sincronización automática para items modificados.
        
        Args:
            items_data: Datos de View_Items para sincronizar
            
        Returns:
            Dict: Resultado de la sincronización
        """
        try:
            items_count = len(items_data)
            logger.info(f"🔄 Iniciando sincronización automática para {items_count} items")
            
            # Agrupar por CCOD para sincronizar productos completos
            ccods_to_sync = set()
            skus_to_sync = set()
            
            for item in items_data:
                if item.get("CCOD"):
                    ccods_to_sync.add(item["CCOD"])
                elif item.get("C_ARTICULO"):
                    skus_to_sync.add(item["C_ARTICULO"])
            
            if not ccods_to_sync and not skus_to_sync:
                logger.warning("No hay CCODs o SKUs válidos para sincronizar")
                return {"success": False, "reason": "no_valid_identifiers"}
            
            sync_results = []
            items_processed = 0
            
            # Sincronizar por CCODs (preferido - productos completos con variantes)
            if ccods_to_sync:
                logger.info(f"Sincronizando {len(ccods_to_sync)} CCODs modificados")
                
                # Procesar CCODs en lotes pequeños
                ccod_list = list(ccods_to_sync)
                batch_size = 5  # Lotes pequeños para evitar sobrecarga
                
                for i in range(0, len(ccod_list), batch_size):
                    batch = ccod_list[i:i + batch_size]
                    
                    for ccod in batch:
                        try:
                            result = await self.sync_service.sync_products(
                                ccod=ccod,
                                force_update=True,
                                include_zero_stock=True,
                                batch_size=10
                            )
                            
                            sync_results.append(result)
                            items_processed += result.get("products_processed", 0)
                            
                            # Pausa entre sincronizaciones para rate limiting
                            await asyncio.sleep(1)
                            
                        except Exception as e:
                            logger.error(f"Error sincronizando CCOD {ccod}: {e}")
                            self.error_aggregator.add_error(e, {"ccod": ccod})
                    
                    # Pausa entre lotes
                    if i + batch_size < len(ccod_list):
                        await asyncio.sleep(3)
            
            # Log de resultado
            logger.info(f"✅ Sincronización automática completada: {items_processed} productos procesados")
            
            return {
                "success": True,
                "items_detected": items_count,
                "ccods_synced": len(ccods_to_sync),
                "items_processed": items_processed,
                "sync_results": sync_results,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error en sincronización automática: {e}")
            self.error_aggregator.add_error(e, {"operation": "automatic_sync"})
            return {"success": False, "error": str(e)}

    async def manual_check_and_sync(self) -> Dict[str, Any]:
        """Ejecuta una verificación y sincronización manual."""
        try:
            logger.info("🔄 Ejecutando verificación manual de cambios")
            result = await self.check_for_changes()
            return result
        except Exception as e:
            logger.error(f"Error en verificación manual: {e}")
            return {"success": False, "error": str(e)}

    async def force_full_sync(self) -> Dict[str, Any]:
        """Fuerza una sincronización completa independiente de cambios."""
        try:
            logger.info("🔄 Iniciando sincronización completa forzada")
            
            result = await self.sync_service.sync_products(
                force_update=True,
                batch_size=20,
                include_zero_stock=False
            )
            
            self.stats["items_synced"] += result.get("products_processed", 0)
            self.stats["last_sync_time"] = datetime.now(timezone.utc).isoformat()
            
            logger.info("✅ Sincronización completa forzada completada")
            return {"success": True, "result": result}
            
        except Exception as e:
            logger.error(f"Error en sincronización forzada: {e}")
            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del detector."""
        return {
            **self.stats,
            "running": self.running,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "next_check_estimate": (
                (self.last_check_time + timedelta(minutes=settings.SYNC_INTERVAL_MINUTES)).isoformat()
                if self.last_check_time and self.running else None
            ),
            "monitoring_active": self.monitoring_task is not None and not self.monitoring_task.done(),
            "error_summary": self.error_aggregator.get_summary()
        }

    def is_running(self) -> bool:
        """Verifica si el detector está ejecutándose."""
        return self.running and self.monitoring_task is not None and not self.monitoring_task.done()


# Instancia global del detector
_change_detector: Optional[ChangeDetector] = None


async def get_change_detector() -> ChangeDetector:
    """Obtiene la instancia global del detector de cambios."""
    global _change_detector
    
    if _change_detector is None:
        _change_detector = ChangeDetector()
        await _change_detector.initialize()
    
    return _change_detector


async def start_change_monitoring(check_interval_minutes: int = None):
    """Inicia el monitoreo de cambios global."""
    detector = await get_change_detector()
    await detector.start_monitoring(check_interval_minutes)


async def stop_change_monitoring():
    """Detiene el monitoreo de cambios global."""
    global _change_detector
    
    if _change_detector:
        await _change_detector.stop_monitoring()


async def get_change_detection_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del detector de cambios."""
    global _change_detector
    
    if _change_detector:
        return _change_detector.get_stats()
    else:
        return {"status": "not_initialized"}


async def manual_sync_check() -> Dict[str, Any]:
    """Ejecuta una verificación manual de cambios."""
    detector = await get_change_detector()
    return await detector.manual_check_and_sync()


async def force_full_sync() -> Dict[str, Any]:
    """Fuerza una sincronización completa."""
    detector = await get_change_detector()
    return await detector.force_full_sync()