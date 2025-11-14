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
from app.db.rms.query_executor import QueryExecutor
from app.services.rms_to_shopify.sync_orchestrator import RMSToShopifySyncOrchestrator as RMSToShopifySync
from app.utils.error_handler import ErrorAggregator
from app.utils.update_checkpoint import UpdateCheckpointManager

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
        # SOLID repository instead of monolithic handler
        self.query_executor = QueryExecutor()
        self.sync_service = None
        self.error_aggregator = ErrorAggregator()
        self.update_checkpoint_manager = UpdateCheckpointManager()
        self.last_check_time: Optional[datetime] = None
        self.running = False
        self.monitoring_task = None
        self.stats = {
            "total_checks": 0,
            "changes_detected": 0,
            "items_synced": 0,
            "last_sync_time": None,
            "errors": 0,
            "last_error": None,
        }

    async def initialize(self):
        """Inicializa el detector."""
        try:
            # Initialize SOLID repository
            await self.query_executor.initialize()

            # Initialize sync service with a specific sync_id for traceability
            sync_id = f"change_detector_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self.sync_service = RMSToShopifySync(sync_id=sync_id, use_update_checkpoint=True)
            await self.sync_service.initialize()

            # Set initial check time from the checkpoint manager
            self.last_check_time = self.update_checkpoint_manager.get_last_update_timestamp(
                default_days_back=settings.CHECKPOINT_DEFAULT_DAYS
            )

            logger.info(
                f"🔍 Change Detector initialized. Will check for changes since: {self.last_check_time.isoformat()}"
            )

        except Exception as e:
            logger.error(f"Error inicializando Change Detector: {e}")
            raise

    async def close(self):
        """Cierra el detector."""
        try:
            await self.stop_monitoring()
            if self.query_executor:
                await self.query_executor.close()
            if self.sync_service:
                await self.sync_service.close()  # type: ignore
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
                logger.info(
                    f"🔔 Detected {changes_count} items modified in RMS since {self.last_check_time.isoformat()}"
                )

                # Trigger automatic sync for the detected CCODs
                # This part needs to be adapted to pass CCODs or a list of items
                sync_result = await self._trigger_automatic_sync(changed_items)

                # After sync, update checkpoint based on results
                total_processed = sync_result.get("statistics", {}).get("total_processed", 0)
                success_rate = sync_result.get("statistics", {}).get("success_rate", 0)

                # Update stats regardless of success
                if total_processed > 0:
                    self.stats["items_synced"] += total_processed
                    self.stats["last_sync_time"] = check_start.isoformat()

                # Update checkpoint if:
                # 1. We processed at least one item successfully, OR
                # 2. There were no errors (even if 0 products - means everything is up to date)
                if total_processed > 0 or (changes_count > 0 and sync_result and not sync_result.get("error")):
                    if success_rate >= (settings.CHECKPOINT_SUCCESS_THRESHOLD * 100) or total_processed == 0:
                        logger.info(
                            f"✅ [UPDATE CHECKPOINT] Updating - Processed: {total_processed}, Success rate: {
                                success_rate:.1f}%"
                        )
                        self.update_checkpoint_manager.save_checkpoint(check_start)

                        # Notify scheduler that RMS→Shopify sync completed successfully
                        # This triggers reverse stock sync after configured delay
                        try:
                            from app.core.scheduler import notify_rms_sync_completed
                            notify_rms_sync_completed(success=True)
                            logger.info("📝 Scheduler notified of successful RMS→Shopify sync")
                        except Exception as e:
                            logger.error(f"Error notifying scheduler: {e}")
                    else:
                        logger.warning(
                            f"⚠️ [UPDATE CHECKPOINT] Not updated - Success rate {success_rate:.1f}% < {
                                settings.CHECKPOINT_SUCCESS_THRESHOLD * 100
                            }% threshold"
                        )

                        # Notify scheduler that sync completed with low success rate
                        # This prevents reverse sync from executing
                        try:
                            from app.core.scheduler import notify_rms_sync_completed
                            notify_rms_sync_completed(success=False)
                            logger.info("📝 Scheduler notified of failed RMS→Shopify sync")
                        except Exception as e:
                            logger.error(f"Error notifying scheduler: {e}")
                else:
                    logger.info("ℹ️ [UPDATE CHECKPOINT] No changes to sync, checkpoint remains at current position")

            else:
                logger.debug("✅ No hay cambios detectados")

            # Actualizar tiempo de última verificación
            self.last_check_time = check_start

            return {
                "timestamp": check_start.isoformat(),
                "changes_detected": changes_count,
                "changed_items": [
                    {"item_id": item["ID"], "last_updated": item["LastUpdated"]} for item in changed_items
                ],
                "sync_triggered": changes_count > 0,
                "stats": self.stats.copy(),
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
            # The timestamp is now a datetime object, no string formatting needed
            query = """
            SELECT TOP 500
                i.ID,
                i.LastUpdated,
                i.ItemLookupCode as c_articulo,
                v.CCOD as real_ccod
            FROM Item i
            LEFT JOIN View_Items v ON i.ID = v.ItemID
            WHERE i.LastUpdated > :last_check
                AND i.LastUpdated IS NOT NULL
            ORDER BY i.LastUpdated DESC
            """

            result = await self.query_executor.execute_custom_query(query, {"last_check": self.last_check_time})

            logger.debug(f"Query executed: {len(result)} modified items found since {self.last_check_time.isoformat()}")

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

                result = await self.query_executor.execute_custom_query(query, {"item_id": item_ids[0]})
            else:
                # Para múltiples IDs, construir query dinámica
                placeholders = ",".join([f":item_{i}" for i in range(len(item_ids))])
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

                result = await self.query_executor.execute_custom_query(query, params)

            logger.debug(f"Obtenidos {len(result)} productos válidos de View_Items")

            return result

        except Exception as e:
            logger.error(f"Error obteniendo datos de View_Items: {e}")
            return []

    async def _trigger_automatic_sync(self, changed_items: List[Dict]) -> Dict[str, Any]:
        """
        Trigger automatic sync for a list of changed items.

        This now receives a list of item dictionaries, extracts the CCODs,
        and triggers a sync for those specific products.

        Args:
            changed_items: List of dictionaries, each with at least a `c_articulo`

        Returns:
            Dict: Result of the synchronization
        """
        if not changed_items:
            return {}

        # Extract unique CCODs from the changed items
        # Use real_ccod from View_Items if available, otherwise extract from ItemLookupCode
        ccods_to_sync = set()
        for item in changed_items:
            # First try to use the real CCOD from View_Items
            real_ccod = item.get("real_ccod")
            if real_ccod:
                ccods_to_sync.add(real_ccod)
            else:
                # Fallback to extracting from ItemLookupCode
                c_articulo = item.get("c_articulo", "")
                if c_articulo:
                    # Some products have ItemLookupCode like '6PP900005' but CCOD like '6PP905'
                    # Try to extract the base CCOD
                    parts = c_articulo.split("-")
                    if parts:
                        ccods_to_sync.add(parts[0])

        ccods_to_sync = list(ccods_to_sync)

        if not ccods_to_sync:
            logger.warning("No valid CCODs found in changed items to sync.")
            return {"statistics": {"total_processed": 0, "success_rate": 0}}

        logger.info(f"Triggering automatic sync for {len(ccods_to_sync)} CCODs: {ccods_to_sync}")

        try:
            all_results = []
            total_synced = 0

            for ccod in ccods_to_sync:
                try:
                    logger.debug(f"Syncing CCOD: {ccod}")
                    result = await self.sync_service.sync_products(
                        cod_product=ccod,
                        force_update=True,  # Always force update for changed items
                        use_streaming=False,  # Sync CCOD by CCOD
                        include_zero_stock=True,  # IMPORTANT: Include zero stock products to update inventory
                    )
                    all_results.append(result)

                    # Track successful syncs
                    if result and result.get("statistics", {}).get("total_processed", 0) > 0:
                        total_synced += result["statistics"]["total_processed"]

                except Exception as e:
                    logger.error(f"Failed to sync CCOD {ccod}: {e}")
                    continue

            # Aggregate results
            if all_results:
                total_processed = sum(r.get("statistics", {}).get("total_processed", 0) for r in all_results)
                success_rate = sum(r.get("success_rate", 0) for r in all_results) / len(all_results)
            else:
                total_processed = 0
                success_rate = 0

            final_stats = {
                "total_processed": total_processed,
                "success_rate": success_rate,
            }

            logger.info(f"Automatic sync completed for {len(ccods_to_sync)} CCODs. Processed: {total_processed}")
            return {"statistics": final_stats}

        except Exception as e:
            logger.error(f"Error during automatic sync: {e}")
            self.error_aggregator.add_error(e, {"operation": "_trigger_automatic_sync"})
            return {"error": str(e)}

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
                force_update=True, batch_size=20, include_zero_stock=False, use_streaming=False
            )

            self.stats["items_synced"] += result.get("products_processed", 0)
            self.stats["last_sync_time"] = datetime.now(timezone.utc).isoformat()

            logger.info("✅ Sincronización completa forzada completada")

            # Notify scheduler about full sync completion
            # This triggers reverse stock sync after configured delay
            try:
                success_rate = result.get("success_rate", 0) / 100  # Convert to decimal
                from app.core.scheduler import notify_rms_sync_completed
                notify_rms_sync_completed(success=success_rate >= 0.95)
                logger.info(f"📝 Scheduler notified of full sync (success: {success_rate >= 0.95})")
            except Exception as notify_error:
                logger.error(f"Error notifying scheduler after full sync: {notify_error}")

            return {"success": True, "result": result}

        except Exception as e:
            logger.error(f"Error en sincronización forzada: {e}")

            # Notify scheduler about failed sync
            try:
                from app.core.scheduler import notify_rms_sync_completed
                notify_rms_sync_completed(success=False)
            except Exception as notify_error:
                logger.error(f"Error notifying scheduler about failed sync: {notify_error}")

            return {"success": False, "error": str(e)}

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del detector."""
        return {
            **self.stats,
            "running": self.running,
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "next_check_estimate": (
                (self.last_check_time + timedelta(minutes=settings.SYNC_INTERVAL_MINUTES)).isoformat()
                if self.last_check_time and self.running
                else None
            ),
            "monitoring_active": self.monitoring_task is not None and not self.monitoring_task.done(),
            "error_summary": self.error_aggregator.get_summary(),
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
